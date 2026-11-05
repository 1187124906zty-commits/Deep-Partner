use crate::service::DesktopService;
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::{
    io::AsyncWriteExt,
    process::{Child, Command},
    sync::Mutex,
};

pub struct Tunnel {
    process: Mutex<Option<Child>>,
    inherited: Mutex<Option<InheritedTunnel>>,
    message: Mutex<String>,
    operation: Mutex<()>,
}
impl Tunnel {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            process: Mutex::new(None),
            inherited: Mutex::new(None),
            message: Mutex::new("尚未连接电脑工具".into()),
            operation: Mutex::new(()),
        })
    }
    pub async fn status(&self) -> Value {
        let mut process = self.process.lock().await;
        let mut connected = if let Some(p) = process.as_mut() {
            matches!(p.try_wait(), Ok(None))
        } else {
            false
        };
        if !connected {
            *process = None;
            let mut inherited = self.inherited.lock().await;
            connected = inherited.as_ref().is_some_and(InheritedTunnel::alive);
            if !connected { *inherited = None; }
        }
        json!({"connected":connected,"message":self.message.lock().await.clone()})
    }
    pub async fn connect(&self, service: &Arc<DesktopService>) -> Result<Value> {
        let _serial = self.operation.lock().await;
        if self.status().await["connected"] == true {
            return Ok(self.status().await);
        }
        *self.message.lock().await = "正在连接电脑工具…".into();
        let config = service.config.read().unwrap().clone();
        let mut enroll = ssh();
        enroll
            .args([
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-T",
                &config.ssh_host,
                "sudo -n python3 /srv/deeptutor/migration/desktop_bridge_ctl.py enroll",
            ])
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .kill_on_drop(true);
        let mut child = enroll.spawn().context("找不到 Windows OpenSSH 客户端")?;
        let mut input = child.stdin.take().unwrap();
        input
            .write_all(json!({"token":service.token}).to_string().as_bytes())
            .await?;
        input.shutdown().await?;
        drop(input);
        let output =
            tokio::time::timeout(std::time::Duration::from_secs(18), child.wait_with_output())
                .await
                .context("服务器工具登记超时")??;
        if !output.status.success() {
            let message = serde_json::from_slice::<Value>(&output.stdout).ok()
                .and_then(|v|v["message"].as_str().map(str::to_owned))
                .unwrap_or_else(||"无法登记电脑工具，请检查服务器连接后重试。".into());
            *self.message.lock().await = format!("电脑工具连接失败：{message}");
            bail!("服务器工具登记失败：{message}");
        }
        let forward = format!(
            "/srv/deeptutor/data/system/desktop-bridge.sock:127.0.0.1:{}",
            config.bridge_port
        );
        let reused = serde_json::from_slice::<Value>(&output.stdout).ok()
            .is_some_and(|v| v["reused"] == true);
        if reused {
            let inherited = InheritedTunnel::find(&config.ssh_host, &forward)
                .context("已有电脑通道不属于当前桌面连接，请关闭旧桌面程序后重试。")?;
            *self.inherited.lock().await = Some(inherited);
        } else {
        let mut command = ssh();
        command
            .args([
                "-N",
                "-T",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-o",
                "ExitOnForwardFailure=yes",
                "-o",
                "ServerAliveInterval=15",
                "-o",
                "ServerAliveCountMax=2",
                "-R",
                &forward,
                &config.ssh_host,
            ])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true);
        let mut child = command.spawn()?;
        tokio::time::sleep(std::time::Duration::from_millis(700)).await;
        if let Some(status) = child.try_wait()? {
            *self.message.lock().await = "电脑通道未建立，请检查 SSH 连接".into();
            bail!("SSH 通道启动失败：{status}");
        }
        *self.process.lock().await = Some(child);
        }
        let mut activate = ssh();
        activate
            .args([
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-T",
                &config.ssh_host,
                "python3 /srv/deeptutor/migration/desktop_bridge_ctl.py activate",
            ])
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .kill_on_drop(true);
        let activation =
            tokio::time::timeout(std::time::Duration::from_secs(75), activate.output()).await;
        if !matches!(&activation,Ok(Ok(output)) if output.status.success()) {
            if let Some(mut process) = self.process.lock().await.take() {
                let _ = process.kill().await;
            }
            self.inherited.lock().await.take();
            *self.message.lock().await =
                "通道已建立，但 Deep partner 工具加载失败；点击连接重试".into();
            bail!("Deep partner 工具加载失败，请检查服务器登记接口");
        }
        *self.message.lock().await = "电脑工具已连接 · SSH 加密通道".into();
        Ok(self.status().await)
    }
    pub async fn disconnect(&self) {
        let _serial = self.operation.lock().await;
        if let Some(mut process) = self.process.lock().await.take() {
            let _ = process.kill().await;
            let _ = process.wait().await;
        }
        if let Some(inherited) = self.inherited.lock().await.take() { inherited.stop(); }
        *self.message.lock().await = "电脑工具已断开".into();
    }
}

/// A previous app may have exited without dropping its SSH child. Keep its
/// validated PID/start time so reconnect is idempotent and disconnect owns it.
struct InheritedTunnel { pid:sysinfo::Pid, started:u64, host:String, forward:String }
impl InheritedTunnel {
    fn matches(process:&sysinfo::Process,host:&str,forward:&str)->bool {
        let args=process.cmd();
        process.name().to_string_lossy().eq_ignore_ascii_case("ssh.exe")
            && args.last().is_some_and(|v|v==host)
            && args.windows(2).any(|v|v[0]=="-R"&&v[1]==forward)
    }
    fn find(host:&str,forward:&str)->Option<Self> {
        let system=sysinfo::System::new_all();
        let mut candidates=system.processes().values().filter(|p|Self::matches(p,host,forward));
        let process=candidates.next()?;
        if candidates.next().is_some(){return None}
        Some(Self{pid:process.pid(),started:process.start_time(),host:host.into(),forward:forward.into()})
    }
    fn alive(&self)->bool {
        sysinfo::System::new_all().process(self.pid).is_some_and(|p|p.start_time()==self.started&&Self::matches(p,&self.host,&self.forward))
    }
    fn stop(self) {
        if let Some(p)=sysinfo::System::new_all().process(self.pid) {
            if p.start_time()==self.started&&Self::matches(p,&self.host,&self.forward){p.kill();}
        }
    }
}
fn ssh() -> Command {
    let mut command = Command::new("ssh.exe");
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    command
}
