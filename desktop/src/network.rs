//! Apply the same existing proxy rules to HTTP and live WebSocket connections.
use anyhow::{Context,Result,bail};
use hyper_util::client::proxy::matcher::{Intercept,Matcher};
use tokio::io::{AsyncReadExt,AsyncWriteExt};
use tokio::net::TcpStream;
use tokio_tungstenite::{MaybeTlsStream,WebSocketStream,tungstenite::handshake::client::Request};

type Socket=WebSocketStream<MaybeTlsStream<TcpStream>>;

pub async fn connect(request:Request)->Result<Socket>{
    let uri=request.uri().to_string();
    let destination=uri.replacen("wss://","https://",1).replacen("ws://","http://",1).parse()?;
    selected(request,Matcher::from_system().intercept(&destination)).await
}

async fn selected(request:Request,proxy:Option<Intercept>)->Result<Socket>{
    let Some(proxy)=proxy else{return Ok(tokio_tungstenite::connect_async(request).await?.0)};
    if proxy.uri().scheme_str()!=Some("http"){bail!("实时连接需要支持 HTTP CONNECT 的系统代理")}
    let target=request.uri();let host=target.host().context("实时连接地址缺少主机")?;
    let port=target.port_u16().unwrap_or(if target.scheme_str()==Some("wss"){443}else{80});
    let authority=if host.contains(':'){format!("[{host}]:{port}")}else{format!("{host}:{port}")};
    let mut socket=TcpStream::connect((proxy.uri().host().context("系统代理缺少主机")?,proxy.uri().port_u16().unwrap_or(80))).await?;
    socket.set_nodelay(true)?;
    let mut tunnel=format!("CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n");
    if let Some(auth)=proxy.basic_auth(){tunnel.push_str("Proxy-Authorization: ");tunnel.push_str(auth.to_str()?);tunnel.push_str("\r\n")}
    tunnel.push_str("\r\n");socket.write_all(tunnel.as_bytes()).await?;
    let mut response=Vec::new();
    while !response.ends_with(b"\r\n\r\n"){
        if response.len()>=8192{bail!("系统代理返回的连接响应过长")}
        response.push(socket.read_u8().await?);
    }
    let status=std::str::from_utf8(&response)?.lines().next().unwrap_or("");
    if status.split_whitespace().nth(1)!=Some("200"){bail!("系统代理未能建立实时连接")}
    Ok(tokio_tungstenite::client_async_tls_with_config(request,socket,None,None).await?.0)
}

#[cfg(test)]
mod tests{
    use super::*;
    use futures_util::{SinkExt,StreamExt};
    use tokio_tungstenite::tungstenite::{Message,client::IntoClientRequest};

    #[tokio::test]
    async fn live_connection_uses_proxy_without_leaking_the_session_cookie_in_connect(){
        let listener=tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();let port=listener.local_addr().unwrap().port();
        let server=tokio::spawn(async move{
            let(mut stream,_)=listener.accept().await.unwrap();let mut header=Vec::new();
            while !header.ends_with(b"\r\n\r\n"){header.push(stream.read_u8().await.unwrap())}
            let text=String::from_utf8(header).unwrap();assert!(text.starts_with("CONNECT example.invalid:80 HTTP/1.1"));assert!(!text.contains("Cookie:"));
            stream.write_all(b"HTTP/1.1 200 Connection Established\r\n\r\n").await.unwrap();
            let mut websocket=tokio_tungstenite::accept_async(stream).await.unwrap();
            assert_eq!(websocket.next().await.unwrap().unwrap().into_text().unwrap(),"progress-probe");websocket.send(Message::Text("ready".into())).await.unwrap();
        });
        let matcher=Matcher::builder().http(format!("http://127.0.0.1:{port}")).build();
        let mut request="ws://example.invalid/events".into_client_request().unwrap();request.headers_mut().insert("Cookie","private-session".parse().unwrap());
        let mut socket=selected(request,matcher.intercept(&"http://example.invalid/events".parse().unwrap())).await.unwrap();
        socket.send(Message::Text("progress-probe".into())).await.unwrap();assert_eq!(socket.next().await.unwrap().unwrap().into_text().unwrap(),"ready");server.await.unwrap();
    }
}
