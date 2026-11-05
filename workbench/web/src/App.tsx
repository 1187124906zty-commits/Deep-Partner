import {ProjectCanvas} from './ProjectCanvas'
import {TaskCenter} from './TaskCenter'
import {subscribeProjectJobs} from './jobUpdates'
import {WorkbenchSettings} from './WorkbenchSettings'
import {useEmbeddedWorkbench} from './EmbeddedHost'
import {Fragment,useEffect,useRef,useState} from 'react'
import {Plus,BookOpen,FolderCode,FilePenLine,Presentation,Settings2,Trash2,ArrowUpRight,LayoutGrid,ChevronDown,Loader2,Check,Clock,Download,Upload,PanelLeftClose,PanelLeft,MessageSquare} from 'lucide-react'
import {api,jsonBody,projectPath,prettySize,type Project,type Job} from './api'
import {IconButton,Modal,Loading,Empty} from './ui'
import {LibraryPanel} from './Library'
import {FilesPanel} from './Files'
import {PaperWorkspace} from './PaperWorkspace'
import {ActivityPanel,TrashContents} from './HistoryPanel'
import {StorageMeter} from './StorageMeter'
import {selectTheme,type Theme} from './theme'
import {ContextMenu,type ReviewItem} from './Review'
import {SlidesPanel} from './Slides'
import {initialProject} from './workspaceLocation'

export type WorkbenchArea='literature'|'files'|'figures'|'code'|'paper'|'slides'|'questions'
type Area=WorkbenchArea
const sections:[Area,string,typeof BookOpen][]=[['literature','文献',BookOpen],['code','程序',FolderCode],['paper','论文',FilePenLine],['slides','PPT',Presentation],['questions','项目画布',MessageSquare]]
const jobNames:Record<string,string>={'material-import':'研究材料导入','manuscript-export':'稿件导出','slides-plan':'汇报规划','slides-export':'PPT导出','template':'模板解析','manuscript-translate':'稿件翻译','literature-download':'文献下载','journal-preview':'期刊排版预览','quality-review':'阶段评分'}

export interface WorkbenchAppProps{embedded?:boolean;selectedProject?:Project|null;onProjectChange?:(project:Project|null)=>void;currentArea?:WorkbenchArea;onAreaChange?:(area:WorkbenchArea)=>void}
export default function App({embedded=false,selectedProject,onProjectChange,currentArea,onAreaChange}:WorkbenchAppProps={}){
 const embeddedHost=useEmbeddedWorkbench()
 const [nativeStatus,setNativeStatus]=useState<any>();const [renaming,setRenaming]=useState(false);const renameInput=useRef<HTMLInputElement>(null);const [unavailable,setUnavailable]=useState(false);const [user,setUser]=useState<any>();const [projects,setProjects]=useState<Project[]>([]);const [project,setProject]=useState<Project|null>(null)
 const [savedArea,setArea]=useState<Area>(()=>{const v=new URL(location.href).searchParams.get('area')||localStorage.getItem('research-area');return ['literature','files','figures','code','paper','slides','questions'].includes(v||'')?v as Area:'literature'});const [error,setError]=useState('');const [toast,setToast]=useState('');const [modal,setModal]=useState('');const [name,setName]=useState('');const [busy,setBusy]=useState(false);const [jobs,setJobs]=useState<Job[]>([]);const [sidebar,setSidebar]=useState(false);const [projectMenu,setProjectMenu]=useState(false)
 useEffect(()=>{const updated=()=>setJobVersion(v=>v+1);window.addEventListener('workbench:artifact-updated',updated);return()=>window.removeEventListener('workbench:artifact-updated',updated)},[])
 const area=currentArea||savedArea
 useEffect(()=>{if(location.hostname==='127.0.0.1')void fetch('/desktop/status').then(r=>r.ok?r.json():null).then(setNativeStatus).catch(()=>{})},[project?.id])
 const beforeNavigation=useRef<()=>Promise<void>>(async()=>{});const [jobVersion,setJobVersion]=useState(0);const knownJobs=useRef(new Map<string,string>())
 const [target,setTarget]=useState<ReviewItem|null>(null)
 const [exportMenu,setExportMenu]=useState<{x:number;y:number}|null>(null)
 const importInput=useRef<HTMLInputElement>(null);const [importing,setImporting]=useState(false)
 const importMaterials=async(file?:File)=>{if(!file||!project)return;setImporting(true);try{await beforeNavigation.current();const data=new FormData();data.append('file',file);await api(projectPath(project,'/import'),{method:'POST',body:data});setModal('');tell('正在导入研究材料')}catch(e){fail(e)}finally{setImporting(false);if(importInput.current)importInput.current.value=''}}
 const [settings,setSettings]=useState<Record<string,any>>({base_url:'',model:'',api_key:'',configured:false,translation_prompt:'',literature_token:'',literature_configured:false,native_available:false,literature_provider:'auto',scholar_api_key:'',wos_api_key:'',scholar_configured:false,wos_configured:false,web_search_api_key:'',jcr_api_key:'',web_search_configured:false,jcr_configured:false})
 const tell=(message:string)=>{setToast(message);setTimeout(()=>setToast(''),3600)}
 const fail=(e:unknown)=>{const message=e instanceof Error?e.message:String(e);if(embedded&&embeddedHost?.notify)embeddedHost.notify(message);else setError(message)}
 const refresh=async(selected?:string)=>{const data=await api('/projects');setProjects(data.projects);if(selected)setProject(data.projects.find((p:Project)=>p.id===selected)||null);return data.projects as Project[]}
 useEffect(()=>{if(embedded){void api('/me').then(setUser).catch(fail);return}void (async()=>{try{const me=await api('/me');setUser(me);const rows=await refresh();const requested=new URL(location.href).searchParams.get('project');const resolved=initialProject(rows,requested,localStorage.getItem('research-project:'+me.id));setProject(resolved.project);setUnavailable(resolved.unavailable);if(requested&&resolved.project&&requested!==resolved.project.id){const canonical=new URL(location.href);canonical.searchParams.set('project',resolved.project.id);history.replaceState(null,'',canonical)}if(resolved.unavailable){setSidebar(true);setError('当前账户（'+me.username+'）无法访问链接中的项目。请从侧栏选择本账户的项目，或切换到账户所有者。')}}catch(e){fail(e)}})()},[])
 useEffect(()=>{if(!project)return;let closed=false;const receive=async(rows:Job[])=>{if(closed)return;setJobs(rows);const hadJobs=knownJobs.current.size>0;for(const j of rows){const previous=knownJobs.current.get(j.id);if(previous!==j.status&&['completed','failed'].includes(j.status)&&(!previous?hadJobs:true)){if(j.kind==='material-import'&&j.status==='completed')await refresh(project.id);setJobVersion(v=>v+1);if(j.status==='failed')setError(j.error);else tell((j.task?.type_label||jobNames[j.kind]||'任务')+'完成')}knownJobs.current.set(j.id,j.status)}};const stop=subscribeProjectJobs(project,rows=>void receive(rows));const local=async()=>{if(location.hostname!=='127.0.0.1')return;try{const response=await fetch('/desktop/jobs');if(response.ok&&!closed){const value=await response.json();setNativeStatus((previous:any)=>previous?{...previous,jobs:value.jobs}:previous)}}catch{}};void local();const timer=setInterval(()=>void local(),1000);return()=>{closed=true;stop();clearInterval(timer)}},[project?.id])
 useEffect(()=>{if(embedded){setProject(selectedProject||null);setJobs([]);knownJobs.current.clear()}},[embedded,selectedProject?.id])
 const navigate=async(p:Project|null,next?:Area)=>{try{await beforeNavigation.current();beforeNavigation.current=async()=>{};if(p?.id!==project?.id){setUnavailable(false);setProject(p);setJobs([]);knownJobs.current.clear();if(p&&user)localStorage.setItem('research-project:'+user.id,p.id)}if(next){setArea(next);onAreaChange?.(next);localStorage.setItem('research-area',next)}if(embedded){if(p?.id!==project?.id)onProjectChange?.(p);setError('');return}const url=new URL(location.href);if(p?.id!==project?.id||next&&next!=='code')url.searchParams.delete('file');if(p)url.searchParams.set('project',p.id);if(next)url.searchParams.set('area',next);history.replaceState(null,'',url);setProjectMenu(false);setError('')}catch(e){fail(e)}}
 const registerSave=(fn:()=>Promise<void>)=>{beforeNavigation.current=fn;embeddedHost?.registerSave(fn)}
 const created=async()=>{if(!name.trim())return;setBusy(true);try{const p=await api('/projects',jsonBody({name:name.trim()}));await refresh();await navigate(p,'literature');setModal('');setName('')}catch(e){fail(e)}finally{setBusy(false)}}
 const openSettings=async()=>{try{const r=await api('/api-settings');setSettings({base_url:r.base_url||'',model:r.model||'',configured:Boolean(r.configured),api_key:'',translation_prompt:r.translation_prompt||'',literature_token:'',literature_configured:!!r.literature_configured,native_available:!!r.native_available,literature_provider:r.literature_provider||'auto',scholar_api_key:'',wos_api_key:'',scholar_configured:!!r.scholar_configured,wos_configured:!!r.wos_configured,web_search_api_key:'',jcr_api_key:'',web_search_configured:!!r.web_search_configured,jcr_configured:!!r.jcr_configured,reviewer_mode:r.reviewer_mode||'inherit',reviewer_base_url:r.reviewer_base_url||'',reviewer_model:r.reviewer_model||'',reviewer_api_key:'',reviewer_configured:!!r.reviewer_configured,reviewer_supports_vision:!!r.reviewer_supports_vision});setModal('settings')}catch(e){fail(e)}}
 const openTrash=async()=>{if(!project)return;try{await beforeNavigation.current();setModal('trash')}catch(e){fail(e)}}
 const exportPaper=async(format:string,language='source')=>{if(!project)return;try{await api(projectPath(project,'/manuscript/export'),jsonBody({format,language}));tell('正在导出')}catch(e){fail(e)}}
 const nativeJobs=(nativeStatus?.jobs||[]).filter((j:any)=>j.project_id===project?.id);const activeJobs=[...jobs,...nativeJobs].filter(j=>['running','queued','starting','cancelling','waiting_service','waiting_input','paused'].includes(j.status))
 const shared={project:project!,onError:fail,notify:tell,version:jobVersion,target}
 const locate=(item:ReviewItem)=>{setTarget(item);void navigate(project,(item.area==='image'?'figures':item.area) as Area)}
 return <div className={'app-shell'+(!sidebar?' no-sidebar':'')+(projectMenu?' mobile-sidebar-open':'')+(embedded?' embedded-workbench':'')}>
  {!embedded&&projectMenu&&<button className="project-menu-backdrop" aria-label="收起项目菜单" onClick={()=>setProjectMenu(false)}/>}
  {!embedded&&sidebar&&<aside className="sidebar"><div className="brand"><LayoutGrid size={22}/><span>研究工作台</span><IconButton title="收起侧栏" onClick={()=>setSidebar(false)}><PanelLeftClose size={17}/></IconButton></div>
   <button className="new-project" onClick={()=>{setModal('create');setName('')}}><Plus size={18}/>新建项目</button>
   <nav className="project-list">{projects.map(p=><button key={p.id} className={'project-item'+(p.id===project?.id?' selected':'')} onClick={()=>void navigate(p)}><span className="project-dot"/><span>{p.name}</span></button>)}</nav>
   <div className="sidebar-bottom"><StorageMeter/>{project&&<button onClick={()=>void openTrash()}><Trash2 size={17}/>垃圾箱</button>}<button onClick={()=>void openSettings()}><Settings2 size={17}/>工作台设置</button><a href="/chat"><BookOpen size={17}/>DeepTutor<ArrowUpRight size={14}/></a></div>
  </aside>}
  <main className="workspace">
   {!embedded&&<header className="project-header"><span className="mobile-project-menu"><IconButton title="项目菜单" onClick={()=>{setSidebar(true);setProjectMenu(!projectMenu)}}><PanelLeft size={19}/></IconButton></span>{!sidebar&&<span className="desktop-project-menu"><IconButton title="展开侧栏" onClick={()=>setSidebar(true)}><PanelLeft size={19}/></IconButton></span>}
    <div className="project-name">{project?(renaming?<input ref={renameInput} autoFocus aria-label="就地修改项目名称" value={name} maxLength={100} onChange={e=>setName(e.target.value)} onBlur={()=>{setRenaming(false);if(name.trim()&&name.trim()!==project.name)void api(projectPath(project),jsonBody({name:name.trim()},'PATCH')).then(p=>{setProject(p);void refresh()}).catch(fail)}} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();if(e.key==='Escape'){setName(project.name);setRenaming(false)}}}/>:<button title="点击修改项目名称" onClick={()=>{setName(project.name);setRenaming(true)}}>{project.name}</button>):<span>项目</span>}</div>
    {project&&<nav className="area-tabs">{sections.map(([id,label,Icon])=><button key={id} className={area===id?'current':''} onClick={()=>void navigate(project,id)}><Icon size={17}/>{label}</button>)}</nav>}
    <div className="header-end">{!sidebar&&<StorageMeter compact/>}{!sidebar&&<><IconButton title="工作台设置" onClick={()=>void openSettings()}><Settings2 size={17}/></IconButton>{project&&<IconButton title="垃圾箱" onClick={()=>void openTrash()}><Trash2 size={17}/></IconButton>}</>}{(jobs.length>0||location.hostname==='127.0.0.1')&&<button className={'job-indicator'+(activeJobs.length?' working':'')} data-task-trigger aria-haspopup="dialog" aria-expanded={modal==='jobs'} aria-label="查看项目任务" onClick={()=>setModal('jobs')}>{activeJobs.some(j=>j.status==='running')?<Loader2 className="spin" size={16}/>:activeJobs.length?<Clock size={16}/>:<Check size={16}/>}<span>{activeJobs.length?'任务 · '+activeJobs.length:'任务'}</span></button>}<a className="avatar" href="/settings/profile" title={user?.username||'账户'}>{(user?.username||'R').slice(0,1).toUpperCase()}</a></div>
   </header>}
   {embedded&&<div className="embedded-workbench-toolbar"><nav className="area-tabs" aria-label="研究成果" hidden={!!currentArea}>{sections.map(([id,label,Icon])=><button key={id} aria-current={area===id?"page":undefined} className={area===id?"current":""} onClick={()=>void navigate(project,id)}><Icon size={16}/><span>{label}</span></button>)}</nav><div className="toolbar-spacer"/>{(jobs.length>0||location.hostname==='127.0.0.1')&&<button className="job-indicator" data-task-trigger aria-haspopup="dialog" aria-expanded={modal==='jobs'} aria-label="查看项目任务" onClick={()=>setModal("jobs")}>{activeJobs.some(j=>j.status==='running')?<Loader2 size={15} className="spin"/>:activeJobs.length?<Clock size={15}/>:<Check size={15}/>}<span>{activeJobs.length?"任务 · "+activeJobs.length:"任务"}</span></button>}<IconButton title="历史版本与垃圾箱" onClick={()=>void openTrash()}><Trash2 size={16}/></IconButton></div>}
   {error&&<div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setError('')}>关闭</button></div>}
   <div className="main-content">{!user&&!error?<Loading/>:!project?<Empty action={<button className="primary" onClick={()=>{setName('');setModal('create')}}><Plus size={18}/>新建项目</button>}>{unavailable?'当前链接的项目不属于这个登录账户，请在左侧选择项目。':'从一个研究项目开始'}</Empty>:<Fragment key={project.id}>
    {area==='literature'&&<LibraryPanel {...shared} onUpdate={p=>{setProject(p);void refresh()}}/>}
    {['files','figures','code'].includes(area)&&<FilesPanel key={area} {...shared} mode={area==='figures'?'images':area==='code'?'code':'all'} registerSave={registerSave}/>}
    {area==='paper'&&<PaperWorkspace {...shared} author={user} registerSave={registerSave}/>}
    {area==='questions'&&<ProjectCanvas project={project!} onError={fail} onOpenArea={next=>void navigate(project,next as Area)}/>}
    {area==='slides'&&<SlidesPanel {...shared} registerSave={registerSave}/>}
   </Fragment>}</div>
  </main>

  {toast&&<div className="toast" role="status"><Check size={17}/>{toast}</div>}
  {modal==='create'&&<Modal title="新建项目" onClose={()=>setModal('')}><form onSubmit={e=>{e.preventDefault();void created()}}><input autoFocus className="large-input" aria-label="项目名称" placeholder="研究项目名称" value={name} onChange={e=>setName(e.target.value)} maxLength={100}/><div className="modal-actions"><button type="button" onClick={()=>setModal('')}>取消</button><button className="primary" disabled={busy||!name.trim()}>{busy?<Loader2 className="spin" size={16}/>:null}创建</button></div></form></Modal>}
  {!embedded&&modal==='settings'&&<WorkbenchSettings project={project} value={settings} onChange={setSettings} onClose={()=>setModal('')} onError={fail} notify={tell} onImport={importMaterials} importing={importing}/>}
  {modal==='trash'&&project&&<Modal title="历史版本与垃圾箱" onClose={()=>setModal('')} wide><TrashContents project={project} onError={fail} notify={tell} onRestored={()=>{setJobVersion(v=>v+1);window.dispatchEvent(new CustomEvent('workbench:artifact-updated'))}}/></Modal>}
  {modal==='jobs'&&project&&<TaskCenter jobs={jobs} nativeStatus={nativeStatus} project={project} onClose={()=>setModal('')} onChanged={()=>window.dispatchEvent(new Event('workbench:jobs-updated'))}/> }
 </div>
}
