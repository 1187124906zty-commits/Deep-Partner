//! Native forms generated from the existing backend contracts, not web pages.
use serde_json::{Value, json};
use std::sync::OnceLock;

pub fn contract() -> &'static Value {
    static CONTRACT: OnceLock<Value> = OnceLock::new();
    CONTRACT.get_or_init(|| {
        serde_json::from_str(include_str!("../assets/backend-openapi.json")).unwrap()
    })
}
pub fn resolve(value: &Value) -> Value {
    if let Some(reference) = value["$ref"].as_str() {
        return contract()
            .pointer(reference.trim_start_matches('#'))
            .cloned()
            .unwrap_or_else(|| json!({}));
    }
    if let Some(variants) = value["anyOf"].as_array() {
        return variants
            .iter()
            .find(|v| v["type"] != "null")
            .map(resolve)
            .unwrap_or_else(|| json!({}));
    }
    value.clone()
}
pub fn expand_local_refs(schema: &Value) -> Value {
    fn visit(value: &Value, root: &Value, depth: usize) -> Value {
        if depth > 16 {
            return json!({});
        }
        if let Some(reference) = value["$ref"].as_str() {
            let target = if reference.starts_with("#/$defs/") {
                root.pointer(reference.trim_start_matches('#'))
            } else {
                contract().pointer(reference.trim_start_matches('#'))
            };
            return target
                .map(|v| visit(v, root, depth + 1))
                .unwrap_or_else(|| json!({}));
        }
        match value {
            Value::Object(object) => Value::Object(
                object
                    .iter()
                    .map(|(k, v)| (k.clone(), visit(v, root, depth + 1)))
                    .collect(),
            ),
            Value::Array(array) => {
                Value::Array(array.iter().map(|v| visit(v, root, depth + 1)).collect())
            }
            _ => value.clone(),
        }
    }
    visit(schema, schema, 0)
}
pub fn body_schema(path: &str, method: &str) -> Value {
    let operation = &contract()["paths"][path][method.to_lowercase()];
    let content = &operation["requestBody"]["content"];
    resolve(
        content
            .get("application/json")
            .or_else(|| content.get("multipart/form-data"))
            .and_then(|v| v.get("schema"))
            .unwrap_or(&Value::Null),
    )
}
pub fn default_value(schema: &Value) -> Value {
    let schema = resolve(schema);
    if let Some(value) = schema.get("default") {
        return value.clone();
    }
    if let Some(options) = schema["enum"].as_array() {
        return options.first().cloned().unwrap_or(Value::Null);
    }
    match schema["type"].as_str() {
        Some("object") => {
            let mut object = serde_json::Map::new();
            if let Some(properties) = schema["properties"].as_object() {
                for (name, property) in properties {
                    object.insert(name.clone(), default_value(property));
                }
            }
            Value::Object(object)
        }
        Some("array") => json!([]),
        Some("boolean") => json!(false),
        Some("integer" | "number") => schema.get("minimum").cloned().unwrap_or(json!(0)),
        _ => json!(""),
    }
}
pub fn prepare_body(schema: &Value, value: &Value) -> Value {
    let schema = resolve(schema);
    if schema["type"] == "object" {
        if schema["properties"].as_object().is_none() {
            return value.clone();
        }
        let required = schema["required"].as_array().cloned().unwrap_or_default();
        let mut out = serde_json::Map::new();
        if let Some(properties) = schema["properties"].as_object() {
            for (name, property) in properties {
                let Some(v) = value.get(name) else {
                    continue;
                };
                if !required.contains(&json!(name))
                    && (v.is_null()
                        || v.as_str() == Some("")
                        || v.as_array().is_some_and(Vec::is_empty))
                {
                    continue;
                }
                out.insert(name.clone(), prepare_body(property, v));
            }
        }
        return Value::Object(out);
    }
    value.clone()
}
pub fn extract_rows(value: &Value) -> Vec<Value> {
    if let Some(array) = value.as_array() {
        return array.clone();
    }
    for key in [
        "items",
        "books",
        "materials",
        "workspaces",
        "notebooks",
        "documents",
        "cards",
        "topics",
        "entries",
        "courses",
        "partners",
        "groups",
        "connections",
        "personas",
        "skills",
        "servers",
        "apps",
        "devices",
        "requests",
        "users",
        "sessions",
        "favorites",
        "records",
        "sources",
        "results",
        "tools",
        "docs",
    ] {
        if let Some(array) = value[key].as_array() {
            return array.clone();
        }
        if let Some(object) = value[key].as_object() {
            return object
                .iter()
                .map(|(id, v)| {
                    let mut v = v.clone();
                    if let Some(o) = v.as_object_mut() {
                        o.entry("id").or_insert(json!(id));
                    }
                    v
                })
                .collect();
        }
    }
    Vec::new()
}
pub fn row_title(value: &Value) -> String {
    [
        "display_name",
        "title",
        "name",
        "username",
        "model_name",
        "filename",
        "question",
        "label",
        "key",
        "id",
        "book_id",
        "material_id",
    ]
    .into_iter()
    .find_map(|k| value[k].as_str().filter(|s| !s.is_empty()))
    .unwrap_or("未命名")
    .into()
}
pub fn row_id(value: &Value) -> String {
    [
        "id",
        "book_id",
        "material_id",
        "workspace_id",
        "notebook_id",
        "doc_id",
        "path_id",
        "session_id",
        "partner_id",
        "name",
        "username",
        "resource_id",
        "key",
    ]
    .into_iter()
    .find_map(|k| {
        value[k]
            .as_str()
            .map(str::to_owned)
            .or_else(|| value[k].as_i64().map(|n| n.to_string()))
    })
    .unwrap_or_default()
}
pub fn label(key: &str) -> &str {
    match key {
        "name" => "名称",
        "title" => "标题",
        "description" => "说明",
        "content" => "内容",
        "goal" => "学习目标",
        "user_intent" => "学习需求",
        "source_refs" => "来源材料",
        "knowledge_bases" => "知识库",
        "language" => "语言",
        "depth" => "深度",
        "email" => "联系邮箱",
        "reason" => "自我介绍与使用目的",
        "username" => "用户名",
        "password" => "密码",
        "note" => "备注",
        "due_date" => "截止日期",
        "status" => "状态",
        "question" => "题目",
        "correct_answer" => "正确答案",
        "explanation" => "解析",
        "text" => "文字",
        "prompt" => "要求",
        "body" => "正文",
        "url" => "网址",
        "urls" => "网址列表",
        "color" => "颜色",
        "icon" => "图标",
        "content_workspace_id" | "workspace_id" => "工作区",
        "model" => "模型",
        "provider" => "提供方",
        "api_key" => "密钥",
        "base_url" => "服务地址",
        "timeout" => "超时时间",
        "enabled" => "启用",
        "tags" => "标签",
        "blocks" => "文档块",
        "sources" => "资料来源",
        "must_cover" => "必须覆盖的知识",
        "modules" => "模块",
        "query" => "查询",
        "limit" => "数量",
        "offset" => "起始位置",
        "name_request" => "设备名称",
        _ => key,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn local_capability_outline_refs_remain_editable() {
        let schema = json!({"$defs":{"Item":{"type":"object","properties":{"title":{"type":"string"}}}},"type":"object","properties":{"outline":{"type":"array","items":{"$ref":"#/$defs/Item"}}}});
        let expanded = expand_local_refs(&schema);
        assert_eq!(
            expanded["properties"]["outline"]["items"]["properties"]["title"]["type"],
            "string"
        );
    }
    #[test]
    fn registration_matches_live_contract() {
        let s = body_schema("/api/registration/requests", "post");
        assert_eq!(s["properties"]["reason"]["minLength"], 5);
        assert_eq!(s["required"].as_array().unwrap().len(), 4);
    }
    #[test]
    fn extract_collections_and_omit_optional_empty_values() {
        assert_eq!(extract_rows(&json!({"notebooks":[{"id":"x"}]})).len(), 1);
        let s = json!({"type":"object","properties":{"title":{"type":"string"},"description":{"type":"string"}},"required":["title"]});
        assert_eq!(
            prepare_body(&s, &json!({"title":"hello","description":""})),
            json!({"title":"hello"})
        );
    }
}
