//! The GUI, MCP and dp share this durable, noninteractive CLI task service.
use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::PathBuf,
    process::Stdio,
    sync::{Arc, Mutex},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    process::Command,
};

fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Engine {
    pub id: String,
    pub available: bool,
    pub version: Option<String>,
    pub path: Option<PathBuf>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JobRequest {
    pub engine: String,
    pub cwd: PathBuf,
    pub prompt: String,
    #[serde(default)]
    pub project_id: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Job {
    pub id: String,
    pub engine: String,
    pub cwd: PathBuf,
    pub prompt: String,
    #[serde(default)]
    pub project_id: Option<String>,
    pub status: String,
    pub created_at: u64,
    pub updated_at: u64,
    pub pid: Option<u32>,
    pub worker_pid: Option<u32>,
    pub exit_code: Option<i32>,
    pub error: Option<String>,
}
impl Job {
    pub fn terminal(&self) -> bool {
        matches!(
            self.status.as_str(),
            "completed" | "failed" | "cancelled" | "interrupted"
        )
    }
}
pub struct JobManager {
    root: PathBuf,
    writer: Mutex<BTreeMap<String, u64>>,
}

impl JobManager {
    pub fn new(root: PathBuf) -> Arc<Self> {
        Arc::new(Self {
            root,
            writer: Mutex::new(BTreeMap::new()),
        })
    }
    pub fn standard() -> Arc<Self> {
        Self::new(crate::config::data_dir().join("jobs"))
    }
    fn directory(&self, id: &str) -> Result<PathBuf> {
        uuid::Uuid::parse_str(id).context("Invalid job id")?;
        Ok(self.root.join(id))
    }
    fn store(&self, job: &Job) -> Result<()> {
        let directory = self.directory(&job.id)?;
        fs::create_dir_all(&directory)?;
        let temporary = directory.join(format!("{}.tmp", uuid::Uuid::new_v4()));
        fs::write(&temporary, serde_json::to_vec_pretty(job)?)?;
        fs::rename(temporary, directory.join("job.json"))?;
        Ok(())
    }
    pub fn status(&self, id: &str) -> Result<Job> {
        let mut job: Job = serde_json::from_slice(
            &fs::read(self.directory(id)?.join("job.json")).context("Job not found")?,
        )?;
        if !job.terminal() {
            let worker_pid = job.worker_pid.or_else(|| {
                fs::read_to_string(self.directory(id).ok()?.join("worker.pid"))
                    .ok()?
                    .parse()
                    .ok()
            });
            if let Some(pid) = worker_pid {
                if !process_alive(pid) {
                    // The worker may have committed its terminal state between
                    // our first read and the liveness check. Never overwrite it.
                    job = serde_json::from_slice(&fs::read(self.directory(id)?.join("job.json"))?)?;
                    if job.terminal() {
                        return Ok(job);
                    }
                    job.status = "interrupted".into();
                    job.error = Some("Task worker exited before recording a final state".into());
                    job.updated_at = now();
                    self.store(&job)?;
                }
            }
        }
        Ok(job)
    }
    pub fn list(&self) -> Vec<Job> {
        let mut jobs: Vec<Job> = fs::read_dir(&self.root)
            .into_iter()
            .flatten()
            .flatten()
            .filter_map(|e| self.status(&e.file_name().to_string_lossy()).ok())
            .collect();
        jobs.sort_by_key(|j| std::cmp::Reverse(j.created_at));
        jobs.truncate(100);
        jobs
    }
    pub async fn engines() -> Vec<Engine> {
        let mut result = Vec::new();
        for id in ["codex", "claude"] {
            let path = find_engine(id);
            let mut engine = Engine {
                id: id.into(),
                available: false,
                version: None,
                path: path.clone(),
            };
            if let Some(path) = path {
                let mut command = Command::new(path);
                command
                    .arg("--version")
                    .stdin(Stdio::null())
                    .kill_on_drop(true);
                hidden(&mut command);
                if let Ok(Ok(output)) =
                    tokio::time::timeout(Duration::from_secs(8), command.output()).await
                {
                    engine.available = output.status.success();
                    engine.version = Some(
                        String::from_utf8_lossy(&output.stdout)
                            .trim()
                            .chars()
                            .take(200)
                            .collect(),
                    );
                }
            }
            result.push(engine);
        }
        result
    }
    pub async fn start(&self, request: JobRequest) -> Result<Job> {
        if !matches!(request.engine.as_str(), "codex" | "claude") {
            bail!("Engine must be codex or claude");
        }
        if request.prompt.trim().is_empty() || request.prompt.len() > 200_000 {
            bail!("Prompt must contain 1..200000 bytes");
        }
        let cwd = request
            .cwd
            .canonicalize()
            .context("Working directory does not exist")?;
        if !cwd.is_dir() {
            bail!("Working directory must be a folder");
        }
        let engine = Self::engines()
            .await
            .into_iter()
            .find(|e| e.id == request.engine && e.available)
            .context("CLI is not installed or its version probe failed")?;
        let timestamp = now();
        let mut job = Job {
            id: uuid::Uuid::new_v4().to_string(),
            engine: engine.id,
            cwd,
            prompt: request.prompt,
            project_id: request.project_id,
            status: "queued".into(),
            created_at: timestamp,
            updated_at: timestamp,
            pid: None,
            worker_pid: None,
            exit_code: None,
            error: None,
        };
        self.store(&job)?;
        let executable = std::env::current_exe()?;
        let worker = executable
            .parent()
            .context("Executable directory missing")?
            .join(if cfg!(windows) { "dp.exe" } else { "dp" });
        match spawn_worker(&worker, &job.id, &self.root) {
            Ok(pid) => {
                job.worker_pid = Some(pid); /* The worker owns subsequent writes. */
                fs::write(self.directory(&job.id)?.join("worker.pid"), pid.to_string())?;
            }
            Err(error) => {
                job.status = "failed".into();
                job.error = Some(format!("Cannot start packaged dp worker: {error}"));
                self.store(&job)?;
                bail!("{}", job.error.as_deref().unwrap());
            }
        }
        // A worker can complete immediately; do not overwrite its state with queued.
        Ok(job)
    }
    pub fn cancel(&self, id: &str) -> Result<Job> {
        let job = self.status(id)?;
        if !job.terminal() {
            fs::write(self.directory(id)?.join("cancel"), b"cancel")?;
        }
        Ok(job)
    }
    pub fn events(&self, id: &str, after: u64) -> Result<Value> {
        let directory = self.directory(id)?;
        self.status(id)?;
        let text = fs::read_to_string(directory.join("events.jsonl")).unwrap_or_default();
        let events: Vec<Value> = text
            .lines()
            .filter_map(|l| serde_json::from_str::<Value>(l).ok())
            .filter(|e| e["seq"].as_u64().unwrap_or(0) > after)
            .take(1000)
            .collect();
        let next = events
            .last()
            .and_then(|e| e["seq"].as_u64())
            .unwrap_or(after);
        Ok(json!({"events":events,"next_cursor":next}))
    }
    fn event(&self, id: &str, stream: &str, data: Value) -> Result<()> {
        let mut sequences = self.writer.lock().unwrap();
        let path = self.directory(id)?.join("events.jsonl");
        let sequence = sequences.entry(id.into()).or_insert_with(|| {
            fs::read_to_string(&path)
                .unwrap_or_default()
                .lines()
                .count() as u64
        });
        *sequence += 1;
        let mut file = fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(path)?;
        writeln!(
            file,
            "{}",
            json!({"seq":*sequence,"timestamp":now(),"stream":stream,"data":data})
        )?;
        file.flush()?;
        Ok(())
    }
    pub async fn run_worker(self: &Arc<Self>, id: &str) -> Result<()> {
        let outcome = self.run_worker_inner(id).await;
        if let Err(error) = &outcome {
            if let Ok(directory) = self.directory(id) {
                let _ = fs::write(directory.join("worker-error.txt"), format!("{error:#}"));
            }
            if let Ok(mut job) = self.status(id) {
                if !job.terminal() {
                    job.status = "failed".into();
                    job.error = Some(format!("{error:#}"));
                    job.updated_at = now();
                    let _ = self.store(&job);
                }
            }
        }
        outcome
    }
    async fn run_worker_inner(self: &Arc<Self>, id: &str) -> Result<()> {
        let job = self.status(id)?;
        let path = find_engine(&job.engine).context("CLI no longer installed")?;
        let mut command = Command::new(path);
        match job.engine.as_str() {
            "codex" => {
                command.args([
                    "exec",
                    "--json",
                    "--color",
                    "never",
                    "--sandbox",
                    "workspace-write",
                    "--skip-git-repo-check",
                    "-",
                ]);
            }
            "claude" => {
                command.args(["-p", "--output-format", "stream-json", "--verbose"]);
            }
            _ => bail!("Unknown engine"),
        }
        self.execute(id, command).await
    }
    /// Exposed to the process harness; production engines always use run_worker.
    pub async fn execute(self: &Arc<Self>, id: &str, mut command: Command) -> Result<()> {
        let directory = self.directory(id)?;
        let _lease = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(directory.join("worker.lock"))
            .context("Job already has a worker")?;
        let mut job = self.status(id)?;
        job.worker_pid = Some(std::process::id());
        job.updated_at = now();
        if directory.join("cancel").exists() {
            job.status = "cancelled".into();
            self.store(&job)?;
            return Ok(());
        }
        command
            .current_dir(&job.cwd)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        hidden(&mut command);
        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                job.status = "failed".into();
                job.error = Some(error.to_string());
                self.store(&job)?;
                return Err(error.into());
            }
        };
        job.pid = child.id();
        job.status = "running".into();
        self.store(&job)?;
        self.event(
            id,
            "lifecycle",
            json!({"type":"started","pid":job.pid,"engine":job.engine}),
        )?;
        let mut input = child.stdin.take().context("stdin unavailable")?;
        let prompt = job.prompt.clone();
        let input_task = tokio::spawn(async move {
            let _ = input.write_all(prompt.as_bytes()).await;
            let _ = input.shutdown().await;
        });
        let stdout = self.read_output(id, "stdout", child.stdout.take().unwrap());
        let stderr = self.read_output(id, "stderr", child.stderr.take().unwrap());
        let mut cancelled = false;
        let result = loop {
            tokio::select! {
                result=child.wait()=>break result,
                _=tokio::time::sleep(Duration::from_millis(200))=>{
                    if directory.join("cancel").exists() {
                        cancelled=true;
                        if let Some(pid)=job.pid { kill_tree(pid).await; }
                        let _=child.start_kill(); break child.wait().await;
                    }
                }
            }
        };
        let _ = input_task.await;
        let semantic_failure = stdout.await.unwrap_or(false) | stderr.await.unwrap_or(false);
        job.updated_at = now();
        match result {
            Ok(status) => {
                job.exit_code = status.code();
                job.status = if cancelled {
                    "cancelled"
                } else if status.success() && !semantic_failure {
                    "completed"
                } else {
                    "failed"
                }
                .into();
                if semantic_failure {
                    job.error =
                        Some("CLI reported a failed provider result; see task events".into());
                }
            }
            Err(error) => {
                job.status = "failed".into();
                job.error = Some(error.to_string());
            }
        }
        self.store(&job)?;
        self.event(
            id,
            "lifecycle",
            json!({"type":"finished","status":job.status,"exit_code":job.exit_code}),
        )?;
        Ok(())
    }
    fn read_output<R: tokio::io::AsyncRead + Unpin + Send + 'static>(
        self: &Arc<Self>,
        id: &str,
        stream: &str,
        reader: R,
    ) -> tokio::task::JoinHandle<bool> {
        let manager = self.clone();
        let id = id.to_owned();
        let stream = stream.to_owned();
        tokio::spawn(async move {
            let mut failed = false;
            let mut lines = BufReader::new(reader).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                let data: Value =
                    serde_json::from_str(&line).unwrap_or_else(|_| json!({"text":line}));
                if matches!(data["type"].as_str(), Some("turn.failed" | "error"))
                    || (data["type"] == "result"
                        && (data["is_error"] == true
                            || data["subtype"]
                                .as_str()
                                .is_some_and(|s| s.starts_with("error"))))
                {
                    failed = true;
                }
                let _ = manager.event(&id, &stream, data);
            }
            failed
        })
    }
    #[cfg(test)]
    fn harness_job(&self, cwd: &std::path::Path) -> Job {
        let timestamp = now();
        let job = Job {
            id: uuid::Uuid::new_v4().to_string(),
            engine: "harness".into(),
            cwd: cwd.into(),
            prompt: "test".into(),
            project_id: None,
            status: "queued".into(),
            created_at: timestamp,
            updated_at: timestamp,
            pid: None,
            worker_pid: None,
            exit_code: None,
            error: None,
        };
        self.store(&job).unwrap();
        job
    }
}
fn hidden(command: &mut Command) {
    #[cfg(windows)]
    command.creation_flags(0x08000000);
}
#[cfg(windows)]
fn process_alive(pid: u32) -> bool {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::Threading::{GetExitCodeProcess, OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION},
    };
    let handle = unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid) };
    if handle.is_null() {
        return false;
    }
    let mut code = 0;
    let result = unsafe { GetExitCodeProcess(handle, &mut code) };
    unsafe {
        CloseHandle(handle);
    }
    result != 0 && code == 259
}
#[cfg(not(windows))]
fn process_alive(pid: u32) -> bool {
    sysinfo::System::new_all()
        .process(sysinfo::Pid::from_u32(pid))
        .is_some()
}
#[cfg(windows)]
fn spawn_worker(worker: &std::path::Path, id: &str, root: &std::path::Path) -> Result<u32> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::Threading::{CREATE_NO_WINDOW, CreateProcessW, PROCESS_INFORMATION, STARTUPINFOW},
    };
    fn quote(value: &std::ffi::OsStr) -> String {
        let text = value.to_string_lossy();
        let mut result = String::from("\"");
        let mut slashes = 0;
        for ch in text.chars() {
            if ch == '\\' {
                slashes += 1;
                continue;
            }
            if ch == '"' {
                result.push_str(&"\\".repeat(slashes * 2 + 1));
                result.push('"');
            } else {
                result.push_str(&"\\".repeat(slashes));
                result.push(ch);
            }
            slashes = 0;
        }
        result.push_str(&"\\".repeat(slashes * 2));
        result.push('"');
        result
    }
    let application: Vec<u16> = worker.as_os_str().encode_wide().chain(Some(0)).collect();
    let line = format!(
        "{} __worker {} --jobs-root {}",
        quote(worker.as_os_str()),
        id,
        quote(root.as_os_str())
    );
    let mut line: Vec<u16> = std::ffi::OsStr::new(&line)
        .encode_wide()
        .chain(Some(0))
        .collect();
    let mut startup = STARTUPINFOW::default();
    startup.cb = std::mem::size_of::<STARTUPINFOW>() as u32;
    let mut process = PROCESS_INFORMATION::default();
    // No inherited handles: a background worker must never keep the caller's
    // stdout pipe or window handles alive after dp task run exits.
    let ok = unsafe {
        CreateProcessW(
            application.as_ptr(),
            line.as_mut_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            0,
            CREATE_NO_WINDOW,
            std::ptr::null(),
            std::ptr::null(),
            &startup,
            &mut process,
        )
    };
    if ok == 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    unsafe {
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    }
    Ok(process.dwProcessId)
}
#[cfg(not(windows))]
fn spawn_worker(worker: &std::path::Path, id: &str, root: &std::path::Path) -> Result<u32> {
    Ok(std::process::Command::new(worker)
        .arg("__worker")
        .arg(id)
        .arg("--jobs-root")
        .arg(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?
        .id())
}
async fn kill_tree(pid: u32) {
    #[cfg(windows)]
    {
        let mut command = Command::new("taskkill.exe");
        command
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        hidden(&mut command);
        let _ = command.status().await;
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status()
            .await;
    }
}
fn find_engine(id: &str) -> Option<PathBuf> {
    let override_name = if id == "codex" {
        "DEEP_PARTNER_CODEX"
    } else {
        "DEEP_PARTNER_CLAUDE"
    };
    if let Some(path) = std::env::var_os(override_name)
        .map(PathBuf::from)
        .filter(|p| p.is_file())
    {
        return Some(path);
    }
    let mut candidates = Vec::new();
    for directory in std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()) {
        for suffix in if cfg!(windows) {
            vec![".exe", ".cmd", ".bat", ""]
        } else {
            vec![""]
        } {
            candidates.push(directory.join(format!("{id}{suffix}")));
        }
    }
    if id == "codex" {
        if let Some(local) = std::env::var_os("LOCALAPPDATA") {
            candidates.push(PathBuf::from(local).join("Programs/OpenAI/Codex/bin/codex.exe"));
        }
    }
    if let Some(home) = std::env::var_os("USERPROFILE") {
        candidates.push(PathBuf::from(home).join(format!(".local/bin/{id}.exe")));
    }
    if let Some(appdata) = std::env::var_os("APPDATA") {
        candidates.push(PathBuf::from(appdata).join(format!("npm/{id}.cmd")));
    }
    candidates.into_iter().find(|p| p.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn durable_process_output_exit_and_cancel() {
        let temp = tempfile::tempdir().unwrap();
        let manager = JobManager::new(temp.path().join("jobs"));
        let job = manager.harness_job(temp.path());
        let mut command = Command::new("powershell.exe");
        command.args(["-NoProfile","-Command","Write-Output '{\"type\":\"harness\",\"ok\":true}'; [Console]::Error.WriteLine('diagnostic'); exit 7"]);
        manager.execute(&job.id, command).await.unwrap();
        let reopened = JobManager::new(temp.path().join("jobs"));
        let status = reopened.status(&job.id).unwrap();
        assert_eq!(status.status, "failed");
        assert_eq!(status.exit_code, Some(7));
        let events = reopened.events(&job.id, 0).unwrap();
        let events = events["events"].as_array().unwrap();
        assert!(events.iter().any(|e| e["data"]["type"] == "harness"));
        assert!(events.iter().any(|e| e["stream"] == "stderr"));
        let job = manager.harness_job(temp.path());
        let mut command = Command::new("powershell.exe");
        command.args(["-NoProfile", "-Command", "Start-Sleep -Seconds 30"]);
        let task = {
            let manager = manager.clone();
            let id = job.id.clone();
            tokio::spawn(async move { manager.execute(&id, command).await })
        };
        tokio::time::sleep(Duration::from_millis(500)).await;
        reopened.cancel(&job.id).unwrap();
        tokio::time::timeout(Duration::from_secs(8), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        assert_eq!(reopened.status(&job.id).unwrap().status, "cancelled");
    }
    #[tokio::test]
    async fn provider_error_overrides_successful_process_exit() {
        let temp = tempfile::tempdir().unwrap();
        let manager = JobManager::new(temp.path().join("jobs"));
        for line in [
            r#"{"type":"turn.failed","error":{"message":"provider failed"}}"#,
            r#"{"type":"result","is_error":true,"subtype":"error_during_execution"}"#,
        ] {
            let job = manager.harness_job(temp.path());
            let mut command = Command::new("powershell.exe");
            command.args([
                "-NoProfile",
                "-Command",
                &format!("Write-Output '{line}'; exit 0"),
            ]);
            manager.execute(&job.id, command).await.unwrap();
            let status = manager.status(&job.id).unwrap();
            assert_eq!(status.exit_code, Some(0));
            assert_eq!(status.status, "failed");
        }
    }
    #[tokio::test]
    async fn cancellation_terminates_child_process_tree() {
        let temp = tempfile::tempdir().unwrap();
        let manager = JobManager::new(temp.path().join("jobs"));
        let job = manager.harness_job(temp.path());
        let mut command = Command::new("powershell.exe");
        command.args(["-NoProfile","-Command","$p=Start-Process powershell.exe -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 30' -WindowStyle Hidden -PassThru; Write-Output ('{\"child_pid\":'+$p.Id+'}'); Start-Sleep -Seconds 30"]);
        let task = {
            let manager = manager.clone();
            let id = job.id.clone();
            tokio::spawn(async move { manager.execute(&id, command).await })
        };
        let child_pid = tokio::time::timeout(Duration::from_secs(8), async {
            loop {
                let events = manager.events(&job.id, 0).unwrap();
                if let Some(pid) = events["events"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .find_map(|e| e["data"]["child_pid"].as_u64())
                {
                    break pid as u32;
                }
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        })
        .await
        .unwrap();
        manager.cancel(&job.id).unwrap();
        tokio::time::timeout(Duration::from_secs(8), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        assert!(
            sysinfo::System::new_all()
                .process(sysinfo::Pid::from_u32(child_pid))
                .is_none(),
            "descendant remained alive"
        );
        assert_eq!(manager.status(&job.id).unwrap().status, "cancelled");
    }
}
