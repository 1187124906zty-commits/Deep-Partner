//! Project-bound conversations and deterministic research operations.
use crate::{config::{Config,data_dir},project_cli,remote::{RemoteClient,EventSink}};
use anyhow::{Result,Context,bail};
use clap::Subcommand;
use serde_json::{Value,json};
use std::{path::PathBuf,sync::{Arc,Mutex},io::{self,Write}};
use tokio::sync::mpsc;

#[derive(Subcommand)]
pub enum ChatAction {
    List { #[arg(long)] project:String },
    History { #[arg(long)] project:String, #[arg(long)] session:String, #[arg(long,default_value_t=12)] limit:usize, #[arg(long,default_value_t=0)] offset:usize },
    Send {
        #[arg(long)] project:String,
        #[arg(long)] session:Option<String>,
        #[arg(long,conflicts_with="file")] message:Option<String>,
        #[arg(long)] file:Option<PathBuf>,
        #[arg(long,default_value="chat",value_parser=["chat","code"])] capability:String,
        #[arg(long)] jsonl:bool,
    },
    Resume { #[arg(long)] project:String, #[arg(long)] session:Option<String>, #[arg(long)] jsonl:bool },
    Reply { #[arg(long)] project:String, #[arg(long)] session:String, #[arg(long)] message:String, #[arg(long)] jsonl:bool },
    Stop { #[arg(long)] project:String, #[arg(long)] session:String, #[arg(long)] jsonl:bool },
}
#[derive(Subcommand)]
pub enum WorkflowAction {
    Routes { #[arg(long)] project:String, #[arg(long)] kind:Option<String> },
    Run { #[arg(long)] project:String, #[arg(long)] file:PathBuf },
    Status { #[arg(long)] project:String, #[arg(long)] id:String },
    Resume { #[arg(long)] project:String, #[arg(long)] id:String },
    Reply { #[arg(long)] project:String, #[arg(long)] id:String, #[arg(long)] file:PathBuf },
    Record { #[arg(long)] project:String, #[arg(long)] file:PathBuf },
    Graph { #[arg(long)] project:String, #[arg(long,default_value_t=80)] limit:usize, #[arg(long,default_value_t=0)] offset:usize },
}
fn encoded(value:&str)->String { url::form_urlencoded::byte_serialize(value.as_bytes()).collect() }
fn input(file:&PathBuf)->Result<Value> { Ok(serde_json::from_slice(&std::fs::read(file)?)?) }
async fn bind(query:&str)->Result<(Config,Arc<RemoteClient>,Value)> {
    let config=Config::load()?;let remote=project_cli::authenticated(&config).await?;
    let rows=remote.get(&config,"/research/api/projects").await?;
    let project=project_cli::resolve_project(&rows,query)?;
    Ok((config,remote,project))
}
pub async fn workflow(action:WorkflowAction)->Result<()> {
    let query=match &action { WorkflowAction::Routes{project,..}|WorkflowAction::Run{project,..}|WorkflowAction::Status{project,..}|WorkflowAction::Resume{project,..}|WorkflowAction::Reply{project,..}|WorkflowAction::Record{project,..}|WorkflowAction::Graph{project,..}=>project };
    let (mut config,remote,project)=bind(query).await?;
    let prefix=format!("/research/api/projects/{}/research-flow",project["id"].as_str().context("项目 ID 无效")?);
    let (method,path,body)=match action {
        WorkflowAction::Routes{kind,..}=>("GET",format!("{prefix}/routes?kind={}",encoded(kind.as_deref().unwrap_or(""))),None),
        WorkflowAction::Run{file,..}=>{
            let payload=input(&file)?;
            {
                let root=std::env::var_os("CODEX_HOME").map(PathBuf::from).unwrap_or_else(||PathBuf::from(std::env::var_os("USERPROFILE").unwrap_or_default()).join(".codex"));
                let script=root.join("skills/deep-partner-research/scripts/workflow_runtime.py");
                let python=PathBuf::from(std::env::var_os("USERPROFILE").unwrap_or_default()).join("DeepTutor/.venv/Scripts/python.exe");
                if script.is_file() && python.is_file(){
                    let mut command=tokio::process::Command::new(python);command.arg("-X").arg("utf8").arg(script).arg("--kind").arg(payload["kind"].as_str().unwrap_or("survey"));
                    #[cfg(windows)] {command.creation_flags(0x08000000);}
                    match command.output().await {Ok(output)=>eprintln!("{}",String::from_utf8_lossy(&output.stdout).trim()),Err(error)=>eprintln!("Scholar 启动未完成，保留备用检索：{error}")}
                }
            }
            if matches!(payload["kind"].as_str(),Some("survey"|"download")) {
                let profile=remote.get(&config,"/api/auth/profile").await?;
                let owner=profile["id"].as_str().context("账户身份无效")?;
                if config.download_worker.is_none(){
                    let user=PathBuf::from(std::env::var_os("USERPROFILE").unwrap_or_default());
                    let root=std::env::var_os("CODEX_HOME").map(PathBuf::from).unwrap_or_else(||user.join(".codex"));
                    let script=root.join("skills/deep-partner-research/scripts/download_runtime.py");let python=user.join("DeepTutor/.venv/Scripts/python.exe");
                    if script.is_file()&&python.is_file(){
                        let output=tokio::process::Command::new(python).args(["-X","utf8"]).arg(script).output().await?;
                        if output.status.success(){
                            let mut found:Value=serde_json::from_slice(&output.stdout)?;
                            if found["configured"]==true&&found["origin"].as_str().map(|s|s.trim_end_matches('/'))==Some(config.server_url.trim_end_matches('/')){
                                let devices=remote.get(&config,"/research/api/download-worker/devices").await?;
                                if devices["devices"].as_array().is_some_and(|rows|rows.iter().any(|d|d["id"]==found["device_id"]&&d["revoked_at"].is_null())){
                                    found["runtime"]["owner"]=json!(owner);config.download_worker=Some(serde_json::from_value(found["runtime"].clone())?);config.save()?;
                                }
                            }
                        }
                    }
                }
                let worker=crate::download_worker::DownloadWorker::default().ensure(&config,owner)?;
                eprintln!("{}",json!({"download_worker":worker}));
            }
            ("POST",format!("{prefix}/runs"),Some(payload))
        },
        WorkflowAction::Status{id,..}=>("GET",format!("{prefix}/runs/{}",encoded(&id)),None),
        WorkflowAction::Resume{id,..}=>("POST",format!("{prefix}/runs/{}/resume",encoded(&id)),Some(json!({}))),
        WorkflowAction::Reply{id,file,..}=>("POST",format!("{prefix}/runs/{}/reply",encoded(&id)),Some(input(&file)?)),
        WorkflowAction::Record{file,..}=>("POST",format!("{prefix}/records"),Some(input(&file)?)),
        WorkflowAction::Graph{limit,offset,..}=>("GET",format!("{prefix}/graph?limit={}&offset={offset}",limit.clamp(1,200)),None),
    };
    println!("{}",remote.api(&config,method,&path,body,true).await?);Ok(())
}
fn checkpoint(pid:&str)->PathBuf { data_dir().join("cli-chats").join(format!("{pid}.json")) }
fn write_checkpoint(path:&PathBuf,value:&Value)->Result<()> {
    std::fs::create_dir_all(path.parent().unwrap())?;
    let pending=path.with_extension("pending");std::fs::write(&pending,serde_json::to_vec_pretty(value)?)?;
    std::fs::rename(pending,path)?;Ok(())
}
async fn session(remote:&RemoteClient,config:&Config,workspace:&str,id:&str)->Result<Value> {
    let value=remote.get(config,&format!("/api/sessions/{}?dt_workspace={}",encoded(id),encoded(workspace))).await?;
    if value["workspace_id"].as_str().or(value["preferences"]["workspace_id"].as_str()).is_some_and(|s|s!=workspace) { bail!("会话不属于指定项目") }
    let actual=value["session_id"].as_str().or(value["id"].as_str()).context("会话响应缺少 ID")?;
    if actual!=id { bail!("会话身份不一致") }
    Ok(value)
}
pub async fn chat(action:ChatAction)->Result<()> {
    let query=match &action { ChatAction::List{project}|ChatAction::History{project,..}|ChatAction::Send{project,..}|ChatAction::Resume{project,..}|ChatAction::Reply{project,..}|ChatAction::Stop{project,..}=>project };
    let (config,remote,project)=bind(query).await?;
    let workspace=project["native_id"].as_str().filter(|s|!s.is_empty()).context("项目未绑定工作区")?;
    let pid=project["id"].as_str().context("项目 ID 无效")?;
    match &action {
        ChatAction::List{..}=>{println!("{}",remote.get(&config,&format!("/api/sessions?dt_workspace={}&workspace_id={}&limit=50",encoded(workspace),encoded(workspace))).await?);return Ok(())},
        ChatAction::History{session:id,limit,offset,..}=>{
            let mut value=session(&remote,&config,workspace,id).await?;
            let messages=value["messages"].as_array().cloned().unwrap_or_default();let total=messages.len();let end=total.saturating_sub(*offset);let start=end.saturating_sub((*limit).clamp(1,200));
            value["messages"]=json!(messages[start..end].iter().map(|message|{let mut result=serde_json::Map::new();for key in ["id","role","content","created_at","timestamp"]{if let Some(v)=message.get(key){result.insert(key.into(),v.clone());}}Value::Object(result)}).collect::<Vec<_>>());
            value["total_messages"]=json!(total);value["next_offset"]=if start>0{json!(offset+end-start)}else{Value::Null};
            println!("{value}");return Ok(())
        },_=>(),
    }
    let path=checkpoint(pid);let saved=if path.is_file(){input(&path)?}else{json!({})};
    let expected_cancel=matches!(&action,ChatAction::Stop{..});
    let (request,jsonl,initial_session,control)=match action {
        ChatAction::Send{session:id,message,file,capability,jsonl,..}=>{
            if let Some(id)=&id {let previous=session(&remote,&config,workspace,id).await?;if previous["active_turn_id"].as_str().is_some_and(|s|!s.is_empty()){bail!("会话已有正在生成的回答，请用 dp chat resume 恢复")}}
            let text=if let Some(file)=file{std::fs::read_to_string(file)?}else{message.context("请提供 --message 或 --file")?};
            if text.trim().is_empty()||text.len()>100000{bail!("消息长度应为 1 至 100000 字节")}
            remote.refresh_models(&config).await?;
            let mut req=json!({"type":"start_turn","protocol_version":"2.0","workspace_id":workspace,"content":text,"capability":capability,"language":"zh","client_submission_id":uuid::Uuid::new_v4().to_string(),"llm_selection":remote.choice(&config,false)?,"knowledge_bases":project["config"]["knowledge_bases"].as_array().cloned().unwrap_or_default()});
            if let Some(id)=&id{req["session_id"]=json!(id)};(req,jsonl,id.unwrap_or_default(),None)
        },
        ChatAction::Resume{session:id,jsonl,..}=>{
            let id=id.or_else(||saved["session_id"].as_str().map(str::to_owned)).context("请提供 --session，或先发送一次消息")?;
            let previous=session(&remote,&config,workspace,&id).await?;
            let turn=previous["active_turn_id"].as_str().or_else(||if saved["session_id"]==id{saved["turn_id"].as_str()}else{None}).context("没有可恢复的执行，使用 history 读取已保存回复")?;
            let seq=if saved["turn_id"]==turn{saved["seq"].as_u64().unwrap_or(0)}else{0};
            (json!({"type":"resume_from","protocol_version":"2.0","workspace_id":workspace,"turn_id":turn,"seq":seq}),jsonl,id,None)
        },
        ChatAction::Reply{session:id,message,jsonl,..}=>{
            let previous=session(&remote,&config,workspace,&id).await?;let turn=previous["active_turn_id"].as_str().filter(|s|!s.is_empty()).context("没有正在等待回复的执行")?;
            (json!({"type":"resume_from","protocol_version":"2.0","workspace_id":workspace,"turn_id":turn,"seq":0}),jsonl,id,Some(json!({"type":"submit_user_reply","text":message})))
        },
        ChatAction::Stop{session:id,jsonl,..}=>{
            let previous=session(&remote,&config,workspace,&id).await?;let turn=previous["active_turn_id"].as_str().filter(|s|!s.is_empty()).context("没有正在运行的执行")?;
            (json!({"type":"resume_from","protocol_version":"2.0","workspace_id":workspace,"turn_id":turn,"seq":0}),jsonl,id,Some(json!({"type":"cancel_turn"})))
        },_=>unreachable!(),
    };
    let state=Arc::new(Mutex::new(json!({"project_id":pid,"workspace_id":workspace,"server":config.server_url,"session_id":initial_session,"turn_id":request["turn_id"],"seq":request["seq"].as_u64().unwrap_or(0)})));
    let (sender,mut events)=mpsc::unbounded_channel::<Value>();
    let sink:EventSink=Arc::new(move|value|{let _=sender.send(value);});
    let client=remote.clone();let conf=config.clone();let req=request.clone();
    let (_controls,rx)=mpsc::channel(4);
    if let Some(control)=control{_controls.send(control).await?;}
    let mut task=tokio::spawn(async move{client.stream(&sink,&conf,req,rx).await});
    let mut failed=None;let mut completed=false;
    loop {
        tokio::select! {
            event=events.recv()=>{if let Some(event)=event {display(&event,jsonl,&state,&path,&mut completed,&mut failed)?}},
            result=&mut task=>{result??;while let Ok(event)=events.try_recv(){display(&event,jsonl,&state,&path,&mut completed,&mut failed)?}break},
        }
    }
    if !jsonl{println!()}
    if let Some(error)=failed{if !expected_cancel{bail!("{error}")}}
    if !completed{bail!("对话订阅已结束，尚未收到完成事件；可用 resume 继续")}
    let state=state.lock().unwrap().clone();
    if let Some(id)=state["session_id"].as_str().filter(|s|!s.is_empty()) {
        let receipt=remote.api(&config,"POST",&format!("/research/api/projects/{pid}/research-flow/conversation"),Some(json!({"session_id":id,"turn_id":state["turn_id"]})),true).await;
        match receipt {Ok(value)=>{if jsonl{println!("{}",json!({"type":"project_receipt","data":value}))}else{eprintln!("会话及研究记录已保存到项目：{}",project["name"])}},Err(error)=>{eprintln!("回复已保存；项目材料整理未完成：{error}");return Err(error)}}
    }
    Ok(())
}
fn display(event:&Value,jsonl:bool,state:&Arc<Mutex<Value>>,path:&PathBuf,completed:&mut bool,failed:&mut Option<String>)->Result<()> {
    let kind=event["type"].as_str().unwrap_or("");
    {let mut value=state.lock().unwrap();for key in ["session_id","turn_id"]{if event[key].as_str().is_some_and(|s|!s.is_empty()){value[key]=event[key].clone()}}if event["seq"].as_u64().unwrap_or(0)>value["seq"].as_u64().unwrap_or(0){value["seq"]=event["seq"].clone()}write_checkpoint(path,&value)?;}
    if jsonl{println!("{event}")}else if matches!(kind,"content"|"token"|"chunk"|"content_delta"|"text_delta"){print!("{}",event["content"].as_str().or(event["delta"].as_str()).or(event["text"].as_str()).unwrap_or(""));io::stdout().flush()?}
    else if kind=="desktop_reconnecting"{eprintln!("正在恢复对话连接…")}
    if matches!(kind,"protocol_error"|"error"|"turn_failed"){*failed=Some(event["message"].as_str().or(event["content"].as_str()).unwrap_or("对话执行失败").to_owned())}
    if kind=="done"{*completed=true;let status=event["status"].as_str().or(event["metadata"]["status"].as_str());if status.is_some_and(|s|matches!(s,"failed"|"cancelled"|"interrupted")){*failed=Some(format!("执行状态：{}",status.unwrap()))}}
    Ok(())
}
