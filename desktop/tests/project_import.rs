//! The real archive preparer must accept Chinese Windows paths.
#![cfg(windows)]
use deeptutor_desktop::{config::Config,project_import};
#[test]
fn prepares_unicode_folder_without_runtime_or_credentials() {
    let root=tempfile::tempdir().unwrap();
    let source=root.path().join("中文研究目录");
    std::fs::create_dir_all(source.join("node_modules")).unwrap();
    std::fs::write(source.join("模型.py"),b"print(7)\n").unwrap();
    std::fs::write(source.join(".env"),b"private").unwrap();
    std::fs::write(source.join("node_modules/ignored.js"),b"runtime").unwrap();
    // This integration test is the only test in its own process, before any
    // asynchronous runtime or child process has started.
    unsafe {std::env::set_var("DEEP_PARTNER_HOME",root.path().join("profile"));}
    let config=Config {workspace:source.clone(),..Default::default()};
    let receipt=project_import::prepare(&config,&source).unwrap();
    assert_eq!(receipt["files"],1);
    assert_eq!(receipt["bytes"],9);
    assert_eq!(receipt["applied"],false);
    assert!(std::path::Path::new(receipt["bundle"].as_str().unwrap()).is_file());
    assert!(project_import::prepare(&config,root.path()).is_err());
}
