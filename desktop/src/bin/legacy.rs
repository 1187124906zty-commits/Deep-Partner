#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use deeptutor_desktop::{
    config::{Config, data_dir},
    desktop::DesktopApp,
    service::DesktopService,
    tunnel::Tunnel,
};
fn token() -> anyhow::Result<String> {
    let path = data_dir().join("bridge-token");
    if path.exists() {
        let token = std::fs::read_to_string(&path)?;
        if token.trim().len() >= 32 {
            return Ok(token.trim().into());
        }
    }
    let token = format!(
        "{}{}",
        uuid::Uuid::new_v4().simple(),
        uuid::Uuid::new_v4().simple()
    );
    std::fs::write(path, &token)?;
    Ok(token)
}
fn main() -> anyhow::Result<()> {
    let config = Config::load()?;
    config.save()?;
    let service = DesktopService::new(config.clone(), token()?);
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(config.cpu_workers)
        .thread_name("deeptutor-io")
        .enable_all()
        .build()?;
    if std::env::args().any(|a| a == "--verify-api") {
        use std::io::Read;
        let mut input = String::new();
        std::io::stdin().read_to_string(&mut input)?;
        let login: serde_json::Value = serde_json::from_str(&input)?;
        let client = deeptutor_desktop::remote::RemoteClient::new();
        let report=runtime.block_on(async{
            client.login(&config,login["username"].as_str().unwrap_or(""),login["password"].as_str().unwrap_or("")).await?;
            let bootstrap=client.bootstrap(&config).await?;let capabilities=client.get(&config,"/api/capabilities/registered").await?;
            let mut checks=Vec::new();for page in deeptutor_desktop::desktop::pages::PAGES{if page.list.is_empty(){continue;}let result=client.get(&config,page.list).await;checks.push(serde_json::json!({"page":page.id,"ok":result.is_ok(),"error":result.err().map(|e|e.to_string())}));}
            Ok::<_,anyhow::Error>(serde_json::json!({"native_http_login":true,"cookie_session":true,"models":bootstrap["models"]["options"].as_array().map(Vec::len),"capabilities":capabilities["capabilities"].as_array().map(Vec::len),"pages":checks}))
        })?;
        println!("{}", serde_json::to_string(&report)?);
        return Ok(());
    }
    let listener = runtime.block_on(tokio::net::TcpListener::bind((
        "127.0.0.1",
        config.bridge_port,
    )));
    if let Ok(listener) = listener {
        let router = deeptutor_desktop::transport::router(service.clone());
        runtime.spawn(async move {
            let _ = axum::serve(listener, router).await;
        });
    }
    if std::env::args().any(|a| a == "--bridge-only") {
        println!(
            "Deep partner bridge ready on 127.0.0.1:{}",
            config.bridge_port
        );
        runtime.block_on(std::future::pending::<()>());
        return Ok(());
    }
    if let Some(index) = std::env::args().position(|a| a == "--benchmark-ui") {
        let path = std::env::args()
            .nth(index + 1)
            .unwrap_or_else(|| "native-performance.json".into());
        let context = egui::Context::default();
        let mut app = DesktopApp::new(
            context,
            config,
            service,
            Tunnel::new(),
            runtime.handle().clone(),
        );
        let report = app.benchmark();
        std::fs::write(path, serde_json::to_vec_pretty(&report)?)?;
        println!("{report}");
        return Ok(());
    }
    use eframe::egui_wgpu::{WgpuConfiguration, WgpuSetupCreateNew};
    let mut setup = WgpuSetupCreateNew::without_display_handle();
    setup.instance_descriptor.backends = wgpu::Backends::DX12;
    setup
        .instance_descriptor
        .backend_options
        .dx12
        .shader_compiler = wgpu::Dx12Compiler::Fxc;
    setup.power_preference = wgpu::PowerPreference::LowPower;
    let icon = image::load_from_memory(include_bytes!("../../icons/icon.png"))?.into_rgba8();
    let icon = egui::IconData {
        width: icon.width(),
        height: icon.height(),
        rgba: icon.into_raw(),
    };
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("Deep partner")
            .with_icon(icon)
            .with_inner_size([880., 700.])
            .with_min_inner_size([480., 560.]),
        centered: true,
        renderer: eframe::Renderer::Wgpu,
        wgpu_options: WgpuConfiguration {
            wgpu_setup: setup.into(),
            ..Default::default()
        },
        ..Default::default()
    };
    let tunnel = Tunnel::new();
    let exit_tunnel = tunnel.clone();
    let exit_service = service.clone();
    let handle = runtime.handle().clone();
    let args = std::env::args().collect::<Vec<_>>();
    eframe::run_native(
        "Deep partner",
        options,
        Box::new(move |cc| {
            let mut app = DesktopApp::new(cc.egui_ctx.clone(), config, service, tunnel, handle);
            if let Some(i) = args.iter().position(|a| a == "--capture") {
                if let Some(path) = args.get(i + 1) {
                    let page = args
                        .iter()
                        .position(|a| a == "--preview-page")
                        .and_then(|i| args.get(i + 1))
                        .map(String::as_str);
                    app.enable_capture(path.into(), page);
                }
            }
            Ok(Box::new(app))
        }),
    )
    .map_err(|e| anyhow::anyhow!(e.to_string()))?;
    runtime.block_on(async {
        exit_tunnel.disconnect().await;
        exit_service.browser.close().await;
    });
    Ok(())
}
