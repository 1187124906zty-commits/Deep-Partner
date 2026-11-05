import {ProjectMaterialsProvider} from './ProjectMaterials'
import WorkflowWorkspace from './WorkflowWorkspace'
import ResearchOverview from './ResearchOverview'
import {surfaceFromRoute,type Surface} from './workspace-navigation'
import ThemeSelect from './ThemeSelect'
import {workspaceGroups,workspaceEntries,workspaceArea} from './workspace-navigation'
import type {WorkbenchArea} from '@workbench/App'
import {DitoTaskProvider,DitoFeedbackBridge,useDitoTasks} from './host/DitoTasks'
import AppShell from '@/components/layout/AppShell'
import {SidebarShell as LayoutSidebarShell} from '@/components/sidebar/SidebarShell'
import {useSidebarDrawer} from '@/components/layout/AppShell'
import {notify} from '@/lib/notifications'
import {useCallback,useEffect,useMemo,useRef,useState} from 'react'
import {Activity,BookOpen,FolderOpen,MessageSquare,PanelLeftClose,PanelLeft,Plus,Settings2,Terminal,X,Loader2,Columns2,ArrowLeft,RefreshCw,PanelRight,PanelRightClose,History,ChevronRight,Sparkles,FolderPlus,FolderInput,Network} from 'lucide-react'
import ChatWorkspace from '@/features/chat/components/ChatWorkspace'
import {useChatStateAdapter} from '@/features/chat/ChatStateAdapter'
import SessionList from '@/components/SessionList'
import {listSessions,updateSessionTitle,deleteSession,type SessionSummary} from '@/lib/session-api'
import {subscribeSessionChanges} from '@/lib/session-events'
import {WorkspaceRuntimeBoundary} from '@/components/workspaces/WorkspaceRuntimeBoundary'
import {ChatRuntimeRoot} from '@/features/chat/ChatRuntimeRoot'
import {PageCustomizationProvider} from '@/context/PageCustomizationContext'
import TaskBoardRuntime from '@/components/tasks/TaskBoardRuntime'
import {CapabilityAccessProvider} from '@/components/access/CapabilityAccessContext'
import {logout} from '@/lib/auth'
import {updateRecoveryPrincipal} from '@/lib/recovery-principal'
import {setRuntimeAuthEnabled} from '@/lib/api'
import Login from './Login'
import {ReadingProvider} from '@/context/ReadingContext'
import {WorkspaceNavigation} from '@/components/workspaces/WorkspaceNavigation'
import {api as workbenchApi,jsonBody,projectPath,type Project} from '@workbench/api'
import WorkbenchApp from '@workbench/App'
import {EmbeddedWorkbenchProvider} from '@workbench/EmbeddedHost'
import Button from '@/shared/ui/Button'
import {Dialog} from '@/shared/ui/Dialog'
import {UnifiedLinks} from './host/UnifiedLinks'
import {useDevice} from '@/hooks/useDevice'
import {entryPath,navigate,useLocationSnapshot,setProjectRouteIndex} from './host/navigation'
import {projectHref} from './host/routes'
import {selectWorkspace} from '@/lib/workspace-scope'
import {ProductPolicyProvider} from './host/ProductPolicy'
import {useDesktopStatus,useManifest,needsUpgrade,compatibilityMessage,desktopRequest} from './services'
import Settings from './Settings'
import NativeTools from './NativeTools'

export default function App(){
 const snapshot=useLocationSnapshot(),query=new URL(snapshot,location.origin).searchParams
 const [needsLogin,setNeedsLogin]=useState(false)
 const [projects,setProjects]=useState<Project[]>([]),[user,setUser]=useState<any>(),[error,setError]=useState(''),[loading,setLoading]=useState(true),[creating,setCreating]=useState(false),[name,setName]=useState(''),[createBusy,setCreateBusy]=useState(false)
 const {status:desktop}=useDesktopStatus(),{manifest,error:manifestError}=useManifest()
 useEffect(()=>{if(!user?.id||!desktop)return;let stopped=false;const connect=()=>void desktopRequest('/connect',{}).then(()=>{if(!stopped)window.dispatchEvent(new Event('deeppartner:connections-ready'))}).catch(()=>{});connect();window.addEventListener('online',connect);return()=>{stopped=true;window.removeEventListener('online',connect)}},[user?.id,!!desktop])
 const settings=query.get('surface')==='settings'
 const setSettings=(open:boolean)=>{if(open){if(!settings)try{sessionStorage.setItem('deeptutor:settings-return',location.pathname+location.search+location.hash)}catch{};navigate('/settings/general')}else{const next=new URLSearchParams(location.search);next.delete('surface');next.delete('settings_section');navigate(entryPath+(next.size?'?'+next:''))}}
 const selectedId=query.get('project'),project=projects.find(p=>p.id===selectedId)||null
 const beforeProjectChange=useRef<()=>Promise<void>>(async()=>{})
 const load=useCallback(async()=>{setLoading(true);setError('');try{const authResponse=await fetch('/research/api/bootstrap',{credentials:'same-origin',cache:'no-store'});if(authResponse.status===401){setNeedsLogin(true);return}if(!authResponse.ok)throw new Error('无法连接服务，请检查网络后重试。');const bootstrap=await authResponse.json();const auth=bootstrap.auth;setRuntimeAuthEnabled(Boolean(auth.enabled));updateRecoveryPrincipal(auth);if(auth.enabled&&!auth.authenticated){setNeedsLogin(true);return}setNeedsLogin(false);const me=bootstrap.user,result={projects:bootstrap.projects};setUser(me);setProjects(result.projects);setProjectRouteIndex(result.projects);const q=new URL(location.href).searchParams;const requested=q.get('project');let next=result.projects.find((p:Project)=>p.id===requested||p.native_id===requested);if(!requested){const remembered=localStorage.getItem('deeppartner.project.'+me.id);next=result.projects.find((p:Project)=>p.id===remembered)||result.projects[0]}if(requested&&!next){setError('当前账户无法访问这个项目，请选择可用项目。');return}if(next&&(q.get('dt_workspace')!==next.native_id||q.get('project')!==next.id)){navigate(projectHref(entryPath,next,q.get('dt_workspace')===next.native_id?q.get('session'):null),true)}}catch(e){setError((e as Error).message)}finally{setLoading(false)}},[])
 useEffect(()=>{const updated=(event:Event)=>{const project=(event as CustomEvent<Project>).detail;setProjects(old=>old.map(item=>item.id===project.id?project:item))};window.addEventListener('deeppartner:project-updated',updated);return()=>window.removeEventListener('deeppartner:project-updated',updated)},[])
 useEffect(()=>{void load();const required=()=>setNeedsLogin(true);window.addEventListener('deeppartner:auth-required',required);return()=>window.removeEventListener('deeppartner:auth-required',required)},[load])
 const chooseProject=async(next:Project)=>{try{await beforeProjectChange.current();beforeProjectChange.current=async()=>{};if(user)localStorage.setItem('deeppartner.project.'+user.id,next.id);await selectWorkspace(next.native_id,projectHref(entryPath,next));setError('')}catch(e){setError((e as Error).message)}}
 const create=async()=>{if(!name.trim())return;setCreateBusy(true);try{const next=await workbenchApi<Project>('/projects',jsonBody({name:name.trim()}));setProjects(old=>[...old,next]);await chooseProject(next);setName('');setCreating(false)}catch(e){setError((e as Error).message)}finally{setCreateBusy(false)}}
 const ready=project&&query.get('dt_workspace')===project.native_id
 const signOut=async()=>{await logout();setSettings(false);setProjects([]);setUser(undefined);setNeedsLogin(true);navigate(entryPath+'?surface=login',true)}
 if(needsLogin||query.get('surface')==='login')return <Login onSuccess={async()=>{navigate(entryPath,true);setNeedsLogin(false);window.dispatchEvent(new CustomEvent('deeppartner:authenticated'));await load()}}/>
 return <><UnifiedLinks/><WorkspaceNavigation/>{ready?<PageCustomizationProvider><CapabilityAccessProvider><WorkspaceRuntimeBoundary><TaskBoardRuntime><ChatRuntimeRoot><ReadingProvider><DitoTaskProvider key={project.id} project={project}><ProjectShell project={project} projects={projects} user={user} onProject={chooseProject} onCreate={()=>setCreating(true)} onSettings={()=>setSettings(true)} desktop={desktop} registerSave={fn=>{beforeProjectChange.current=fn}} manifest={manifest} manifestError={manifestError} error={error} onError={setError}/></DitoTaskProvider></ReadingProvider></ChatRuntimeRoot></TaskBoardRuntime></WorkspaceRuntimeBoundary></CapabilityAccessProvider></PageCustomizationProvider>:<div className="dp-start"><div className="dp-brand"><BookOpen size={26}/><span>DeepPartner</span></div>{loading?<p role="status"><Loader2 size={18} className="animate-spin"/>正在打开研究项目…</p>:<><h1>{error?'项目暂时无法打开':'从一个研究项目开始'}</h1>{error&&<p role="alert">{error}</p>}{projects.length>0&&<div className="dp-start-projects">{projects.map(p=><button key={p.id} onClick={()=>void chooseProject(p)}><FolderOpen size={18}/>{p.name}</button>)}</div>}<div className="dp-start-actions"><Button onClick={()=>setCreating(true)} icon={<Plus size={16}/>}>新建项目</Button>{error&&<Button variant="secondary" onClick={()=>void load()}>重试</Button>}</div></>}</div>}<Settings open={settings} onClose={()=>setSettings(false)} user={user} desktop={desktop} manifest={manifest} onLogout={()=>void signOut()}/><Dialog open={creating} title="新建研究项目" onClose={()=>setCreating(false)} busy={createBusy} closeLabel="关闭" footer={<><Button variant="ghost" onClick={()=>setCreating(false)}>取消</Button><Button disabled={!name.trim()} loading={createBusy} onClick={()=>void create()}>创建项目</Button></>}><form onSubmit={e=>{e.preventDefault();void create()}}><label className="dp-field">项目名称<input data-autofocus value={name} maxLength={100} onChange={e=>setName(e.target.value)} placeholder="例如：多孔材料中的离子传输"/></label></form></Dialog></>
}

function ProjectShell({project,projects,user,onProject,onCreate,onSettings,desktop,registerSave,manifest,manifestError,error,onError}:{project:Project;projects:Project[];user:any;onProject:(p:Project)=>Promise<void>;onCreate:()=>void;onSettings:()=>void;desktop:ReturnType<typeof useDesktopStatus>['status'];registerSave:(fn:()=>Promise<void>)=>void;manifest:ReturnType<typeof useManifest>['manifest'];manifestError:string;error:string;onError:(s:string)=>void}){
 const {state,newSession,configureSession,loadSession,selectedSessionId,sidebarRefreshToken,sessionStatuses}=useChatStateAdapter()
 const wasStreaming=useRef(false)
 useEffect(()=>{if(wasStreaming.current&&!state.isStreaming)window.dispatchEvent(new CustomEvent('workbench:artifact-updated'));wasStreaming.current=state.isStreaming},[state.isStreaming])
 const [sessions,setSessions]=useState<SessionSummary[]>([]),[sessionLoading,setSessionLoading]=useState(true),[surface,setSurface]=useState<Surface>(()=>surfaceFromRoute(location.search)),[submitting,setSubmitting]=useState(false)
  const [area,setArea]=useState<WorkbenchArea>(()=>workspaceArea(new URL(location.href).searchParams.get('area'))||workspaceArea(localStorage.getItem('deeppartner.last-area.'+project.id))||'files')
 const [assistantWidth,setAssistantWidth]=useState(()=>{const value=Number(localStorage.getItem('deeppartner.assistant-width'));return value>=320&&value<=640?value:400})
 const current=workspaceEntries.find(item=>item.id===area)!
 const CurrentIcon=current.icon
 const openArea=async(next:WorkbenchArea)=>{try{await beforeSave.current();setArea(next);localStorage.setItem('deeppartner.last-area.'+project.id,next);setSurface(old=>old==='split'?'split':'artifacts');const url=new URL(location.href);url.searchParams.delete('view');url.searchParams.set('area',next);if(next!=='figures'&&next!=='files')url.searchParams.delete('file');navigate(url.pathname+url.search+url.hash)}catch(e){onError((e as Error).message)}}
 const beforeSave=useRef<()=>Promise<void>>(async()=>{})
 const registerWorkbenchSave=useCallback((save:()=>Promise<void>)=>{beforeSave.current=save;registerSave(save)},[registerSave])
 const showWorkflow=(taskId?:string)=>{setSurface('workflow');const url=new URL(location.href);url.searchParams.delete('area');url.searchParams.delete('file');url.searchParams.set('view','workflow');if(taskId)url.searchParams.set('task',taskId);else url.searchParams.delete('task');navigate(url.pathname+url.search+url.hash)}
 const showOverview=()=>{setSurface('overview');const url=new URL(location.href);url.searchParams.delete('area');url.searchParams.delete('file');url.searchParams.set('view','overview');navigate(url.pathname+url.search+url.hash)}
 const showChat=()=>{setSurface('chat');const url=new URL(location.href);url.searchParams.set('view','chat');url.searchParams.delete('area');url.searchParams.delete('file');navigate(url.pathname+url.search+url.hash)}
 const routeSnapshot=useLocationSnapshot()
 useEffect(()=>{const q=new URL(routeSnapshot,location.origin).searchParams;const next=workspaceArea(q.get('area'));if(next&&next!==area)setArea(next);const target=surfaceFromRoute(q.toString());setSurface(old=>(old==='split'&&target==='artifacts')||(old==='overview-split'&&target==='overview')?old:target)},[routeSnapshot])
 useEffect(()=>{const restore=()=>setSurface(surfaceFromRoute(location.search));window.addEventListener('popstate',restore);return()=>window.removeEventListener('popstate',restore)},[])
 const {request:ditoRequest,openTask:openDitoTask,setLocation:setDitoLocation}=useDitoTasks()
 useEffect(()=>{if(ditoRequest)setSurface(old=>old==='overview'||old==='overview-split'?'overview-split':old==='artifacts'||old==='split'?'split':'chat')},[ditoRequest?.id])
 const scope=project.native_id,scopeRef=useRef(scope),alive=useRef(true);scopeRef.current=scope
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 const incompatible=Boolean(manifest&&needsUpgrade(manifest))
 const refresh=useCallback(async()=>{try{const rows=await listSessions(100,0,{workspaceId:scope,force:true});if(scopeRef.current===scope)setSessions(rows)}catch(e){onError((e as Error).message)}finally{if(scopeRef.current===scope)setSessionLoading(false)}},[scope,onError])
 useEffect(()=>{setSessionLoading(true);void refresh();return subscribeSessionChanges(()=>void refresh())},[refresh,sidebarRefreshToken])
 // The route owns scope before ChatWorkspace is mounted or a draft can send.
 useEffect(()=>{if(!state.sessionId&&state.workspaceId!==scope)configureSession({workspaceId:scope},state.sessionKey)},[scope,state.sessionId,state.sessionKey,state.workspaceId,configureSession])
 const startChat=()=>{newSession({workspaceId:scope});navigate(projectHref(entryPath,project)+'&view=chat');setSurface('chat')}
 const openSession=async(id:string)=>{if(!sessions.some(s=>s.session_id===id))return;setSurface('chat');navigate(projectHref(entryPath,project,id))}
 const submitAnnotations=useCallback(async(boundProject:Project,ids:string[],attachments?:{type:string;filename?:string;base64?:string;mime_type?:string}[])=>{
   if(boundProject.id!==project.id||scopeRef.current!==boundProject.native_id)throw new Error('项目已切换，请重新打开批注后发送。')
   if(incompatible)throw new Error('请手动升级后开始新的批注任务。')
   if(state.isStreaming)throw new Error('当前会话仍在执行。请在完成后发送批注，或先停止当前任务。')
   setSubmitting(true)
   try{const result=await workbenchApi<{session_id:string;turn_id?:string;url:string;operation_id:string}>(projectPath(boundProject,'/annotations/submit'),jsonBody({ids,attachments:attachments||[],session_id:state.sessionId||undefined,operation_id:crypto.randomUUID()}));if(!alive.current||scopeRef.current!==boundProject.native_id)return;setSurface('split');navigate(projectHref(entryPath,boundProject,result.session_id));await loadSession(result.session_id);void refresh()}finally{setSubmitting(false)}
 },[project.id,state.sessionId,state.isStreaming,loadSession,refresh,incompatible])
 const submitFigure=useCallback(async(boundProject:Project,request:Parameters<import('@workbench/EmbeddedHost').EmbeddedWorkbenchHost['submitFigure']>[1])=>{
   if(boundProject.id!==project.id||scopeRef.current!==boundProject.native_id)throw new Error('项目已切换，请重新打开图形后发送。')
   if(incompatible)throw new Error('请手动升级后开始新的图形任务。')
   if(state.isStreaming)throw new Error('当前会话仍在执行，请在完成后发送图形修改要求。')
   setSubmitting(true)
   try{const result=await workbenchApi<{session_id:string;turn_id?:string;url?:string}>(projectPath(boundProject,'/figure/chat'),jsonBody({...request,embedded:true,session_id:state.sessionId||undefined,operation_id:crypto.randomUUID()}));if(!result.session_id)throw new Error('服务尚未返回可恢复的图形会话，请更新服务后重试。');if(!alive.current||scopeRef.current!==boundProject.native_id)return;setSurface('split');navigate(projectHref(entryPath,boundProject,result.session_id));await loadSession(result.session_id);void refresh()}finally{setSubmitting(false)}
 },[project.id,state.sessionId,state.isStreaming,loadSession,refresh,incompatible])
 const host=useMemo(()=>({renderLocalTaskForm:desktop?(project:Project,onStarted:()=>void)=><NativeTools status={desktop} projectId={project.id} compact onStarted={onStarted}/>:undefined,previewFile:(url:string,filename:string)=>{setSurface(old=>old==='artifacts'?'split':old==='workflow'?'chat':old);window.dispatchEvent(new CustomEvent('deeppartner:preview-file',{detail:{type:'file',url,filename}}))},sessionId:state.sessionId,notify:(message:string)=>notify(message,{tone:"error"}),submitAnnotations,submitFigure,registerSave:registerWorkbenchSave,setDitoLocation,openDito:(project:Project,anchor?:import('@workbench/Review').Anchor)=>openDitoTask({kind:'chat',project,anchor}),renderFeedback:(props:{project:Project;anchor:import('@workbench/Review').Anchor;onError:(e:unknown)=>void;onClose?:()=>void})=><DitoFeedbackBridge {...props}/>}),[state.sessionId,submitAnnotations,submitFigure,registerWorkbenchSave,setDitoLocation,openDitoTask,desktop])
 const liveSessions=sessions.filter(s=>s.preferences?.session_kind!=='selection_tutor').map(s=>sessionStatuses[s.session_id]?{...s,status:sessionStatuses[s.session_id].status}:s)
 const sidebarContent=<ResearchSidebar project={project} projects={projects} user={user} desktop={!!desktop} area={area} surface={surface} onArea={next=>void openArea(next)} onChat={showChat} onOverview={showOverview} onWorkflow={showWorkflow} sessions={liveSessions} selectedSessionId={selectedSessionId} sessionLoading={sessionLoading} incompatible={incompatible} onProject={onProject} onCreate={onCreate} onImport={()=>openDitoTask({kind:'import',project})} onSettings={onSettings} onNative={()=>setSurface('native')} onNewChat={startChat} onSelect={openSession} onRename={async(id,title)=>{await updateSessionTitle(id,title);await refresh()}} onDelete={async id=>{await deleteSession(id);if(id===state.sessionId)startChat();await refresh()}}/>
 return <div className={'dp-native-shell dp-workspace dp-surface-'+surface} style={{'--assistant-width':assistantWidth+'px'} as React.CSSProperties}><AppShell sidebar={sidebarContent} pageBar={<header className="dp-workspace-header"><div className="dp-workspace-location"><span>{project.name}</span><ChevronRight size={13}/>{surface.startsWith('overview')?<><Network size={15}/><strong>研究总览</strong></>:surface==='workflow'?<><Activity size={15}/><strong>工作流</strong></>:surface==='chat'?<><MessageSquare size={15}/><strong>研究对话</strong></>:surface==='native'?<><Terminal size={15}/><strong>本机任务</strong></>:<><CurrentIcon size={15}/><strong>{current.label}</strong></>}</div><div className="dp-workspace-actions">{surface!=='workflow'&&<button onClick={()=>showWorkflow()}><Activity size={15}/><span>工作流</span></button>}{surface==='chat'&&<button onClick={()=>void openArea(area)}><FolderOpen size={15}/><span>打开工作区</span></button>}<button aria-label="问 Dito" title="打开独立侧边提问" onClick={()=>openDitoTask({kind:'chat',project})}><Sparkles size={15}/><span>问 Dito</span></button></div></header>} homeHref={projectHref(entryPath,project)}><div className="dp-main">
   {manifest&&needsUpgrade(manifest)&&<div role="alert" className="dp-upgrade">此版本需要手动升级后使用新增能力。{compatibilityMessage(manifest.compatibility?.reasons)}<button onClick={onSettings}>查看版本</button></div>}
   {error&&<div role="alert" className="dp-error"><span>{error}</span><button aria-label="关闭错误" onClick={()=>onError('')}><X size={16}/></button></div>}
   <div className="dp-content">{surface.startsWith('overview')&&<section className="dp-research-overview-pane"><ResearchOverview key={project.id} project={project} onArea={next=>void openArea(next)} onWorkflow={showWorkflow} onDiscuss={(anchor,prompt)=>openDitoTask({kind:'chat',project,anchor,prompt})}/></section>}<section className="dp-artifacts" aria-label="研究成果" hidden={surface==='chat'||surface==='native'||surface==='workflow'||surface.startsWith('overview')}><EmbeddedWorkbenchProvider value={host}><WorkbenchApp embedded currentArea={area} onAreaChange={setArea} selectedProject={project} onProjectChange={p=>{if(p)void onProject(p)}}/></EmbeddedWorkbenchProvider></section>
   {(surface==='split'||surface==='overview-split')&&<div className="dp-assistant-resize" role="separator" tabIndex={0} aria-label="调整助手宽度" aria-orientation="vertical" aria-valuemin={320} aria-valuemax={640} aria-valuenow={assistantWidth} onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setAssistantWidth(width=>Math.max(320,Math.min(640,width+(e.key==='ArrowLeft'?20:-20))))}}} onPointerDown={e=>e.currentTarget.setPointerCapture(e.pointerId)} onPointerMove={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))setAssistantWidth(Math.max(320,Math.min(640,innerWidth-e.clientX)))}} onPointerUp={e=>{e.currentTarget.releasePointerCapture(e.pointerId);localStorage.setItem('deeppartner.assistant-width',String(assistantWidth))}}/>}
   <section className="dp-chat-pane" aria-label="项目会话" hidden={surface==='artifacts'||surface==='native'||surface==='workflow'||surface==='overview'}>{(surface==='split'||surface==='overview-split')&&<div className="dp-assistant-header"><Sparkles size={15}/><strong>研究助手</strong><span>当前项目</span><button title="展开对话" aria-label="展开对话" onClick={showChat}><Columns2 size={14}/></button><button title="收起助手" aria-label="收起助手" onClick={()=>{setSurface(surface==='overview-split'?'overview':'artifacts');const url=new URL(location.href);url.searchParams.delete('research_session');history.replaceState(history.state,'',url)}}><X size={15}/></button></div>}<div className="dp-chat-runtime"><ProjectMaterialsProvider project={project}><ProductPolicyProvider upgradeRequired={incompatible} onUpgrade={onSettings}><ChatWorkspace/></ProductPolicyProvider></ProjectMaterialsProvider></div>{submitting&&<div className="dp-handoff-status" role="status"><Loader2 size={15} className="animate-spin"/>正在接入当前会话…</div>}</section>{surface==='workflow'&&<section className="dp-workflow-pane dp-artifacts"><EmbeddedWorkbenchProvider value={host}><WorkflowWorkspace key={project.id} project={project} onChat={showChat} onArea={next=>void openArea(next)}/></EmbeddedWorkbenchProvider></section>}{surface==='native'&&desktop&&<div className="dp-native-page"><NativeTools status={desktop}/></div>}</div>
   {manifestError&&<div className="dp-connection-note" role="status">{manifestError} · 联网后自动重试。</div>}
  </div></AppShell></div>
}

function ResearchSidebar({project,projects,user,desktop,area,surface,onArea,onChat,onOverview,onWorkflow,sessions,selectedSessionId,sessionLoading,incompatible,onProject,onCreate,onImport,onSettings,onNative,onNewChat,onSelect,onRename,onDelete}:{project:Project;projects:Project[];user:any;desktop:boolean;area:WorkbenchArea;surface:string;onArea:(area:WorkbenchArea)=>void;onChat:()=>void;onOverview:()=>void;onWorkflow:()=>void;sessions:SessionSummary[];selectedSessionId:string|null;sessionLoading:boolean;incompatible:boolean;onProject:(p:Project)=>Promise<void>;onCreate:()=>void;onImport:()=>void;onSettings:()=>void;onNative:()=>void;onNewChat:()=>void;onSelect:(id:string)=>Promise<void>;onRename:(id:string,title:string)=>Promise<void>;onDelete:(id:string)=>Promise<void>}){
 const drawer=useSidebarDrawer()
 const action=(run:()=>void)=>{drawer?.close();run()}
 const navRow=(label:string,Icon:typeof BookOpen,run:()=>void,active=false,collapsed=false)=><button key={label} title={label} aria-label={label} aria-current={active?'page':undefined} className="dp-nav-row" onClick={()=>action(run)}><Icon size={16}/>{!collapsed&&<span>{label}</span>}</button>
 return <LayoutSidebarShell brandHref={projectHref(entryPath,project)} initialWidth={224} widthStorageKey="deeppartner.workspace-sidebar-width" homeSlot={collapsed=><div className={'dp-sidebar-home'+(collapsed?' is-collapsed':'')}>
   {!collapsed&&<div className="dp-project-switch"><ThemeSelect aria-label="切换研究项目" value={project.id} onChange={e=>{const next=projects.find(p=>p.id===e.target.value);if(next){drawer?.close();void onProject(next)}}}>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</ThemeSelect><button aria-label="新建项目" title="新建项目" onClick={()=>action(onCreate)}><FolderPlus size={15}/></button></div>}
   {collapsed&&navRow('新建项目',FolderPlus,onCreate,false,true)}
   {navRow('研究总览',Network,onOverview,surface.startsWith('overview'),collapsed)}
   <div className="dp-chat-entry">{navRow('研究对话',MessageSquare,onChat,surface==='chat',collapsed)}{!collapsed&&<button aria-label="新会话" title="新会话" disabled={incompatible} onClick={()=>action(onNewChat)}><Plus size={15}/></button>}</div>
   {navRow('工作流',Activity,onWorkflow,surface==='workflow',collapsed)}
   <nav aria-label="科研工作区">{workspaceGroups.map(group=><div className="dp-navigation-group" key={group.label}>{!collapsed&&<h2>{group.label}</h2>}{group.items.map(item=>navRow(item.label,item.icon,()=>onArea(item.id),(surface==='artifacts'||surface==='split')&&area===item.id,collapsed))}</div>)}</nav>
 </div>} bodySlot={collapsed=><div className="dp-sidebar-conversations">{!collapsed&&<><div className="dp-recent-heading"><span>近期会话</span><button title="新会话" aria-label="新会话" disabled={incompatible} onClick={()=>action(onNewChat)}><Plus size={14}/></button></div><SessionList sessions={sessions} activeSessionId={surface==='chat'?selectedSessionId:null} loading={sessionLoading} compact onSelect={id=>{drawer?.close();void onSelect(id)}} onRename={onRename} onDelete={onDelete}/></>}</div>} footerOverride={collapsed=><div className="dp-sidebar-footer">{navRow('项目画布',Network,()=>onArea('questions'),(surface==='artifacts'||surface==='split')&&area==='questions',collapsed)}<div className="dp-sidebar-account">{navRow('设置',Settings2,onSettings,false,collapsed)}{!collapsed&&<span>{user?.username||''}</span>}</div></div>}/>
}
