//! Explicit source preparation and owner-authenticated import, shared with MCP.
use anyhow::{Result,Context,bail};
use serde_json::{json,Value};
use std::{path::{Path,PathBuf},fs,process::{Command,Stdio}};
use crate::{config::{Config,data_dir},remote::RemoteClient};

pub fn prepare(config:&Config,source:&Path)->Result<Value>{
 let root=source.canonicalize().context("导入来源目录不存在")?;
 let allowed=config.workspace.canonicalize()?;
 if !root.starts_with(&allowed){bail!("请先在导入卡片中选择并授权来源文件夹");}
 let id=uuid::Uuid::new_v4().to_string();let stage=data_dir().join("imports").join(&id);fs::create_dir_all(&stage)?;
 let has_manifest=root.join("workbench-import.json").is_file();
 let mut meta=if has_manifest {serde_json::from_slice::<Value>(&fs::read(root.join("workbench-import.json"))?)?}else{json!({"format":"workbench-project.v2","source":root.to_string_lossy(),"name":root.file_name().unwrap_or_default().to_string_lossy()})};
 meta["format"]=json!("workbench-project.v2");
 let mut entries=Vec::new();let mut total=0u64;let mut skipped=0;
 for entry in walkdir::WalkDir::new(&root).follow_links(false).into_iter().filter_entry(|e| !e.file_type().is_symlink() && ![".git",".venv","node_modules","__pycache__",".trash",".deeptutor"].contains(&e.file_name().to_string_lossy().as_ref())) {
  let entry=entry?;if !entry.file_type().is_file(){continue}let relative=entry.path().strip_prefix(&root)?;let name=relative.to_string_lossy().replace('\\',"/");
  if name=="workbench-import.json"||name=="导出来源.json"||name.starts_with(".workbench/")||name.split('/').any(|p|p.starts_with(".env")||["auth.json","credentials.json"].contains(&p)){skipped+=1;continue}
  let destination=if has_manifest {if !["project/","manuscript/","slides/","literature/"].iter().any(|p|name.starts_with(p)){skipped+=1;continue}name}else{format!("project/{name}")};
  total+=entry.metadata()?.len();if total>290*1024*1024||entries.len()>=2400{bail!("当前导入批次超过290MiB或2400文件，请按材料目录分批；大型原始数据保留映射");}
  entries.push(json!({"source":entry.path(),"entry":destination}));
 }
 if entries.is_empty(){bail!("来源目录中没有可导入的材料");}
 let metadata=stage.join("workbench-import.json");fs::write(&metadata,serde_json::to_vec_pretty(&meta)?)?;
 entries.push(json!({"source":metadata,"entry":"workbench-import.json"}));
 let list=stage.join("entries.json");fs::write(&list,serde_json::to_vec(&entries)?)?;
 let bundle=stage.join("project-import.zip");
 let script=r#"$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Add-Type -AssemblyName System.IO.Compression; $items=Get-Content -LiteralPath $env:DP_IMPORT_LIST -Raw -Encoding UTF8 | ConvertFrom-Json; $f=[IO.File]::Open($env:DP_IMPORT_ZIP,[IO.FileMode]::CreateNew); $z=[IO.Compression.ZipArchive]::new($f,[IO.Compression.ZipArchiveMode]::Create); try { foreach($item in $items){ $e=$z.CreateEntry($item.entry,[IO.Compression.CompressionLevel]::Fastest); $src=[IO.File]::OpenRead($item.source); $dst=$e.Open(); try{$src.CopyTo($dst)}finally{$dst.Dispose();$src.Dispose()} } }finally{$z.Dispose();$f.Dispose()}"#;
 let mut command=Command::new("powershell.exe");command.args(["-NoProfile","-NonInteractive","-Command",script]).env("DP_IMPORT_LIST",&list).env("DP_IMPORT_ZIP",&bundle).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped());
 #[cfg(windows)]{use std::os::windows::process::CommandExt;command.creation_flags(0x08000000);}
 let result=command.output()?;if !result.status.success(){bail!("导入包准备失败：{}",String::from_utf8_lossy(&result.stderr));}
 let receipt=json!({"import_id":id,"source":root,"files":entries.len()-1,"bytes":total,"skipped_runtime_files":skipped,"bundle":bundle,"status":"prepared","applied":false});
 fs::write(stage.join("receipt.json"),serde_json::to_vec_pretty(&receipt)?)?;Ok(receipt)
}
pub async fn apply(remote:&RemoteClient,config:&Config,id:&str,project_id:&str)->Result<Value>{
 uuid::Uuid::parse_str(id)?;if project_id.len()!=32||!project_id.chars().all(|c|c.is_ascii_hexdigit()){bail!("项目编号无效");}
 let stage=data_dir().join("imports").join(id);let saved=stage.join("applied.json");
 if saved.is_file(){let value:Value=serde_json::from_slice(&fs::read(saved)?)?;if value["project_id"]!=project_id {bail!("此导入操作已用于另一个项目");}return Ok(value)}
 let bundle:Value=serde_json::from_slice(&fs::read(stage.join("receipt.json"))?)?;
 let path=PathBuf::from(bundle["bundle"].as_str().context("导入包不存在")?);
 let result=remote.upload(config,&format!("/research/api/projects/{project_id}/import"),json!({"operation_id":id}),vec![("file".into(),path)]).await?;
 let value=json!({"project_id":project_id,"import_id":id,"job_id":result["job_id"],"status":"accepted","note":"等待工作台任务completed后回读成果，accepted不是导入完成"});fs::write(saved,serde_json::to_vec_pretty(&value)?)?;Ok(value)
}
