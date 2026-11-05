//! Exercises the packaged dp parent/worker boundary without a model provider.
#![cfg(windows)]
use serde_json::Value;
use std::{
    path::Path,
    process::Command,
    time::{Duration, Instant},
};
fn dp(home: &Path, engine: &Path, args: &[&str]) -> Value {
    let output = Command::new(env!("CARGO_BIN_EXE_dp"))
        .env("DEEP_PARTNER_HOME", home)
        .env("DEEP_PARTNER_CODEX", engine)
        .args(args)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}
#[test]
fn detached_worker_survives_requester_and_shares_persistent_status() {
    let temp = tempfile::tempdir().unwrap();
    let script = temp.path().join("engine.ps1");
    std::fs::write(&script,"Write-Output '{\"type\":\"turn.started\"}'; Start-Sleep -Seconds 20; Write-Output '{\"type\":\"turn.completed\"}'").unwrap();
    let shim = temp.path().join("codex-harness.cmd");
    std::fs::write(&shim,format!("@echo off\r\nif \"%~1\"==\"--version\" (echo codex-process-harness 1.0& exit /b 0)\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File \"{}\"\r\n",script.display())).unwrap();
    let home = temp.path().join("profile");
    let job = dp(
        &home,
        &shim,
        &[
            "task",
            "run",
            "--engine",
            "codex",
            "--cwd",
            temp.path().to_str().unwrap(),
            "--prompt",
            "harmless process harness",
            "--json",
        ],
    );
    let id = job["id"].as_str().unwrap();
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let events = dp(&home, &shim, &["task", "events", id]);
        if events["events"]
            .as_array()
            .unwrap()
            .iter()
            .any(|e| e["data"]["type"] == "turn.started")
        {
            break;
        }
        assert!(
            Instant::now() < deadline,
            "detached worker did not produce output: {events}"
        );
        std::thread::sleep(Duration::from_millis(100));
    }
    let status = dp(&home, &shim, &["task", "status", id, "--json"]);
    assert_eq!(status["status"], "running");
    dp(&home, &shim, &["task", "cancel", id]);
    loop {
        let status = dp(&home, &shim, &["task", "status", id, "--json"]);
        if status["status"] == "cancelled" {
            break;
        }
        assert!(
            Instant::now() < deadline,
            "cancel did not complete: {status}"
        );
        std::thread::sleep(Duration::from_millis(100));
    }
}
