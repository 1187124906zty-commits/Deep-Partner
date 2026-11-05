use crate::{
    browser::Browser,
    cache::TextCache,
    config::{Config, workspace_path},
};
use anyhow::{Context, Result, bail};
use serde::Serialize;
use serde_json::{Value, json};
use std::{
    collections::VecDeque,
    sync::{
        Arc, Mutex, RwLock,
        atomic::{AtomicBool, Ordering},
    },
    time::Instant,
};
use tokio::sync::Semaphore;

#[derive(Clone, Serialize)]
pub struct Activity {
    pub tool: String,
    pub ok: bool,
    pub elapsed_ms: u128,
}

pub struct DesktopService {
    pub remote: Arc<crate::remote::RemoteClient>,
    pub jobs: Arc<crate::jobs::JobManager>,
    pub config: RwLock<Config>,
    pub cache: TextCache,
    pub browser: Browser,
    pub token: String,
    pub enabled: AtomicBool,
    pub cpu: Arc<Semaphore>,
    pub desktop: Arc<Semaphore>,
    pub activity: Mutex<VecDeque<Activity>>,
}

impl DesktopService {
    pub fn new(config: Config, token: String) -> Arc<Self> {
        Arc::new(Self {
            remote: crate::remote::RemoteClient::new(),
            jobs: crate::jobs::JobManager::standard(),
            cache: TextCache::new(config.cache_mb * 1024 * 1024),
            browser: Browser::new(config.browser_port),
            cpu: Arc::new(Semaphore::new(config.cpu_workers)),
            desktop: Arc::new(Semaphore::new(1)),
            config: RwLock::new(config),
            token,
            enabled: AtomicBool::new(true),
            activity: Mutex::new(VecDeque::new()),
        })
    }
    pub fn status(&self) -> Value {
        json!({"enabled":self.enabled.load(Ordering::Relaxed),"config":self.config.read().unwrap().clone(),"cache":self.cache.stats(),"activity":*self.activity.lock().unwrap(),"cpu_available_slots":self.cpu.available_permits()})
    }
    pub async fn call(self: &Arc<Self>, name: &str, args: Value) -> Result<Value> {
        if !self.enabled.load(Ordering::Relaxed) {
            bail!("电脑工具已在桌面端暂停");
        }
        let begin = Instant::now();
        let result = self.call_inner(name, args).await;
        let mut activity = self.activity.lock().unwrap();
        activity.push_front(Activity {
            tool: name.into(),
            ok: result.is_ok(),
            elapsed_ms: begin.elapsed().as_millis(),
        });
        activity.truncate(40);
        result
    }
    async fn call_inner(self: &Arc<Self>, name: &str, args: Value) -> Result<Value> {
        match name {
            "project_import" => {
                let config=self.config.read().unwrap().clone();
                return match required(&args,"action")? {
                    "prepare"=>{let source=std::path::PathBuf::from(required(&args,"source")?);tokio::task::spawn_blocking(move||crate::project_import::prepare(&config,&source)).await?},
                    "apply"=>crate::project_import::apply(&self.remote,&config,required(&args,"import_id")?,required(&args,"project_id")?).await,
                    _=>bail!("导入action需为prepare或apply"),
                };
            }
            "cli_engines" => {
                return Ok(json!({"engines":crate::jobs::JobManager::engines().await}));
            }
            "cli_task_start" => {
                let request: crate::jobs::JobRequest = serde_json::from_value(args)?;
                let shared = self.config.read().unwrap().workspace.canonicalize()?;
                let cwd = request.cwd.canonicalize()?;
                if !cwd.starts_with(shared) {
                    bail!("Remote CLI task cwd must be within the selected shared folder");
                }
                return Ok(serde_json::to_value(self.jobs.start(request).await?)?);
            }
            "cli_task_status" => {
                return Ok(serde_json::to_value(
                    self.jobs.status(required(&args, "id")?)?,
                )?);
            }
            "cli_task_events" => {
                return self
                    .jobs
                    .events(required(&args, "id")?, args["after"].as_u64().unwrap_or(0));
            }
            "cli_task_cancel" => {
                return Ok(serde_json::to_value(
                    self.jobs.cancel(required(&args, "id")?)?,
                )?);
            }
            "browser_open" => return self.browser.open(required(&args, "url")?).await,
            "browser_snapshot" => return self.browser.snapshot().await,
            "browser_click" => return self.browser.click(required(&args, "target")?).await,
            "browser_type" => {
                return self
                    .browser
                    .type_text(required(&args, "target")?, required(&args, "text")?)
                    .await;
            }
            "browser_screenshot" => {
                return Ok(
                    json!({"content":[{"type":"image","mimeType":"image/png","data":self.browser.screenshot().await?}]}),
                );
            }
            "browser_close" => {
                self.browser.close().await;
                return Ok(json!({"closed":true}));
            }
            _ => {}
        }
        let _desktop_order = if name.starts_with("desktop_") {
            Some(self.desktop.clone().acquire_owned().await?)
        } else {
            None
        };
        let permit = self.cpu.clone().acquire_owned().await?;
        let service = self.clone();
        let name = name.to_owned();
        tokio::task::spawn_blocking(move || {
            let _permit=permit;
            let config=service.config.read().unwrap().clone();
            match name.as_str() {
                "system_info" => Ok(crate::native::system_info()),
                "workspace_list" => {
                    let path=workspace_path(&config.workspace,args["path"].as_str().unwrap_or("."))?;
                    let mut files=Vec::new();
                    for entry in std::fs::read_dir(path)?.take(500) {
                        let entry=entry?; let meta=entry.metadata()?;
                        files.push(json!({"name":entry.file_name().to_string_lossy(),"directory":meta.is_dir(),"bytes":meta.len()}));
                    }
                    files.sort_by_key(|f|(!f["directory"].as_bool().unwrap_or(false),f["name"].as_str().unwrap_or("").to_lowercase()));
                    Ok(json!({"entries":files,"limit":500}))
                }
                "workspace_read" => {
                    let path=workspace_path(&config.workspace,required(&args,"path")?)?;
                    let text=service.cache.read(&path)?;
                    let start=args["start_line"].as_u64().unwrap_or(1).max(1) as usize;
                    let limit=args["lines"].as_u64().unwrap_or(200).clamp(1,1000) as usize;
                    let total=text.lines().count();
                    let content=text.lines().skip(start-1).take(limit).collect::<Vec<_>>().join("\n");
                    Ok(json!({"text":content,"start_line":start,"total_lines":total,"truncated":total>start-1+limit}))
                }
                "workspace_search" => {
                    let query=required(&args,"query")?.to_lowercase();
                    if query.is_empty() { bail!("搜索词不能为空"); }
                    let mut matches=Vec::new(); let mut scanned=0usize; let mut bytes=0u64; let mut skipped=0usize; let mut truncated=false;
                    let root=config.workspace.canonicalize()?;
                    for entry in walkdir::WalkDir::new(&root).follow_links(false).into_iter().filter_entry(|e| !matches!(e.file_name().to_str(), Some(".git"|"node_modules"|".venv"|"target"))) {
                        let Ok(entry)=entry else { skipped+=1; continue; };
                        if !entry.file_type().is_file() { continue; }
                        scanned+=1;
                        if scanned>10000 || bytes>128*1024*1024 || matches.len()>=50 { truncated=true; break; }
                        let Ok(meta)=entry.metadata() else { skipped+=1; continue; };
                        if meta.len()>2*1024*1024 { skipped+=1; continue; }
                        // Canonicalise every file so junctions cannot widen the selected folder.
                        let Ok(path)=entry.path().canonicalize() else { skipped+=1; continue; };
                        if !path.starts_with(&root) { skipped+=1; continue; }
                        bytes+=meta.len();
                        let Ok(text)=service.cache.read(&path) else { skipped+=1; continue; };
                        for (line_index,line) in text.lines().enumerate() {
                            if line.to_lowercase().contains(&query) {
                                matches.push(json!({"path":entry.path().strip_prefix(&root)?.to_string_lossy(),"line":line_index+1,"text":line.chars().take(400).collect::<String>()}));
                                if matches.len()>=50 { truncated=true; break; }
                            }
                        }
                    }
                    Ok(json!({"matches":matches,"scanned_files":scanned,"skipped_files":skipped,"truncated":truncated}))
                }
                "workspace_write" => {
                    let relative=std::path::Path::new(required(&args,"path")?);
                    if relative.is_absolute() || relative.components().any(|c| !matches!(c,std::path::Component::Normal(_))) { bail!("输出文件需要普通相对路径"); }
                    let root=config.workspace.canonicalize()?;
                    let output=root.join("Deep partner Outputs"); std::fs::create_dir_all(&output)?;
                    let output=output.canonicalize()?; if !output.starts_with(&root) { bail!("输出文件夹位于共享范围之外"); }
                    // Walk existing parents before creating them; reject reparse links outside output.
                    let path=output.join(relative);
                    let mut parent=output.clone();
                    if let Some(parts)=relative.parent() { for part in parts.components() {
                        parent.push(part);
                        if parent.exists() { if !parent.canonicalize()?.starts_with(&output) { bail!("输出路径越过输出文件夹"); } }
                        else { std::fs::create_dir(&parent)?; }
                    }}
                    if path.exists() { bail!("输出文件已存在，请使用新的文件名"); }
                    let text=required(&args,"text")?; if text.len()>2*1024*1024 { bail!("单个文本输出上限 2 MB"); }
                    use std::io::Write;
                    let mut file=std::fs::OpenOptions::new().create_new(true).write(true).open(&path)?;
                    file.write_all(text.as_bytes())?;
                    Ok(json!({"saved":format!("Deep partner Outputs/{}",relative.display()),"bytes":text.len()}))
                }
                "open_path" => {
                    let path=workspace_path(&config.workspace,args["path"].as_str().unwrap_or("."))?;
                    open::that_detached(path)?; Ok(json!({"opened":true}))
                }
                "open_url" => {
                    let address=required(&args,"url")?; crate::browser::validate_url(address)?;
                    open::that_detached(address)?; Ok(json!({"opened":address}))
                }
                "desktop_screenshot"|"desktop_click"|"desktop_type"|"desktop_key" => {
                    if !config.desktop_control { bail!("桌面控制已在本机配置中关闭；请恢复本机桌面工具配置"); }
                    match name.as_str() {
                        "desktop_screenshot" => {
                            let mut screenshot=crate::native::screenshot()?;
                            let data=screenshot.as_object_mut().unwrap().remove("data").unwrap();
                            Ok(json!({"content":[{"type":"image","mimeType":"image/png","data":data},{"type":"text","text":screenshot.to_string()}]}))
                        }
                        "desktop_click" => {
                            let x=i32::try_from(args["x"].as_i64().context("x 需要整数")?)?;
                            let y=i32::try_from(args["y"].as_i64().context("y 需要整数")?)?;
                            crate::native::desktop_click(x,y,args["button"]=="right")
                        }
                        "desktop_type" => crate::native::desktop_type(required(&args,"text")?),
                        _ => crate::native::desktop_key(required(&args,"key")?),
                    }
                }
                _ => bail!("未知电脑工具：{name}"),
            }
        }).await?
    }
}

fn required<'a>(args: &'a Value, name: &str) -> Result<&'a str> {
    args[name]
        .as_str()
        .with_context(|| format!("缺少参数 {name}"))
}

pub fn tools() -> Value {
    fn tool(
        name: &str,
        description: &str,
        properties: Value,
        required: &[&str],
        read_only: bool,
    ) -> Value {
        json!({"name":name,"description":description,"inputSchema":{"type":"object","properties":properties,"required":required,"additionalProperties":false},"annotations":{"readOnlyHint":read_only,"destructiveHint":false,"idempotentHint":read_only}})
    }
    let s = json!({"type":"string"});
    json!({"tools":[
        tool("project_import","Import an explicitly selected local project folder. prepare first returns import_id and inventory without writing server files; apply uploads that prepared package to the authenticated project and returns a job_id. Never import an unspecified source. Poll /research/api/projects/PROJECT/jobs until completed and read back files. Source must be in the user-selected shared folder.",json!({"action":{"type":"string","enum":["prepare","apply"]},"source":s,"import_id":s,"project_id":s}),&["action"],false),
        tool("cli_engines","Detect installed local Codex and Claude Code. No model call.",json!({}),&[],true),
        tool("cli_task_start","Start a noninteractive local Codex/Claude task using that CLI's existing login. Does not support interactive approvals.",json!({"engine":{"type":"string","enum":["codex","claude"]},"cwd":s,"prompt":s}),&["engine","cwd","prompt"],false),
        tool("cli_task_status","Read durable local CLI task status.",json!({"id":s}),&["id"],true),
        tool("cli_task_events","Read ordered local CLI task output events after sequence.",json!({"id":s,"after":{"type":"integer","minimum":0}}),&["id"],true),
        tool("cli_task_cancel","Cancel a local CLI task and its process tree.",json!({"id":s}),&["id"],false),
        tool("system_info","读取用户 Windows 电脑的 CPU、内存与操作系统信息。",json!({}),&[],true),
        tool("workspace_list","列出用户在桌面端选定的本机共享文件夹。路径相对于共享文件夹。",json!({"path":s}),&[],true),
        tool("workspace_read","读取共享文件夹中的 UTF-8 文本。按行分页；2 MB 上限。PDF、Word 等二进制文件请通过相应解析工具处理。",json!({"path":s,"start_line":{"type":"integer","minimum":1},"lines":{"type":"integer","minimum":1,"maximum":1000}}),&["path"],true),
        tool("workspace_search","在共享文件夹的文本文件中查找字面关键词。返回真实相对路径、行号与原文，最多 50 处。",json!({"query":s}),&["query"],true),
        tool("workspace_write","把新文本文件保存到本机共享文件夹的 Deep partner Outputs 子目录；不覆盖已有文件。",json!({"path":s,"text":s}),&["path","text"],false),
        tool("open_path","在本机默认软件中打开共享文件夹内的文件或文件夹。",json!({"path":s}),&[],false),
        tool("open_url","在用户默认浏览器打开 HTTP/HTTPS 地址。若要操作网页请改用 browser_open。",json!({"url":s}),&["url"],false),
        tool("browser_open","在本机专用工具浏览器打开网页；浏览器可见，登录状态独立保存。",json!({"url":s}),&["url"],false),
        tool("browser_snapshot","读取工具浏览器当前页面文字与可交互元素的 ref。点击输入前先读取当前页面。",json!({}),&[],true),
        tool("browser_click","点击工具浏览器中最近快照返回的元素 ref（如 dt-3），或已观察到的 CSS 选择器。",json!({"target":s}),&["target"],false),
        tool("browser_type","向工具浏览器输入框填写文字，触发框架 input/change 事件。",json!({"target":s,"text":s}),&["target","text"],false),
        tool("browser_screenshot","截取工具浏览器当前可视网页，返回 PNG。",json!({}),&[],true),
        tool("browser_close","关闭本应用启动的工具浏览器，保留登录与浏览器资料。",json!({}),&[],false),
        tool("desktop_screenshot","截取 Windows 桌面，返回屏幕坐标与缩放信息。桌面工具默认启用，可在本机暂停。",json!({}),&[],true),
        tool("desktop_click","在 Windows 桌面原始像素坐标点击。先用 desktop_screenshot 观察；缩小截图需要换算坐标。",json!({"x":{"type":"integer"},"y":{"type":"integer"},"button":{"type":"string","enum":["left","right"]}}),&["x","y"],false),
        tool("desktop_type","向 Windows 当前焦点窗口输入 Unicode 文字。需要桌面控制已开启。",json!({"text":s}),&["text"],false),
        tool("desktop_key","发送 Windows 按键或组合键，例如 ENTER、CTRL+L、ALT+TAB。需要桌面控制已开启。",json!({"key":s}),&["key"],false)
    ]})
}
