#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use anyhow::Result;
use deeptutor_desktop::{config::Config, local_web::LocalWeb};
use tauri::Manager;
fn main() -> Result<()> {
    let config = Config::load()?;
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(config.cpu_workers)
        .enable_all()
        .build()?;
    let running = runtime.block_on(LocalWeb::start(config.clone()))?;
    let service = running.state.service.clone();
    let listener = runtime.block_on(tokio::net::TcpListener::bind((
        "127.0.0.1",
        config.bridge_port,
    )));
    match listener {
        Ok(listener) => {
            running
                .state
                .mcp_listening
                .store(true, std::sync::atomic::Ordering::Relaxed);
            runtime.spawn(async move {
                let _ = axum::serve(listener, deeptutor_desktop::transport::router(service)).await;
            });
        }
        Err(error) => {
            *running.state.mcp_error.lock().unwrap() = Some(format!(
                "Local MCP bridge could not bind port {}: {error}",
                config.bridge_port
            ));
        }
    }
    if std::env::args().any(|a| a == "--headless-ui") {
        println!(
            "{}",
            serde_json::json!({"url":running.bootstrap_url,"version":env!("CARGO_PKG_VERSION")})
        );
        runtime.block_on(std::future::pending::<()>());
        return Ok(());
    }
    let start: url::Url = running.bootstrap_url.parse()?;
    let origin = running.url.clone();
    let popup_origin = origin.clone();
    tauri::Builder::default()
        .setup(move |app| {
            let popup_handle = app.handle().clone();
            tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::External(start.clone()),
            )
            .title("DeepPartner")
            .disable_drag_drop_handler()
            .inner_size(1280., 850.)
            .min_inner_size(720., 560.)
            .on_navigation(move |url| {
                if url.origin().ascii_serialization() == origin {
                    return true;
                }
                if matches!(url.scheme(), "http" | "https") {
                    let _ = open::that_detached(url.as_str());
                }
                false
            })
            .on_new_window(move |url, _| {
                if url.origin().ascii_serialization() == popup_origin {
                    if let Some(window) = popup_handle.get_webview_window("main") {
                        let _ = window.navigate(url);
                    }
                } else if matches!(url.scheme(), "http" | "https") {
                    let _ = open::that_detached(url.as_str());
                }
                tauri::webview::NewWindowResponse::Deny
            })
            .on_download(|_, event| {
                if let tauri::webview::DownloadEvent::Requested { destination, .. } = event {
                    let name = destination
                        .file_name()
                        .and_then(|n| n.to_str())
                        .unwrap_or("download");
                    if let Some(path) = rfd::FileDialog::new().set_file_name(name).save_file() {
                        *destination = path;
                    } else {
                        return false;
                    }
                }
                true
            })
            .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())?;
    runtime.block_on(running.state.close());
    Ok(())
}
