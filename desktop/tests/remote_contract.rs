//! Exercise the native client's actual HTTP/cookie/WebSocket implementation locally.
use axum::{
    Json, Router,
    extract::{
        State, WebSocketUpgrade,
        ws::{Message, WebSocket},
    },
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use deeptutor_desktop::{
    config::Config,
    remote::{EventSink, RemoteClient},
};
use serde_json::{Value, json};
use std::sync::{Arc, Mutex};
#[derive(Clone, Default)]
struct Seen(Arc<Mutex<Vec<Value>>>);
async fn login(headers: HeaderMap, Json(body): Json<Value>) -> Response {
    assert_eq!(
        headers["origin"].to_str().unwrap().split(':').next(),
        Some("http")
    );
    assert_eq!(body, json!({"username":"alice","password":"password123"}));
    (
        [("set-cookie", "dt_token=test-session; HttpOnly; Path=/")],
        Json(json!({"ok":true})),
    )
        .into_response()
}
async fn signup(State(seen): State<Seen>, Json(body): Json<Value>) -> Response {
    assert_eq!(body["username"], "new-user");
    assert_eq!(body["email"], "n@example.com");
    assert!(body["reason"].as_str().unwrap().chars().count() >= 5);
    seen.0.lock().unwrap().push(body);
    (
        StatusCode::ACCEPTED,
        Json(json!({"message":"注册申请已提交"})),
    )
        .into_response()
}
async fn options(headers: HeaderMap) -> Json<Value> {
    assert!(
        headers["cookie"]
            .to_str()
            .unwrap()
            .contains("dt_token=test-session")
    );
    Json(
        json!({"options":[{"profile_id":"study","model_id":"sol","model":"gpt-6.1-sol","is_active_default":true},{"profile_id":"study","model_id":"terra","model":"gpt-6.1-terra"}]}),
    )
}
async fn upgrade(headers: HeaderMap, State(seen): State<Seen>, ws: WebSocketUpgrade) -> Response {
    assert!(
        headers["cookie"]
            .to_str()
            .unwrap()
            .contains("dt_token=test-session")
    );
    ws.on_upgrade(move |socket| exchange(socket, seen))
}
async fn exchange(mut socket: WebSocket, seen: Seen) {
    let Some(Ok(Message::Text(raw))) = socket.recv().await else {
        panic!("missing start_turn")
    };
    let request: Value = serde_json::from_str(&raw).unwrap();
    assert_eq!(request["type"], "start_turn");
    assert_eq!(request["protocol_version"], "2.0");
    assert!(!request["llm_selection"].get("reasoning").is_some());
    seen.0.lock().unwrap().push(request.clone());
    let sid = request["session_id"].as_str().unwrap_or("same-session");
    socket.send(Message::Text(json!({"type":"content","content":"原生流式回答","session_id":sid,"turn_id":"turn-1","seq":1}).to_string().into())).await.unwrap();
    if request["capability"] == "ask_questions" {
        socket.send(Message::Text(json!({"type":"wait_for_input","content":"请选择研究范围","turn_id":"turn-1","seq":2}).to_string().into())).await.unwrap();
        loop {
            let Some(Ok(Message::Text(raw))) = socket.recv().await else {
                panic!("missing reply")
            };
            let reply: Value = serde_json::from_str(&raw).unwrap();
            if reply["type"] == "ping" {
                continue;
            }
            assert_eq!(reply["type"], "submit_user_reply");
            assert_eq!(reply["text"], "本地研究");
            assert_eq!(reply["turn_id"], "turn-1");
            assert!(reply["command_id"].is_string());
            seen.0.lock().unwrap().push(reply);
            break;
        }
    }
    socket
        .send(Message::Text(
            json!({"type":"done","turn_id":"turn-1","seq":3})
                .to_string()
                .into(),
        ))
        .await
        .unwrap();
    // Keep the upgraded connection alive until the client closes it after done.
    // Dropping a TCP socket with an unread heartbeat can reset it on Windows.
    while let Some(message) = socket.recv().await {
        if matches!(message, Ok(Message::Close(_)) | Err(_)) {
            break;
        }
    }
}
#[tokio::test]
async fn native_auth_signup_modes_reply_and_same_session() {
    let seen = Seen::default();
    let app = Router::new()
        .route("/api/auth/login", post(login))
        .route("/api/registration/requests", post(signup))
        .route("/api/settings/llm-options", get(options))
        .route(
            "/api/sessions",
            get(|| async { Json(json!({"sessions":[]})) }),
        )
        .route("/api/knowledge-bases", get(|| async { Json(json!([])) }))
        .route("/ws", get(upgrade))
        .with_state(seen.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    let config = Config {
        server_url: format!("http://127.0.0.1:{port}"),
        ..Default::default()
    };
    let remote = RemoteClient::new();
    remote.api(&config,"POST","/api/registration/requests",Some(json!({"username":"new-user","password":"password123","email":"n@example.com","reason":"用于学习和研究"})),false).await.unwrap();
    remote.login(&config, "alice", "password123").await.unwrap();
    remote.bootstrap(&config).await.unwrap();
    assert_eq!(
        remote.choice(&config, false).unwrap(),
        json!({"profile_id":"study","model_id":"sol"})
    );
    assert_eq!(
        remote.choice(&config, true).unwrap(),
        json!({"profile_id":"study","model_id":"terra"})
    );
    for capability in ["chat", "code", "ask_questions"] {
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        let sink: EventSink = Arc::new(move |v| {
            let _ = tx.send(v);
        });
        remote
            .send(
                sink,
                tokio::runtime::Handle::current(),
                config.clone(),
                json!({"content":"测试任务","capability":capability,"session_id":"same-session"}),
            )
            .await
            .unwrap();
        loop {
            let event = tokio::time::timeout(std::time::Duration::from_secs(5), rx.recv())
                .await
                .unwrap()
                .unwrap();
            if event["type"] == "wait_for_input" {
                remote
                    .control(json!({"type":"submit_user_reply","text":"本地研究"}))
                    .await
                    .unwrap();
            }
            if event["type"] == "desktop_error" {
                panic!("{}", event["content"]);
            }
            if event["type"] == "desktop_finished" {
                break;
            }
        }
    }
    let events = seen.0.lock().unwrap();
    let turns = events
        .iter()
        .filter(|v| v["type"] == "start_turn")
        .collect::<Vec<_>>();
    assert_eq!(turns.len(), 3);
    assert!(turns.iter().all(|v| v["session_id"] == "same-session"));
    assert_eq!(turns[1]["capability"], "code");
    drop(events);
    server.abort();
}
