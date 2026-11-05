use anyhow::{Context, Result, bail};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Value, json};
use std::{path::PathBuf, time::Duration};
use tokio::{
    process::{Child, Command},
    sync::Mutex,
};
use tokio_tungstenite::tungstenite::Message;

pub struct Browser {
    port: u16,
    client: reqwest::Client,
    process: Mutex<Option<Child>>,
    actions: Mutex<()>,
}

impl Browser {
    pub fn new(port: u16) -> Self {
        Self {
            port,
            client: reqwest::Client::builder()
                .no_proxy()
                .timeout(Duration::from_secs(15))
                .build()
                .unwrap(),
            process: Mutex::new(None),
            actions: Mutex::new(()),
        }
    }
    async fn ensure(&self) -> Result<()> {
        let mut process = self.process.lock().await;
        if let Some(child) = process.as_mut() {
            if child.try_wait()?.is_none() {
                return Ok(());
            }
            *process = None;
        }
        if tokio::net::TcpStream::connect(("127.0.0.1", self.port))
            .await
            .is_ok()
        {
            bail!("浏览器工具端口被占用；请在设置中换一个端口后重启");
        }
        let executable = browser_executable().context("未找到 Microsoft Edge 或 Chrome")?;
        let profile = crate::config::data_dir().join("browser-profile");
        let mut command = Command::new(executable);
        command.args([
            format!("--remote-debugging-port={}", self.port),
            format!("--user-data-dir={}", profile.display()),
            "--no-first-run".into(),
            "--no-default-browser-check".into(),
            "about:blank".into(),
        ]);
        #[cfg(windows)]
        command.creation_flags(0x08000000);
        command
            .kill_on_drop(true)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null());
        *process = Some(command.spawn()?);
        for _ in 0..80 {
            if self
                .client
                .get(format!("http://127.0.0.1:{}/json/version", self.port))
                .send()
                .await
                .is_ok()
            {
                return Ok(());
            }
            if process.as_mut().unwrap().try_wait()?.is_some() {
                bail!("工具浏览器启动后退出，请查看浏览器安装状态");
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        bail!("工具浏览器启动超时")
    }
    async fn target(&self) -> Result<String> {
        self.ensure().await?;
        let targets: Vec<Value> = self
            .client
            .get(format!("http://127.0.0.1:{}/json/list", self.port))
            .send()
            .await?
            .json()
            .await?;
        targets
            .iter()
            .find(|t| t["type"] == "page")
            .and_then(|t| t["webSocketDebuggerUrl"].as_str())
            .map(str::to_owned)
            .context("浏览器没有可操作的网页标签")
    }
    async fn cdp(&self, method: &str, params: Value) -> Result<Value> {
        let target = self.target().await?;
        let (mut ws, _) = tokio_tungstenite::connect_async(&target).await?;
        ws.send(Message::Text(
            json!({"id":1,"method":method,"params":params})
                .to_string()
                .into(),
        ))
        .await?;
        let response = tokio::time::timeout(Duration::from_secs(15), async {
            while let Some(message) = ws.next().await {
                let message = message?;
                if let Message::Text(text) = message {
                    let response: Value = serde_json::from_str(&text)?;
                    if response["id"] == 1 {
                        return Ok::<_, anyhow::Error>(response);
                    }
                }
            }
            bail!("浏览器连接已关闭")
        })
        .await
        .context("浏览器操作超时")??;
        if let Some(error) = response.get("error") {
            bail!("浏览器返回：{error}");
        }
        Ok(response["result"].clone())
    }
    async fn evaluate(&self, expression: &str) -> Result<Value> {
        let result = self
            .cdp(
                "Runtime.evaluate",
                json!({"expression":expression,"returnByValue":true,"awaitPromise":true}),
            )
            .await?;
        if result.get("exceptionDetails").is_some() {
            bail!("网页操作失败：{}", result["exceptionDetails"]);
        }
        Ok(result["result"]["value"].clone())
    }
    pub async fn open(&self, address: &str) -> Result<Value> {
        validate_url(address)?;
        let _serial = self.actions.lock().await;
        let result = self.cdp("Page.navigate", json!({"url": address})).await?;
        if let Some(error) = result.get("errorText") {
            bail!("网页未打开：{error}");
        }
        let mut ready = false;
        for _ in 0..50 {
            if let Ok(value) = self
                .evaluate("({ready:document.readyState,url:location.href})")
                .await
            {
                if value["url"] != "about:blank" && value["ready"] != "loading" {
                    ready = true;
                    break;
                }
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        Ok(json!({"opened":address,"loaded":ready,"note":"页面内容请用 browser_snapshot 读取"}))
    }
    pub async fn snapshot(&self) -> Result<Value> {
        let _serial = self.actions.lock().await;
        self.evaluate(r#"(() => {
          const nodes = [...document.querySelectorAll('a[href],button,input,textarea,select,[role="button"]')]
            .filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').slice(0,150);
          return {url:location.href,title:document.title,text:document.body.innerText.slice(0,24000),elements:nodes.map((e,i)=>{
            const ref='dt-'+i; e.setAttribute('data-dtd-target',ref);
            return {ref,tag:e.tagName.toLowerCase(),role:e.getAttribute('role'),text:(e.innerText||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').slice(0,180),type:e.getAttribute('type'),value:e.type==='password'?'[password]':e.value,href:e.href};
          })};
        })()"#).await
    }
    pub async fn click(&self, target: &str) -> Result<Value> {
        let _serial = self.actions.lock().await;
        let selector = target_selector(target);
        let expression = format!(
            "(() => {{ const e=document.querySelector({}); if(!e) throw Error('没有找到元素，请先重新读取页面'); e.scrollIntoView({{block:'center'}}); e.click(); return {{clicked:true}}; }})()",
            serde_json::to_string(&selector)?
        );
        self.evaluate(&expression).await
    }
    pub async fn type_text(&self, target: &str, text: &str) -> Result<Value> {
        let _serial = self.actions.lock().await;
        if text.len() > 20000 {
            bail!("单次输入最多 20000 字节");
        }
        let expression = format!(
            r#"(() => {{
          const e=document.querySelector({selector}); if(!e) throw Error('没有找到输入框'); e.focus();
          if(e.isContentEditable) {{ e.textContent={text}; }} else {{
            const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
            const setter=Object.getOwnPropertyDescriptor(proto,'value').set; setter.call(e,{text});
          }}
          e.dispatchEvent(new Event('input',{{bubbles:true}})); e.dispatchEvent(new Event('change',{{bubbles:true}}));
          return {{typed:true}};
        }})()"#,
            selector = serde_json::to_string(&target_selector(target))?,
            text = serde_json::to_string(text)?
        );
        self.evaluate(&expression).await
    }
    pub async fn screenshot(&self) -> Result<String> {
        let _serial = self.actions.lock().await;
        let result = self
            .cdp(
                "Page.captureScreenshot",
                json!({"format":"png","captureBeyondViewport":false}),
            )
            .await?;
        result["data"]
            .as_str()
            .map(str::to_owned)
            .context("浏览器截图为空")
    }
    pub async fn close(&self) {
        let _serial = self.actions.lock().await;
        {
            let mut process = self.process.lock().await;
            let running = if let Some(child) = process.as_mut() {
                matches!(child.try_wait(), Ok(None))
            } else {
                false
            };
            if !running {
                *process = None;
                return;
            }
        }
        let _ = self.cdp("Browser.close", json!({})).await;
        if let Some(mut process) = self.process.lock().await.take() {
            let _ = process.kill().await;
        }
    }
}

pub fn validate_url(address: &str) -> Result<()> {
    let url = url::Url::parse(address)?;
    if !matches!(url.scheme(), "http" | "https")
        || !url.username().is_empty()
        || url.password().is_some()
    {
        bail!("只支持不含凭据的 HTTP/HTTPS 网页地址");
    }
    Ok(())
}
fn target_selector(target: &str) -> String {
    if target
        .strip_prefix("dt-")
        .is_some_and(|n| !n.is_empty() && n.chars().all(|c| c.is_ascii_digit()))
    {
        format!("[data-dtd-target='{target}']")
    } else {
        target.to_owned()
    }
}
fn browser_executable() -> Option<PathBuf> {
    ["PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"]
        .into_iter()
        .filter_map(std::env::var_os)
        .flat_map(|root| {
            [
                "Microsoft/Edge/Application/msedge.exe",
                "Google/Chrome/Application/chrome.exe",
            ]
            .map(|suffix| PathBuf::from(&root).join(suffix))
        })
        .find(|p| p.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_non_web_navigation_and_encodes_element_refs() {
        assert!(validate_url("https://example.org").is_ok());
        assert!(validate_url("file:///C:/Windows/win.ini").is_err());
        assert!(validate_url("javascript:alert(1)").is_err());
        assert_eq!(target_selector("dt-12"), "[data-dtd-target='dt-12']");
        assert_eq!(target_selector("#search"), "#search");
    }
}
