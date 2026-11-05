use crate::schema::{self, resolve};
use egui::{Color32, RichText, Ui};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::PathBuf};

pub struct ActionForm {
    pub id: egui::Id,
    pub title: String,
    pub template: String,
    pub method: String,
    pub schema: Value,
    pub value: Value,
    pub parameters: Vec<Value>,
    pub params: BTreeMap<String, String>,
    pub files: BTreeMap<String, PathBuf>,
    pub multipart: bool,
    pub error: String,
}
impl ActionForm {
    pub fn new(path: &str, method: &str, row: &Value) -> Self {
        let op = &schema::contract()["paths"][path][method];
        let schema = schema::body_schema(path, method);
        let mut value = schema::default_value(&schema);
        if let (Some(properties), Some(object)) =
            (schema["properties"].as_object(), value.as_object_mut())
        {
            for (name, _) in properties {
                if let Some(v) = row.get(name) {
                    object.insert(name.clone(), v.clone());
                }
            }
        }
        let parameters = op["parameters"]
            .as_array()
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|p| p["in"] == "path" || p["in"] == "query")
            .collect::<Vec<_>>();
        let mut params = BTreeMap::new();
        for parameter in &parameters {
            let name = parameter["name"].as_str().unwrap_or("");
            let v = row
                .get(name)
                .and_then(Value::as_str)
                .map(str::to_owned)
                .unwrap_or_else(|| {
                    if parameter["in"] == "path" {
                        schema::row_id(row)
                    } else {
                        parameter["schema"]["default"].as_str().unwrap_or("").into()
                    }
                });
            params.insert(name.into(), v);
        }
        Self {
            id: egui::Id::unique(uuid::Uuid::new_v4()),
            title: super::pages::operation_title(path, method, op),
            template: path.into(),
            method: method.into(),
            schema,
            value,
            parameters,
            params,
            files: BTreeMap::new(),
            multipart: op["requestBody"]["content"]
                .get("multipart/form-data")
                .is_some(),
            error: String::new(),
        }
    }
    pub fn path(&self) -> String {
        let mut path = self.template.clone();
        let mut query = Vec::new();
        for p in &self.parameters {
            let name = p["name"].as_str().unwrap_or("");
            let value = self.params.get(name).map(String::as_str).unwrap_or("");
            if p["in"] == "path" {
                path = path.replace(
                    &format!("{{{name}}}"),
                    &url::form_urlencoded::byte_serialize(value.as_bytes()).collect::<String>(),
                );
            } else if p["in"] == "query" && !value.is_empty() {
                query.push((name.to_string(), value.to_string()));
            }
        }
        if !query.is_empty() {
            let q = url::form_urlencoded::Serializer::new(String::new())
                .extend_pairs(query)
                .finish();
            path.push(if path.contains('?') { '&' } else { '?' });
            path.push_str(&q);
        }
        path
    }
    pub fn draw(&mut self, ui: &mut Ui) -> bool {
        ui.data_mut(|d| d.insert_temp(egui::Id::unique("invalid-native-form"), false));
        let mut submit = false;
        ui.heading(&self.title);
        ui.add_space(12.);
        if self.method == "delete" {
            ui.colored_label(
                Color32::from_rgb(175, 71, 66),
                "此操作将删除所选项目，请确认对象后提交。",
            );
        }
        for parameter in &self.parameters {
            let name = parameter["name"].as_str().unwrap_or("");
            ui.horizontal(|ui| {
                ui.label(schema::label(name));
                let value = self.params.entry(name.into()).or_default();
                ui.add(egui::TextEdit::singleline(value).desired_width(340.));
            });
        }
        ui.add_space(8.);
        if self.multipart {
            if let Some(properties) = self.schema["properties"].as_object() {
                for (name, property) in properties {
                    let property = resolve(property);
                    let is_file = property.get("contentMediaType").is_some()
                        || property["format"] == "binary"
                        || property["items"]["format"] == "binary"
                        || property["items"].get("contentMediaType").is_some();
                    if is_file {
                        ui.horizontal(|ui| {
                            ui.label(schema::label(name));
                            if ui.button("选择文件…").clicked() {
                                if let Some(path) = rfd::FileDialog::new().pick_file() {
                                    self.files.insert(name.clone(), path);
                                }
                            }
                            if let Some(path) = self.files.get(name) {
                                ui.small(path.file_name().unwrap_or_default().to_string_lossy());
                            }
                        });
                    } else {
                        if let Some(object) = self.value.as_object_mut() {
                            let v = object
                                .entry(name.clone())
                                .or_insert_with(|| schema::default_value(&property));
                            field(ui, name, &property, v, 0);
                        }
                    }
                }
            }
        } else {
            field(ui, "", &self.schema, &mut self.value, 0);
        }
        if !self.error.is_empty() {
            ui.colored_label(Color32::from_rgb(170, 65, 60), &self.error);
        }
        ui.add_space(16.);
        ui.horizontal(|ui| {
            let text = if self.method == "get" {
                "加载"
            } else if self.method == "delete" {
                "确认删除"
            } else {
                "提交"
            };
            let valid = !ui.data(|d| {
                d.get_temp::<bool>(egui::Id::unique("invalid-native-form"))
                    .unwrap_or(false)
            });
            if ui
                .add_enabled_ui(valid, |ui| {
                    ui.add_sized(
                        [100., 36.],
                        egui::Button::new(
                            RichText::new(text).color(super::theme::current(ui).on_accent),
                        )
                        .fill(super::theme::current(ui).accent),
                    )
                })
                .inner
                .clicked()
            {
                submit = true;
            }
        });
        submit
    }
}

pub fn field(ui: &mut Ui, name: &str, schema: &Value, value: &mut Value, depth: usize) {
    if depth > 7 {
        return;
    }
    let schema = resolve(schema);
    let label = schema::label(name);
    if let Some(options) = schema["enum"].as_array() {
        ui.horizontal(|ui| {
            if !name.is_empty() {
                ui.label(label);
            }
            egui::ComboBox::from_id_salt((ui.scope_id(), name))
                .selected_text(value.as_str().unwrap_or("选择"))
                .show_ui(ui, |ui| {
                    for option in options {
                        ui.selectable_value(
                            value,
                            option.clone(),
                            option
                                .as_str()
                                .map(str::to_owned)
                                .unwrap_or_else(|| option.to_string()),
                        );
                    }
                });
        });
        return;
    }
    match schema["type"].as_str() {
        Some("object") => {
            if !value.is_object() {
                *value = json!({});
            }
            if let Some(properties) = schema["properties"].as_object() {
                for (key, property) in properties {
                    let v = value
                        .as_object_mut()
                        .unwrap()
                        .entry(key.clone())
                        .or_insert_with(|| crate::schema::default_value(property));
                    ui.push_id(key, |ui| {
                        field(ui, key, property, v, depth + 1);
                    });
                }
            } else {
                let canonical = serde_json::to_string_pretty(value).unwrap_or_default();
                let key = ui.scope_id().with(("json-draft", name));
                let mut text = ui
                    .data(|d| d.get_temp::<(String, String)>(key))
                    .filter(|(last, _)| last == &canonical)
                    .map(|(_, text)| text)
                    .unwrap_or(canonical);
                ui.collapsing(
                    if name.is_empty() {
                        "扩展字段"
                    } else {
                        label
                    },
                    |ui| {
                        let r = ui.add(
                            egui::TextEdit::multiline(&mut text)
                                .code_editor()
                                .desired_rows(5)
                                .desired_width(f32::INFINITY),
                        );
                        if r.changed() {
                            if let Ok(parsed) = serde_json::from_str::<Value>(&text) {
                                if parsed.is_object() {
                                    *value = parsed;
                                }
                            }
                        }
                        if serde_json::from_str::<Value>(&text).is_err() {
                            ui.colored_label(Color32::from_rgb(174, 66, 61), "JSON 格式尚未完成");
                            ui.data_mut(|d| {
                                d.insert_temp(egui::Id::unique("invalid-native-form"), true)
                            });
                        }
                    },
                );
                if !serde_json::from_str::<Value>(&text).is_ok_and(|v| v.is_object()) {
                    ui.data_mut(|d| d.insert_temp(egui::Id::unique("invalid-native-form"), true));
                }
                ui.data_mut(|d| {
                    d.insert_temp(
                        key,
                        (
                            serde_json::to_string_pretty(value).unwrap_or_default(),
                            text,
                        ),
                    )
                });
            }
        }
        Some("array") => {
            if !value.is_array() {
                *value = json!([]);
            }
            let items = resolve(&schema["items"]);
            let array = value.as_array_mut().unwrap();
            ui.collapsing(format!("{}  ({})", label, array.len()), |ui| {
                let mut remove = None;
                for (index, item) in array.iter_mut().enumerate() {
                    ui.push_id(index, |ui| {
                        ui.horizontal(|ui| {
                            ui.small(format!("{}", index + 1));
                            if ui.small_button("移除").clicked() {
                                remove = Some(index);
                            }
                        });
                        field(ui, "", &items, item, depth + 1);
                    });
                    ui.add_space(7.);
                }
                if let Some(index) = remove {
                    array.remove(index);
                }
                if ui.small_button("＋ 添加一项").clicked() {
                    array.push(crate::schema::default_value(&items));
                }
            });
        }
        Some("boolean") => {
            let mut v = value.as_bool().unwrap_or(false);
            if ui.checkbox(&mut v, label).changed() {
                *value = json!(v);
            }
        }
        Some("number" | "integer") => {
            let mut v = value.as_f64().unwrap_or(0.);
            ui.horizontal(|ui| {
                ui.label(label);
                let mut widget = egui::DragValue::new(&mut v);
                if let Some(min) = schema["minimum"].as_f64() {
                    widget = widget.range(min..=schema["maximum"].as_f64().unwrap_or(1e12));
                }
                if ui.add(widget).changed() {
                    *value = if schema["type"] == "integer" {
                        json!(v as i64)
                    } else {
                        json!(v)
                    };
                }
            });
        }
        _ => {
            let mut v = value.as_str().map(str::to_owned).unwrap_or_default();
            let multiline = matches!(
                name,
                "content"
                    | "description"
                    | "reason"
                    | "text"
                    | "prompt"
                    | "body"
                    | "instruction"
                    | "selected_text"
                    | "goal"
                    | "note"
                    | "output"
                    | "user_intent"
                    | "system_prompt"
                    | "soul"
            ) || v.contains('\n');
            if !name.is_empty() {
                ui.label(RichText::new(label).size(13.));
            }
            let widget = if multiline {
                egui::TextEdit::multiline(&mut v).desired_rows(5)
            } else {
                egui::TextEdit::singleline(&mut v).password(
                    name.contains("password")
                        || name.contains("api_key")
                        || name.contains("secret"),
                )
            };
            let response = ui.add(widget.desired_width(f32::INFINITY));
            if response.changed() {
                *value = json!(v);
            }
            if let Some(description) = schema["description"].as_str().filter(|s| s.len() < 160) {
                response.on_hover_text(description);
            }
            ui.add_space(9.);
        }
    }
}
