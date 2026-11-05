mod forms;
mod layout;
mod theme;
use theme::Icon;
pub mod pages;

use crate::{
    config::{Config, data_dir},
    remote::{EventSink, RemoteClient},
    schema,
    service::DesktopService,
    tunnel::Tunnel,
};
use egui::{Color32, Frame, Margin, RichText, Stroke, Ui, Vec2};
use egui_commonmark::{CommonMarkCache, CommonMarkViewer};
use forms::ActionForm;
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    future::Future,
    sync::{Arc, mpsc},
    time::{Duration, Instant},
};

enum Event {
    Result(String, Result<Value, String>),
    Stream(Value),
}
#[derive(Default)]
struct Login {
    tab: usize,
    show_password: bool,
    username: String,
    password: String,
    confirm: String,
    email: String,
    reason: String,
    device: String,
    pair: Value,
    last_poll: Option<Instant>,
}
#[derive(Clone)]
struct Message {
    role: String,
    text: String,
}

pub struct DesktopApp {
    config: Config,
    service: Arc<DesktopService>,
    remote: Arc<RemoteClient>,
    tunnel: Arc<Tunnel>,
    runtime: tokio::runtime::Handle,
    tx: mpsc::Sender<Event>,
    rx: mpsc::Receiver<Event>,
    ctx: egui::Context,
    auth: bool,
    user: Value,
    login: Login,
    notice: String,
    error: String,
    inflight: BTreeSet<String>,
    data: BTreeMap<String, Value>,
    page: String,
    category: usize,
    sidebar_collapsed: bool,
    activities: bool,
    nav_filter: String,
    global_query: String,
    applied_theme: String,
    chat_width: f32,
    search: String,
    selected: Value,
    detail: Value,
    detail_path: String,
    form: Option<ActionForm>,
    operations: bool,
    operation_search: String,
    md: CommonMarkCache,
    draft: String,
    messages: Vec<Message>,
    message_heights: BTreeMap<usize, f32>,
    session: String,
    mode: String,
    mode_config: Value,
    streaming: bool,
    waiting: Value,
    trace: Vec<String>,
    workspace: String,
    selected_kb: BTreeSet<String>,
    selected_skills: BTreeSet<String>,
    selected_mcp: BTreeSet<String>,
    selected_tools: BTreeSet<String>,
    persona: String,
    attachment_paths: Vec<std::path::PathBuf>,
    writer_title: String,
    writer_text: String,
    writer_dirty: bool,
    preview: bool,
    reader_locator: String,
    capture: Option<std::path::PathBuf>,
    capture_frames: u32,
    started: Instant,
}

pub fn style(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();
    for (name, bytes) in [
        ("Lora", include_bytes!("../../assets/Lora.ttf").as_slice()),
        (
            "Lora Italic",
            include_bytes!("../../assets/Lora-Italic.ttf").as_slice(),
        ),
    ] {
        fonts
            .font_data
            .insert(name.into(), egui::FontData::from_static(bytes).into());
        fonts
            .families
            .insert(egui::FontFamily::Name(name.into()), vec![name.into()]);
    }
    fonts.font_data.insert(
        "Geist".into(),
        egui::FontData::from_static(include_bytes!("../../assets/Geist-Regular.ttf")).into(),
    );
    fonts
        .families
        .entry(egui::FontFamily::Proportional)
        .or_default()
        .insert(0, "Geist".into());
    if let Ok(bytes) = std::fs::read("C:/Windows/Fonts/msyh.ttc") {
        fonts.font_data.insert(
            "Microsoft YaHei".into(),
            egui::FontData::from_owned(bytes).into(),
        );
        fonts
            .families
            .entry(egui::FontFamily::Proportional)
            .or_default()
            .push("Microsoft YaHei".into());
        fonts
            .families
            .entry(egui::FontFamily::Monospace)
            .or_default()
            .push("Microsoft YaHei".into());
    }
    if let Ok(bytes) = std::fs::read("C:/Windows/Fonts/simsun.ttc") {
        fonts
            .font_data
            .insert("Greeting".into(), egui::FontData::from_owned(bytes).into());
        fonts.families.insert(
            egui::FontFamily::Name("Greeting".into()),
            vec!["Greeting".into(), "Geist".into()],
        );
    }
    ctx.set_fonts(fonts);
    egui_extras::install_image_loaders(ctx);
    theme::apply(ctx, "dark", true);
}

impl DesktopApp {
    pub fn new(
        ctx: egui::Context,
        config: Config,
        service: Arc<DesktopService>,
        tunnel: Arc<Tunnel>,
        runtime: tokio::runtime::Handle,
    ) -> Self {
        style(&ctx);
        let (tx, rx) = mpsc::channel();
        let remote = RemoteClient::new();
        #[allow(unused_mut)]
        let mut app = Self {
            config,
            service,
            remote,
            tunnel,
            runtime,
            tx,
            rx,
            ctx,
            auth: false,
            user: Value::Null,
            login: Login {
                device: std::env::var("COMPUTERNAME").unwrap_or_else(|_| "Windows 电脑".into()),
                ..Default::default()
            },
            notice: String::new(),
            error: String::new(),
            inflight: BTreeSet::new(),
            data: BTreeMap::new(),
            page: "chat".into(),
            category: 0,
            sidebar_collapsed: false,
            activities: false,
            nav_filter: String::new(),
            global_query: String::new(),
            applied_theme: String::new(),
            chat_width: 0.,
            search: String::new(),
            selected: Value::Null,
            detail: Value::Null,
            detail_path: String::new(),
            form: None,
            operations: false,
            operation_search: String::new(),
            md: CommonMarkCache::default(),
            draft: String::new(),
            messages: Vec::new(),
            message_heights: BTreeMap::new(),
            session: String::new(),
            mode: "chat".into(),
            mode_config: json!({}),
            streaming: false,
            waiting: Value::Null,
            trace: Vec::new(),
            workspace: String::new(),
            selected_kb: BTreeSet::new(),
            selected_skills: BTreeSet::new(),
            selected_mcp: BTreeSet::new(),
            selected_tools: BTreeSet::new(),
            persona: String::new(),
            attachment_paths: Vec::new(),
            writer_title: String::new(),
            writer_text: String::new(),
            writer_dirty: false,
            preview: false,
            reader_locator: String::new(),
            capture: None,
            capture_frames: 0,
            started: Instant::now(),
        };
        #[cfg(not(test))]
        if let Ok(credential) = crate::secure_store::load(&data_dir().join("device-credential")) {
            app.remote.set_trusted(credential);
            app.request(
                "auth:trusted",
                "POST",
                "/api/quick-login/login",
                Some(json!({})),
                false,
            );
        }
        app
    }
    fn job<F>(&mut self, key: &str, future: F)
    where
        F: Future<Output = anyhow::Result<Value>> + Send + 'static,
    {
        if !self.inflight.insert(key.into()) {
            return;
        }
        let tx = self.tx.clone();
        let ctx = self.ctx.clone();
        let key = key.to_owned();
        self.runtime.spawn(async move {
            let result = future.await.map_err(|e| format!("{e:#}"));
            let _ = tx.send(Event::Result(key, result));
            ctx.request_repaint();
        });
    }
    fn request(&mut self, key: &str, method: &str, path: &str, body: Option<Value>, auth: bool) {
        let remote = self.remote.clone();
        let config = self.config.clone();
        let method = method.to_owned();
        let path = path.to_owned();
        self.job(key, async move {
            remote.api(&config, &method, &path, body, auth).await
        });
    }
    fn get(&mut self, key: &str, path: &str) {
        self.request(key, "GET", path, None, true);
    }
    fn bootstrap(&mut self) {
        for (key, path) in [
            ("user", "/api/auth/status"),
            ("capabilities", "/api/capabilities/registered"),
            ("workspaces", "/api/settings/workspace/registrations"),
            ("skills", "/api/skills/list"),
            ("personas", "/api/personas"),
            ("mcps", "/api/space/mcp/servers"),
            ("tools", "/api/tools"),
        ] {
            self.get(key, path);
        }
        let remote = self.remote.clone();
        let config = self.config.clone();
        self.job("bootstrap", async move { remote.bootstrap(&config).await });
        self.load_page();
    }
    fn load_page(&mut self) {
        let p = pages::page(&self.page);
        if !p.list.is_empty() {
            self.get(&format!("page:{}", p.id), p.list);
        }
    }
    fn navigate(&mut self, page: &str) {
        self.page = page.into();
        self.category = layout::category_for(page);
        self.data.remove("reader");
        self.search.clear();
        self.selected = Value::Null;
        self.detail = Value::Null;
        self.detail_path.clear();
        self.writer_dirty = false;
        self.operations = false;
        self.error.clear();
        self.load_page();
    }
    fn pump(&mut self) {
        while let Ok(event) = self.rx.try_recv() {
            match event {
                Event::Result(key, result) => {
                    self.inflight.remove(&key);
                    match result {
                        Err(e) => {
                            if key == "auth:trusted" {
                                self.remote.logout();
                            } else {
                                self.error = e;
                            }
                            if key == "chat:send" {
                                self.streaming = false;
                            }
                        }
                        Ok(value) => {
                            match key.as_str() {
                                "auth:login" | "auth:trusted" | "auth:complete" => {
                                    self.auth = true;
                                    self.window_size(true, false);
                                    self.user = value.clone();
                                    self.login.password.clear();
                                    self.login.confirm.clear();
                                    self.error.clear();
                                    self.notice.clear();
                                    self.bootstrap();
                                    if let Some(token) = self.remote.trusted() {
                                        if let Err(e) = crate::secure_store::save(
                                            &data_dir().join("device-credential"),
                                            &token,
                                        ) {
                                            self.error = e.to_string();
                                        }
                                    }
                                }
                                "auth:register" => {
                                    self.notice = value["message"]
                                        .as_str()
                                        .unwrap_or("注册申请已提交，请等待管理员审核。")
                                        .into();
                                    self.login.password.clear();
                                    self.login.confirm.clear();
                                    self.login.tab = 0;
                                }
                                "auth:pair" | "auth:status" => {
                                    self.login.pair = value.clone();
                                    if value["status"] == "approved" {
                                        self.request(
                                            "auth:complete",
                                            "POST",
                                            "/api/quick-login/complete",
                                            Some(json!({})),
                                            false,
                                        );
                                    }
                                }
                                "bootstrap" => {
                                    for name in ["models", "sessions", "knowledge"] {
                                        self.data.insert(name.into(), value[name].clone());
                                    }
                                }
                                "user" => {
                                    self.user = value.clone();
                                    if self.user["is_admin"] == true || self.user["role"] == "admin"
                                    {
                                        let service = self.service.clone();
                                        let tunnel = self.tunnel.clone();
                                        self.job("tunnel", async move {
                                            tunnel.connect(&service).await
                                        });
                                    }
                                }
                                "detail" => {
                                    self.detail = value.clone();
                                    self.writer_title = value["title"]
                                        .as_str()
                                        .or_else(|| value["document"]["title"].as_str())
                                        .unwrap_or("")
                                        .into();
                                    self.writer_text = document_text(&value);
                                    self.writer_dirty = false;
                                }
                                "session" => {
                                    self.messages = parse_messages(&value);
                                    self.message_heights.clear();
                                    let mut artifacts = Vec::new();
                                    collect_artifacts(&value, &mut artifacts, 0);
                                    self.data.insert("artifacts".into(), json!(artifacts));
                                }
                                "mutation" => {
                                    self.notice = "已保存到 Deep partner".into();
                                    self.form = None;
                                    self.load_page();
                                    if !self.detail_path.is_empty() {
                                        let path = self.detail_path.clone();
                                        self.get("detail", &path);
                                    }
                                }
                                "remember" => {
                                    if let Some(token) = self.remote.trusted() {
                                        match crate::secure_store::save(
                                            &data_dir().join("device-credential"),
                                            &token,
                                        ) {
                                            Ok(()) => {
                                                self.notice =
                                                    "已保存此设备的免密登录凭证，可在账户页面撤销。"
                                                        .into()
                                            }
                                            Err(e) => self.error = e.to_string(),
                                        }
                                    }
                                }
                                "writer:save" => {
                                    self.notice = "文档已保存".into();
                                    self.detail = value.clone();
                                    self.writer_dirty = false;
                                }
                                "download" => {
                                    self.notice = "文件已保存".into();
                                }
                                _ => {}
                            }
                            self.data.insert(key, value);
                        }
                    }
                }
                Event::Stream(value) => self.on_stream(value),
            }
        }
        if !self.auth
            && self.login.tab == 2
            && !self.login.pair.is_null()
            && self
                .login
                .last_poll
                .is_none_or(|t| t.elapsed() > Duration::from_secs(3))
        {
            self.login.last_poll = Some(Instant::now());
            self.request("auth:status", "GET", "/api/quick-login/status", None, false);
        }
    }
    fn on_stream(&mut self, value: Value) {
        let mut artifacts = self
            .data
            .get("artifacts")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        collect_artifacts(&value, &mut artifacts, 0);
        self.data.insert("artifacts".into(), json!(artifacts));
        let kind = value["type"].as_str().unwrap_or("");
        if let Some(id) = value["session_id"]
            .as_str()
            .or_else(|| value["data"]["session_id"].as_str())
        {
            self.session = id.into();
        }
        match kind {
            "content" | "delta" | "text_delta" => {
                let text = value["content"]
                    .as_str()
                    .or_else(|| value["delta"].as_str())
                    .or_else(|| value["data"]["content"].as_str())
                    .unwrap_or("");
                if let Some(last) = self.messages.last_mut().filter(|m| m.role == "assistant") {
                    last.text.push_str(text);
                }
            }
            "result" => {
                let text = value["metadata"]["response"]
                    .as_str()
                    .or_else(|| value["content"].as_str())
                    .or_else(|| value["data"]["response"].as_str())
                    .unwrap_or("");
                if !text.is_empty() {
                    if let Some(last) = self.messages.last_mut().filter(|m| m.role == "assistant") {
                        last.text = text.into();
                    }
                }
            }
            "wait_for_input" => {
                self.waiting = value.clone();
            }
            "desktop_error" | "protocol_error" | "error" => {
                self.error = value["content"]
                    .as_str()
                    .or_else(|| value["message"].as_str())
                    .unwrap_or("对话请求失败")
                    .into();
            }
            "desktop_finished" => {
                self.streaming = false;
                self.get("sessions", "/api/sessions?all_workspaces=true&limit=100");
            }
            "done" => {
                self.waiting = Value::Null;
            }
            "tool_call" | "tool_result" | "thinking" | "status" | "desktop_reconnecting" => {
                let text = value["content"]
                    .as_str()
                    .or_else(|| value["tool_name"].as_str())
                    .or_else(|| value["message"].as_str())
                    .unwrap_or(kind);
                self.trace.push(text.chars().take(450).collect());
                if self.trace.len() > 100 {
                    self.trace.remove(0);
                }
            }
            _ => {}
        }
    }
    fn submit_login(&mut self) {
        self.error.clear();
        if self.login.username.trim().is_empty() || self.login.password.is_empty() {
            self.error = "请填写用户名和密码".into();
            return;
        }
        let remote = self.remote.clone();
        let config = self.config.clone();
        let username = self.login.username.trim().to_owned();
        let password = self.login.password.clone();
        self.job("auth:login", async move {
            remote.login(&config, &username, &password).await
        });
    }
    fn submit_registration(&mut self) {
        if let Err(e) = validate_registration(
            &self.login.username,
            &self.login.password,
            &self.login.confirm,
            &self.login.email,
            &self.login.reason,
        ) {
            self.error = e;
            return;
        }
        let body = pages::registration_body(
            self.login.username.trim(),
            &self.login.password,
            self.login.email.trim(),
            self.login.reason.trim(),
        );
        self.request(
            "auth:register",
            "POST",
            "/api/registration/requests",
            Some(body),
            false,
        );
    }

    fn window_size(&self, authenticated: bool, register: bool) {
        self.ctx
            .send_viewport_cmd(egui::ViewportCommand::MinInnerSize(if authenticated {
                Vec2::new(1100., 760.)
            } else if register {
                Vec2::new(500., 760.)
            } else {
                Vec2::new(480., 560.)
            }));
        self.ctx
            .send_viewport_cmd(egui::ViewportCommand::InnerSize(if authenticated {
                Vec2::new(1430., 960.)
            } else if register {
                Vec2::new(880., 900.)
            } else {
                Vec2::new(880., 700.)
            }));
    }

    fn is_admin(&self) -> bool {
        self.user["is_admin"] == true || self.user["role"] == "admin"
    }
    fn new_chat(&mut self, computer: bool) {
        if self.streaming {
            return;
        }
        self.navigate(if computer { "computer" } else { "chat" });
        self.session.clear();
        self.messages.clear();
        self.message_heights.clear();
        self.trace.clear();
        self.data.remove("artifacts");
        self.waiting = Value::Null;
    }

    fn page_ui(&mut self, ui: &mut Ui) {
        if !self.error.is_empty() {
            Frame::new()
                .fill(theme::current(ui).card)
                .inner_margin(10)
                .corner_radius(8)
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(&self.error);
                        if ui.small_button("关闭").clicked() {
                            self.error.clear();
                        }
                    });
                });
        }
        if !self.notice.is_empty() {
            ui.horizontal(|ui| {
                ui.colored_label(theme::current(ui).accent, &self.notice);
                if ui.small_button("×").clicked() {
                    self.notice.clear();
                }
            });
        }
        let page = self.page.clone();
        match page.as_str() {
            "home" => self.home(ui),
            "learning" | "resources" | "personalization" => self.hub(ui),
            "calendar" => self.calendar(ui),
            "chat" | "computer" => self.chat(ui),
            "files" => self.local_files(ui),
            "board" => self.board(ui),
            "settings" => self.settings(ui),
            _ => self.resources(ui),
        }
    }
    fn home(&mut self, ui: &mut Ui) {
        egui::ScrollArea::vertical().show(ui, |ui| {
            ui.add_space(20.);
            ui.label(RichText::new("今天想理解什么？").size(31.).strong());
            ui.add_space(10.);
            ui.label(
                RichText::new("从一个问题开始，或继续你正在推进的学习。")
                    .size(16.)
                    .color(theme::current(ui).muted),
            );
            ui.add_space(26.);
            ui.horizontal_wrapped(|ui| {
                for (id, title, desc) in [
                    ("chat", "提出问题", "12 种学习与研究能力"),
                    ("reading", "继续阅读", "原文、摘录与讨论"),
                    ("books", "构建书籍", "系统整理你的知识"),
                    ("computer", "电脑助手", "Terra 执行本机任务"),
                ] {
                    if card_button(ui, title, desc, 190.).clicked() {
                        self.navigate(id);
                    }
                }
            });
            ui.add_space(24.);
            ui.heading("最近的对话");
            ui.add_space(10.);
            let sessions = self
                .data
                .get("sessions")
                .map(schema::extract_rows)
                .unwrap_or_default();
            if sessions.is_empty() {
                ui.label(
                    RichText::new("登录后，你的历史会话会显示在这里。")
                        .color(theme::current(ui).muted),
                );
            }
            for row in sessions.iter().take(8) {
                ui.horizontal(|ui| {
                    if ui
                        .add_sized(
                            [ui.available_width() - 100., 40.],
                            egui::Button::new(schema::row_title(row)),
                        )
                        .clicked()
                    {
                        self.open_session(row);
                    }
                    ui.small(row["updated_at"].as_str().unwrap_or(""));
                });
            }
            let data = self.data.get("page:home").cloned().unwrap_or(Value::Null);
            if !data.is_null() {
                ui.add_space(22.);
                ui.collapsing("学习概览", |ui| show_value(ui, &mut self.md, &data, 0));
            }
        });
    }
    fn resources(&mut self, ui: &mut Ui) {
        let p = pages::page(&self.page);
        ui.heading(p.title);
        ui.label(
            RichText::new(p.subtitle)
                .size(13.)
                .color(theme::current(ui).muted),
        );
        ui.add_space(20.);
        let data = self
            .data
            .get(&format!("page:{}", p.id))
            .cloned()
            .unwrap_or(Value::Null);
        let rows = schema::extract_rows(&data);
        if !self.selected.is_null() {
            ui.horizontal(|ui| {
                if ui.button("← 返回列表").clicked() {
                    self.selected = Value::Null;
                    self.detail = Value::Null;
                    self.detail_path.clear();
                }
                ui.label(RichText::new(schema::row_title(&self.selected)).strong());
                if ui.button("项目操作").clicked() {
                    self.operations = true;
                }
            });
            ui.add_space(12.);
            if self.page == "writer" {
                self.writer(ui);
                return;
            }
            let detail = if self.detail.is_null() {
                self.selected.clone()
            } else {
                self.detail.clone()
            };
            egui::ScrollArea::vertical()
                .id_salt("detail-scroll")
                .show(ui, |ui| {
                    if self.page == "reading" || self.page == "books" {
                        self.reader(ui, &detail);
                    } else {
                        show_value(ui, &mut self.md, &detail, 0);
                    }
                });
            return;
        }
        ui.horizontal(|ui| {
            ui.add(
                egui::TextEdit::singleline(&mut self.search)
                    .hint_text("搜索…")
                    .desired_width(300.),
            );
            ui.small(format!("{} 项", rows.len()));
            if p.id == "reading" {
                if ui.button("导入文档").clicked() {
                    self.form = Some(ActionForm::new(
                        "/api/reading/materials",
                        "post",
                        &json!({}),
                    ));
                }
                if ui.button("导入网址").clicked() {
                    self.form = Some(ActionForm::new(
                        "/api/reading/library/import-urls",
                        "post",
                        &json!({}),
                    ));
                }
            }
            if p.id == "profile" && ui.button("记住此设备").clicked() {
                self.request(
                    "remember",
                    "POST",
                    "/api/quick-login/remember",
                    Some(json!({"name":self.login.device})),
                    true,
                );
            }
        });
        ui.add_space(14.);
        egui::ScrollArea::vertical()
            .id_salt("resource-scroll")
            .show(ui, |ui| {
                if rows.is_empty() {
                    if self.inflight.contains(&format!("page:{}", p.id)) {
                        ui.spinner();
                        ui.label("正在加载…");
                    } else if !data.is_null() && !data.is_object() {
                        show_value(ui, &mut self.md, &data, 0);
                    } else if !data.is_null()
                        && data.as_object().is_some_and(|o| !o.is_empty())
                        && p.id != "books"
                        && p.id != "notebooks"
                        && p.id != "writer"
                    {
                        show_value(ui, &mut self.md, &data, 0);
                    } else {
                        ui.add_space(45.);
                        ui.label(
                            RichText::new("还没有内容")
                                .size(21.)
                                .color(theme::current(ui).muted),
                        );
                        ui.label("点击上方“新建”或“更多操作”开始。");
                    }
                }
                for row in rows {
                    let title = schema::row_title(&row);
                    if !self.search.is_empty()
                        && !row
                            .to_string()
                            .to_lowercase()
                            .contains(&self.search.to_lowercase())
                    {
                        continue;
                    }
                    Frame::new()
                        .fill(theme::current(ui).card)
                        .stroke(Stroke::new(1., theme::current(ui).border))
                        .corner_radius(11)
                        .inner_margin(16)
                        .show(ui, |ui| {
                            ui.horizontal(|ui| {
                                if ui
                                    .add(
                                        egui::Button::new(RichText::new(&title).size(17.).strong())
                                            .frame(false),
                                    )
                                    .clicked()
                                {
                                    self.open_resource(&row);
                                }
                                ui.with_layout(
                                    egui::Layout::right_to_left(egui::Align::Center),
                                    |ui| {
                                        if ui.small_button("···").clicked() {
                                            self.selected = row.clone();
                                            self.operations = true;
                                        }
                                    },
                                );
                            });
                            for key in ["description", "summary", "note", "status", "updated_at"] {
                                if let Some(text) = row[key].as_str().filter(|s| !s.is_empty()) {
                                    ui.label(
                                        RichText::new(text.chars().take(200).collect::<String>())
                                            .size(13.)
                                            .color(theme::current(ui).muted),
                                    );
                                }
                            }
                        });
                    ui.add_space(7.);
                }
            });
    }
    fn open_resource(&mut self, row: &Value) {
        if self.page == "chat" {
            self.open_session(row);
            return;
        }
        self.selected = row.clone();
        self.detail = Value::Null;
        let p = pages::page(&self.page);
        if let Some(template) = p.detail {
            let path = pages::fill_path(template, row);
            if !path.contains('{') && schema::contract()["paths"][template].get("get").is_some() {
                self.detail_path = path.clone();
                self.get("detail", &path);
            }
        }
    }
    fn reader(&mut self, ui: &mut Ui, detail: &Value) {
        if self.page == "books" {
            let id = schema::row_id(&self.selected);
            ui.horizontal(|ui| {
                for (label, suffix) in [("章节目录", "spine"), ("书籍状态", "health")] {
                    if ui.button(label).clicked() {
                        self.get("reader", &format!("/api/books/{id}/{suffix}"));
                    }
                }
                if ui.button("导出书籍").clicked() {
                    self.download(&format!("/api/books/{id}/export"), "book.md");
                }
            });
        }
        if self.page == "reading" {
            ui.horizontal(|ui| {
                ui.label("原文位置");
                ui.text_edit_singleline(&mut self.reader_locator);
                if ui.button("打开该段").clicked() {
                    let id = schema::row_id(&self.selected);
                    self.get(
                        "reader",
                        &format!(
                            "/api/reading/materials/{id}/units/{}",
                            encode(&self.reader_locator)
                        ),
                    );
                }
                if ui.button("下载原文").clicked() {
                    self.download(
                        &format!(
                            "/api/reading/materials/{}/raw",
                            schema::row_id(&self.selected)
                        ),
                        "material",
                    );
                }
            });
        }
        ui.add_space(12.);
        let reader = self.data.get("reader").cloned();
        if let Some(reader) = reader {
            show_value(ui, &mut self.md, &reader, 0);
        } else {
            show_value(ui, &mut self.md, detail, 0);
        }
        ui.add_space(12.);
        if primary(ui, "就这份内容提问", true).clicked() {
            let id = schema::row_id(&self.selected);
            let title = schema::row_title(&self.selected);
            let is_book = self.page == "books";
            self.navigate("chat");
            self.mode = if is_book {
                "chat".into()
            } else {
                "immersive_reading".into()
            };
            self.data
                .insert("reading_context".into(), json!({"id":id,"title":title}));
            self.draft = format!("请结合《{title}》解释：");
        }
    }
    fn download(&mut self, path: &str, name: &str) {
        if let Some(target) = rfd::FileDialog::new().set_file_name(name).save_file() {
            let remote = self.remote.clone();
            let config = self.config.clone();
            let path = path.to_owned();
            self.job("download", async move {
                let bytes = remote.download(&config, &path).await?;
                tokio::task::spawn_blocking(move || std::fs::write(target, bytes)).await??;
                Ok(json!({"ok":true}))
            });
        }
    }
    fn open_artifact(&mut self, path: &str) {
        let name = path
            .split('?')
            .next()
            .unwrap_or(path)
            .rsplit('/')
            .next()
            .unwrap_or("output")
            .to_owned();
        let extension = std::path::Path::new(&name)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_lowercase();
        if ![
            "pdf", "png", "jpg", "jpeg", "svg", "webp", "gif", "mp4", "webm", "mp3", "wav", "ogg",
            "html", "htm", "txt", "md", "csv",
        ]
        .contains(&extension.as_str())
        {
            self.download(path, &name);
            return;
        }
        let remote = self.remote.clone();
        let config = self.config.clone();
        let path = path.to_owned();
        self.job("output:open", async move {
            let bytes = remote.download(&config, &path).await?;
            tokio::task::spawn_blocking(move || -> anyhow::Result<()> {
                let directory = data_dir().join("outputs");
                std::fs::create_dir_all(&directory)?;
                let file = directory.join(name);
                std::fs::write(&file, bytes)?;
                open::that_detached(file)?;
                Ok(())
            })
            .await??;
            Ok(json!({"ok":true}))
        });
    }
    fn writer(&mut self, ui: &mut Ui) {
        ui.horizontal(|ui| {
            if ui
                .add(egui::TextEdit::singleline(&mut self.writer_title).desired_width(400.))
                .changed()
            {
                self.writer_dirty = true;
            }
            if primary(
                ui,
                if self.writer_dirty {
                    "保存更改"
                } else {
                    "已保存"
                },
                self.writer_dirty && !self.inflight.contains("writer:save"),
            )
            .clicked()
            {
                let mut body = json!({"title":self.writer_title,"content":self.writer_text});
                if let Some(revision) = self.detail.get("revision") {
                    body["expected_revision"] = revision.clone();
                }
                self.request(
                    "writer:save",
                    "PUT",
                    &format!("/api/documents/{}", schema::row_id(&self.selected)),
                    Some(body),
                    true,
                );
            }
            ui.checkbox(&mut self.preview, "阅读预览");
        });
        ui.add_space(10.);
        egui::ScrollArea::vertical().show(ui, |ui| {
            if self.preview {
                CommonMarkViewer::new().show(ui, &mut self.md, &self.writer_text);
            } else if ui
                .add(
                    egui::TextEdit::multiline(&mut self.writer_text)
                        .desired_width(f32::INFINITY)
                        .desired_rows(30),
                )
                .changed()
            {
                self.writer_dirty = true;
            }
        });
    }
    fn board(&mut self, ui: &mut Ui) {
        let cards = self
            .data
            .get("page:board")
            .map(schema::extract_rows)
            .unwrap_or_default();
        let states = [("todo", "待办"), ("doing", "进行中"), ("done", "已完成")];
        ui.columns(3, |columns| {
            for (index, (status, label)) in states.iter().enumerate() {
                let ui = &mut columns[index];
                ui.label(RichText::new(*label).size(17.).strong());
                ui.separator();
                egui::ScrollArea::vertical().id_salt(status).show(ui, |ui| {
                    for card in &cards {
                        let state = card["status"].as_str().unwrap_or("todo");
                        if state != *status {
                            continue;
                        }
                        Frame::new()
                            .fill(theme::current(ui).card)
                            .stroke(Stroke::new(1., theme::current(ui).border))
                            .inner_margin(14)
                            .corner_radius(10)
                            .show(ui, |ui| {
                                ui.label(RichText::new(schema::row_title(card)).strong());
                                if let Some(note) = card["note"].as_str() {
                                    ui.label(note);
                                }
                                ui.horizontal_wrapped(|ui| {
                                    if ui.small_button("编辑").clicked() {
                                        self.form = Some(ActionForm::new(
                                            "/api/task-board/cards/{card_id}",
                                            "patch",
                                            card,
                                        ));
                                    }
                                    for (next, next_label) in states {
                                        if next != *status && ui.small_button(next_label).clicked()
                                        {
                                            self.request(
                                                "mutation",
                                                "PATCH",
                                                &format!(
                                                    "/api/task-board/cards/{}",
                                                    schema::row_id(card)
                                                ),
                                                Some(json!({"status":next})),
                                                true,
                                            );
                                        }
                                    }
                                });
                            });
                        ui.add_space(8.);
                    }
                });
            }
        });
    }
    fn settings(&mut self, ui: &mut Ui) {
        egui::ScrollArea::vertical().show(ui, |ui| {
            ui.heading("外观");
            ui.add_space(12.);
            let old = self.config.theme.clone();
            ui.horizontal(|ui| {
                for (id, label) in [("dark", "深色"), ("cream", "奶油"), ("snow", "浅色")] {
                    ui.selectable_value(&mut self.config.theme, id.into(), label);
                }
            });
            if old != self.config.theme {
                self.save_config();
            }
            ui.add_space(25.);
            ui.heading("模型与运行");
            ui.add_space(12.);
            self.model_picker(ui, false);
            self.model_picker(ui, true);
            ui.add_space(15.);
            ui.label(RichText::new("桌面配置").size(18.).strong());
            let mut changed = false;
            ui.horizontal(|ui| {
                ui.label("CPU 后台并发");
                changed |= ui
                    .add(egui::DragValue::new(&mut self.config.cpu_workers).range(1..=16))
                    .changed();
                ui.label("缓存 MiB");
                changed |= ui
                    .add(egui::DragValue::new(&mut self.config.cache_mb).range(4..=256))
                    .changed();
            });
            if ui.button("选择本机共享目录…").clicked() {
                if let Some(path) = rfd::FileDialog::new().pick_folder() {
                    self.config.workspace = path;
                    changed = true;
                }
            }
            ui.small(self.config.workspace.display().to_string());
            if changed {
                self.save_config();
            }
            ui.add_space(20.);
            ui.label(RichText::new("服务设置").size(18.).strong());
            ui.label(
                RichText::new("选择设置分类后，在原生表单中查看和修改现有配置。")
                    .color(theme::current(ui).muted),
            );
            for (label, path) in [
                ("模型提供方与目录", "/api/settings/llm"),
                ("搜索", "/api/settings/search"),
                ("语音", "/api/settings/voice"),
                ("文档解析", "/api/settings/document-parsing"),
                ("附件", "/api/settings/chat-attachments"),
                ("外观", "/api/settings/ui"),
                ("工具", "/api/settings/tools"),
            ] {
                if schema::contract()["paths"][path].get("get").is_some()
                    && ui.button(label).clicked()
                {
                    self.form = Some(ActionForm::new(path, "get", &json!({})));
                }
            }
            ui.add_space(16.);
            let status = self.service.status();
            ui.collapsing("运行状态", |ui| {
                show_value(ui, &mut self.md, &status, 0)
            });
        });
    }
    fn model_picker(&mut self, ui: &mut Ui, computer: bool) {
        let options = self.remote.model_options()["options"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let current = if computer {
            self.config.computer_model.clone()
        } else {
            self.config.learning_model.clone()
        };
        let selected = current
            .as_ref()
            .and_then(|v| {
                options
                    .iter()
                    .find(|o| o["profile_id"] == v["profile_id"] && o["model_id"] == v["model_id"])
            })
            .map(model_label)
            .unwrap_or_else(|| {
                if computer {
                    "GPT-6.1 Terra".into()
                } else {
                    "服务端默认".into()
                }
            });
        ui.horizontal(|ui|{ui.label(if computer{"电脑助手模型"}else{"学习模型"});egui::ComboBox::from_id_salt(("model",computer)).selected_text(selected).width(300.).show_ui(ui,|ui|{for option in options{if ui.selectable_label(current.as_ref().is_some_and(|v|v["model_id"]==option["model_id"]&&v["profile_id"]==option["profile_id"]),model_label(&option)).clicked(){let choice=json!({"model_id":option["model_id"],"profile_id":option["profile_id"]});if computer{self.config.computer_model=Some(choice);}else{self.config.learning_model=Some(choice);}self.save_config();}}});});
    }
    fn save_config(&mut self) {
        *self.service.config.write().unwrap() = self.config.clone();
        if let Err(e) = self.config.save() {
            self.error = e.to_string();
        }
    }
    fn local_files(&mut self, ui: &mut Ui) {
        ui.horizontal(|ui| {
            if ui.button("打开共享目录").clicked() {
                let _ = open::that_detached(&self.config.workspace);
            }
            if ui.button("选择目录").clicked() {
                if let Some(path) = rfd::FileDialog::new().pick_folder() {
                    self.config.workspace = path;
                    self.save_config();
                }
            }
            ui.small(self.config.workspace.display().to_string());
        });
        if !self.data.contains_key("local:files") && !self.inflight.contains("local:files") {
            let service = self.service.clone();
            self.job("local:files", async move {
                service.call("workspace_list", json!({"path":"."})).await
            });
        }
        if ui.button("刷新文件").clicked() {
            self.data.remove("local:files");
        }
        let files = self.data.get("local:files").cloned().unwrap_or(Value::Null);
        egui::ScrollArea::vertical().show(ui, |ui| show_value(ui, &mut self.md, &files, 0));
    }
    fn open_session(&mut self, row: &Value) {
        if self.streaming {
            return;
        }
        self.navigate("chat");
        self.session = schema::row_id(row);
        self.messages.clear();
        let mut path = format!("/api/sessions/{}", encode(&self.session));
        if let Some(workspace) = row["content_workspace_id"].as_str() {
            path.push_str(&format!("?dt_workspace={}", encode(workspace)));
            self.workspace = workspace.into();
        }
        self.get("session", &path);
    }

    fn capability_schema(&self) -> Value {
        let raw = self
            .data
            .get("capabilities")
            .and_then(|v| v["capabilities"].as_array())
            .and_then(|a| a.iter().find(|c| c["id"] == self.mode))
            .and_then(|c| c.get("config_schema"))
            .cloned()
            .unwrap_or_else(|| json!({"type":"object","properties":{}}));
        schema::expand_local_refs(&raw)
    }
    fn chat_resources(&mut self, ui: &mut Ui) {
        ui.set_max_width(450.);
        egui::ScrollArea::vertical()
            .max_height(480.)
            .show(ui, |ui| {
                let workspaces = self
                    .data
                    .get("workspaces")
                    .map(schema::extract_rows)
                    .unwrap_or_default();
                ui.label("工作区");
                egui::ComboBox::from_id_salt("workspace")
                    .selected_text(if self.workspace.is_empty() {
                        "当前工作区"
                    } else {
                        &self.workspace
                    })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut self.workspace, String::new(), "当前工作区");
                        for row in workspaces {
                            ui.selectable_value(
                                &mut self.workspace,
                                schema::row_id(&row),
                                schema::row_title(&row),
                            );
                        }
                    });
                for (key, label, target) in [
                    ("knowledge", "知识库", 0),
                    ("skills", "技能", 1),
                    ("mcps", "MCP 工具", 2),
                    ("tools", "内置工具", 3),
                ] {
                    let rows = self
                        .data
                        .get(key)
                        .map(schema::extract_rows)
                        .unwrap_or_default();
                    ui.collapsing(label, |ui| {
                        if rows.is_empty() {
                            ui.small("当前没有可用项目");
                        }
                        for row in rows {
                            let id = schema::row_id(&row);
                            let set = match target {
                                0 => &mut self.selected_kb,
                                1 => &mut self.selected_skills,
                                2 => &mut self.selected_mcp,
                                _ => &mut self.selected_tools,
                            };
                            let mut selected = set.contains(&id);
                            if ui
                                .checkbox(&mut selected, schema::row_title(&row))
                                .changed()
                            {
                                if selected {
                                    set.insert(id);
                                } else {
                                    set.remove(&id);
                                }
                            }
                        }
                    });
                }
                let personas = self
                    .data
                    .get("personas")
                    .map(schema::extract_rows)
                    .unwrap_or_default();
                ui.label("人格");
                egui::ComboBox::from_id_salt("persona")
                    .selected_text(if self.persona.is_empty() {
                        "默认人格"
                    } else {
                        &self.persona
                    })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut self.persona, String::new(), "默认人格");
                        for row in personas {
                            ui.selectable_value(
                                &mut self.persona,
                                schema::row_id(&row),
                                schema::row_title(&row),
                            );
                        }
                    });
            });
    }
    fn send_chat(&mut self, computer: bool) {
        let text = self.draft.trim().to_owned();
        if text.is_empty() {
            return;
        }
        if !self.waiting.is_null() {
            let remote = self.remote.clone();
            self.job("chat:control", async move {
                remote
                    .control(json!({"type":"submit_user_reply","text":text}))
                    .await
            });
            self.waiting = Value::Null;
            self.draft.clear();
            return;
        }
        if self.streaming {
            return;
        }
        self.error.clear();
        let mut payload = json!({"content":text,"mode":if computer{"computer"}else{"learn"},"capability":self.mode,"config":schema::prepare_body(&self.capability_schema(),&self.mode_config),"knowledge_bases":self.selected_kb,"skills":self.selected_skills,"mcp":self.selected_mcp,"tools":self.selected_tools});
        if !self.session.is_empty() {
            payload["session_id"] = json!(self.session);
        }
        if !self.workspace.is_empty() {
            payload["workspace_id"] = json!(self.workspace);
        }
        if !self.persona.is_empty() {
            payload["persona"] = json!(self.persona);
        }
        if let Some(context) = self.data.get("reading_context") {
            payload["reading_material_id"] = context["id"].clone();
        }
        let files = std::mem::take(&mut self.attachment_paths);
        let remote = self.remote.clone();
        let config = self.config.clone();
        let runtime = self.runtime.clone();
        let tx = self.tx.clone();
        let ctx = self.ctx.clone();
        let sink: EventSink = Arc::new(move |value| {
            let _ = tx.send(Event::Stream(value));
            ctx.request_repaint();
        });
        self.messages.push(Message {
            role: "user".into(),
            text,
        });
        self.messages.push(Message {
            role: "assistant".into(),
            text: String::new(),
        });
        self.draft.clear();
        self.trace.clear();
        self.streaming = true;
        self.job("chat:send",async move{
            if !files.is_empty(){
                // The socket contract accepts attachment data; the backend owns parsing and storage.
                let mut attachments=Vec::new();for path in files{let name=path.file_name().unwrap_or_default().to_string_lossy().into_owned();let bytes=tokio::task::spawn_blocking(move||std::fs::read(path)).await??;anyhow::ensure!(bytes.len()<=20*1024*1024,"单个附件不能超过 20 MiB");use base64::Engine;attachments.push(json!({"type":if name.to_lowercase().ends_with(".png")||name.to_lowercase().ends_with(".jpg")||name.to_lowercase().ends_with(".jpeg")||name.to_lowercase().ends_with(".webp"){ "image" }else{"file"},"filename":name,"base64":base64::engine::general_purpose::STANDARD.encode(bytes)}));}payload["attachments"]=json!(attachments);
            }
            remote.send(sink,runtime,config,payload).await
        });
    }
    fn dialogs(&mut self) {
        let ctx = self.ctx.clone();
        if self.data.get("global-search") == Some(&json!(true)) {
            let mut open = true;
            let mut target = None;
            let mut session = None;
            egui::Window::new("搜索")
                .open(&mut open)
                .default_size([600., 500.])
                .show(&ctx, |ui| {
                    ui.add(
                        egui::TextEdit::singleline(&mut self.global_query)
                            .hint_text("搜索功能或会话…")
                            .desired_width(f32::INFINITY),
                    );
                    ui.add_space(12.);
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for page in pages::PAGES {
                            if page.id == "users" && !self.is_admin() {
                                continue;
                            }
                            if self.global_query.is_empty()
                                || format!("{} {}", page.title, page.subtitle)
                                    .to_lowercase()
                                    .contains(&self.global_query.to_lowercase())
                            {
                                if ui.button(page.title).clicked() {
                                    target = Some(page.id);
                                }
                            }
                        }
                        ui.separator();
                        for row in self
                            .data
                            .get("sessions")
                            .map(schema::extract_rows)
                            .unwrap_or_default()
                        {
                            if self.global_query.is_empty()
                                || schema::row_title(&row)
                                    .to_lowercase()
                                    .contains(&self.global_query.to_lowercase())
                            {
                                if ui.button(schema::row_title(&row)).clicked() {
                                    session = Some(row);
                                }
                            }
                        }
                    });
                });
            if let Some(page) = target {
                self.navigate(page);
                open = false;
            }
            if let Some(row) = session {
                self.open_session(&row);
                open = false;
            }
            if !open {
                self.data.remove("global-search");
            }
        }
        if self.operations {
            let mut open = true;
            let p = pages::page(&self.page);
            let ops = pages::operations(p);
            let selected = self.selected.clone();
            let mut choose = None;
            egui::Window::new(format!("{} · 更多操作", p.title))
                .open(&mut open)
                .default_size([620., 540.])
                .show(&ctx, |ui| {
                    ui.add(
                        egui::TextEdit::singleline(&mut self.operation_search)
                            .hint_text("搜索操作…")
                            .desired_width(f32::INFINITY),
                    );
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for (path, method, op) in ops {
                            let title = pages::operation_title(&path, &method, &op);
                            if !self.operation_search.is_empty()
                                && !format!("{title} {path}")
                                    .to_lowercase()
                                    .contains(&self.operation_search.to_lowercase())
                            {
                                continue;
                            }
                            ui.horizontal(|ui| {
                                if ui.button(&title).clicked() {
                                    choose = Some((path.clone(), method.clone()));
                                }
                                ui.label(
                                    RichText::new(method.to_uppercase())
                                        .size(10.)
                                        .color(theme::current(ui).muted),
                                );
                            });
                        }
                    });
                });
            self.operations = open;
            if let Some((path, method)) = choose {
                self.form = Some(ActionForm::new(&path, &method, &selected));
                self.operations = false;
            }
        }
        if let Some(mut form) = self.form.take() {
            let mut open = true;
            let mut submit = false;
            egui::Window::new("操作")
                .id(form.id)
                .open(&mut open)
                .default_size([650., 580.])
                .show(&ctx, |ui| {
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        submit = form.draw(ui);
                    });
                });
            if submit {
                let path = form.path();
                if path.contains('{') {
                    form.error = "请填写目标项目".into();
                } else if form.method == "get" {
                    self.get("operation:result", &path);
                    self.data.remove("operation:result");
                    self.data.insert(
                        "operation:target".into(),
                        json!({"path":form.template,"row":self.selected}),
                    );
                } else {
                    let body = schema::prepare_body(&form.schema, &form.value);
                    if form.multipart {
                        let remote = self.remote.clone();
                        let config = self.config.clone();
                        let files = form
                            .files
                            .iter()
                            .map(|(k, v)| (k.clone(), v.clone()))
                            .collect();
                        self.job("mutation", async move {
                            remote.upload(&config, &path, body, files).await
                        });
                    } else {
                        self.request(
                            "mutation",
                            &form.method.to_uppercase(),
                            &path,
                            Some(body),
                            true,
                        );
                    }
                }
            }
            if open {
                self.form = Some(form);
            }
        }
        if let Some(result) = self.data.get("operation:result").cloned() {
            let mut open = true;
            let mut edit = false;
            egui::Window::new("操作结果")
                .open(&mut open)
                .default_size([700., 580.])
                .show(&ctx, |ui| {
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        show_value(ui, &mut self.md, &result, 0);
                    });
                    if ui.button("编辑当前设置").clicked() {
                        edit = true;
                    }
                });
            if edit {
                let target = self
                    .data
                    .get("operation:target")
                    .cloned()
                    .unwrap_or(Value::Null);
                let path = target["path"].as_str().unwrap_or("");
                for method in ["put", "patch"] {
                    if schema::contract()["paths"][path].get(method).is_some() {
                        self.form = Some(ActionForm::new(path, method, &result));
                        break;
                    }
                }
            }
            if !open {
                self.data.remove("operation:result");
            }
        }
    }
    pub fn render(&mut self, ui: &mut Ui) {
        self.pump();
        let style_key = format!("{}:{}", self.config.theme, self.auth);
        if style_key != self.applied_theme {
            theme::apply(&self.ctx, &self.config.theme, !self.auth);
            let selected = if self.config.theme == "dark" {
                egui::Theme::Dark
            } else {
                egui::Theme::Light
            };
            ui.set_style(self.ctx.style_of(selected));
            self.applied_theme = style_key;
        }

        if self.auth {
            let p = theme::palette(&self.config.theme);
            let rail_anim = self.ctx.animate_bool_with_time(
                egui::Id::unique("rail-collapse"),
                self.sidebar_collapsed,
                0.16,
            );
            let rail_width = egui::lerp(272.0..=58.0, rail_anim);
            egui::Panel::left("app-sidebar")
                .default_size(rail_width)
                .exact_size(rail_width)
                .resizable(false)
                .frame(Frame::new().fill(p.rail).stroke(Stroke::new(1., p.border)))
                .show(ui, |ui| self.sidebar(ui));
            egui::Panel::top("web-breadcrumb")
                .exact_size(52.)
                .frame(
                    Frame::new()
                        .fill(p.bg)
                        .inner_margin(Margin::symmetric(16, 9)),
                )
                .show(ui, |ui| self.header(ui));
            egui::CentralPanel::default()
                .frame(Frame::new().fill(p.bg).inner_margin(
                    if ["chat", "computer"].contains(&self.page.as_str()) {
                        Margin::ZERO
                    } else {
                        Margin::symmetric(32, 24)
                    },
                ))
                .show(ui, |ui| self.page_ui(ui));
            self.dialogs();
        } else {
            let p = if self.config.theme == "dark" {
                theme::KRILL_DARK
            } else {
                theme::KRILL_LIGHT
            };
            egui::CentralPanel::default()
                .frame(Frame::new().fill(p.bg).inner_margin(0))
                .show(ui, |ui| self.login_ui(ui));
        }
        if !self.auth && self.login.tab == 2 {
            self.ctx.request_repaint_after(Duration::from_secs(1));
        }
        if self.capture.is_some() {
            self.capture_frames += 1;
            if self.capture_frames == 4 {
                let path = self.capture.clone().unwrap();
                let ctx = self.ctx.clone();
                self.ctx.request_screenshot(move |image| {
                    let pixels = image
                        .pixels
                        .iter()
                        .flat_map(|p| p.to_array())
                        .collect::<Vec<_>>();
                    if let Some(image) = image::RgbaImage::from_raw(
                        image.size[0] as u32,
                        image.size[1] as u32,
                        pixels,
                    ) {
                        let _ = image.save(path);
                    }
                    ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                });
            }
            self.ctx.request_repaint_after(Duration::from_millis(120));
        }
    }
    pub fn benchmark(&mut self) -> Value {
        let mut results = Vec::new();
        for page in ["login", "register", "home", "chat"] {
            self.auth = page == "home" || page == "chat";
            self.page = page.into();
            self.login.tab = usize::from(page == "register");
            self.user = json!({"role":"admin"});
            if page == "chat" {
                self.messages = (0..40)
                    .map(|i| Message {
                        role: if i % 2 == 0 {
                            "user".into()
                        } else {
                            "assistant".into()
                        },
                        text: format!(
                            "第 {} 条测试消息\n\n{}",
                            i + 1,
                            "异步任务与界面绘制独立调度。\n\n".repeat(15)
                        ),
                    })
                    .collect();
                self.inflight.insert("background-test".into());
            }
            let mut times = Vec::<f64>::new();
            for frame in 0..80 {
                let start = Instant::now();
                let context = self.ctx.clone();
                let mut output = context.run_ui(
                    egui::RawInput {
                        screen_rect: Some(egui::Rect::from_min_size(
                            egui::Pos2::ZERO,
                            Vec2::new(1430., 960.),
                        )),
                        time: Some(frame as f64 / 60.),
                        ..Default::default()
                    },
                    |ui| self.render(ui),
                );
                let ms = start.elapsed().as_secs_f64() * 1000.;
                output.textures_delta.clear();
                if frame >= 10 {
                    times.push(ms);
                }
            }
            times.sort_by(f64::total_cmp);
            results.push(json!({"page":page,"frames":times.len(),"p50_ms":times[times.len()/2],"p95_ms":times[times.len()*95/100],"max_ms":times[times.len()-1]}));
        }
        json!({"measurement":"Native egui CPU layout; warmed frames; excludes GPU presentation, input hardware, network and model inference","version":env!("CARGO_PKG_VERSION"),"logical_cores":std::thread::available_parallelism().map(usize::from).unwrap_or(0),"results":results})
    }
    pub fn enable_capture(&mut self, path: std::path::PathBuf, page: Option<&str>) {
        if std::env::var("DEEP_PARTNER_PREVIEW_THEME")
            .is_ok_and(|id| ["dark", "snow", "cream"].contains(&id.as_str()))
        {
            self.config.theme = std::env::var("DEEP_PARTNER_PREVIEW_THEME").unwrap();
        }

        self.capture = Some(path);
        if page == Some("register") {
            self.login.tab = 1;
            self.window_size(false, true);
            return;
        }
        if let Some(page) = page {
            self.auth = true;
            self.window_size(true, false);
            self.page = page.into();
            self.category = layout::category_for(page);
            self.user = json!({"username":"桌面预览","role":"admin"});
            self.data.insert("sessions".into(), json!({"sessions":[]}));
        }
    }
}

impl eframe::App for DesktopApp {
    fn ui(&mut self, ui: &mut Ui, _frame: &mut eframe::Frame) {
        self.render(ui);
        if self.capture.is_some() && self.started.elapsed() > Duration::from_secs(20) {
            self.ctx.send_viewport_cmd(egui::ViewportCommand::Close);
        }
    }
}

fn primary(ui: &mut Ui, text: &str, enabled: bool) -> egui::Response {
    ui.add_enabled(
        enabled,
        egui::Button::new(RichText::new(text).color(Color32::WHITE))
            .fill(theme::current(ui).accent)
            .corner_radius(8),
    )
}
fn card_button(ui: &mut Ui, title: &str, desc: &str, width: f32) -> egui::Response {
    ui.add_sized(
        [width, 102.],
        egui::Button::new(RichText::new(format!("{title}\n\n{desc}")).size(15.))
            .fill(theme::current(ui).card)
            .stroke(Stroke::new(1., theme::current(ui).border))
            .corner_radius(12),
    )
}
fn encode(text: &str) -> String {
    url::form_urlencoded::byte_serialize(text.as_bytes()).collect()
}
fn model_label(value: &Value) -> String {
    format!(
        "{}{}",
        value["display_name"]
            .as_str()
            .or_else(|| value["model"].as_str())
            .unwrap_or("模型"),
        if value["is_active_default"] == true {
            " · 默认"
        } else {
            ""
        }
    )
}
fn document_text(value: &Value) -> String {
    if let Some(text) = value["content"]
        .as_str()
        .or_else(|| value["markdown"].as_str())
        .or_else(|| value["document"]["content"].as_str())
    {
        return text.into();
    }
    if let Some(blocks) = value["blocks"]
        .as_array()
        .or_else(|| value["document"]["blocks"].as_array())
    {
        return blocks
            .iter()
            .filter_map(|b| b["content"].as_str().or_else(|| b["text"].as_str()))
            .collect::<Vec<_>>()
            .join("\n\n");
    }
    String::new()
}
fn parse_messages(value: &Value) -> Vec<Message> {
    let rows = value["messages"]
        .as_array()
        .or_else(|| value["session"]["messages"].as_array());
    rows.map(|rows| {
        rows.iter()
            .filter_map(|row| {
                let text = row["content"].as_str().or_else(|| row["text"].as_str())?;
                Some(Message {
                    role: row["role"].as_str().unwrap_or("assistant").into(),
                    text: text.into(),
                })
            })
            .collect()
    })
    .unwrap_or_default()
}
pub fn validate_registration(
    username: &str,
    password: &str,
    confirm: &str,
    email: &str,
    reason: &str,
) -> Result<(), String> {
    if !(3..=128).contains(&username.trim().len()) {
        return Err("用户名需要 3–128 个字符".into());
    }
    if !(8..=64).contains(&password.chars().count()) {
        return Err("密码需要 8–64 个字符".into());
    }
    if password != confirm {
        return Err("两次密码不一致".into());
    }
    if !email.contains('@') || email.contains(' ') {
        return Err("请填写有效的联系邮箱".into());
    }
    if !(5..=1000).contains(&reason.trim().chars().count()) {
        return Err("使用目的需要 5–1000 个字符".into());
    }
    Ok(())
}
fn collect_artifacts(value: &Value, output: &mut Vec<Value>, depth: usize) {
    if depth > 10 || output.len() > 80 {
        return;
    }
    match value {
        Value::String(text) if text.len() < 131072 => {
            for token in text.split(|c: char| {
                c.is_whitespace() || ['(', ')', '[', ']', '"', '\'', '<', '>'].contains(&c)
            }) {
                if (token.starts_with("/files/outputs/")
                    || token.starts_with("/files/attachments/"))
                    && !output.contains(&json!(token))
                {
                    output.push(json!(token));
                }
            }
        }
        Value::Object(object) => {
            for (key, v) in object {
                if !["base64", "data", "api_key", "token", "secret"].contains(&key.as_str()) {
                    collect_artifacts(v, output, depth + 1);
                }
            }
        }
        Value::Array(array) => {
            for v in array {
                collect_artifacts(v, output, depth + 1);
            }
        }
        _ => {}
    }
}
fn show_value(ui: &mut Ui, cache: &mut CommonMarkCache, value: &Value, depth: usize) {
    if depth > 9 {
        return;
    }
    match value {
        Value::Null => {}
        Value::String(text) => {
            if text.starts_with("https://") && !text.contains('\n') && text.len() < 1500 {
                ui.hyperlink(text);
            } else {
                CommonMarkViewer::new().show(ui, cache, text);
            }
        }
        Value::Bool(b) => {
            ui.label(if *b { "已启用" } else { "未启用" });
        }
        Value::Number(n) => {
            ui.label(n.to_string());
        }
        Value::Array(rows) => {
            for (index, row) in rows.iter().enumerate() {
                ui.push_id(index, |ui| {
                    if row.is_object() {
                        let title = schema::row_title(row);
                        ui.collapsing(format!("{}  {}", index + 1, title), |ui| {
                            show_value(ui, cache, row, depth + 1)
                        });
                    } else {
                        show_value(ui, cache, row, depth + 1);
                    }
                });
            }
        }
        Value::Object(object) => {
            for (key, v) in object {
                if matches!(
                    key.as_str(),
                    "token" | "password" | "api_key" | "secret" | "access_token"
                ) {
                    continue;
                }
                if v.is_null() || v.as_str() == Some("") {
                    continue;
                }
                ui.push_id(key, |ui| {
                    if v.is_object() || v.is_array() {
                        ui.collapsing(schema::label(key), |ui| show_value(ui, cache, v, depth + 1));
                    } else {
                        ui.label(
                            RichText::new(schema::label(key))
                                .size(12.)
                                .color(theme::current(ui).muted),
                        );
                        show_value(ui, cache, v, depth + 1);
                        ui.add_space(6.);
                    }
                });
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn web_category_navigation_and_sidebar_buttons_respond_to_pointer() {
        let ctx = egui::Context::default();
        let rt = tokio::runtime::Runtime::new().unwrap();
        let cfg = Config::default();
        let svc = DesktopService::new(cfg.clone(), "test".repeat(12));
        let mut app = DesktopApp::new(ctx.clone(), cfg, svc, Tunnel::new(), rt.handle().clone());
        app.auth = true;
        app.user = json!({"role":"admin"});
        fn frame(ctx: &egui::Context, app: &mut DesktopApp, events: Vec<egui::Event>) {
            let mut output = ctx.run_ui(
                egui::RawInput {
                    screen_rect: Some(egui::Rect::from_min_size(
                        egui::Pos2::ZERO,
                        Vec2::new(1430., 960.),
                    )),
                    events,
                    ..Default::default()
                },
                |ui| app.render(ui),
            );
            output.textures_delta.clear();
        }
        fn click(ctx: &egui::Context, app: &mut DesktopApp, x: f32, y: f32) {
            let pos = egui::Pos2::new(x, y);
            frame(
                ctx,
                app,
                vec![
                    egui::Event::PointerMoved(pos),
                    egui::Event::PointerButton {
                        pos,
                        button: egui::PointerButton::Primary,
                        pressed: true,
                        modifiers: Default::default(),
                    },
                ],
            );
            frame(
                ctx,
                app,
                vec![egui::Event::PointerButton {
                    pos,
                    button: egui::PointerButton::Primary,
                    pressed: false,
                    modifiers: Default::default(),
                }],
            );
        }
        frame(&ctx, &mut app, Vec::new());
        click(&ctx, &mut app, 96., 80.);
        assert_eq!(app.category, 1, "learning category must open");
        click(&ctx, &mut app, 85., 262.);
        assert_eq!(app.page, "books", "book row must navigate");
        let rect = ctx
            .data(|d| d.get_temp::<egui::Rect>(egui::Id::unique(("icon-rect", "收起侧栏"))))
            .unwrap();
        click(&ctx, &mut app, rect.center().x, rect.center().y);
        assert!(app.sidebar_collapsed, "collapse control must work");
        frame(&ctx, &mut app, Vec::new());
        let rect = ctx
            .data(|d| d.get_temp::<egui::Rect>(egui::Id::unique(("icon-rect", "展开侧栏"))))
            .unwrap();
        click(&ctx, &mut app, rect.center().x, rect.center().y);
        assert!(!app.sidebar_collapsed, "expand control must work");
    }
    #[test]
    fn signup_restored_and_validated() {
        assert!(
            validate_registration(
                "alice",
                "password123",
                "password123",
                "a@example.com",
                "用于研究和学习"
            )
            .is_ok()
        );
        assert!(
            validate_registration("alice", "short", "short", "a@example.com", "用于研究和学习")
                .is_err()
        );
        assert!(
            validate_registration(
                "alice",
                "password123",
                "different",
                "a@example.com",
                "用于研究和学习"
            )
            .is_err()
        );
    }
    #[test]
    fn renders_login_and_all_native_pages() {
        let ctx = egui::Context::default();
        let rt = tokio::runtime::Runtime::new().unwrap();
        let cfg = Config::default();
        let svc = DesktopService::new(cfg.clone(), "test".repeat(12));
        let mut app = DesktopApp::new(ctx.clone(), cfg, svc, Tunnel::new(), rt.handle().clone());
        app.inflight.clear();
        app.login.tab = 1;
        let mut output = ctx.run_ui(
            egui::RawInput {
                screen_rect: Some(egui::Rect::from_min_size(
                    egui::Pos2::ZERO,
                    Vec2::new(1400., 1000.),
                )),
                ..Default::default()
            },
            |ctx| {
                egui::CentralPanel::default().show(ctx, |ui| app.login_ui(ui));
            },
        );
        assert!(!output.shapes.is_empty());
        output.textures_delta.clear();
        for theme in ["dark", "cream", "snow"] {
            app.config.theme = theme.into();
            for p in pages::PAGES {
                app.auth = true;
                app.page = p.id.into();
                app.category = layout::category_for(p.id);
                app.user = json!({"role":"admin"});
                let mut output = ctx.run_ui(
                    egui::RawInput {
                        screen_rect: Some(egui::Rect::from_min_size(
                            egui::Pos2::ZERO,
                            Vec2::new(1430., 960.),
                        )),
                        ..Default::default()
                    },
                    |ui| app.render(ui),
                );
                assert!(!output.shapes.is_empty(), "{} {}", theme, p.id);
                output.textures_delta.clear();
            }
        }
    }
}
