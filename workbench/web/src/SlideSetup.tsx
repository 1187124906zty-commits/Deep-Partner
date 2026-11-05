import {useEffect,useRef,useState} from 'react'
import {ArrowUpRight,Check,Loader2,Upload} from 'lucide-react'
import {api,base,jsonBody,projectPath,type Project} from './api'
import {BusyOverlay,Modal} from './ui'

async function finishJob(project:Project,id:string,onStage:(s:string)=>void){
 for(let i=0;i<300;i++){
  const value=await api(projectPath(project,'/jobs'));const job=value.jobs.find((j:any)=>j.id===id)
  if(job?.status==='failed')throw new Error(job.error)
  if(job?.status==='completed')return job.result
  onStage(job?.stage||'正在准备');await new Promise(resolve=>setTimeout(resolve,1200))
 }
 throw new Error('任务仍在运行，可在任务面板查看进度')
}

export function SlideSetup({project,onClose,onDone,onError,restyle=false}:{project:Project;onClose:()=>void;onDone:()=>void;onError:(e:unknown)=>void;restyle?:boolean}){
 const [catalog,setCatalog]=useState<any>({templates:[],profiles:[]});const [template,setTemplate]=useState('');const [profile,setProfile]=useState('');const [length,setLength]=useState('medium');const [instruction,setInstruction]=useState('');const [native,setNative]=useState(true);const [busy,setBusy]=useState('正在加载模板');const upload=useRef<HTMLInputElement>(null)
 const load=async()=>{const value=await api(projectPath(project,'/slide-templates'));setCatalog(value);return value}
 useEffect(()=>{let closed=false;void load().then(value=>{if(closed)return;if(value.confirmation){setTemplate(value.selected);setProfile(value.confirmation.profile)}setBusy('')}).catch(e=>{setBusy('');onError(e)});return()=>{closed=true}},[project.id])
 const styleOnly=restyle&&Boolean(catalog.confirmation)
 const selected=catalog.templates.find((t:any)=>t.id===template);const purpose=catalog.profiles.find((p:any)=>p.id===profile)
 const prepare=async(id:string)=>{setTemplate(id);const item=catalog.templates.find((t:any)=>t.id===id);if(item?.manifest)return;setBusy('正在解析模板与示例页');try{const r=await api(projectPath(project,'/slide-templates/'+id+'/prepare'),{method:'POST'});await finishJob(project,r.job_id,setBusy);await load()}catch(e){onError(e)}finally{setBusy('')}}
 const uploading=async(file?:File)=>{if(!file)return;setBusy('正在读取私人模板');try{const data=new FormData();data.append('file',file);const r=await api(projectPath(project,'/slide-templates'),{method:'POST',body:data});await finishJob(project,r.job_id,setBusy);await load();setTemplate('uploaded')}catch(e){onError(e)}finally{setBusy('');if(upload.current)upload.current.value=''}}
 const generate=async()=>{if(!template||!profile)return;setBusy(styleOnly?'正在应用版式':'正在确认生成设置');try{
  const receipt=await api(projectPath(project,'/slides/confirm'),jsonBody({template,profile,action:styleOnly?'restyle':'generate'}))
  if(!styleOnly){const planned=await api(projectPath(project,'/slides/plan'),jsonBody({confirmation_id:receipt.id,instruction,length,use_native:native}));const plannedResult=await finishJob(project,planned.job_id,setBusy);if(plannedResult?.quality&&!plannedResult.quality.can_proceed)throw new Error('内容计划已保存，阶段评分仍需修订；请在“阶段评分”查看依据或记录作者决定。')}
  const deck=await api(projectPath(project,'/slides/export'),{method:'POST'});await finishJob(project,deck.job_id,setBusy);onDone()
 }catch(e){onError(e)}finally{setBusy('')}}
 return <Modal title={styleOnly?'更换演示模板':'生成研究汇报'} onClose={()=>{if(!busy)onClose()}} wide><div className="slide-setup activity-host"><div className="slide-setup-body"><div className="slide-setup-label">演示模板<button onClick={()=>upload.current?.click()} disabled={Boolean(busy)}><Upload size={14}/>我的模板</button><input ref={upload} type="file" accept=".pptx" hidden onChange={e=>void uploading(e.target.files?.[0])}/></div><div className="slide-template-choices">{catalog.templates.map((t:any)=><button key={t.id} className={template===t.id?'selected':''} disabled={Boolean(busy)} onClick={()=>void prepare(t.id)}><div>{t.manifest?<img src={base+projectPath(project,'/slide-preview?kind='+t.id+'&page='+(t.manifest.examples?.content||1))} alt={t.name}/>:<span className={'template-swatch swatch-'+t.id}><strong>{t.name}</strong><i/></span>}{template===t.id&&<i className="template-check"><Check size={14}/></i>}</div><strong>{t.name}</strong></button>)}</div><div className="slide-setup-label">汇报类型</div><div className="talk-profile-choices">{catalog.profiles.map((p:any)=><button key={p.id} disabled={Boolean(busy)||styleOnly} className={profile===p.id?'selected':''} onClick={()=>setProfile(p.id)}>{p.name}</button>)}</div>{purpose&&<div className="talk-purpose"><strong>{purpose.audience}</strong><p>{purpose.purpose}</p><div>{purpose.structure.join(' → ')}</div><details><summary>组织依据</summary>{purpose.sources.map((url:string)=><a href={url} key={url} target="_blank" rel="noreferrer">{new URL(url).hostname+new URL(url).pathname}<ArrowUpRight size={12}/></a>)}</details></div>}{!styleOnly&&<><div className="slide-generation-options"><label>篇幅<select aria-label="汇报篇幅" value={length} onChange={e=>setLength(e.target.value)}><option value="short">简短</option><option value="medium">适中</option><option value="long">完整</option></select></label><label>模型<select aria-label="生成模型" value={native?'native':'api'} onChange={e=>setNative(e.target.value==='native')}><option value="native">DeepTutor</option><option value="api">工作台 API</option></select></label></div><textarea aria-label="本次汇报要求" rows={2} placeholder="本次想突出的问题或结果…" value={instruction} onChange={e=>setInstruction(e.target.value)}/></>}</div><footer className="modal-actions"><button disabled={Boolean(busy)} onClick={onClose}>取消</button><button className="primary" disabled={Boolean(busy)||!template||!profile} onClick={()=>void generate()}>{busy?<Loader2 size={15} className="spin"/>:<Check size={15}/>}{styleOnly?'确认并应用':'确认并生成'}</button></footer>{busy&&<BusyOverlay label={busy}/>}</div></Modal>
}
