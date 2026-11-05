//! Restore the owner's already-paired ScanSci worker after account login.
use crate::config::Config;
use anyhow::{Context,Result,bail};
use serde::{Deserialize,Serialize};
use serde_json::{Value,json};
use std::{path::PathBuf,process::{Child,Command,Stdio},sync::Mutex,time::{SystemTime,UNIX_EPOCH}};

#[derive(Clone,Debug,Serialize,Deserialize)]
pub struct DownloadRuntime {
    pub owner:String,
    pub python:PathBuf,
    pub device_config:PathBuf,
    pub data_dir:PathBuf,
}

#[derive(Default)]
pub struct DownloadWorker { child:Mutex<Option<Child>> }

impl DownloadWorker {
    pub fn status(&self,config:&Config)->Value {
        let Some(runtime)=&config.download_worker else{return json!({"configured":false,"running":false})};
        let status=std::fs::read(runtime.device_config.with_extension("status.json")).ok()
            .and_then(|bytes|serde_json::from_slice::<Value>(&bytes).ok()).unwrap_or_else(||json!({}));
        let fresh=SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64()-status["heartbeat"].as_f64().unwrap_or(0.0)<45.0;
        json!({"configured":true,"running":fresh,"state":status["state"],"phase":status["phase"],"job_id":status["job_id"],"error":status["error"],"pid":status["pid"]})
    }

    pub fn ensure(&self,config:&Config,owner:&str)->Result<Value> {
        let Some(runtime)=&config.download_worker else{return Ok(self.status(config))};
        if runtime.owner!=owner{return Ok(json!({"configured":false,"running":false}))}
        let mut child=self.child.lock().unwrap();
        if let Some(process)=child.as_mut() {
            if process.try_wait()?.is_none(){
                // Windows virtualenv launchers have a different PID from Python.
                // Once the worker reports, expose its own PID consistently.
                let status=self.status(config);
                if status["running"]==true{return Ok(status)}
                return Ok(json!({"configured":true,"running":true,"state":"starting","pid":process.id()}))
            }
        }
        *child=None;
        let status=self.status(config);
        if status["running"]==true{return Ok(status)}
        let device:Value=serde_json::from_slice(&std::fs::read(&runtime.device_config).context("下载设备配置不存在")?)?;
        if device["origin"].as_str().map(|s|s.trim_end_matches('/'))!=Some(config.server_url.trim_end_matches('/')) {bail!("下载设备配置属于另一个服务")}
        if !runtime.python.is_file(){bail!("ScanSci Python 环境不存在")}
        let folder=crate::config::data_dir().join("downloads");std::fs::create_dir_all(&folder)?;
        let script=folder.join("download_worker.py");let source=include_str!("../assets/download_worker.py");
        if std::fs::read_to_string(&script).ok().as_deref()!=Some(source){std::fs::write(&script,source)?}
        let stdout=std::fs::OpenOptions::new().append(true).create(true).open(folder.join("worker.stdout.log"))?;
        let stderr=std::fs::OpenOptions::new().append(true).create(true).open(folder.join("worker.stderr.log"))?;
        let mut command=Command::new(&runtime.python);
        command.args(["-X","utf8","-u"]).arg(&script).arg("--config").arg(&runtime.device_config)
            .env("SCANSCI_PDF_DATA_DIR",&runtime.data_dir).stdin(Stdio::null()).stdout(stdout).stderr(stderr);
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let process=command.spawn().context("下载设备启动失败")?;let pid=process.id();*child=Some(process);
        Ok(json!({"configured":true,"running":true,"state":"starting","pid":pid}))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unconfigured_and_other_accounts_cannot_start_an_owner_worker(){
        let worker=DownloadWorker::default();let mut config=Config::default();
        assert_eq!(worker.ensure(&config,"user").unwrap()["configured"],false);
        config.download_worker=Some(DownloadRuntime{owner:"owner".into(),python:"missing".into(),device_config:"missing".into(),data_dir:"missing".into()});
        assert_eq!(worker.ensure(&config,"other").unwrap()["configured"],false);
    }
    #[test]
    fn existing_worker_heartbeat_is_reused_without_a_duplicate_process(){
        let dir=tempfile::tempdir().unwrap();let device=dir.path().join("worker.json");
        let heartbeat=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f64();
        std::fs::write(device.with_extension("status.json"),json!({"heartbeat":heartbeat,"state":"idle","pid":123}).to_string()).unwrap();
        let mut config=Config::default();config.download_worker=Some(DownloadRuntime{owner:"owner".into(),python:"unused".into(),device_config:device.clone(),data_dir:dir.path().into()});
        let worker=DownloadWorker::default();assert_eq!(worker.ensure(&config,"owner").unwrap()["pid"],123);
        std::fs::write(device.with_extension("status.json"),json!({"heartbeat":heartbeat-120.,"state":"idle","pid":123}).to_string()).unwrap();
        assert_eq!(worker.status(&config)["running"],false);
        assert!(worker.ensure(&config,"owner").is_err());
    }
}
