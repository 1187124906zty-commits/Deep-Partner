use serde_json::{Value, json};

#[derive(Clone, Copy, Debug)]
pub struct Page {
    pub id: &'static str,
    pub group: &'static str,
    pub title: &'static str,
    pub subtitle: &'static str,
    pub list: &'static str,
    pub prefixes: &'static [&'static str],
    pub create: Option<&'static str>,
    pub detail: Option<&'static str>,
}

pub const PAGES: &[Page] = &[
    Page {
        id: "learning",
        group: "学习",
        title: "学习",
        subtitle: "阅读、书籍与掌握路径",
        list: "",
        prefixes: &[],
        create: None,
        detail: None,
    },
    Page {
        id: "resources",
        group: "资料",
        title: "全部资料",
        subtitle: "对话与资料",
        list: "",
        prefixes: &[],
        create: None,
        detail: None,
    },
    Page {
        id: "personalization",
        group: "个性化",
        title: "全部个性化",
        subtitle: "为你的工作方式配置资源",
        list: "",
        prefixes: &[],
        create: None,
        detail: None,
    },
    Page {
        id: "calendar",
        group: "工作台",
        title: "日历",
        subtitle: "学习与任务安排",
        list: "/api/task-board",
        prefixes: &["/api/task-board"],
        create: Some("/api/task-board/cards"),
        detail: None,
    },
    Page {
        id: "home",
        group: "工作台",
        title: "概览",
        subtitle: "继续学习、管理资料，或从一个新问题开始。",
        list: "/api/dashboard/learning-index",
        prefixes: &["/api/dashboard"],
        create: None,
        detail: None,
    },
    Page {
        id: "chat",
        group: "工作台",
        title: "对话",
        subtitle: "聊天、研究、代码和解题共用同一会话。",
        list: "/api/sessions?all_workspaces=true&limit=100",
        prefixes: &["/api/sessions", "/api/capabilities", "/api/tools"],
        create: None,
        detail: None,
    },
    Page {
        id: "computer",
        group: "工作台",
        title: "电脑助手",
        subtitle: "GPT-6.1 Terra · 本机文件、浏览器和桌面操作",
        list: "",
        prefixes: &[],
        create: None,
        detail: None,
    },
    Page {
        id: "partners",
        group: "工作台",
        title: "学习伙伴",
        subtitle: "和你的伙伴交流，管理人格、群组与渠道。",
        list: "/api/partners",
        prefixes: &["/api/partners", "/api/partner-groups"],
        create: Some("/api/partners"),
        detail: Some("/api/partners/{partner_id}"),
    },
    Page {
        id: "books",
        group: "学习",
        title: "书籍",
        subtitle: "从你的资料构建书籍，阅读、练习并持续扩展。",
        list: "/api/books",
        prefixes: &["/api/books"],
        create: Some("/api/books"),
        detail: Some("/api/books/{book_id}"),
    },
    Page {
        id: "reading",
        group: "学习",
        title: "沉浸阅读",
        subtitle: "阅读文档、网页、音频和视频，按原文位置与助手讨论。",
        list: "/api/reading/library/materials",
        prefixes: &["/api/reading", "/api/video-learning"],
        create: Some("/api/reading/workspaces"),
        detail: Some("/api/reading/materials/{material_id}"),
    },
    Page {
        id: "mastery",
        group: "学习",
        title: "掌握路径",
        subtitle: "创建学习目标，沿知识图谱学习和复习。",
        list: "/api/mastery-paths/topics",
        prefixes: &["/api/mastery-paths"],
        create: Some("/api/mastery-paths/topics"),
        detail: Some("/api/mastery-paths/topics/{path_id}"),
    },
    Page {
        id: "practice",
        group: "学习",
        title: "练习与题库",
        subtitle: "管理题目、答题记录和间隔练习。",
        list: "/api/question-notebook/entries",
        prefixes: &[
            "/api/question-notebook",
            "/api/questions",
            "/api/quiz-judge",
        ],
        create: Some("/api/question-notebook/entries/upsert"),
        detail: Some("/api/question-notebook/entries/{entry_id}"),
    },
    Page {
        id: "library",
        group: "资料",
        title: "知识库",
        subtitle: "导入、索引和检索你的原始资料。",
        list: "/api/knowledge-bases?resource_library=true",
        prefixes: &["/api/knowledge-bases"],
        create: Some("/api/knowledge-bases"),
        detail: Some("/api/knowledge-bases/{kb_name}"),
    },
    Page {
        id: "notebooks",
        group: "资料",
        title: "笔记本",
        subtitle: "保留问题、阅读摘录、研究结论和学习记录。",
        list: "/api/notebooks",
        prefixes: &["/api/notebooks", "/api/note-documents"],
        create: Some("/api/notebooks"),
        detail: Some("/api/notebooks/{notebook_id}"),
    },
    Page {
        id: "files",
        group: "资料",
        title: "本机文件",
        subtitle: "访问共享文件夹，导入资料与导出结果。",
        list: "",
        prefixes: &["/api/library"],
        create: None,
        detail: None,
    },
    Page {
        id: "journal",
        group: "资料",
        title: "学习记录",
        subtitle: "回顾问题、学习状态和最近的进展。",
        list: "/api/learning-journal",
        prefixes: &["/api/learning-journal"],
        create: None,
        detail: None,
    },
    Page {
        id: "board",
        group: "创作与任务",
        title: "任务看板",
        subtitle: "按状态组织任务、备注与截止日期。",
        list: "/api/task-board",
        prefixes: &["/api/task-board"],
        create: Some("/api/task-board/cards"),
        detail: None,
    },
    Page {
        id: "writer",
        group: "创作与任务",
        title: "协同写作",
        subtitle: "编辑文档，基于资料改写、扩展和精简。",
        list: "/api/documents",
        prefixes: &["/api/documents"],
        create: Some("/api/documents"),
        detail: Some("/api/documents/{doc_id}"),
    },
    Page {
        id: "agents",
        group: "个性化",
        title: "我的智能体",
        subtitle: "连接 Codex、Claude Code 和其他已有智能体。",
        list: "/api/subagents/connections",
        prefixes: &["/api/subagents", "/api/imports"],
        create: Some("/api/subagents/connections"),
        detail: None,
    },
    Page {
        id: "personas",
        group: "个性化",
        title: "人格",
        subtitle: "为不同学习与研究任务保存人格和指引。",
        list: "/api/personas",
        prefixes: &["/api/personas"],
        create: Some("/api/personas"),
        detail: Some("/api/personas/{name}"),
    },
    Page {
        id: "skills",
        group: "个性化",
        title: "技能",
        subtitle: "阅读、导入和管理可复用的工作方法。",
        list: "/api/skills/list",
        prefixes: &["/api/skills", "/api/plugins"],
        create: Some("/api/skills/create"),
        detail: Some("/api/skills/{name}"),
    },
    Page {
        id: "mcp",
        group: "个性化",
        title: "MCP 服务",
        subtitle: "连接外部工具并管理工作区资源分配。",
        list: "/api/space/mcp/servers",
        prefixes: &["/api/space/mcp", "/api/settings/mcp"],
        create: None,
        detail: None,
    },
    Page {
        id: "cli",
        group: "个性化",
        title: "CLI 应用",
        subtitle: "管理安装在服务端的命令行工具。",
        list: "/api/space/cli-apps/catalog",
        prefixes: &["/api/space/cli-apps"],
        create: None,
        detail: None,
    },
    Page {
        id: "memory",
        group: "个性化",
        title: "记忆",
        subtitle: "检查、编辑和整理可以回查的学习记忆。",
        list: "/api/memory/overview",
        prefixes: &["/api/memory"],
        create: None,
        detail: None,
    },
    Page {
        id: "workspace",
        group: "管理",
        title: "工作区",
        subtitle: "管理话题、文件、资源和会话归属。",
        list: "/api/settings/workspace/registrations",
        prefixes: &["/api/settings/workspace"],
        create: Some("/api/settings/workspace/registrations"),
        detail: None,
    },
    Page {
        id: "settings",
        group: "管理",
        title: "设置",
        subtitle: "模型、提供方、搜索、语音、解析、工具和外观。",
        list: "/api/settings/readiness",
        prefixes: &["/api/settings", "/api/voice", "/api/visualizers"],
        create: None,
        detail: None,
    },
    Page {
        id: "profile",
        group: "管理",
        title: "账户与设备",
        subtitle: "账户信息、可信设备与登录管理。",
        list: "/api/auth/profile",
        prefixes: &["/api/auth/profile", "/api/quick-login"],
        create: None,
        detail: None,
    },
    Page {
        id: "users",
        group: "管理",
        title: "用户与申请",
        subtitle: "查看用户、注册申请与已有权限。",
        list: "/api/registration/requests",
        prefixes: &["/api/registration", "/api/auth/users", "/api/multi-user"],
        create: None,
        detail: None,
    },
];
pub fn page(id: &str) -> Page {
    *PAGES.iter().find(|p| p.id == id).unwrap_or(&PAGES[0])
}
pub fn mode_label(id: &str) -> &str {
    match id {
        "chat" => "聊天",
        "code" => "代码",
        "deep_research" => "研究",
        "deep_solve" => "解题",
        "deep_question" => "出题",
        "ask_questions" => "追问",
        "immersive_reading" => "阅读",
        "mastery_path" => "掌握式学习",
        "visualize" => "可视化",
        "math_animator" => "数学动画",
        "video_lesson" => "视频课程",
        "audio_overview" => "音频概览",
        "course_study" => "课程学习",
        _ => id,
    }
}
pub fn operation_title(path: &str, method: &str, operation: &Value) -> String {
    let tail = path.rsplit('/').next().unwrap_or("");
    let action = match tail {
        "confirm-proposal" => "确认书籍方案",
        "confirm-spine" => "确认章节大纲",
        "compile-page" => "生成章节",
        "resume" => "继续生成",
        "pause" => "暂停生成",
        "rebuild" => "重新生成",
        "export" => "导出",
        "import-urls" => "导入网址",
        "position" => "阅读位置",
        "bookmarks" => "书签",
        "annotations" => "批注",
        "read-aloud" => "朗读",
        "draft" => "生成草稿",
        "map" => "知识图谱",
        "review-settings" => "复习设置",
        "start" => "启动",
        "stop" => "停止",
        "settings" => "偏好设置",
        "test" => "测试连接",
        "install" => "安装",
        "enabled-tools" => "启用工具",
        "catalog" => "提供方与模型",
        "ui" => "外观与语言",
        "remember" => "记住此设备",
        "devices" => "可信设备",
        "name" => "重命名",
        "document-parsing" => "文档解析",
        "chat-attachments" => "附件设置",
        "usage" => "用量统计",
        "network" => "网络",
        "resources" => "资源分配",
        _ => "",
    };
    if !action.is_empty() {
        return action.into();
    }
    let raw = operation["summary"].as_str().unwrap_or(tail);
    let verb = match method {
        "get" => "查看",
        "post" => "新建 / 执行",
        "put" | "patch" => "编辑",
        "delete" => "删除",
        _ => "执行",
    };
    format!("{verb} · {raw}")
}
pub fn operations(page: Page) -> Vec<(String, String, Value)> {
    let mut result = Vec::new();
    if let Some(paths) = crate::schema::contract()["paths"].as_object() {
        for (path, methods) in paths {
            if page
                .prefixes
                .iter()
                .any(|prefix| path == prefix || path.starts_with(&format!("{prefix}/")))
            {
                if let Some(methods) = methods.as_object() {
                    for (method, operation) in methods {
                        if ["get", "post", "put", "patch", "delete"].contains(&method.as_str()) {
                            result.push((path.clone(), method.clone(), operation.clone()));
                        }
                    }
                }
            }
        }
    }
    result
}
pub fn fill_path(template: &str, row: &Value) -> String {
    let mut path = template.to_owned();
    while let Some(start) = path.find('{') {
        let Some(end) = path[start..].find('}').map(|i| i + start) else {
            break;
        };
        let name = &path[start + 1..end];
        let value = row
            .get(name)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .unwrap_or_else(|| crate::schema::row_id(row));
        if value.is_empty() {
            break;
        }
        let value = url::form_urlencoded::byte_serialize(value.as_bytes()).collect::<String>();
        path.replace_range(start..=end, &value);
    }
    path
}

pub fn registration_body(username: &str, password: &str, email: &str, reason: &str) -> Value {
    json!({"username":username,"password":password,"email":email,"reason":reason})
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn key_features_have_pages_and_real_routes() {
        for id in [
            "books",
            "reading",
            "mastery",
            "practice",
            "notebooks",
            "writer",
            "board",
            "memory",
            "skills",
            "mcp",
            "cli",
            "users",
        ] {
            let p = page(id);
            assert!(!p.list.is_empty());
            assert!(!operations(p).is_empty(), "missing {id}");
        }
        assert_eq!(mode_label("code"), "代码");
    }
}
