use crate::service::{DesktopService, tools};
use axum::{
    Json, Router,
    extract::{DefaultBodyLimit, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde_json::{Value, json};
use std::sync::Arc;

pub fn router(service: Arc<DesktopService>) -> Router {
    Router::new()
        .route(
            "/health",
            get(|| async { Json(json!({"service":"Deep partner Desktop","ok":true})) }),
        )
        .route(
            "/test-page",
            get(|| async { axum::response::Html(include_str!("../tests/browser-fixture.html")) }),
        )
        .route(
            "/mcp",
            post(mcp)
                .get(|| async { StatusCode::METHOD_NOT_ALLOWED })
                .delete(|| async { StatusCode::NO_CONTENT }),
        )
        .layer(DefaultBodyLimit::max(4 * 1024 * 1024))
        .with_state(service)
}

async fn mcp(
    State(service): State<Arc<DesktopService>>,
    headers: HeaderMap,
    Json(request): Json<Value>,
) -> Response {
    if headers.get("authorization").and_then(|v| v.to_str().ok())
        != Some(&format!("Bearer {}", service.token))
    {
        return (
            StatusCode::UNAUTHORIZED,
            Json(json!({"error":"unauthorized"})),
        )
            .into_response();
    }
    if let Some(origin) = headers.get("origin").and_then(|v| v.to_str().ok()) {
        if !matches!(origin, "http://tauri.localhost" | "tauri://localhost") {
            return StatusCode::FORBIDDEN.into_response();
        }
    }
    let Some(id) = request.get("id") else {
        return StatusCode::ACCEPTED.into_response();
    };
    let result = match request["method"].as_str().unwrap_or("") {
        "initialize" => {
            json!({"protocolVersion":request["params"]["protocolVersion"].as_str().unwrap_or("2025-06-18"),"capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"deep-partner-desktop","version":env!("CARGO_PKG_VERSION")},"instructions":"Tools run on the user's Windows computer, not the Deep partner server. Read only the selected shared folder. Use browser_snapshot before interacting with browser elements. Tools are enabled by default; the user can pause them in the desktop client."})
        }
        "ping" => json!({}),
        "tools/list" => tools(),
        "tools/call" => {
            let name = request["params"]["name"].as_str().unwrap_or("");
            match service
                .call(
                    name,
                    request["params"]
                        .get("arguments")
                        .cloned()
                        .unwrap_or_else(|| json!({})),
                )
                .await
            {
                Ok(value) if value.get("content").is_some() => value,
                Ok(value) => {
                    json!({"content":[{"type":"text","text":value.to_string()}],"isError":false})
                }
                Err(error) => {
                    json!({"content":[{"type":"text","text":format!("{error:#}")}],"isError":true})
                }
            }
        }
        _ => return Json(
            json!({"jsonrpc":"2.0","id":id,"error":{"code":-32601,"message":"Method not found"}}),
        )
        .into_response(),
    };
    Json(json!({"jsonrpc":"2.0","id":id,"result":result})).into_response()
}
