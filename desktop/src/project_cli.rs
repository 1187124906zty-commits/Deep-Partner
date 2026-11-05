//! Project uploads reuse the existing owner-authenticated workbench endpoints.
use crate::{config::{Config, data_dir}, remote::RemoteClient, secure_store};
use anyhow::{Context, Result, bail};
use clap::{Subcommand, ValueEnum};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::BTreeSet, io::{self, Write}, path::{Component, Path, PathBuf}, sync::Arc};

#[derive(Subcommand)]
pub enum ProjectAction {
    /// Create an owned research project and its native conversation workspace.
    Create { #[arg(long)] name:String, #[arg(long)] json:bool },
    /// List the projects of the signed-in account.
    List {
        #[arg(long)]
        json: bool,
    },
    /// Upload files, or a directory with --recursive, to an existing project.
    Upload {
        #[arg(long, help = "Exact project name or project ID")]
        project: String,
        #[arg(required = true, num_args = 1..)]
        files: Vec<PathBuf>,
        #[arg(long)]
        recursive: bool,
        #[arg(long, value_enum, default_value = "auto")]
        category: Category,
        #[arg(long, value_enum, default_value = "reading")]
        purpose: Purpose,
        #[arg(long, help = "Override the project-relative destination directory for non-PDF files")]
        path: Option<String>,
        #[arg(long, help = "Show the file destinations without uploading")]
        dry_run: bool,
        #[arg(long)]
        json: bool,
    },
    /// List the files in a project directory.
    Files {
        #[arg(long)]
        project: String,
        #[arg(long, default_value = "")]
        path: String,
        #[arg(long)]
        json: bool,
    },
}

#[derive(Clone, Copy, Debug, ValueEnum, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Category { Auto, Literature, Code, Data, Figures, Slides, Documents, Files }

#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum Purpose { References, Methods, Validation, Reading }
impl Purpose {
    fn id(self) -> &'static str {
        match self { Self::References=>"references", Self::Methods=>"methods", Self::Validation=>"validation", Self::Reading=>"reading" }
    }
}

#[derive(Serialize, Deserialize)]
struct Session { server_url: String, token: String }

pub async fn login(username: &str, password_stdin: bool) -> Result<()> {
    let config=Config::load()?;
    let password=read_password(password_stdin)?;
    let remote=RemoteClient::new();
    remote.login(&config, username, &password).await?;
    let session=Session{server_url:config.server_url.trim_end_matches('/').into(),token:remote.session_token().context("登录未返回有效会话")?};
    secure_store::save(&data_dir().join("cli-session"), &serde_json::to_string(&session)?)?;
    println!("{}",json!({"logged_in":true,"username":username,"server":session.server_url}));
    Ok(())
}

fn read_password(from_stdin: bool) -> Result<String> {
    #[cfg(windows)]
    let console=if from_stdin { None } else {
        use windows_sys::Win32::System::Console::*;
        let handle=unsafe{GetStdHandle(STD_INPUT_HANDLE)};let mut mode=0;
        if unsafe{GetConsoleMode(handle,&mut mode)}==0 { bail!("脚本登录请使用 --password-stdin；交互登录请在终端运行") }
        if unsafe{SetConsoleMode(handle,mode & !ENABLE_ECHO_INPUT)}==0 { bail!("无法隐藏密码输入，请使用 --password-stdin") }
        Some((handle,mode))
    };
    #[cfg(not(windows))]
    if !from_stdin { bail!("请使用 --password-stdin") }
    if !from_stdin { eprint!("DeepPartner 密码: ");io::stderr().flush()?; }
    let mut value=String::new();let result=io::stdin().read_line(&mut value);
    #[cfg(windows)]
    if let Some((handle,mode))=console { unsafe{windows_sys::Win32::System::Console::SetConsoleMode(handle,mode)};eprintln!(); }
    result?;
    let value=value.trim_end_matches(['\r','\n']).to_owned();
    if value.is_empty() { bail!("密码不能为空") }
    Ok(value)
}

pub(crate) async fn authenticated(config:&Config) -> Result<Arc<RemoteClient>> {
    let remote=RemoteClient::new();let file=data_dir().join("cli-session");
    if file.is_file() {
        let saved:Session=serde_json::from_str(&secure_store::load(&file)?)?;
        if saved.server_url!=config.server_url.trim_end_matches('/') { bail!("服务地址已更换，请重新运行 dp login --username 用户名") }
        remote.restore_session(saved.token);
    } else if let Ok(trusted)=secure_store::load(&data_dir().join("device-credential")) {
        remote.set_trusted(trusted);
        remote.api(config,"POST","/api/quick-login/login",Some(json!({})),false).await.context("已记住的设备会话无法恢复，请运行 dp login --username 用户名")?;
    } else { bail!("请先运行 dp login --username 用户名；此命令会隐藏密码输入") }
    remote.authenticate(config).await?;
    if let Err(error)=remote.get(config,"/api/auth/profile").await {
        let message=error.to_string().to_lowercase();
        if !message.contains("expired") && !message.contains("invalid token") && !message.contains("invalid or expired") { return Err(error) }
        let trusted=secure_store::load(&data_dir().join("device-credential")).context("会话已过期，请运行 dp login --username 用户名")?;
        remote.set_trusted(trusted);
        remote.api(config,"POST","/api/quick-login/login",Some(json!({})),false).await.context("记住的设备无法恢复会话，请运行 dp login --username 用户名")?;
        let saved=Session{server_url:config.server_url.trim_end_matches('/').into(),token:remote.session_token().context("会话恢复没有返回令牌")?};
        secure_store::save(&file,&serde_json::to_string(&saved)?)?;
    }
    Ok(remote)
}

pub async fn logout() -> Result<()> {
    let config=Config::load()?;let file=data_dir().join("cli-session");
    if file.is_file() {
        let remote=authenticated(&config).await?;
        remote.api(&config,"POST","/api/auth/logout",Some(json!({})),true).await?;
        std::fs::remove_file(file)?;
    }
    println!("{}",json!({"logged_out":true}));Ok(())
}

pub(crate) fn resolve_project(projects:&Value, query:&str) -> Result<Value> {
    let rows=projects["projects"].as_array().context("项目列表响应无效")?;
    if let Some(found)=rows.iter().find(|p|p["id"].as_str()==Some(query)) { return Ok(found.clone()) }
    let matches:Vec<_>=rows.iter().filter(|p|p["name"].as_str()==Some(query)).collect();
    match matches.as_slice() {
        [found]=>Ok((*found).clone()),
        []=>bail!("没有找到项目 {query}，请用 dp project list 查看当前账户项目"),
        _=>bail!("多个项目同名 {query}，请用 dp project list 查看并指定项目 ID"),
    }
}

fn detected(path:&Path) -> Category {
    let ext=path.extension().unwrap_or_default().to_string_lossy().to_ascii_lowercase();
    match ext.as_str() {
        "pdf"=>Category::Literature,
        "png"|"jpg"|"jpeg"|"webp"|"gif"|"svg"|"tif"|"tiff"|"eps"=>Category::Figures,
        "ppt"|"pptx"|"odp"=>Category::Slides,
        "csv"|"tsv"|"xls"|"xlsx"|"npy"|"npz"|"h5"|"hdf5"|"mat"|"vtk"|"vtu"|"stl"=>Category::Data,
        "py"|"pyw"|"ipynb"|"m"|"r"|"f"|"f90"|"c"|"cpp"|"cc"|"h"|"hpp"|"js"|"jsx"|"ts"|"tsx"|"rs"|"jl"|"go"|"java"|"sh"|"sbatch"|"json"|"yaml"|"yml"|"toml"|"ini"|"cfg"=>Category::Code,
        "doc"|"docx"|"odt"|"txt"|"md"|"markdown"|"tex"|"epub"=>Category::Documents,
        _=>Category::Files,
    }
}
fn category_dir(category:Category) -> &'static str {
    match category { Category::Code=>"src",Category::Data=>"data",Category::Figures=>"figures",Category::Slides=>"slides",Category::Documents=>"docs",_=>"files" }
}
fn relative_path(value:&str) -> Result<String> {
    let value=value.replace('\\',"/");
    if Path::new(&value).components().any(|c|!matches!(c,Component::Normal(_))) || value.contains(':') || value.starts_with('/') { bail!("目标目录必须是项目内的相对路径") }
    Ok(value)
}
#[derive(Serialize)]
struct Upload { source:PathBuf, category:Category, destination:String, bytes:u64 }

fn upload_plan(paths:&[PathBuf],recursive:bool,category:Category,directory:Option<&str>,purpose:Purpose) -> Result<(Vec<Upload>,usize)> {
    let directory=directory.map(relative_path).transpose()?;
    let mut sources=Vec::new();let mut skipped=0;
    for source in paths {
        if source.is_dir() {
            if !recursive { bail!("{} 是文件夹，请加 --recursive",source.display()) }
            let base=source.file_name().context("请选择具体材料文件夹")?;
            for entry in walkdir::WalkDir::new(source).follow_links(false).into_iter().filter_entry(|e|!e.file_type().is_symlink() && ![".git",".venv","node_modules","__pycache__","target"].contains(&e.file_name().to_string_lossy().as_ref())) {
                let entry=entry?;
                if !entry.file_type().is_file() { continue }
                if entry.path().components().any(|p|p.as_os_str().to_string_lossy().starts_with(".env")) { skipped+=1;continue }
                sources.push((entry.path().to_path_buf(),PathBuf::from(base).join(entry.path().strip_prefix(source)?)));
            }
        } else {
            if !source.is_file() { bail!("文件不存在：{}",source.display()) }
            sources.push((source.clone(),PathBuf::from(source.file_name().context("文件名无效")?)));
        }
    }
    let mut plan=Vec::new();let mut destinations=BTreeSet::new();
    for (source,relative) in sources {
        let kind=if category==Category::Auto { detected(&source) } else { category };
        if kind==Category::Literature && source.extension().is_none_or(|s|!s.eq_ignore_ascii_case("pdf")) { bail!("文献库仅支持 PDF；其他资料使用 --category documents") }
        let bytes=source.metadata()?.len();let limit=if kind==Category::Literature {100} else {256};
        if bytes>limit*1024*1024 { bail!("{} 超过单文件 {limit} MiB 上限",source.display()) }
        let destination=if kind==Category::Literature {
            format!("literature/{}/{}",purpose.id(),source.file_name().unwrap().to_string_lossy())
        } else {
            format!("project/{}/{}",directory.as_deref().unwrap_or(category_dir(kind)),relative.to_string_lossy().replace('\\',"/"))
        };
        if !destinations.insert(destination.to_lowercase()) { bail!("本批次多个文件目标重名：{destination}，请分批或调整目标目录") }
        plan.push(Upload{source,category:kind,destination,bytes});
    }
    if plan.is_empty() { bail!("没有可上传的文件") }
    Ok((plan,skipped))
}

pub async fn run(command:ProjectAction) -> Result<()> {
    let config=Config::load()?;let remote=authenticated(&config).await?;
    let projects=remote.get(&config,"/research/api/projects").await?;
    match command {
        ProjectAction::Create{name,json:as_json}=>{
            let value=remote.api(&config,"POST","/research/api/projects",Some(json!({"name":name})),true).await?;
            if as_json {println!("{value}")}else{println!("{}\t{}",value["id"].as_str().unwrap_or(""),value["name"].as_str().unwrap_or(""))}
        },
        ProjectAction::List{json:as_json}=>{
            if as_json { println!("{projects}") } else {
                for row in projects["projects"].as_array().context("项目列表响应无效")? { println!("{}\t{}",row["id"].as_str().unwrap_or(""),row["name"].as_str().unwrap_or("")) }
            }
        },
        ProjectAction::Files{project,path,json:as_json}=>{
            let project=resolve_project(&projects,&project)?;let path=relative_path(&path)?;
            let query=url::form_urlencoded::Serializer::new(String::new()).append_pair("path",&path).finish();
            let files=remote.get(&config,&format!("/research/api/projects/{}/files?{query}",project["id"].as_str().context("项目编号无效")?)).await?;
            if as_json { println!("{files}") } else { for row in files["items"].as_array().context("文件列表响应无效")? { println!("{}\t{}",row["kind"].as_str().unwrap_or(""),row["path"].as_str().unwrap_or("")) } }
        },
        ProjectAction::Upload{project,files,recursive,category,purpose,path,dry_run,json:as_json}=>{
            let project=resolve_project(&projects,&project)?;let pid=project["id"].as_str().context("项目编号无效")?;
            let (plan,skipped)=upload_plan(&files,recursive,category,path.as_deref(),purpose)?;
            if dry_run {
                if as_json { println!("{}",json!({"project":project["name"],"project_id":pid,"dry_run":true,"files":plan,"skipped":skipped})) }
                else { println!("项目：{} ({pid})",project["name"].as_str().unwrap_or(""));for item in &plan {println!("{} -> {}",item.source.display(),item.destination)}println!("预览 {} 份文件，未上传",plan.len()) }
                return Ok(())
            }
            let mut results=Vec::new();
            for item in plan {
                eprintln!("上传 {} -> {}",item.source.display(),item.destination);
                let result=if item.category==Category::Literature {
                    remote.upload(&config,&format!("/research/api/projects/{pid}/literature/upload"),json!({"folder":purpose.id()}),vec![("files".into(),item.source.clone())]).await
                } else {
                    let parent=item.destination.strip_prefix("project/").unwrap().rsplit_once('/').unwrap().0;
                    remote.upload(&config,&format!("/research/api/projects/{pid}/files"),json!({"path":parent}),vec![("files".into(),item.source.clone())]).await
                };
                match result {
                    Ok(value)=>results.push(json!({"source":item.source,"destination":item.destination,"category":item.category,"saved":true,"receipt":value})),
                    Err(error)=>results.push(json!({"source":item.source,"destination":item.destination,"saved":false,"error":format!("{error:#}")})),
                }
            }
            let saved=results.iter().filter(|r|r["saved"]==true).count();let failed=results.len()-saved;
            if as_json { println!("{}",json!({"project_id":pid,"project":project["name"],"saved":saved,"failed":failed,"skipped":skipped,"items":results})) }
            else { for item in &results { if item["saved"]==true {println!("已保存 {}",item["destination"].as_str().unwrap_or(""))} else {println!("失败 {}：{}",item["destination"],item["error"])} }println!("完成：{saved} 份已保存，{failed} 份失败") }
            if failed>0 { bail!("{failed} 份文件未上传成功；已保存文件见上方回执") }
        },
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn project_name_must_be_unique_and_id_wins() {
        let rows=json!({"projects":[{"id":"one","name":"研究"},{"id":"two","name":"研究"}]});
        assert!(resolve_project(&rows,"研究").is_err());assert_eq!(resolve_project(&rows,"one").unwrap()["id"],"one");assert!(resolve_project(&rows,"absent").is_err());
    }
    #[test]
    fn mixed_directory_preserves_structure_and_classifies_files() {
        let tmp=tempfile::tempdir().unwrap();let root=tmp.path().join("材料");std::fs::create_dir_all(root.join("sub")).unwrap();
        for name in ["sub/main.py","values.csv","photo.png","talk.pptx","paper.pdf","notes.docx"] { std::fs::write(root.join(name),b"sample").unwrap() }
        let (plan,_)=upload_plan(&[root],true,Category::Auto,None,Purpose::Methods).unwrap();
        let paths:Vec<_>=plan.iter().map(|p|p.destination.as_str()).collect();
        for expected in ["project/src/材料/sub/main.py","project/data/材料/values.csv","project/figures/材料/photo.png","project/slides/材料/talk.pptx","literature/methods/paper.pdf","project/docs/材料/notes.docx"] { assert!(paths.contains(&expected),"Missing {expected}") }
    }
    #[test]
    fn plan_rejects_traversal_collisions_and_non_pdf_literature() {
        let tmp=tempfile::tempdir().unwrap();let source=tmp.path().join("main.py");std::fs::write(&source,b"print(1)").unwrap();
        assert!(upload_plan(&[source.clone()],false,Category::Auto,Some("../escape"),Purpose::Reading).is_err());
        assert!(upload_plan(&[source.clone(),source.clone()],false,Category::Auto,None,Purpose::Reading).is_err());
        assert!(upload_plan(&[source],false,Category::Literature,None,Purpose::Reading).is_err());
    }
}
