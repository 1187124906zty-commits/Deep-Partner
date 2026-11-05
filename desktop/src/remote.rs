use anyhow::{Context, Result, bail};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Value, json};
use std::{
    sync::{Arc, RwLock},
    time::Duration,
};
pub type EventSink = Arc<dyn Fn(Value) + Send + Sync>;
use crate::config::Config;
use tokio::sync::{Mutex, mpsc};
use tokio_tungstenite::tungstenite::{Message, client::IntoClientRequest};

pub struct RemoteClient {
    pub client: reqwest::Client,
    cookie: RwLock<std::collections::BTreeMap<String, String>>,
    options: RwLock<Value>,
    outgoing: Mutex<Option<mpsc::Sender<Value>>>,
    auth_lock: Mutex<()>,
}

impl RemoteClient {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            client: reqwest::Client::builder()
                .redirect(reqwest::redirect::Policy::none())
                .connect_timeout(Duration::from_secs(10))
                .timeout(Duration::from_secs(35))
                .build()
                .unwrap(),
            cookie: RwLock::new(std::collections::BTreeMap::new()),
            options: RwLock::new(json!({})),
            outgoing: Mutex::new(None),
            auth_lock: Mutex::new(()),
        })
    }
    pub async fn authenticate(&self, _config: &Config) -> Result<()> {
        if !self.cookie.read().unwrap().contains_key("dt_token") {
            bail!("请先登录 Deep partner");
        }
        Ok(())
    }
    pub async fn login(&self, config: &Config, username: &str, password: &str) -> Result<Value> {
        let _lock = self.auth_lock.lock().await;
        let body = self
            .api(
                config,
                "POST",
                "/api/auth/login",
                Some(json!({"username":username,"password":password})),
                false,
            )
            .await?;
        self.authenticate(config).await?;
        Ok(body)
    }
    pub(crate) fn cookie_header(&self) -> String {
        self.cookie
            .read()
            .unwrap()
            .iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect::<Vec<_>>()
            .join("; ")
    }
    pub(crate) fn session_token(&self) -> Option<String> {
        self.cookie.read().unwrap().get("dt_token").cloned()
    }
    pub(crate) fn restore_session(&self, token: String) {
        self.cookie.write().unwrap().insert("dt_token".into(), token);
    }
    pub(crate) fn absorb_cookies(&self, headers: &reqwest::header::HeaderMap) {
        let mut cookies = self.cookie.write().unwrap();
        for raw in headers
            .get_all(reqwest::header::SET_COOKIE)
            .iter()
            .filter_map(|h| h.to_str().ok())
        {
            if let Some((name, value)) = raw.split(';').next().and_then(|s| s.split_once('=')) {
                if !name.is_empty() {
                    if value.is_empty() {
                        cookies.remove(name);
                    } else {
                        cookies.insert(name.into(), value.into());
                    }
                }
            }
        }
    }
    pub fn set_trusted(&self, value: String) {
        self.cookie
            .write()
            .unwrap()
            .insert("__Host-dt_trusted".into(), value);
    }
    pub fn trusted(&self) -> Option<String> {
        self.cookie
            .read()
            .unwrap()
            .get("__Host-dt_trusted")
            .cloned()
    }
    pub fn model_options(&self) -> Value {
        self.options.read().unwrap().clone()
    }
    pub async fn api(
        &self,
        config: &Config,
        method: &str,
        path: &str,
        body: Option<Value>,
        auth: bool,
    ) -> Result<Value> {
        if auth {
            self.authenticate(config).await?;
        }
        if !(path.starts_with("/api/") || path.starts_with("/research/api/")) || path.contains("\\") || path.contains("#") {
            bail!("服务路径无效");
        }
        let mut request = self
            .client
            .request(
                method.parse()?,
                format!("{}{}", config.server_url.trim_end_matches('/'), path),
            )
            .header("Origin", config.server_url.trim_end_matches('/'))
            .header("Cookie", self.cookie_header())
            .header(
                "User-Agent",
                concat!(
                    "Deep-partner-Native/",
                    env!("CARGO_PKG_VERSION"),
                    " Windows"
                ),
            );
        if let Some(body) = body {
            request = request.json(&body);
        }
        let response = request.send().await?;
        self.absorb_cookies(response.headers());
        let status = response.status();
        let text = response.text().await?;
        if !status.is_success() {
            let detail = serde_json::from_str::<Value>(&text)
                .ok()
                .and_then(|v| v.get("detail").cloned())
                .unwrap_or_else(|| json!(text.chars().take(400).collect::<String>()));
            bail!(
                "{}",
                if let Some(s) = detail.as_str() {
                    s.to_string()
                } else {
                    detail.to_string()
                }
            );
        }
        if text.is_empty() {
            Ok(json!({"ok":true}))
        } else {
            Ok(serde_json::from_str(&text).unwrap_or_else(|_| json!({"content":text})))
        }
    }
    pub fn logout(&self) {
        self.cookie.write().unwrap().remove("dt_token");
    }
    pub async fn get(&self, config: &Config, path: &str) -> Result<Value> {
        self.api(config, "GET", path, None, true).await
    }
    pub async fn upload(
        &self,
        config: &Config,
        path: &str,
        fields: Value,
        files: Vec<(String, std::path::PathBuf)>,
    ) -> Result<Value> {
        self.authenticate(config).await?;
        let mut form = reqwest::multipart::Form::new();
        if let Some(fields) = fields.as_object() {
            for (k, v) in fields {
                form = form.text(
                    k.clone(),
                    v.as_str()
                        .map(str::to_owned)
                        .unwrap_or_else(|| v.to_string()),
                );
            }
        }
        for (field, file) in files {
            let name = file
                .file_name()
                .context("文件名无效")?
                .to_string_lossy()
                .into_owned();
            let bytes = tokio::task::spawn_blocking(move || std::fs::read(file)).await??;
            form = form.part(
                field,
                reqwest::multipart::Part::bytes(bytes).file_name(name),
            );
        }
        let response = self
            .client
            .post(format!(
                "{}{}",
                config.server_url.trim_end_matches('/'),
                path
            ))
            .header("Cookie", self.cookie_header())
            .header("Origin", config.server_url.trim_end_matches('/'))
            .multipart(form)
            .timeout(Duration::from_secs(180))
            .send()
            .await?;
        let status = response.status();
        let body = response.text().await?;
        if !status.is_success() {
            bail!("上传失败：{}", body.chars().take(500).collect::<String>());
        }
        Ok(serde_json::from_str(&body).unwrap_or_else(|_| json!({"content":body})))
    }
    pub async fn download(&self, config: &Config, path: &str) -> Result<Vec<u8>> {
        self.authenticate(config).await?;
        let url = if path.starts_with("/api/") || path.starts_with("/files/") {
            format!("{}{}", config.server_url.trim_end_matches('/'), path)
        } else {
            bail!("下载地址需要来自当前学习服务");
        };
        let response = self
            .client
            .get(url)
            .header("Cookie", self.cookie_header())
            .timeout(Duration::from_secs(90))
            .send()
            .await?
            .error_for_status()?;
        Ok(response.bytes().await?.to_vec())
    }
    pub async fn refresh_models(&self, config: &Config) -> Result<Value> {
        let models = self.get(config, "/api/settings/llm-options").await?;
        *self.options.write().unwrap() = models.clone();
        Ok(models)
    }
    pub async fn bootstrap(&self, config: &Config) -> Result<Value> {
        self.authenticate(config).await?;
        let (models, sessions, knowledge) = tokio::try_join!(
            self.refresh_models(config),
            self.get(config, "/api/sessions?all_workspaces=true&limit=100"),
            self.get(config, "/api/knowledge-bases?resource_library=true")
        )?;
        *self.options.write().unwrap() = models.clone();
        Ok(json!({"models":models,"sessions":sessions,"knowledge":knowledge}))
    }
    pub fn choice(&self, config: &Config, computer: bool) -> Result<Value> {
        let catalog = self.options.read().unwrap();
        let options = catalog["options"].as_array().context("模型列表尚未加载")?;
        let saved = if computer {
            &config.computer_model
        } else {
            &config.learning_model
        };
        if let Some(choice) = saved {
            let found = options.iter().any(|o| {
                o["profile_id"] == choice["profile_id"] && o["model_id"] == choice["model_id"]
            });
            if found {
                return Ok(choice.clone());
            }
            bail!("已选择的模型当前不可用，请在设置中重新选择");
        }
        let model = if computer {
            options
                .iter()
                .find(|o| o["model"] == "gpt-6.1-terra")
                .context("服务端尚未配置 GPT-6.1 Terra")?
        } else {
            options
                .iter()
                .find(|o| o["is_active_default"] == true)
                .context("没有可用的学习模型")?
        };
        Ok(json!({"profile_id":model["profile_id"],"model_id":model["model_id"]}))
    }
    pub fn validate_choice(&self, choice: &Value) -> Result<Value> {
        let options = self.options.read().unwrap();
        if !options["options"].as_array().is_some_and(|options| {
            options.iter().any(|o| {
                o["profile_id"] == choice["profile_id"] && o["model_id"] == choice["model_id"]
            })
        }) {
            bail!("请选择服务端已配置的模型");
        }
        Ok(json!({"profile_id":choice["profile_id"],"model_id":choice["model_id"]}))
    }
    pub async fn send(
        self: &Arc<Self>,
        sink: EventSink,
        runtime: tokio::runtime::Handle,
        config: Config,
        payload: Value,
    ) -> Result<Value> {
        let mut outgoing = self.outgoing.lock().await;
        if outgoing.is_some() {
            bail!("当前回答还在生成，可以先停止");
        }
        let computer = payload["mode"] == "computer";
        let choice = self.choice(&config, computer)?;
        let content = payload["content"]
            .as_str()
            .filter(|s| !s.trim().is_empty())
            .context("请输入问题或任务")?;
        if content.len() > 100000 {
            bail!("单次消息过长");
        }
        let capability = payload["capability"]
            .as_str()
            .filter(|s| !s.is_empty())
            .unwrap_or("chat");
        let mut request = json!({"type":"start_turn","protocol_version":"2.0","content":content,"capability":if computer{"chat"}else{capability},"language":"zh","client_submission_id":uuid::Uuid::new_v4().to_string(),"llm_selection":choice,"knowledge_bases":payload["knowledge_bases"].as_array().cloned().unwrap_or_default()});
        for key in [
            "tools",
            "config",
            "skills",
            "mcp",
            "persona",
            "attachments",
            "reading_material_id",
            "reading_material_revision",
            "reading_workspace_id",
            "reading_viewport",
            "mastery_path_id",
            "mastery_session_mode",
            "book_references",
            "notebook_references",
            "memory_references",
            "question_notebook_references",
            "parent_message_id",
            "consult_partner_id",
            "answer_by",
        ] {
            if let Some(value) = payload.get(key) {
                request[key] = value.clone();
            }
        }
        if let Some(id) = payload["session_id"].as_str() {
            request["session_id"] = json!(id);
        }
        if let Some(id) = payload["workspace_id"].as_str() {
            request["workspace_id"] = json!(id);
        }
        if computer {
            request["mcp"] = json!(["deployment:windows-desktop"]);
            request["content"] = json!(format!(
                "[电脑助手任务：你使用 Windows 本机工具完成操作。读取本机文件或网页时使用 windows-desktop MCP，而不是服务器的文件或浏览器。先观察再操作；网页优先 browser_snapshot/browser_click/browser_type，桌面使用 desktop_screenshot/desktop_click/desktop_type/desktop_key。工具未开启时清楚说明。]\n\n{content}"
            ));
        }
        let (tx, rx) = mpsc::channel(8);
        *outgoing = Some(tx);
        drop(outgoing);
        let client = self.clone();
        runtime.spawn(async move {
            if let Err(error) = client.stream(&sink, &config, request, rx).await {
                sink(json!({"type":"desktop_error","content":format!("{error:#}")}));
            }
            *client.outgoing.lock().await = None;
            sink(json!({"type":"desktop_finished"}));
        });
        Ok(json!({"accepted":true,"model":choice}))
    }
    pub async fn control(&self, payload: Value) -> Result<Value> {
        let sender = self
            .outgoing
            .lock()
            .await
            .clone()
            .context("没有正在执行的任务")?;
        sender.send(payload).await?;
        Ok(json!({"sent":true}))
    }
    pub(crate) async fn stream(
        &self,
        sink: &EventSink,
        config: &Config,
        request: Value,
        mut controls: mpsc::Receiver<Value>,
    ) -> Result<()> {
        self.authenticate(config).await?;
        let mut address = url::Url::parse(&config.server_url)?;
        let scheme = if address.scheme() == "https" {
            "wss"
        } else {
            "ws"
        };
        address
            .set_scheme(scheme)
            .map_err(|_| anyhow::anyhow!("WebSocket 地址无效"))?;
        address.set_path("/ws");
        address.set_query(None);
        if let Some(workspace)=request["workspace_id"].as_str().filter(|s|!s.is_empty()) {
            address.query_pairs_mut().append_pair("dt_workspace",workspace);
        }
        let mut turn = if request["type"] == "resume_from" { request["turn_id"].as_str().unwrap_or("").to_owned() } else { String::new() };
        let mut seq = request["seq"].as_u64().unwrap_or(0);
        let mut attempts = 0;
        let mut start_retries = 0;
        let mut pending_controls = Vec::<Value>::new();
        'connection: loop {
            let mut handshake = address.as_str().into_client_request()?;
            handshake
                .headers_mut()
                .insert("Cookie", self.cookie_header().parse()?);
            handshake.headers_mut().insert("Origin",config.server_url.trim_end_matches('/').parse()?);
            let mut socket = tokio::time::timeout(
                Duration::from_secs(15),
                crate::network::connect(handshake),
            )
            .await
            .context("对话连接超时")??;
            let command = if turn.is_empty() {
                request.clone()
            } else {
                json!({"type":"resume_from","protocol_version":"2.0","turn_id":turn,"seq":seq})
            };
            socket
                .send(Message::Text(command.to_string().into()))
                .await?;
            let mut heartbeat = tokio::time::interval_at(
                tokio::time::Instant::now() + Duration::from_secs(20),
                Duration::from_secs(20),
            );
            loop {
                tokio::select! {
                    message=socket.next()=>{
                        let Some(message)=message else{break;};
                        let Ok(message)=message else{break;};
                        let Message::Text(text)=message else{continue;};
                        let mut event:Value=serde_json::from_str(&text)?;
                        if let Some(id)=event["turn_id"].as_str().filter(|s|!s.is_empty()){turn=id.into();}
                        if !turn.is_empty(){for mut command in pending_controls.drain(..){
                            command["protocol_version"]=json!("2.0");command["turn_id"]=json!(turn);command["command_id"]=json!(uuid::Uuid::new_v4().to_string());
                            socket.send(Message::Text(command.to_string().into())).await?;
                        }}
                        let event_seq=event["seq"].as_u64().unwrap_or(0);
                        if event_seq>0&&event_seq<=seq{continue;}seq=seq.max(event_seq);
                        let kind=event["type"].as_str().unwrap_or("").to_owned();
                        if kind=="protocol_error" && turn.is_empty() && request["session_id"].is_string()
                            && event["error_code"]=="start_turn_rejected"
                            && event["message"].as_str().is_some_and(|s|s.contains("active or recovering turn")) && start_retries<15 {
                            start_retries+=1;
                            sink(json!({"type":"desktop_reconnecting","content":"上一轮正在结束，等待会话释放…"}));
                            let _=socket.close(None).await;
                            tokio::time::sleep(Duration::from_secs(2)).await;
                            continue 'connection;
                        }
                        // Tool payloads can contain screenshots or long source text. Keep the
                        // UI event small; the model and durable server trace retain originals.
                        if request["cli_full_events"] != true && matches!(kind.as_str(),"tool_result"|"thinking"){
                            if let Some(content)=event["content"].as_str(){event["content"]=json!(content.chars().take(1200).collect::<String>());}
                        }
                        sink(event);
                        if kind=="done"||kind=="protocol_error"{let _=socket.close(None).await;return Ok(());}
                    },
                    command=controls.recv()=>{
                        let Some(mut command)=command else{return Ok(());};
                        if turn.is_empty(){pending_controls.push(command);continue;}
                        command["protocol_version"]=json!("2.0");command["turn_id"]=json!(turn);command["command_id"]=json!(uuid::Uuid::new_v4().to_string());
                        socket.send(Message::Text(command.to_string().into())).await?;
                    },
                    _=heartbeat.tick()=>{socket.send(Message::Text(json!({"type":"ping","protocol_version":"2.0"}).to_string().into())).await?;}
                }
            }
            attempts += 1;
            if turn.is_empty() || attempts > 3 {
                bail!("对话连接中断；可从会话历史重新打开已保存的回答");
            }
            sink(json!({"type":"desktop_reconnecting","content":"连接中断，正在恢复回答…"}));
            tokio::time::sleep(Duration::from_millis(500 * attempts)).await;
        }
    }
}
