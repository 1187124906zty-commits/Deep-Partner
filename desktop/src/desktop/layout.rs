//! Visual structure follows the deployed web application. Business calls stay in mod.rs.
use super::*;
use egui::{Align, Align2, FontId, Layout, Pos2, Rect, Sense};

pub(super) fn category_for(page: &str) -> usize {
    match page {
        "learning" | "books" | "reading" | "mastery" => 1,
        "resources" | "library" | "notebooks" | "files" | "journal" | "practice" => 2,
        "partners" => 3,
        "personalization" | "agents" | "personas" | "skills" | "mcp" | "cli" | "memory" => 4,
        _ => 0,
    }
}
const CATEGORIES: [(Icon, &str); 5] = [
    (Icon::Home, "主页"),
    (Icon::Book, "学习"),
    (Icon::Folder, "资料"),
    (Icon::Partners, "伙伴"),
    (Icon::Sliders, "个性化"),
];

impl DesktopApp {
    pub(super) fn login_ui(&mut self, ui: &mut Ui) {
        let p = theme::current(ui);
        let bounds = ui.max_rect();
        ui.scope_builder(
            egui::UiBuilder::new().max_rect(Rect::from_min_size(
                Pos2::new(bounds.right() - 54., bounds.top() + 18.),
                Vec2::new(36., 34.),
            )),
            |ui| {
                if theme::icon_button(
                    ui,
                    "login-appearance",
                    if self.config.theme == "dark" {
                        Icon::Sun
                    } else {
                        Icon::Moon
                    },
                    "切换外观",
                )
                .clicked()
                {
                    self.config.theme = if self.config.theme == "dark" {
                        "snow".into()
                    } else {
                        "dark".into()
                    };
                    self.save_config();
                }
            },
        );
        let content_width = 336.;
        let height = if self.login.tab == 1 { 752. } else { 482. };
        let top = ((ui.available_height() - height) / 2.).max(24.);
        ui.add_space(top);
        ui.horizontal(|ui| {
            ui.add_space(((bounds.width() - 400.) / 2.).max(18.));
            Frame::new()
                .fill(p.card)
                .stroke(Stroke::new(0.8, p.border))
                .corner_radius(12)
                .inner_margin(Margin::same(32))
                .shadow(egui::Shadow {
                    offset: [0, 8],
                    blur: 30,
                    spread: 0,
                    color: Color32::from_black_alpha(if self.config.theme == "dark" {
                        65
                    } else {
                        20
                    }),
                })
                .show(ui, |ui| {
                    ui.vertical(|ui| {
                        ui.set_width(content_width);
                        ui.spacing_mut().item_spacing.y = 8.;
                        ui.vertical_centered(|ui| {
                            theme::brand(ui, 52., p.accent);
                            ui.add_space(9.);
                            theme::wordmark(ui, 34.);
                        });
                        ui.add_space(23.);
                        Frame::new()
                            .fill(p.rail)
                            .corner_radius(12)
                            .inner_margin(4)
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    ui.spacing_mut().item_spacing.x = 4.;
                                    for (index, label) in ["登录", "注册"].iter().enumerate() {
                                        let size = Vec2::new((content_width - 12.) / 2., 36.);
                                        let (rect, response) =
                                            ui.allocate_exact_size(size, Sense::click());
                                        if self.login.tab == index {
                                            ui.painter().rect_filled(rect, 10., p.selected);
                                        } else if response.hovered() {
                                            ui.painter().rect_filled(rect, 10., p.hover);
                                        }
                                        ui.painter().text(
                                            rect.center(),
                                            Align2::CENTER_CENTER,
                                            label,
                                            FontId::proportional(14.),
                                            if self.login.tab == index {
                                                p.fg
                                            } else {
                                                p.muted
                                            },
                                        );
                                        if response.clicked() {
                                            self.login.tab = index;
                                            self.error.clear();
                                            self.notice.clear();
                                            self.window_size(false, index == 1);
                                        }
                                    }
                                });
                            });
                        ui.add_space(14.);
                        input(ui, "用户名", &mut self.login.username, "输入用户名", false);
                        ui.add_space(5.);
                        ui.label(RichText::new("密码").size(14.).color(p.fg));
                        let password = Frame::new()
                            .fill(p.bg)
                            .stroke(Stroke::new(1., p.border))
                            .corner_radius(12)
                            .inner_margin(Margin::symmetric(12, 8))
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    let edit = ui.add(
                                        egui::TextEdit::singleline(&mut self.login.password)
                                            .font(FontId::proportional(14.))
                                            .frame(Frame::NONE)
                                            .password(!self.login.show_password)
                                            .desired_width(content_width - 64.)
                                            .hint_text(if self.login.tab == 1 {
                                                "8–64 位密码"
                                            } else {
                                                "输入密码"
                                            }),
                                    );
                                    if theme::icon_button(
                                        ui,
                                        "show-password",
                                        Icon::Eye,
                                        "显示 / 隐藏密码",
                                    )
                                    .clicked()
                                    {
                                        self.login.show_password = !self.login.show_password;
                                    }
                                    edit
                                })
                            })
                            .inner
                            .inner;
                        if self.login.tab == 1 {
                            ui.add_space(5.);
                            input(
                                ui,
                                "确认密码",
                                &mut self.login.confirm,
                                "再次输入密码",
                                true,
                            );
                            ui.add_space(5.);
                            input(
                                ui,
                                "联系邮箱",
                                &mut self.login.email,
                                "you@example.com",
                                false,
                            );
                            ui.add_space(5.);
                            ui.label(RichText::new("使用目的").size(14.));
                            Frame::new()
                                .fill(p.bg)
                                .stroke(Stroke::new(1., p.border))
                                .corner_radius(12)
                                .inner_margin(Margin::symmetric(12, 10))
                                .show(ui, |ui| {
                                    ui.add(
                                        egui::TextEdit::multiline(&mut self.login.reason)
                                            .frame(Frame::NONE)
                                            .font(FontId::proportional(14.))
                                            .desired_rows(2)
                                            .desired_width(f32::INFINITY)
                                            .hint_text("简要介绍你的使用需求"),
                                    );
                                });
                        }
                        ui.add_space(14.);
                        let busy = self.inflight.iter().any(|key| key.starts_with("auth:"));
                        let label = if busy {
                            "正在提交…"
                        } else if self.login.tab == 1 {
                            "提交注册申请"
                        } else {
                            "登录"
                        };
                        let button = ui
                            .add_enabled_ui(!busy, |ui| {
                                ui.add_sized(
                                    [content_width, 42.],
                                    egui::Button::new(
                                        RichText::new(label)
                                            .size(14.)
                                            .strong()
                                            .color(Color32::WHITE),
                                    )
                                    .fill(p.accent)
                                    .stroke(Stroke::NONE)
                                    .corner_radius(14),
                                )
                            })
                            .inner;
                        if button.clicked()
                            || (!busy
                                && self.login.tab == 0
                                && password.lost_focus()
                                && ui.input(|i| i.key_pressed(egui::Key::Enter)))
                        {
                            if self.login.tab == 1 {
                                self.submit_registration();
                            } else {
                                self.submit_login();
                            }
                        }
                        if !self.notice.is_empty() {
                            ui.add_space(8.);
                            ui.colored_label(p.accent, &self.notice);
                        }
                        if !self.error.is_empty() {
                            ui.add_space(8.);
                            ui.colored_label(Color32::from_rgb(232, 116, 116), &self.error);
                        }
                    });
                });
        });
    }

    pub(super) fn sidebar(&mut self, ui: &mut Ui) {
        let p = theme::current(ui);
        let collapsed = self.sidebar_collapsed;
        if collapsed {
            Frame::new()
                .inner_margin(Margin::symmetric(12, 6))
                .show(ui, |ui| {
                    if theme::icon_button(ui, "expand-sidebar", Icon::Panel, "展开侧栏").clicked()
                    {
                        self.sidebar_collapsed = false;
                    }
                    ui.add_space(15.);
                    for (index, (icon, label)) in CATEGORIES.iter().enumerate() {
                        if theme::icon_button(ui, index, *icon, label).clicked() {
                            self.category = index;
                            self.sidebar_collapsed = false;
                        }
                    }
                    ui.add_space(18.);
                    if theme::icon_button(ui, "new-collapsed", Icon::Edit, "新对话").clicked() {
                        self.new_chat(false);
                    }
                    if theme::icon_button(ui, "settings-collapsed", Icon::Settings, "设置")
                        .clicked()
                    {
                        self.navigate("settings");
                    }
                });
            return;
        }
        // The pinned bottom controls never scroll with the session list.
        egui::Panel::bottom("sidebar-footer")
            .exact_size(94.)
            .frame(
                Frame::new()
                    .fill(p.rail)
                    .inner_margin(Margin::symmetric(10, 8)),
            )
            .show(ui, |ui| {
                if ui
                    .add_sized(
                        [ui.available_width(), 40.],
                        egui::Button::new(RichText::new("＋  新对话").size(13.))
                            .fill(p.bg)
                            .stroke(Stroke::new(1., p.border))
                            .corner_radius(20),
                    )
                    .clicked()
                {
                    self.new_chat(false);
                }
                ui.horizontal(|ui| {
                    if theme::icon_button(ui, "sidebar-settings", Icon::Settings, "设置").clicked()
                    {
                        self.navigate("settings");
                    }
                    ui.menu_button(
                        RichText::new(self.user["username"].as_str().unwrap_or("账户"))
                            .size(12.)
                            .color(p.muted),
                        |ui| {
                            for (id, label) in [
                                ("profile", "账户与设备"),
                                ("workspace", "工作区"),
                                ("home", "学习概览"),
                            ] {
                                if ui.button(label).clicked() {
                                    self.navigate(id);
                                    ui.close();
                                }
                            }
                            if self.is_admin() && ui.button("用户与申请").clicked() {
                                self.navigate("users");
                                ui.close();
                            }
                            ui.separator();
                            if ui.button("退出登录").clicked() {
                                self.logout_native();
                                ui.close();
                            }
                        },
                    );
                    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                        if theme::icon_button(
                            ui,
                            "toggle-main-theme",
                            if self.config.theme == "dark" {
                                Icon::Sun
                            } else {
                                Icon::Moon
                            },
                            "切换主题",
                        )
                        .clicked()
                        {
                            self.config.theme = if self.config.theme == "dark" {
                                "snow".into()
                            } else {
                                "dark".into()
                            };
                            self.save_config();
                        }
                    });
                });
            });
        Frame::new()
            .fill(p.rail)
            .inner_margin(Margin::symmetric(10, 10))
            .show(ui, |ui| {
                ui.horizontal(|ui| {
                    let workspaces = self
                        .data
                        .get("workspaces")
                        .map(schema::extract_rows)
                        .unwrap_or_default();
                    let label = workspaces
                        .iter()
                        .find(|w| w["workspace_id"] == self.workspace)
                        .map(schema::row_title)
                        .unwrap_or_else(|| "Deep partner".into());
                    theme::brand(ui, 24., p.accent);
                    let available = (ui.available_width() - 76.).max(70.);
                    ui.allocate_ui_with_layout(
                        Vec2::new(available, 30.),
                        Layout::left_to_right(Align::Center),
                        |ui| {
                            ui.set_width(available);
                            ui.style_mut().wrap_mode = Some(egui::TextWrapMode::Truncate);
                            ui.menu_button(
                                if label == "Deep partner" {
                                    RichText::new(&label).font(FontId::new(
                                        16.,
                                        egui::FontFamily::Name("Lora Italic".into()),
                                    ))
                                } else {
                                    RichText::new(truncate(&label, 18)).size(13.).strong()
                                },
                                |ui| {
                                    ui.label(RichText::new("工作区").color(p.muted));
                                    if ui
                                        .selectable_label(self.workspace.is_empty(), "通用工作区")
                                        .clicked()
                                    {
                                        self.workspace.clear();
                                        ui.close();
                                    }
                                    for row in workspaces {
                                        let id = schema::row_id(&row);
                                        if ui
                                            .selectable_label(
                                                self.workspace == id,
                                                schema::row_title(&row),
                                            )
                                            .clicked()
                                        {
                                            self.workspace = id;
                                            ui.close();
                                        }
                                    }
                                    ui.separator();
                                    if ui.button("管理工作区").clicked() {
                                        self.navigate("workspace");
                                        ui.close();
                                    }
                                },
                            );
                        },
                    );
                    if theme::icon_button(ui, "search-all", Icon::Search, "搜索").clicked() {
                        self.activities = false;
                        self.data.insert("global-search".into(), json!(true));
                    }
                    if theme::icon_button(ui, "collapse-sidebar", Icon::Panel, "收起侧栏").clicked()
                    {
                        self.sidebar_collapsed = true;
                    }
                });
                ui.add_space(12.);
                ui.horizontal(|ui| {
                    ui.spacing_mut().item_spacing.x = 3.;
                    for (index, (kind, label)) in CATEGORIES.iter().enumerate() {
                        let selected = self.category == index;
                        let w = if selected {
                            match index {
                                4 => 78.,
                                _ => 65.,
                            }
                        } else {
                            33.
                        };
                        let (rect, response) =
                            ui.allocate_exact_size(Vec2::new(w, 32.), Sense::click());
                        if selected || response.hovered() {
                            ui.painter().rect_filled(
                                rect,
                                7.,
                                if selected { p.selected } else { p.hover },
                            );
                        }
                        theme::icon(
                            ui,
                            Pos2::new(rect.left() + 17., rect.center().y),
                            *kind,
                            17.,
                            if selected { p.fg } else { p.muted },
                        );
                        if selected {
                            ui.painter().text(
                                Pos2::new(rect.left() + 32., rect.center().y),
                                Align2::LEFT_CENTER,
                                label,
                                FontId::proportional(12.),
                                p.fg,
                            );
                        }
                        if response.on_hover_text(*label).clicked() {
                            self.category = index;
                        }
                    }
                });
                ui.add_space(15.);
                egui::ScrollArea::vertical()
                    .id_salt("web-sidebar-content")
                    .auto_shrink([false, false])
                    .show(ui, |ui| {
                        let row_width = ui.available_width();
                        match self.category {
                            0 => {
                                if theme::row(
                                    ui,
                                    "nav-chat",
                                    Icon::Chat,
                                    "聊天",
                                    self.page == "chat",
                                    row_width,
                                )
                                .clicked()
                                {
                                    self.navigate("chat");
                                }
                                ui.add_space(13.);
                                section(ui, "工作台");
                                for (id, label, kind) in [
                                    ("calendar", "日历", Icon::Calendar),
                                    ("board", "任务看板", Icon::Board),
                                    ("writer", "笔记本", Icon::Edit),
                                    ("computer", "电脑助手", Icon::Computer),
                                ] {
                                    if theme::row(ui, id, kind, label, self.page == id, row_width)
                                        .clicked()
                                    {
                                        self.navigate(id);
                                    }
                                }
                                ui.add_space(20.);
                                self.session_sidebar(ui);
                            }
                            1 => {
                                for (id, label, kind) in [
                                    ("learning", "新建学习", Icon::Plus),
                                    ("learning", "全部学习", Icon::Grid),
                                ] {
                                    if theme::row(ui, (id, label), kind, label, false, row_width)
                                        .clicked()
                                    {
                                        self.navigate(id);
                                    }
                                }
                                ui.add_space(17.);
                                section(ui, "学习记录");
                                for (id, label, kind) in [
                                    ("books", "书籍", Icon::Book),
                                    ("reading", "沉浸阅读", Icon::File),
                                    ("mastery", "掌握路径", Icon::Brain),
                                ] {
                                    if theme::row(ui, id, kind, label, self.page == id, row_width)
                                        .clicked()
                                    {
                                        self.navigate(id);
                                    }
                                }
                            }
                            2 => {
                                if theme::row(
                                    ui,
                                    "all-resources",
                                    Icon::Grid,
                                    "全部资料",
                                    self.page == "resources",
                                    row_width,
                                )
                                .clicked()
                                {
                                    self.navigate("resources");
                                }
                                ui.add_space(13.);
                                section(ui, "对话与资料");
                                for (id, label, kind) in [
                                    ("chat", "聊天历史", Icon::Chat),
                                    ("notebooks", "收藏夹", Icon::Book),
                                    ("journal", "学习日志", Icon::Calendar),
                                    ("practice", "题库", Icon::Brain),
                                    ("library", "知识中心", Icon::Folder),
                                    ("files", "本机文件", Icon::Computer),
                                ] {
                                    if theme::row(ui, id, kind, label, self.page == id, row_width)
                                        .clicked()
                                    {
                                        self.navigate(id);
                                        if id == "chat" {
                                            self.category = 2;
                                        }
                                    }
                                }
                            }
                            3 => {
                                if theme::row(
                                    ui,
                                    "nav-partners",
                                    Icon::Partners,
                                    "全部伙伴",
                                    self.page == "partners",
                                    row_width,
                                )
                                .clicked()
                                {
                                    self.navigate("partners");
                                }
                                ui.add_space(16.);
                                section(ui, "伙伴");
                                let rows = self
                                    .data
                                    .get("page:partners")
                                    .map(schema::extract_rows)
                                    .unwrap_or_default();
                                for row in rows {
                                    if theme::row(
                                        ui,
                                        schema::row_id(&row),
                                        Icon::User,
                                        &schema::row_title(&row),
                                        false,
                                        row_width,
                                    )
                                    .clicked()
                                    {
                                        self.navigate("partners");
                                        self.open_resource(&row);
                                    }
                                }
                                if ui.button("＋  新建伙伴").clicked() {
                                    self.navigate("partners");
                                    self.form =
                                        Some(ActionForm::new("/api/partners", "post", &json!({})));
                                }
                            }
                            _ => {
                                if theme::row(
                                    ui,
                                    "all-personalization",
                                    Icon::Sliders,
                                    "全部个性化",
                                    self.page == "personalization",
                                    row_width,
                                )
                                .clicked()
                                {
                                    self.navigate("personalization");
                                }
                                ui.add_space(13.);
                                for (id, label, kind) in [
                                    ("agents", "子智能体", Icon::Computer),
                                    ("personas", "人格", Icon::User),
                                    ("skills", "技能", Icon::Edit),
                                    ("mcp", "MCP 服务", Icon::Sliders),
                                    ("cli", "CLI 应用", Icon::Code),
                                    ("memory", "记忆", Icon::Brain),
                                ] {
                                    if theme::row(ui, id, kind, label, self.page == id, row_width)
                                        .clicked()
                                    {
                                        self.navigate(id);
                                    }
                                }
                            }
                        }
                    });
            });
    }
    fn session_sidebar(&mut self, ui: &mut Ui) {
        let p = theme::current(ui);
        let rows = self
            .data
            .get("sessions")
            .map(schema::extract_rows)
            .unwrap_or_default();
        ui.horizontal(|ui| {
            ui.label(
                RichText::new(format!("对话记录 {}", rows.len()))
                    .size(12.)
                    .color(p.muted),
            );
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if theme::icon_button(ui, "search-sessions", Icon::Search, "搜索对话").clicked()
                {
                    self.data.insert("show-session-search".into(), json!(true));
                }
            });
        });
        if self.data.get("show-session-search") == Some(&json!(true)) {
            ui.add(
                egui::TextEdit::singleline(&mut self.nav_filter)
                    .desired_width(f32::INFINITY)
                    .hint_text("搜索对话…"),
            );
        }
        ui.add_space(8.);
        section(ui, "最近");
        for row in rows {
            let title = schema::row_title(&row);
            if !self.nav_filter.is_empty()
                && !title
                    .to_lowercase()
                    .contains(&self.nav_filter.to_lowercase())
            {
                continue;
            }
            ui.push_id(schema::row_id(&row), |ui| {
                ui.horizontal(|ui| {
                    let id = schema::row_id(&row);
                    let selected = id == self.session;
                    let available = (ui.available_width() - 28.).max(50.);
                    if theme::row(ui, "session", Icon::Chat, &title, selected, available)
                        .on_hover_text(&title)
                        .clicked()
                    {
                        self.open_session(&row);
                    }
                    ui.menu_button("···", |ui| {
                        if ui.button("重命名").clicked() {
                            self.form =
                                Some(ActionForm::new("/api/sessions/{session_id}", "patch", &row));
                            ui.close();
                        }
                        if ui.button("删除").clicked() {
                            self.form = Some(ActionForm::new(
                                "/api/sessions/{session_id}",
                                "delete",
                                &row,
                            ));
                            ui.close();
                        }
                    });
                });
            });
        }
    }
    fn logout_native(&mut self) {
        self.request("logout", "POST", "/api/auth/logout", Some(json!({})), true);
        self.remote.logout();
        self.auth = false;
        self.window_size(false, false);
        self.messages.clear();
        self.data.clear();
        let t = self.tunnel.clone();
        self.runtime.spawn(async move {
            t.disconnect().await;
        });
    }

    pub(super) fn header(&mut self, ui: &mut Ui) {
        ui.visuals_mut().button_frame = false;
        let p = theme::current(ui);
        let page = pages::page(&self.page);
        let chat = ["chat", "computer"].contains(&self.page.as_str());
        ui.horizontal(|ui| {
            theme::icon(
                ui,
                ui.cursor().min + Vec2::new(9., 17.),
                if chat { Icon::Chat } else { Icon::Folder },
                17.,
                p.muted,
            );
            ui.add_space(24.);
            ui.menu_button(
                RichText::new(if chat {
                    if self.page == "computer" {
                        "电脑助手"
                    } else {
                        "聊天"
                    }
                } else {
                    page.title
                })
                .size(13.),
                |ui| {
                    for (id, label) in [
                        ("chat", "聊天"),
                        ("learning", "学习"),
                        ("resources", "资料"),
                        ("partners", "伙伴"),
                        ("personalization", "个性化"),
                    ] {
                        if ui.button(label).clicked() {
                            self.navigate(id);
                            ui.close();
                        }
                    }
                },
            );
            if chat && self.session.is_empty() {
                ui.label(RichText::new("/").size(13.).color(p.muted));
                ui.label(RichText::new("新对话").size(13.).color(p.muted));
            }
            if chat && !self.session.is_empty() {
                ui.label(RichText::new("/").color(p.muted));
                let title = self
                    .data
                    .get("sessions")
                    .map(schema::extract_rows)
                    .unwrap_or_default()
                    .iter()
                    .find(|r| schema::row_id(r) == self.session)
                    .map(schema::row_title)
                    .unwrap_or_else(|| "当前对话".into());
                ui.label(RichText::new(truncate(&title, 54)).size(13.));
            }
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if theme::icon_button(ui, "page-more", Icon::More, "更多操作").clicked() {
                    self.operations = true;
                    self.operation_search.clear();
                }
                if chat {
                    if theme::icon_button(ui, "activity", Icon::Panel, "活动与附件").clicked()
                    {
                        self.activities = !self.activities;
                    }
                    if theme::icon_button(ui, "chat-note", Icon::Edit, "笔记").clicked() {
                        self.navigate("writer");
                    }
                    ui.menu_button("自定义", |ui| {
                        self.model_picker(ui, self.page == "computer");
                        ui.separator();
                        if ui.button("外观设置").clicked() {
                            self.navigate("settings");
                            ui.close();
                        }
                    });
                } else {
                    if !page.list.is_empty()
                        && theme::icon_button(ui, "refresh", Icon::Sliders, "刷新").clicked()
                    {
                        self.load_page();
                    }
                    if let Some(path) = page.create {
                        if schema::contract()["paths"][path].get("post").is_some()
                            && ui.button("＋ 新建").clicked()
                        {
                            self.form = Some(ActionForm::new(path, "post", &json!({})));
                        }
                    }
                }
            });
        });
    }

    pub(super) fn chat(&mut self, ui: &mut Ui) {
        let computer = self.page == "computer";
        let p = theme::current(ui);
        if self.activities {
            egui::Panel::right("web-activity")
                .default_size(300.)
                .size_range(250.0..=420.)
                .frame(
                    Frame::new()
                        .fill(p.card)
                        .stroke(Stroke::new(1., p.border))
                        .inner_margin(16),
                )
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new("活动").strong());
                        if ui.small_button("×").clicked() {
                            self.activities = false;
                        }
                    });
                    ui.add_space(14.);
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for item in &self.trace {
                            ui.label(RichText::new(item).size(12.).color(p.muted));
                            ui.add_space(9.);
                        }
                        let artifacts = self
                            .data
                            .get("artifacts")
                            .and_then(Value::as_array)
                            .cloned()
                            .unwrap_or_default();
                        for artifact in artifacts {
                            if let Some(path) = artifact.as_str() {
                                if ui
                                    .button(path.rsplit('/').next().unwrap_or("文件"))
                                    .clicked()
                                {
                                    self.open_artifact(path);
                                }
                            }
                        }
                        if self.trace.is_empty() {
                            ui.label(
                                RichText::new("任务活动与生成文件会显示在这里。").color(p.muted),
                            );
                        }
                    });
                });
        }
        let empty = self.messages.is_empty();
        let width = ui.available_width();
        if (self.chat_width - width).abs() > 2. {
            self.chat_width = width;
            self.message_heights.clear();
        }
        if empty {
            ui.add_space((ui.available_height() * 0.19).max(35.));
            centered_column(ui, 760., |ui| {
                let greeting = if computer {
                    "电脑助手"
                } else {
                    let hour = (std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs()
                        / 3600
                        + 8)
                        % 24;
                    match hour {
                        0..=5 => "还在熬夜？",
                        6..=11 => "早上好。",
                        12..=17 => "下午好。",
                        _ => "晚上好。",
                    }
                };
                let greeting_width = if computer { 230. } else { 250. };
                centered_column(ui, greeting_width, |ui| {
                    ui.horizontal(|ui| {
                        theme::brand(ui, 38., p.fg);
                        ui.add_space(7.);
                        ui.label(
                            RichText::new(greeting)
                                .font(FontId::new(38., egui::FontFamily::Name("Greeting".into())))
                                .color(p.fg),
                        );
                    });
                });
                ui.add_space(48.);
                self.composer(ui, computer);
                ui.add_space(23.);
                centered_column(ui, 450., |ui| {
                    ui.horizontal_wrapped(|ui| {
                        ui.visuals_mut().button_frame = false;
                        ui.spacing_mut().item_spacing.x = 17.;
                        for (mode, label) in [
                            ("chat", "讲解"),
                            ("deep_solve", "解题"),
                            ("deep_question", "练习"),
                            ("mastery_path", "规划"),
                            ("deep_research", "研究"),
                        ] {
                            if ui
                                .add(
                                    egui::Button::new(
                                        RichText::new(label).size(13.).color(p.muted),
                                    )
                                    .frame(false),
                                )
                                .clicked()
                            {
                                self.mode = mode.into();
                                self.mode_config = schema::default_value(&self.capability_schema());
                            }
                        }
                    });
                });
            });
        } else {
            egui::Panel::bottom("web-composer")
                .exact_size(164.)
                .resizable(false)
                .show_separator_line(false)
                .frame(
                    Frame::new()
                        .fill(p.bg)
                        .inner_margin(Margin::symmetric(20, 12)),
                )
                .show(ui, |ui| {
                    centered_column(ui, 920., |ui| self.composer(ui, computer));
                });
            egui::CentralPanel::default()
                .frame(
                    Frame::new()
                        .fill(p.bg)
                        .inner_margin(Margin::symmetric(24, 10)),
                )
                .show(ui, |ui| {
                    egui::ScrollArea::vertical()
                        .id_salt("messages")
                        .stick_to_bottom(true)
                        .auto_shrink([false, false])
                        .show(ui, |ui| {
                            centered_column(ui, 920., |ui| {
                                for (index, message) in self.messages.iter().enumerate() {
                                    if let Some(height) = self.message_heights.get(&index) {
                                        let rect = Rect::from_min_size(
                                            ui.cursor().min,
                                            Vec2::new(ui.available_width(), *height),
                                        );
                                        if !ui.clip_rect().expand(100.).intersects(rect) {
                                            ui.allocate_space(rect.size());
                                            continue;
                                        }
                                    }
                                    let top = ui.cursor().top();
                                    ui.push_id(index, |ui| {
                                        ui.add_space(17.);
                                        if message.role == "user" {
                                            ui.with_layout(Layout::top_down(Align::RIGHT), |ui| {
                                                Frame::new()
                                                    .fill(p.card)
                                                    .corner_radius(18)
                                                    .inner_margin(Margin::symmetric(18, 12))
                                                    .show(ui, |ui| {
                                                        ui.set_max_width(720.);
                                                        ui.label(
                                                            RichText::new(&message.text).size(15.5),
                                                        );
                                                    });
                                            });
                                        } else {
                                            ui.horizontal(|ui| {
                                                if message.text.is_empty() {
                                                    ui.spinner();
                                                    ui.label(
                                                        RichText::new("正在思考…")
                                                            .size(12.)
                                                            .color(p.muted),
                                                    );
                                                } else {
                                                    theme::icon(
                                                        ui,
                                                        ui.cursor().min + Vec2::new(7., 9.),
                                                        Icon::Check,
                                                        13.,
                                                        p.muted,
                                                    );
                                                    ui.add_space(20.);
                                                    ui.label(
                                                        RichText::new("已完成")
                                                            .size(11.)
                                                            .color(p.muted),
                                                    );
                                                }
                                            });
                                            ui.add_space(11.);
                                            ui.scope(|ui| {
                                                ui.style_mut().text_styles.insert(
                                                    egui::TextStyle::Body,
                                                    FontId::proportional(15.5),
                                                );
                                                ui.spacing_mut().item_spacing.y = 10.;
                                                CommonMarkViewer::new().show(
                                                    ui,
                                                    &mut self.md,
                                                    &message.text,
                                                );
                                            });
                                            if !message.text.is_empty() {
                                                ui.add_space(10.);
                                                ui.horizontal(|ui| {
                                                    if theme::icon_button(
                                                        ui,
                                                        "copy",
                                                        Icon::File,
                                                        "复制回答",
                                                    )
                                                    .clicked()
                                                    {
                                                        ui.ctx().copy_text(message.text.clone());
                                                    }
                                                });
                                            }
                                        }
                                    });
                                    self.message_heights.insert(index, ui.cursor().top() - top);
                                }
                                if !self.waiting.is_null() {
                                    ui.add_space(15.);
                                    ui.colored_label(
                                        p.accent,
                                        self.waiting["content"]
                                            .as_str()
                                            .unwrap_or("助手正在等待你的回复"),
                                    );
                                }
                                let artifacts = self
                                    .data
                                    .get("artifacts")
                                    .and_then(Value::as_array)
                                    .cloned()
                                    .unwrap_or_default();
                                if !artifacts.is_empty() {
                                    ui.add_space(15.);
                                    for artifact in artifacts {
                                        if let Some(path) = artifact.as_str() {
                                            ui.horizontal(|ui| {
                                                ui.label(path.rsplit('/').next().unwrap_or("文件"));
                                                if ui.button("打开").clicked() {
                                                    self.open_artifact(path);
                                                }
                                                if ui.button("另存为").clicked() {
                                                    self.download(
                                                        path,
                                                        path.rsplit('/').next().unwrap_or("output"),
                                                    );
                                                }
                                            });
                                        }
                                    }
                                }
                                ui.add_space(20.);
                            });
                        });
                });
        }
    }
    fn composer(&mut self, ui: &mut Ui, computer: bool) {
        ui.visuals_mut().button_frame = false;
        let p = theme::current(ui);
        let mut send = false;
        Frame::new()
            .fill(p.card)
            .stroke(Stroke::new(1., p.border))
            .corner_radius(22)
            .inner_margin(Margin::symmetric(16, 12))
            .show(ui, |ui| {
                let response = ui.add(
                    egui::TextEdit::multiline(&mut self.draft)
                        .font(FontId::proportional(15.5))
                        .frame(Frame::NONE)
                        .desired_width(f32::INFINITY)
                        .desired_rows(if self.messages.is_empty() { 3 } else { 2 })
                        .hint_text(if computer {
                            "让 Terra 操作浏览器、查找资料或完成电脑任务…"
                        } else {
                            "今天我能帮您什么？"
                        }),
                );
                if response.has_focus()
                    && ui.input(|i| i.modifiers.ctrl && i.key_pressed(egui::Key::Enter))
                {
                    send = true;
                }
                ui.add_space(4.);
                ui.horizontal(|ui| {
                    if theme::icon_button(ui, "attach", Icon::Paperclip, "添加附件").clicked() {
                        if let Some(files) = rfd::FileDialog::new().pick_files() {
                            self.attachment_paths.extend(files);
                        }
                    }
                    if !self.attachment_paths.is_empty() {
                        ui.small(format!("{} 个附件", self.attachment_paths.len()));
                        if ui.small_button("清空").clicked() {
                            self.attachment_paths.clear();
                        }
                    }
                    ui.menu_button(RichText::new("资源").size(12.).color(p.muted), |ui| {
                        self.chat_resources(ui)
                    });
                    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                        let ready = (!self.streaming || !self.waiting.is_null())
                            && !self.draft.trim().is_empty();
                        let stop = self.streaming && self.waiting.is_null();
                        let (rect, response) =
                            ui.allocate_exact_size(Vec2::splat(32.), Sense::click());
                        let color = if ready || stop {
                            p.fg
                        } else {
                            p.muted.gamma_multiply(0.35)
                        };
                        ui.painter()
                            .circle_stroke(rect.center(), 15., Stroke::new(1., p.border));
                        theme::icon(
                            ui,
                            rect.center(),
                            if stop { Icon::Stop } else { Icon::Arrow },
                            17.,
                            color,
                        );
                        if response
                            .on_hover_text(if stop {
                                "停止生成"
                            } else {
                                "发送 · Ctrl + Enter"
                            })
                            .clicked()
                        {
                            if stop {
                                let remote = self.remote.clone();
                                self.job("chat:control", async move {
                                    remote.control(json!({"type":"cancel_turn"})).await
                                });
                            } else if ready {
                                send = true;
                            }
                        }
                        if computer {
                            ui.label(RichText::new("gpt-6.1-terra").size(12.).color(p.muted));
                        } else {
                            let choices = self.remote.model_options()["options"]
                                .as_array()
                                .cloned()
                                .unwrap_or_default();
                            let selected = self.remote.choice(&self.config, false).ok();
                            let label = selected
                                .as_ref()
                                .and_then(|s| {
                                    choices.iter().find(|m| {
                                        m["model_id"] == s["model_id"]
                                            && m["profile_id"] == s["profile_id"]
                                    })
                                })
                                .and_then(|m| m["model"].as_str())
                                .unwrap_or("默认模型");
                            ui.menu_button(
                                RichText::new(format!("◌  {label}"))
                                    .size(12.)
                                    .color(p.muted),
                                |ui| self.model_picker(ui, false),
                            );
                        }
                        if self.streaming {
                            ui.spinner();
                        }
                    });
                });
            });
        ui.add_space(1.);
        Frame::new()
            .fill(p.card)
            .corner_radius(18)
            .inner_margin(Margin::symmetric(12, 2))
            .show(ui, |ui| {
                ui.horizontal_wrapped(|ui| {
                    ui.spacing_mut().item_spacing.x = 6.;
                    ui.menu_button(
                        RichText::new(format!("模式 · {}", pages::mode_label(&self.mode)))
                            .size(12.)
                            .color(p.muted),
                        |ui| {
                            let old = self.mode.clone();
                            let caps = self
                                .data
                                .get("capabilities")
                                .and_then(|v| v["capabilities"].as_array())
                                .cloned()
                                .unwrap_or_default();
                            for cap in caps {
                                let id = cap["id"]
                                    .as_str()
                                    .or_else(|| cap.as_str())
                                    .unwrap_or("chat");
                                if cap["available"] != false
                                    && ui
                                        .selectable_label(self.mode == id, pages::mode_label(id))
                                        .clicked()
                                {
                                    self.mode = id.into();
                                    ui.close();
                                }
                            }
                            if old != self.mode {
                                self.mode_config = schema::default_value(&self.capability_schema());
                            }
                        },
                    );
                    ui.menu_button(
                        RichText::new("技能  自动").size(12.).color(p.muted),
                        |ui| self.chat_resources(ui),
                    );
                    ui.menu_button(
                        RichText::new("连接器  自动").size(12.).color(p.muted),
                        |ui| self.chat_resources(ui),
                    );
                    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                        ui.menu_button(
                            RichText::new("偏好  默认").size(12.).color(p.muted),
                            |ui| {
                                let s = self.capability_schema();
                                forms::field(ui, "", &s, &mut self.mode_config, 0);
                            },
                        );
                        ui.menu_button(RichText::new("伙伴").size(12.).color(p.muted), |ui| {
                            self.chat_resources(ui)
                        });
                    });
                });
            });
        if computer {
            let connected = self
                .data
                .get("tunnel")
                .is_some_and(|v| v["connected"] == true);
            ui.horizontal(|ui| {
                ui.small(if connected {
                    "电脑工具已连接"
                } else {
                    "电脑工具未连接"
                });
                if !connected && ui.small_button("连接").clicked() {
                    let t = self.tunnel.clone();
                    let s = self.service.clone();
                    self.job("tunnel", async move { t.connect(&s).await });
                }
            });
        }
        if send {
            self.send_chat(computer);
        }
    }

    pub(super) fn hub(&mut self, ui: &mut Ui) {
        let p = theme::current(ui);
        let title = pages::page(&self.page).title;
        ui.heading(title);
        ui.add_space(8.);
        let entries: Vec<(&str, &str, &str, Icon)> = match self.page.as_str() {
            "learning" => vec![
                (
                    "reading",
                    "沉浸阅读",
                    "与原文一起阅读、提问与理解",
                    Icon::Book,
                ),
                ("books", "书籍", "从你的资料构建系统性的知识", Icon::Folder),
                (
                    "mastery",
                    "掌握路径",
                    "制定目标，逐步掌握与复习",
                    Icon::Brain,
                ),
            ],
            "resources" => vec![
                ("chat", "聊天历史", "继续已有会话", Icon::Chat),
                ("notebooks", "收藏夹", "整理摘录和笔记", Icon::Book),
                ("journal", "学习日志", "回顾学习进展", Icon::Calendar),
                ("practice", "题库", "练习与题目记录", Icon::Brain),
                ("library", "知识中心", "管理知识库与原始资料", Icon::Folder),
                ("files", "本机文件", "连接本机共享资料", Icon::Computer),
            ],
            _ => vec![
                ("agents", "子智能体", "连接已有智能体", Icon::Computer),
                ("personas", "人格", "配置角色与指引", Icon::User),
                ("skills", "技能", "可复用的工作方法", Icon::Edit),
                ("mcp", "MCP 服务", "管理工具连接", Icon::Sliders),
                ("cli", "CLI 应用", "管理命令行应用", Icon::Code),
                ("memory", "记忆", "编辑和整理学习记忆", Icon::Brain),
            ],
        };
        ui.add_space(25.);
        egui::ScrollArea::vertical().show(ui, |ui| {
            let width = ((ui.available_width() - 24.) / 3.).max(200.);
            for chunk in entries.chunks(3) {
                ui.horizontal(|ui| {
                    for (id, label, description, kind) in chunk {
                        let result = Frame::new()
                            .fill(p.card)
                            .stroke(Stroke::new(1., p.border))
                            .corner_radius(14)
                            .inner_margin(20)
                            .show(ui, |ui| {
                                ui.vertical(|ui| {
                                    ui.set_min_size(Vec2::new(width - 40., 130.));
                                    theme::icon(
                                        ui,
                                        ui.cursor().min + Vec2::splat(13.),
                                        *kind,
                                        24.,
                                        p.accent,
                                    );
                                    ui.add_space(38.);
                                    ui.label(RichText::new(*label).size(19.).strong());
                                    ui.add_space(5.);
                                    ui.label(RichText::new(*description).size(13.).color(p.muted));
                                });
                            });
                        if ui
                            .interact(result.response.rect, ui.scope_id().with(id), Sense::click())
                            .on_hover_cursor(egui::CursorIcon::PointingHand)
                            .clicked()
                        {
                            self.navigate(id);
                        }
                    }
                });
                ui.add_space(12.);
            }
        });
    }
    pub(super) fn calendar(&mut self, ui: &mut Ui) {
        let p = theme::current(ui);
        ui.heading("日历");
        ui.add_space(10.);
        let cards = self
            .data
            .get("page:calendar")
            .map(schema::extract_rows)
            .unwrap_or_default();
        let mut dated = BTreeMap::<String, Vec<Value>>::new();
        for card in cards {
            dated
                .entry(card["due_date"].as_str().unwrap_or("未安排日期").into())
                .or_default()
                .push(card);
        }
        egui::ScrollArea::vertical().show(ui, |ui| {
            if dated.is_empty() {
                ui.add_space(35.);
                ui.label(RichText::new("还没有已安排的任务").color(p.muted));
                if ui.button("＋ 新建任务").clicked() {
                    self.form = Some(ActionForm::new("/api/task-board/cards", "post", &json!({})));
                }
            }
            for (date, cards) in dated {
                ui.label(RichText::new(date).size(17.).strong());
                ui.add_space(8.);
                for card in cards {
                    Frame::new()
                        .fill(p.card)
                        .stroke(Stroke::new(1., p.border))
                        .inner_margin(14)
                        .corner_radius(10)
                        .show(ui, |ui| {
                            ui.horizontal(|ui| {
                                ui.label(RichText::new(schema::row_title(&card)).strong());
                                if ui.small_button("编辑").clicked() {
                                    self.form = Some(ActionForm::new(
                                        "/api/task-board/cards/{card_id}",
                                        "patch",
                                        &card,
                                    ));
                                }
                            });
                            if let Some(note) = card["note"].as_str() {
                                ui.small(note);
                            }
                        });
                    ui.add_space(7.);
                }
                ui.add_space(16.);
            }
        });
    }
}
fn input(ui: &mut Ui, label: &str, text: &mut String, hint: &str, password: bool) {
    let p = theme::current(ui);
    ui.label(RichText::new(label).size(14.).color(p.fg));
    let result = Frame::new()
        .fill(p.bg)
        .stroke(Stroke::new(1., p.border))
        .corner_radius(12)
        .inner_margin(Margin::symmetric(12, 6))
        .show(ui, |ui| {
            ui.add(
                egui::TextEdit::singleline(text)
                    .frame(Frame::NONE)
                    .password(password)
                    .font(FontId::proportional(14.))
                    .desired_width(f32::INFINITY)
                    .hint_text(hint),
            )
        });
    let t = ui.ctx().animate_bool_with_time(
        result.inner.id.with("focus-ring"),
        result.inner.has_focus(),
        0.12,
    );
    if t > 0. {
        ui.painter().rect_stroke(
            result.response.rect,
            12.,
            Stroke::new(1., p.accent.gamma_multiply(t)),
            egui::StrokeKind::Inside,
        );
    }
}

fn section(ui: &mut Ui, label: &str) {
    ui.label(
        RichText::new(label)
            .size(11.)
            .color(theme::current(ui).muted),
    );
    ui.add_space(3.);
}
fn truncate(text: &str, count: usize) -> String {
    if text.chars().count() > count {
        format!("{}…", text.chars().take(count - 1).collect::<String>())
    } else {
        text.into()
    }
}
fn centered_column(ui: &mut Ui, max_width: f32, contents: impl FnOnce(&mut Ui)) {
    let width = ui.available_width().min(max_width);
    let gutter = ((ui.available_width() - width) / 2.).max(0.);
    ui.horizontal_top(|ui| {
        ui.add_space(gutter);
        ui.allocate_ui_with_layout(Vec2::new(width, 0.), Layout::top_down(Align::Min), |ui| {
            ui.set_width(width);
            contents(ui);
        });
    });
}
