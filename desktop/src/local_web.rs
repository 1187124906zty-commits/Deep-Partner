//! Authenticated loopback host for the fixed, bundled shared frontend.
use crate::{
    config::Config, jobs::JobRequest, remote::RemoteClient, service::DesktopService, tunnel::Tunnel,
};
use anyhow::{Context, Result};
use axum::{
    Json, Router,
    body::{Body, to_bytes},
    extract::{
        Path, Query, State, WebSocketUpgrade,
        ws::{Message, WebSocket},
    },
    http::{HeaderMap, Method, StatusCode, Uri, header},
    response::{IntoResponse, Response},
    routing::{any, get, post},
};
use futures_util::{SinkExt, StreamExt};
use rust_embed::RustEmbed;
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    sync::{Arc, Mutex},
    time::Duration,
};
use tokio_tungstenite::tungstenite::{Message as RemoteMessage, client::IntoClientRequest};

#[derive(RustEmbed)]
#[folder = "ui-dist/"]
struct Frontend;
pub struct LocalWeb {
    pub service: Arc<DesktopService>,
    pub remote: Arc<RemoteClient>,
    pub tunnel: Arc<Tunnel>,
    config: Config,
    origin: String,
    cookie_name: String,
    session: String,
    bootstrap: Mutex<Option<String>>,
    bootstrap_started: std::time::Instant,
    pub mcp_listening: std::sync::atomic::AtomicBool,
    pub mcp_error: Mutex<Option<String>>,
    connections: Mutex<Value>,
    downloads: crate::download_worker::DownloadWorker,
    preferences: Mutex<crate::preferences::PreferenceStore>,
}
pub struct RunningWeb {
    pub state: Arc<LocalWeb>,
    pub url: String,
    pub bootstrap_url: String,
}
impl LocalWeb {
    pub async fn start(config: Config) -> Result<RunningWeb> {
        #[cfg(not(test))]
        let credential =
            crate::secure_store::load(&crate::config::data_dir().join("device-credential")).ok();
        #[cfg(test)]
        let credential = None;
        Self::start_with_credential(config, credential).await
    }
    async fn start_with_credential(
        config: Config,
        credential: Option<String>,
    ) -> Result<RunningWeb> {
        let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0)).await?;
        let origin = format!("http://{}", listener.local_addr()?);
        let secret = format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        );
        #[allow(unused_mut)]
        let mut bridge_token = format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        );
        #[cfg(not(test))]
        {
            let token_path = crate::config::data_dir().join("bridge-token");
            if let Ok(existing) = std::fs::read_to_string(&token_path) {
                if existing.trim().len() >= 32 {
                    bridge_token = existing.trim().into();
                }
            } else {
                std::fs::write(token_path, &bridge_token)?;
            }
        }
        let service = DesktopService::new(config.clone(), bridge_token);
        let remote = service.remote.clone();
        if let Some(credential) = credential {
            remote.set_trusted(credential);
            // Restore only an already remembered device, before the frontend's
            // first auth probe. Offline/revoked devices fall back to normal login.
            let restored = tokio::time::timeout(
                Duration::from_secs(7),
                remote.api(
                    &config,
                    "POST",
                    "/api/quick-login/login",
                    Some(json!({})),
                    false,
                ),
            )
            .await;
            if !matches!(restored, Ok(Ok(_))) {
                remote.logout();
            }
        }
        let state = Arc::new(Self {
            service,
            remote,
            tunnel: Tunnel::new(),
            config,
            origin: origin.clone(),
            cookie_name: format!("dp_session_{}", listener.local_addr()?.port()),
            session: uuid::Uuid::new_v4().simple().to_string(),
            bootstrap: Mutex::new(Some(secret.clone())),
            bootstrap_started: std::time::Instant::now(),
            mcp_listening: std::sync::atomic::AtomicBool::new(false),
            mcp_error: Mutex::new(None),
            connections: Mutex::new(json!({})),
            downloads:crate::download_worker::DownloadWorker::default(),
            preferences: Mutex::new(crate::preferences::PreferenceStore::new(
                &crate::config::data_dir(),
            )),
        });
        let router = Self::router(state.clone());
        tokio::spawn(async move {
            if let Err(error) = axum::serve(listener, router).await {
                eprintln!("Local UI host failed: {error}");
            }
        });
        Ok(RunningWeb {
            state,
            url: origin.clone(),
            bootstrap_url: format!("{origin}/desktop/bootstrap?secret={secret}"),
        })
    }
    fn router(state: Arc<Self>) -> Router {
        Router::new()
            .route("/desktop/bootstrap", get(bootstrap))
            .route("/desktop/status", get(status))
            .route("/desktop/connect", post(connect_account))
            .route(
                "/desktop/preferences",
                get(preferences_get).post(preferences_update),
            )
            .route("/desktop/jobs", get(list_jobs).post(start_job))
            .route("/desktop/jobs/{id}", get(job_status))
            .route("/desktop/jobs/{id}/events", get(job_events))
            .route("/desktop/jobs/{id}/cancel", post(cancel_job))
            .route("/desktop/tools", post(local_tool))
            .route("/desktop/choose-workspace", post(choose_workspace))
            .route("/desktop/choose-export", post(choose_export))
            .route("/desktop/save-export", post(save_export))
            .route("/desktop/import-source", post(import_source))
            .route("/desktop/bridge/connect", post(bridge_connect))
            .route("/desktop/bridge/disconnect", post(bridge_disconnect))
            .route("/ws", get(websocket))
            .route("/api", any(proxy))
            .route("/api/{*path}", any(proxy))
            .route("/research/api/{*path}", any(proxy))
            .route("/research/dify/{*path}", any(proxy))
            .route("/research/reader/{*path}", any(proxy))
            .route("/files/{*path}", any(proxy))
            .fallback(static_file)
            .layer(axum::extract::DefaultBodyLimit::max(128 * 1024 * 1024))
            .with_state(state)
    }
    fn host_ok(&self, headers: &HeaderMap) -> bool {
        headers.get(header::HOST).and_then(|h| h.to_str().ok())
            == self.origin.strip_prefix("http://")
    }
    fn origin_ok(&self, headers: &HeaderMap, method: &Method) -> bool {
        if !self.host_ok(headers) {
            return false;
        }
        if let Some(origin) = headers.get(header::ORIGIN) {
            return origin.to_str().ok() == Some(self.origin.as_str());
        }
        // Same-origin browser GET fetches omit Origin. Verify their actual Referer.
        if *method == Method::GET || *method == Method::HEAD {
            return headers
                .get(header::REFERER)
                .and_then(|h| h.to_str().ok())
                .and_then(|s| url::Url::parse(s).ok())
                .is_some_and(|u| u.origin().ascii_serialization() == self.origin);
        }
        false
    }
    fn authenticated(&self, headers: &HeaderMap) -> bool {
        let expected = format!("{}={}", self.cookie_name, self.session);
        headers
            .get(header::COOKIE)
            .and_then(|h| h.to_str().ok())
            .is_some_and(|cookie| cookie.split(';').any(|part| part.trim() == expected))
    }
    fn check(&self, headers: &HeaderMap, method: &Method) -> std::result::Result<(), Response> {
        if !self.origin_ok(headers, method) {
            return Err(error(StatusCode::FORBIDDEN, "Local origin required"));
        }
        if !self.authenticated(headers) {
            return Err(error(StatusCode::UNAUTHORIZED, "Local session required"));
        }
        Ok(())
    }
    pub async fn close(&self) {
        self.tunnel.disconnect().await;
        self.service.browser.close().await;
    }
}
fn error(status: StatusCode, message: &str) -> Response {
    (status, Json(json!({"error":message}))).into_response()
}
fn result<T: serde::Serialize>(value: Result<T>) -> Response {
    match value {
        Ok(value) => Json(value).into_response(),
        Err(error) => (
            StatusCode::BAD_REQUEST,
            Json(json!({"error":format!("{error:#}")})),
        )
            .into_response(),
    }
}
#[derive(Deserialize)]
struct Bootstrap {
    secret: String,
}
async fn bootstrap(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Query(query): Query<Bootstrap>,
) -> Response {
    if !state.host_ok(&headers)
        || headers
            .get(header::ORIGIN)
            .is_some_and(|h| h.to_str().ok() != Some(state.origin.as_str()))
    {
        return error(StatusCode::FORBIDDEN, "Local host required");
    }
    let mut secret = state.bootstrap.lock().unwrap();
    if state.bootstrap_started.elapsed() > Duration::from_secs(300)
        || secret.as_deref() != Some(query.secret.as_str())
    {
        return error(StatusCode::UNAUTHORIZED, "Bootstrap expired");
    }
    *secret = None;
    let mut response = StatusCode::SEE_OTHER.into_response();
    response
        .headers_mut()
        .insert(header::LOCATION, "/".parse().unwrap());
    response.headers_mut().insert(
        header::SET_COOKIE,
        format!(
            "{}={}; HttpOnly; SameSite=Strict; Path=/",
            state.cookie_name, state.session
        )
        .parse()
        .unwrap(),
    );
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, "no-store".parse().unwrap());
    response
        .headers_mut()
        .insert("referrer-policy", "no-referrer".parse().unwrap());
    response
}
async fn status(State(state): State<Arc<LocalWeb>>, headers: HeaderMap) -> Response {
    if let Err(e) = state.check(&headers, &Method::GET) {
        return e;
    }
    let workspace = state.service.config.read().unwrap().workspace.clone();
    let engines = crate::jobs::JobManager::engines().await;
    let bridge = state.tunnel.status().await;
    Json(json!({"version":env!("CARGO_PKG_VERSION"),"engines":engines,"jobs":state.service.jobs.list(),"workspace":workspace,"mode":"noninteractive","interactive_approvals":false,"connections":state.connections.lock().unwrap().clone(),"downloads":state.downloads.status(&state.config),"bridge":{"mode":"owner_ssh_compatibility","connected":bridge["connected"],"listening":state.mcp_listening.load(std::sync::atomic::Ordering::Relaxed),"port":state.config.bridge_port,"error":state.mcp_error.lock().unwrap().clone()}})).into_response()
}
async fn list_jobs(State(state):State<Arc<LocalWeb>>,headers:HeaderMap)->Response {
    if let Err(e)=state.check(&headers,&Method::GET){return e;}
    Json(json!({"jobs":state.service.jobs.list()})).into_response()
}
async fn preferences_get(State(state): State<Arc<LocalWeb>>, headers: HeaderMap) -> Response {
    if let Err(e) = state.check(&headers, &Method::GET) {
        return e;
    }
    result(state.preferences.lock().unwrap().load())
}
async fn preferences_update(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Json(patch): Json<crate::preferences::Preferences>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    result(state.preferences.lock().unwrap().update(patch))
}
async fn start_job(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Json(request): Json<JobRequest>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    result(state.service.jobs.start(request).await)
}
async fn job_status(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::GET) {
        return e;
    }
    result(state.service.jobs.status(&id))
}
#[derive(Deserialize)]
struct Cursor {
    #[serde(default)]
    after: u64,
}
async fn job_events(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Query(cursor): Query<Cursor>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::GET) {
        return e;
    }
    result(state.service.jobs.events(&id, cursor.after))
}
async fn cancel_job(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    result(state.service.jobs.cancel(&id))
}
async fn local_tool(
    State(state): State<Arc<LocalWeb>>,
    headers: HeaderMap,
    Json(value): Json<Value>,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    result(
        state
            .service
            .call(
                value["name"].as_str().unwrap_or(""),
                value["arguments"].clone(),
            )
            .await,
    )
}
async fn choose_workspace(State(state): State<Arc<LocalWeb>>, headers: HeaderMap) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    if let Some(folder) = rfd::AsyncFileDialog::new().pick_folder().await {
        let mut config = state.service.config.write().unwrap();
        config.workspace = folder.path().into();
        return result(config.save().map(|_| json!({"workspace":config.workspace})));
    }
    Json(json!({"cancelled":true})).into_response()
}
async fn choose_export(State(state):State<Arc<LocalWeb>>,headers:HeaderMap,Json(value):Json<Value>)->Response {
    if let Err(e)=state.check(&headers,&Method::POST){return e;}
    let name=value["filename"].as_str().unwrap_or("稿件.docx");
    let extension=std::path::Path::new(name).extension().and_then(|v|v.to_str()).unwrap_or("docx");
    let mut dialog=rfd::AsyncFileDialog::new().set_file_name(name).add_filter(extension.to_uppercase(),&[extension]);
    if let Some(path)=value["path"].as_str().filter(|v|!v.is_empty()) {
        let path=std::path::Path::new(path);
        if let Some(parent)=path.parent().filter(|p|p.is_dir()){dialog=dialog.set_directory(parent);}
    }
    if let Some(file)=dialog.save_file().await {return Json(json!({"path":file.path().to_string_lossy()})).into_response();}
    Json(json!({"cancelled":true})).into_response()
}
fn export_url(config:&Config,path:&str)->Result<String> {
    let uri:Uri=path.parse()?;
    anyhow::ensure!(uri.scheme().is_none()&&uri.authority().is_none()&&uri.path().starts_with("/research/api/projects/")&&uri.path().ends_with("/download")&&!path.contains('\\'),"导出文件地址无效");
    Ok(format!("{}{path}",config.server_url.trim_end_matches('/')))
}
async fn save_export(State(state):State<Arc<LocalWeb>>,headers:HeaderMap,Json(value):Json<Value>)->Response {
    if let Err(e)=state.check(&headers,&Method::POST){return e;}
    result(async {
        state.remote.authenticate(&state.config).await?;
        let source=export_url(&state.config,value["url"].as_str().context("导出文件地址不存在")?)?;
        let destination=std::path::PathBuf::from(value["path"].as_str().context("请填写保存位置")?);
        anyhow::ensure!(destination.is_absolute()&&destination.file_name().is_some(),"请填写完整文件路径");
        let extension=destination.extension().and_then(|v|v.to_str()).unwrap_or("").to_ascii_lowercase();
        anyhow::ensure!(["docx","pdf","pptx","zip","tex"].contains(&extension.as_str()),"保存文件扩展名无效");
        let response=state.remote.client.get(source).header("Cookie",state.remote.cookie_header()).header("Origin",state.config.server_url.trim_end_matches('/')).timeout(Duration::from_secs(180)).send().await?.error_for_status()?;
        let data=response.bytes().await?;anyhow::ensure!(!data.is_empty(),"导出文件为空");
        if let Some(parent)=destination.parent(){tokio::fs::create_dir_all(parent).await?;}
        tokio::fs::write(&destination,&data).await?;
        Ok(json!({"saved":true,"path":destination.to_string_lossy(),"bytes":data.len()}))
    }.await)
}
async fn import_source(State(state):State<Arc<LocalWeb>>,headers:HeaderMap,Json(value):Json<Value>)->Response {
    if let Err(e)=state.check(&headers,&Method::POST){return e;}
    result((|| -> anyhow::Result<Value> {
        let source=value["source"].as_str().context("请填写来源文件夹")?;
        let directory=std::path::PathBuf::from(source).canonicalize().context("来源文件夹不存在，请检查路径")?;
        anyhow::ensure!(directory.is_dir(),"请选择文件夹作为导入来源");
        let mut config=state.service.config.write().unwrap();
        let mut updated=config.clone();updated.workspace=directory;updated.save()?;
        *config=updated;
        Ok(json!({"workspace":config.workspace,"authorized":true}))
    })())
}
async fn bridge_connect(State(state): State<Arc<LocalWeb>>, headers: HeaderMap) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    if !state
        .mcp_listening
        .load(std::sync::atomic::Ordering::Relaxed)
    {
        return error(
            StatusCode::CONFLICT,
            "Local MCP bridge port is unavailable; close the other instance and restart",
        );
    }
    result(state.tunnel.connect(&state.service).await)
}
async fn connect_account(State(state):State<Arc<LocalWeb>>,headers:HeaderMap)->Response {
    if let Err(e)=state.check(&headers,&Method::POST){return e;}
    let config=state.config.clone();
    let profile=match state.remote.get(&config,"/api/auth/profile").await {Ok(value)=>value,Err(_)=>return error(StatusCode::UNAUTHORIZED,"请重新登录账户")};
    let models=state.remote.refresh_models(&config).await;
    let mut value=json!({"authenticated":true,"models_loaded":models.is_ok(),"bridge":{"connected":false}});
    if profile["role"]=="admin"&&state.mcp_listening.load(std::sync::atomic::Ordering::Relaxed){
        value["bridge"]=match state.tunnel.connect(&state.service).await {Ok(status)=>status,Err(e)=>json!({"connected":false,"error":e.to_string()})};
    }
    if profile["role"]=="admin" && !config.cluster_host.is_empty() {
        let mut command=tokio::process::Command::new("ssh");
        #[cfg(windows)]
        command.creation_flags(0x08000000);
        command.args(["-o","BatchMode=yes","-o","ConnectTimeout=8","-T",&config.cluster_host,"printf DEEP_PARTNER_CLUSTER_READY; command -v squeue >/dev/null && printf _SLURM"]).kill_on_drop(true);
        value["cluster"]=match tokio::time::timeout(Duration::from_secs(12),command.output()).await {
            Ok(Ok(output)) if output.status.success() && output.stdout.starts_with(b"DEEP_PARTNER_CLUSTER_READY")=>json!({"configured":true,"connected":true,"host":config.cluster_host,"scheduler":String::from_utf8_lossy(&output.stdout).contains("_SLURM")}),
            _=>json!({"configured":true,"connected":false,"host":config.cluster_host,"error":"集群暂未连通，联网后将自动重试"}),
        };
    }
    value["downloads"]=match state.downloads.ensure(&config,profile["id"].as_str().unwrap_or("")) {Ok(status)=>status,Err(error)=>json!({"configured":true,"running":false,"error":error.to_string()})};
    *state.connections.lock().unwrap()=value.clone();
    Json(value).into_response()
}
async fn bridge_disconnect(State(state): State<Arc<LocalWeb>>, headers: HeaderMap) -> Response {
    if let Err(e) = state.check(&headers, &Method::POST) {
        return e;
    }
    state.tunnel.disconnect().await;
    Json(json!({"disconnected":true})).into_response()
}
async fn proxy(
    State(state): State<Arc<LocalWeb>>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Body,
) -> Response {
    if let Err(e) = state.check(&headers, &method) {
        return e;
    }
    match proxy_inner(&state, method, uri, headers, body).await {
        Ok(r) => r,
        Err(_) => error(StatusCode::BAD_GATEWAY, "Upstream request failed"),
    }
}
async fn proxy_inner(
    state: &LocalWeb,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
    body: Body,
) -> Result<Response> {
    let path = uri
        .path_and_query()
        .context("Request path missing")?
        .as_str();
    let remote_base = state.config.server_url.trim_end_matches('/');
    let mut request = state
        .remote
        .client
        .request(method, format!("{remote_base}{path}"))
        .timeout(Duration::from_secs(600));
    for (name, value) in &headers {
        if !matches!(
            name.as_str(),
            "host"
                | "cookie"
                | "origin"
                | "referer"
                | "connection"
                | "content-length"
                | "transfer-encoding"
                | "accept-encoding"
        ) && !name.as_str().starts_with("sec-")
        {
            request = request.header(name, value);
        }
    }
    request = request
        .header("Origin", remote_base)
        .header("Cookie", state.remote.cookie_header());
    let is_project_import = uri.path().starts_with("/research/api/projects/")
        && uri.path().ends_with("/import");
    let body_limit = if is_project_import { 301 } else { 128 } * 1024 * 1024;
    let body = to_bytes(body, body_limit).await?;
    let upstream = request.body(body).send().await?;
    state.remote.absorb_cookies(upstream.headers());
    if uri.path() == "/api/auth/logout" && upstream.status().is_success() {
        state.remote.logout();
    }
    if let Some(trusted) = state.remote.trusted() {
        let _ = crate::secure_store::save(
            &crate::config::data_dir().join("device-credential"),
            &trusted,
        );
    }
    let mut response = Response::builder().status(upstream.status());
    for (name, value) in upstream.headers() {
        if matches!(
            name.as_str(),
            "set-cookie"
                | "connection"
                | "transfer-encoding"
                | "content-length"
                | "access-control-allow-origin"
                | "access-control-allow-credentials"
        ) {
            continue;
        }
        if name == header::LOCATION {
            let location = value.to_str()?;
            if let Some(local) = location.strip_prefix(remote_base) {
                response = response.header(header::LOCATION, format!("{}{local}", state.origin));
            } else {
                response = response.header(name, value);
            }
        } else {
            response = response.header(name, value);
        }
    }
    response = response.header("referrer-policy", "same-origin");
    Ok(response.body(Body::from_stream(upstream.bytes_stream()))?)
}
async fn websocket(
    State(state): State<Arc<LocalWeb>>,
    uri:Uri,
    headers: HeaderMap,
    ws: WebSocketUpgrade,
) -> Response {
    if let Err(e) = state.check(&headers, &Method::GET) {
        return e;
    }
    ws.max_message_size(64 * 1024 * 1024)
        .on_upgrade(move |socket| async move {
            let _ = forward_ws(state, socket,uri.query()).await;
        })
        .into_response()
}
async fn forward_ws(state: Arc<LocalWeb>, socket: WebSocket,query:Option<&str>) -> Result<()> {
    let mut address = url::Url::parse(&state.config.server_url)?;
    address
        .set_scheme(if address.scheme() == "https" {
            "wss"
        } else {
            "ws"
        })
        .map_err(|_| anyhow::anyhow!("Invalid WS URL"))?;
    address.set_path("/ws");
    address.set_query(query);
    let mut request = address.as_str().into_client_request()?;
    request
        .headers_mut()
        .insert("Cookie", state.remote.cookie_header().parse()?);
    request.headers_mut().insert(
        "Origin",
        state.config.server_url.trim_end_matches('/').parse()?,
    );
    let remote = tokio::time::timeout(
        Duration::from_secs(15),
        crate::network::connect(request),
    )
    .await??;
    let (mut local_send, mut local_recv) = socket.split();
    let (mut remote_send, mut remote_recv) = remote.split();
    let to_remote = async {
        while let Some(Ok(message)) = local_recv.next().await {
            let message = match message {
                Message::Text(t) => RemoteMessage::Text(t.to_string().into()),
                Message::Binary(b) => RemoteMessage::Binary(b),
                Message::Ping(b) => RemoteMessage::Ping(b),
                Message::Pong(b) => RemoteMessage::Pong(b),
                Message::Close(_) => RemoteMessage::Close(None),
            };
            if remote_send.send(message).await.is_err() {
                break;
            }
        }
    };
    let to_local = async {
        while let Some(Ok(message)) = remote_recv.next().await {
            let message = match message {
                RemoteMessage::Text(t) => Message::Text(t.to_string().into()),
                RemoteMessage::Binary(b) => Message::Binary(b),
                RemoteMessage::Ping(b) => Message::Ping(b),
                RemoteMessage::Pong(b) => Message::Pong(b),
                RemoteMessage::Close(_) => Message::Close(None),
                _ => continue,
            };
            if local_send.send(message).await.is_err() {
                break;
            }
        }
    };
    tokio::select! {_=to_remote=>{},_=to_local=>{}};
    Ok(())
}
async fn static_file(
    State(state): State<Arc<LocalWeb>>,
    method: Method,
    uri: Uri,
    headers: HeaderMap,
) -> Response {
    if !state.host_ok(&headers) || !state.authenticated(&headers) {
        return error(
            StatusCode::UNAUTHORIZED,
            "Open the installed DeepPartner application",
        );
    }
    if method != Method::GET && method != Method::HEAD {
        return StatusCode::METHOD_NOT_ALLOWED.into_response();
    }
    if let Some(origin) = headers.get(header::ORIGIN) {
        if origin.to_str().ok() != Some(state.origin.as_str()) {
            return StatusCode::FORBIDDEN.into_response();
        }
    }
    if uri.path().starts_with("/desktop/") {
        return StatusCode::NOT_FOUND.into_response();
    }
    let path = uri.path().trim_start_matches('/');
    let path = if path.is_empty() { "index.html" } else { path };
    let asset = Frontend::get(path).or_else(|| {
        if !path.rsplit('/').next().unwrap_or("").contains('.') {
            Frontend::get("index.html")
        } else {
            None
        }
    });
    let Some(asset) = asset else {
        return StatusCode::NOT_FOUND.into_response();
    };
    let content_type = if Frontend::get(path).is_some() {
        mime_guess::from_path(path)
            .first_or_octet_stream()
            .to_string()
    } else {
        "text/html".into()
    };
    let mut response = Response::new(if method == Method::HEAD {
        Body::empty()
    } else {
        Body::from(asset.data.into_owned())
    });
    response
        .headers_mut()
        .insert(header::CONTENT_TYPE, content_type.parse().unwrap());
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, "no-cache".parse().unwrap());
    response
        .headers_mut()
        .insert("referrer-policy", "same-origin".parse().unwrap());
    response
        .headers_mut()
        .insert("x-content-type-options", "nosniff".parse().unwrap());
    response.headers_mut().insert("content-security-policy","default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' ws:; media-src 'self' blob: https:; frame-src 'self' blob: https: http:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'".parse().unwrap());
    response
}

#[cfg(test)]
mod tests {
    #[test]
    fn export_location_fetches_only_owned_project_download_routes(){
        let config=crate::config::Config::default();
        assert!(super::export_url(&config,"/research/api/projects/12345678901234567890123456789012/download?area=manuscript&name=paper.pdf").is_ok());
        assert!(super::export_url(&config,"https://example.com/private.pdf").is_err());
        assert!(super::export_url(&config,"/api/auth/profile").is_err());
    }
    use super::*;
    #[tokio::test]
    async fn remembered_device_is_restored_before_initial_auth_probe() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        let attempts = Arc::new(AtomicUsize::new(0));
        let unexpected = Arc::new(AtomicUsize::new(0));
        let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0))
            .await
            .unwrap();
        let config = Config {
            server_url: format!("http://{}", listener.local_addr().unwrap()),
            ..Config::default()
        };
        let login_attempts = attempts.clone();
        let unexpected_requests = unexpected.clone();
        let app = Router::new()
            .route(
                "/api/quick-login/login",
                post(move |headers: HeaderMap, Json(body): Json<Value>| {
                    let attempts = login_attempts.clone();
                    async move {
                        attempts.fetch_add(1, Ordering::SeqCst);
                        assert_eq!(body, json!({}));
                        match headers.get("cookie").and_then(|v| v.to_str().ok()) {
                            Some("__Host-dt_trusted=remembered-test-device") => (
                                [(
                                    "set-cookie",
                                    "dt_token=restored-test-session; HttpOnly; Path=/",
                                )],
                                Json(json!({"ok":true})),
                            )
                                .into_response(),
                            Some("__Host-dt_trusted=slow-test-device") => {
                                tokio::time::sleep(Duration::from_secs(30)).await;
                                Json(json!({"ok":true})).into_response()
                            }
                            _ => (
                                StatusCode::UNAUTHORIZED,
                                Json(json!({"detail":"Device was revoked"})),
                            )
                                .into_response(),
                        }
                    }
                }),
            )
            .route(
                "/api/auth/status",
                get(|headers: HeaderMap| async move {
                    assert!(
                        headers["cookie"]
                            .to_str()
                            .unwrap()
                            .contains("dt_token=restored-test-session")
                    );
                    Json(json!({"authenticated":true}))
                }),
            )
            .fallback(move || {
                let unexpected = unexpected_requests.clone();
                async move {
                    unexpected.fetch_add(1, Ordering::SeqCst);
                    StatusCode::NOT_FOUND
                }
            });
        let server = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        let remembered =
            LocalWeb::start_with_credential(config.clone(), Some("remembered-test-device".into()))
                .await
                .unwrap();
        assert!(
            remembered.state.remote.authenticate(&config).await.is_ok(),
            "Existing remembered device must restore a session before the frontend probes authentication"
        );
        assert_eq!(
            remembered
                .state
                .remote
                .api(&config, "GET", "/api/auth/status", None, true)
                .await
                .unwrap()["authenticated"],
            true
        );
        let fresh = LocalWeb::start_with_credential(config.clone(), None)
            .await
            .unwrap();
        assert!(fresh.state.remote.authenticate(&config).await.is_err());
        assert_eq!(
            attempts.load(Ordering::SeqCst),
            1,
            "A new profile must not create trust or attempt remembered login"
        );
        let revoked =
            LocalWeb::start_with_credential(config.clone(), Some("revoked-test-device".into()))
                .await
                .unwrap();
        assert!(revoked.state.remote.authenticate(&config).await.is_err());
        let slow = tokio::time::timeout(
            Duration::from_secs(9),
            LocalWeb::start_with_credential(config.clone(), Some("slow-test-device".into())),
        )
        .await
        .expect("Remembered login must have a bounded offline fallback")
        .unwrap();
        assert!(slow.state.remote.authenticate(&config).await.is_err());
        assert_eq!(attempts.load(Ordering::SeqCst), 3);
        assert_eq!(
            unexpected.load(Ordering::SeqCst),
            0,
            "Startup must never create a new persistent trust record"
        );
        server.abort();
    }
    #[tokio::test]
    async fn bootstrap_cookie_origin_and_replay() {
        let running = LocalWeb::start(Config::default()).await.unwrap();
        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .unwrap();
        assert_eq!(
            client
                .get(format!("{}/desktop/status", running.url))
                .header("Origin", &running.url)
                .send()
                .await
                .unwrap()
                .status(),
            StatusCode::UNAUTHORIZED
        );
        let reply = client.get(&running.bootstrap_url).send().await.unwrap();
        assert_eq!(reply.status(), StatusCode::SEE_OTHER);
        let cookie = reply.headers()["set-cookie"]
            .to_str()
            .unwrap()
            .split(';')
            .next()
            .unwrap()
            .to_string();
        assert_eq!(
            client
                .get(&running.bootstrap_url)
                .send()
                .await
                .unwrap()
                .status(),
            StatusCode::UNAUTHORIZED
        );
        assert_eq!(
            client
                .get(format!("{}/desktop/jobs/not-id", running.url))
                .header("Origin", "https://evil.invalid")
                .header("Cookie", &cookie)
                .send()
                .await
                .unwrap()
                .status(),
            StatusCode::FORBIDDEN
        );
        assert_eq!(
            client
                .get(format!("{}/desktop/jobs/not-id", running.url))
                .header("Referer", format!("{}/", running.url))
                .header("Cookie", &cookie)
                .send()
                .await
                .unwrap()
                .status(),
            StatusCode::BAD_REQUEST
        );
    }

    #[tokio::test]
    async fn proxy_keeps_remote_cookie_private_and_forwards_authenticated_ws() {
        let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0))
            .await
            .unwrap();
        let remote_url = format!("http://{}", listener.local_addr().unwrap());
        let expected_origin = remote_url.clone();
        let app = Router::new()
            .route(
                "/api/auth/login",
                post(|| async {
                    (
                        [(
                            "set-cookie",
                            "dt_token=remote-private-test; HttpOnly; Path=/",
                        )],
                        Json(json!({"ok":true})),
                    )
                }),
            )
            .route(
                "/research/api/check",
                get(move |headers: HeaderMap| {
                    let expected = expected_origin.clone();
                    async move {
                        assert_eq!(headers["cookie"], "dt_token=remote-private-test");
                        assert_eq!(headers["origin"], expected);
                        Json(json!({"ok":true}))
                    }
                }),
            )
            .route(
                "/api/redirect",
                get(|| async {
                    (
                        StatusCode::FOUND,
                        [("location", "http://127.0.0.1:1/never-follow")],
                    )
                }),
            )
            .route(
                "/research/api/download",
                get(|| async {
                    (
                        [
                            ("content-type", "text/plain; charset=utf-8"),
                            (
                                "content-disposition",
                                "attachment; filename=\"native-check.txt\"",
                            ),
                        ],
                        "DEEP_PARTNER_DOWNLOAD_OK",
                    )
                }),
            )
            .route(
                "/ws",
                get(|uri:Uri, headers: HeaderMap, ws: WebSocketUpgrade| async move {
                    assert_eq!(headers["cookie"], "dt_token=remote-private-test");
                    assert_eq!(uri.query(),Some("dt_workspace=ws-project-scope"));
                    ws.on_upgrade(|mut socket| async move {
                        if let Some(Ok(message)) = socket.recv().await {
                            let _ = socket.send(message).await;
                        }
                    })
                }),
            );
        let remote_task = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        let config = Config {
            server_url: remote_url,
            ..Config::default()
        };
        let running = LocalWeb::start(config).await.unwrap();
        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .unwrap();
        let response = client.get(&running.bootstrap_url).send().await.unwrap();
        let cookie = response.headers()["set-cookie"]
            .to_str()
            .unwrap()
            .split(';')
            .next()
            .unwrap()
            .to_string();
        let response = client
            .post(format!("{}/api/auth/login", running.url))
            .header("Origin", &running.url)
            .header("Cookie", &cookie)
            .json(&json!({}))
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert!(response.headers().get("set-cookie").is_none());
        let response = client
            .get(format!("{}/research/api/check", running.url))
            .header("Referer", format!("{}/", running.url))
            .header("Cookie", &cookie)
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let response = client
            .get(format!("{}/api/redirect", running.url))
            .header("Origin", &running.url)
            .header("Cookie", &cookie)
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FOUND);
        let response = client
            .get(format!("{}/research/api/download", running.url))
            .header("Referer", format!("{}/", running.url))
            .header("Cookie", &cookie)
            .send()
            .await
            .unwrap();
        assert_eq!(
            response.headers()["content-disposition"],
            "attachment; filename=\"native-check.txt\""
        );
        assert_eq!(response.text().await.unwrap(), "DEEP_PARTNER_DOWNLOAD_OK");
        let mut request = format!("{}/ws?dt_workspace=ws-project-scope", running.url.replace("http:", "ws:"))
            .into_client_request()
            .unwrap();
        request
            .headers_mut()
            .insert("Origin", running.url.parse().unwrap());
        request
            .headers_mut()
            .insert("Cookie", cookie.parse().unwrap());
        let (mut socket, _) = tokio_tungstenite::connect_async(request).await.unwrap();
        socket
            .send(RemoteMessage::Text("native-ws-echo".into()))
            .await
            .unwrap();
        let message = tokio::time::timeout(Duration::from_secs(5), socket.next())
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        assert_eq!(message.to_text().unwrap(), "native-ws-echo");
        remote_task.abort();
    }
}
