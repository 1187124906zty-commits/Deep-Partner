use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub server_url: String,
    pub theme: String,
    pub workspace: PathBuf,
    pub ssh_host: String,
    pub cluster_host: String,
    pub download_worker: Option<crate::download_worker::DownloadRuntime>,
    pub bridge_port: u16,
    pub browser_port: u16,
    pub cpu_workers: usize,
    pub cache_mb: usize,
    pub desktop_control: bool,
    pub computer_model: Option<serde_json::Value>,
    pub learning_model: Option<serde_json::Value>,
}

impl Default for Config {
    fn default() -> Self {
        let cores = std::thread::available_parallelism()
            .map(usize::from)
            .unwrap_or(4);
        Self {
            server_url: "https://tutor.example.invalid".into(),
            theme: "dark".into(),
            workspace: data_dir().join("workspace"),
            ssh_host: "papers-research".into(),
            cluster_host: String::new(),
            download_worker: None,
            bridge_port: 19388,
            browser_port: 19389,
            cpu_workers: cores.saturating_sub(2).clamp(1, 6),
            cache_mb: 32,
            desktop_control: true,
            computer_model: None,
            learning_model: None,
        }
    }
}

pub fn data_dir() -> PathBuf {
    std::env::var_os("DEEP_PARTNER_HOME")
        .or_else(|| std::env::var_os("DEEPTUTOR_DESKTOP_HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_else(|| ".".into()))
                .join("DeepPartner")
        })
}

impl Config {
    pub fn load() -> Result<Self> {
        std::fs::create_dir_all(data_dir())?;
        let path = data_dir().join("config.json");
        if !path.exists()
            && std::env::var_os("DEEP_PARTNER_HOME").is_none()
            && std::env::var_os("DEEPTUTOR_DESKTOP_HOME").is_none()
        {
            if let Some(local) = std::env::var_os("LOCALAPPDATA") {
                let legacy = PathBuf::from(local).join("DeepTutorDesktop");
                for name in ["config.json", "bridge-token", "device-credential"] {
                    let from = legacy.join(name);
                    let to = data_dir().join(name);
                    if from.is_file() && !to.exists() {
                        std::fs::copy(from, to)?;
                    }
                }
            }
        }
        let config: Self = if path.exists() {
            serde_json::from_slice(&std::fs::read(path)?).context("桌面配置无法读取")?
        } else {
            Self::default()
        };
        config.validate()?;
        std::fs::create_dir_all(&config.workspace)?;
        Ok(config)
    }
    pub fn validate(&self) -> Result<()> {
        let url = url::Url::parse(&self.server_url)?;
        if url.scheme() != "https"
            && !(url.scheme() == "http"
                && matches!(url.host_str(), Some("127.0.0.1" | "localhost")))
        {
            bail!("服务地址需要 HTTPS；本机调试可用 HTTP");
        }
        if !url.username().is_empty() || url.password().is_some() {
            bail!("服务地址不能包含登录凭据");
        }
        if self.cpu_workers == 0 || self.cpu_workers > 16 || !(4..=256).contains(&self.cache_mb) {
            bail!("并发或缓存参数超出范围");
        }
        if self.ssh_host.is_empty()
            || self.ssh_host.starts_with('-')
            || !self
                .ssh_host
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || "._-@".contains(c))
        {
            bail!("SSH 主机需要是已有的主机别名");
        }
        if self.bridge_port == 0 || self.browser_port == 0 || self.bridge_port == self.browser_port
        {
            bail!("工具端口配置无效");
        }
        Ok(())
    }
    pub fn save(&self) -> Result<()> {
        self.validate()?;
        std::fs::create_dir_all(&self.workspace)?;
        let path = data_dir().join("config.json");
        let temp = data_dir().join("config.tmp");
        std::fs::write(&temp, serde_json::to_vec_pretty(self)?)?;
        std::fs::rename(temp, path)?;
        Ok(())
    }
}

pub fn workspace_path(root: &Path, relative: &str) -> Result<PathBuf> {
    let canonical_root = root.canonicalize()?;
    let candidate = root.join(relative).canonicalize().context("文件不存在")?;
    if !candidate.starts_with(&canonical_root) {
        bail!("文件不在当前共享文件夹内");
    }
    Ok(candidate)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_escape_and_allows_relative_file() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path().join("shared");
        std::fs::create_dir(&root).unwrap();
        std::fs::write(root.join("ok.txt"), "ok").unwrap();
        std::fs::write(tmp.path().join("outside.txt"), "private").unwrap();
        assert!(workspace_path(&root, "ok.txt").is_ok());
        assert!(workspace_path(&root, "../outside.txt").is_err());
    }
    #[test]
    fn validates_server_and_parallelism() {
        let mut cfg = Config::default();
        assert!(cfg.validate().is_ok());
        cfg.server_url = "javascript:alert(1)".into();
        assert!(cfg.validate().is_err());
        cfg.server_url = "http://127.0.0.1:8787".into();
        assert!(cfg.validate().is_ok());
        cfg.cpu_workers = 0;
        assert!(cfg.validate().is_err());
    }
}
