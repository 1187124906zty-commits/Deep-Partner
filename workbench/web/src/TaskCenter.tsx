import {WorkflowProgress} from './WorkflowProgress'
import {useEffect,useRef,useState,type CSSProperties} from 'react'
import {Archive,ArrowUpRight,BookOpen,Check,ChevronDown,ChevronRight,Clock,FileText,Languages,Loader2,Presentation,RotateCcw,ShieldCheck,Square,X,AlertCircle} from 'lucide-react'
import {api,jsonBody,projectPath,type Job,type Project} from './api'
import {IconButton} from './ui'
import {useEmbeddedWorkbench} from './EmbeddedHost'
import './task-center.css'
import {nativeEventText,nativeStatusLabel} from '../../unified-ui/src/native-events'

const statusNames:Record<string,string>={queued:'等待中',waiting_service:'等待服务恢复',waiting_input:'需要回复',paused:'已暂停',running:'进行中',completed:'已完成',failed:'未完成',interrupted:'已中断',cancelled:'已取消'}
const icons:Record<string,typeof FileText>={'material-import':Archive,'literature-download':BookOpen,'literature-classify':BookOpen,'manuscript-translate':Languages,'slides-plan':Presentation,'slides-export':Presentation,'quality-review':ShieldCheck}
const pending=(job:Job)=>['queued','running','waiting_service','waiting_input','paused'].includes(job.status)
const time=(value?:string)=>value?new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):''

export function TaskCenter({jobs,project,onClose,onChanged,nativeStatus}:{jobs:Job[];project:Project;onClose:()=>void;onChanged:()=>void;nativeStatus?:any}){
 const host=useEmbeddedWorkbench(),[newLocal,setNewLocal]=useState(false)
 const local=(nativeStatus?.jobs||[]).filter((j:any)=>j.project_id===project.id)
 const [filter,setFilter]=useState<'active'|'all'|'done'>(()=>[...jobs,...local].some(pending)?'active':'all')
 const panel=useRef<HTMLElement>(null),close=useRef(onClose);close.current=onClose
 useEffect(()=>{
  const focused=document.activeElement as HTMLElement|null
  panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
  const outside=(event:PointerEvent)=>{const target=event.target as HTMLElement;if(!panel.current?.contains(target)&&!target.closest('[data-task-trigger],.dp-select-popover'))close.current()}
  const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.stopPropagation();close.current();focused?.focus()}}
  document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key)
  return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)}
 },[])
 const combined=[...jobs,...local.map((j:any)=>({...j,kind:'native-cli',id:j.id,status:j.status==='starting'?'running':j.status==='cancelling'?'running':j.status,local:true}))]
 const active=combined.filter(pending),done=combined.filter(j=>j.status==='completed')
 const rows=filter==='active'?active:filter==='done'?done:combined
 return <section className="task-center" ref={panel} role="dialog" aria-modal="false" aria-label="项目任务">
  <header className="task-center-heading"><div><strong>项目任务</strong><span>{project.name}</span></div>{nativeStatus&&host?.renderLocalTaskForm&&<button className="new-local-task" onClick={()=>setNewLocal(!newLocal)}>{newLocal?'返回任务':'运行本机工具'}</button>}<IconButton title="关闭任务面板" onClick={onClose}><X size={17}/></IconButton></header>
  {newLocal?<div className="task-local-form">{host?.renderLocalTaskForm?.(project,()=>{setNewLocal(false);setFilter('active');onChanged()})}</div>:<><nav className="task-center-filters" aria-label="筛选任务">{([['active','进行中',active.length],['all','全部',combined.length],['done','已完成',done.length]] as const).map(([key,label,count])=><button key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}<span>{count}</span></button>)}</nav>
  <div className="task-center-list">{rows.length?rows.map(job=>job.local?<NativeTaskCard key={'native:'+job.id} job={job}/>:<TaskCard key={job.id} job={job} project={project} onChanged={onChanged} onClose={onClose}/>):<div className="task-center-empty"><Check size={20}/><span>{filter==='active'?'当前没有正在执行的任务':'这里还没有任务记录'}</span>{filter!=='all'&&<button onClick={()=>setFilter('all')}>查看全部任务</button>}</div>}</div></>}
 </section>
}

function NativeTaskCard({job}:{job:any}){
 const [open,setOpen]=useState(['queued','starting','running','cancelling'].includes(job.status)),[events,setEvents]=useState<any[]>([]),[error,setError]=useState('')
 useEffect(()=>{if(!open)return;let active=true,cursor=0,pending=false;const load=async()=>{if(pending)return;pending=true;try{const response=await fetch('/desktop/jobs/'+job.id+'/events?after='+cursor);if(!response.ok)throw new Error('执行记录暂不可用');const value=await response.json();if(active){setEvents(old=>[...old,...value.events]);cursor=value.next_cursor??cursor}}catch(e){if(active)setError((e as Error).message)}finally{pending=false}};setEvents([]);void load();const timer=setInterval(load,2000);return()=>{active=false;clearInterval(timer)}},[job.id,open])
 const running=['queued','starting','running','cancelling'].includes(job.status)
 return <article className={'task-run-card task-run-'+job.status} data-task-id={'native:'+job.id}><button className="task-card-toggle" aria-expanded={open} onClick={()=>setOpen(!open)}><span className="task-card-icon"><FileText size={17}/></span><span className="task-card-identity"><strong>{job.prompt||'本机工具执行'}</strong><span>{job.engine==='codex'?'Codex':'Claude Code'}<time>{time(new Date(job.created_at).toISOString())}</time></span></span><span className={'task-state task-state-'+job.status}>{nativeStatusLabel(job.status)}</span><ChevronDown size={15}/></button><div className="task-card-current"><span>{job.cwd}</span></div>{open&&<div className="task-card-detail"><pre className="native-task-output">{events.map(nativeEventText).filter(Boolean).join('\n')||'暂无输出'}</pre>{(error||job.error)&&<p role="alert" className="task-card-error">{error||job.error}</p>}{running&&<button onClick={()=>void fetch('/desktop/jobs/'+job.id+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(()=>window.dispatchEvent(new Event('workbench:jobs-updated')))}>停止执行</button>}</div>}</article>
}

export function TaskCard({job,project,onChanged,onClose,defaultOpen=false}:{job:Job;project:Project;onChanged:()=>void;onClose:()=>void;defaultOpen?:boolean}){
 const task=job.task,Icon=icons[job.kind]||FileText,host=useEmbeddedWorkbench()
 const [expanded,setExpanded]=useState(()=>defaultOpen||pending(job)||['failed','interrupted'].includes(job.status)),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const [feedback,setFeedback]=useState('')
 const code=job.result?.code_result,interaction=code?.interaction
 const planReview=job.status==='waiting_input'&&interaction?.request?.interaction_type==='plan_review'
 const reply=async(action:'approve'|'modify')=>{setBusy(true);setError('');try{await api(projectPath(project,'/research-flow/runs/'+job.id+'/reply'),jsonBody({interaction_id:interaction.id,response:{action,...(action==='modify'?{feedback:feedback.trim()}:{})}}));setFeedback('');onChanged()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const title=task?.title||'处理 · '+(job.result?.entry?.title||job.result?.name||project.name)
 const current=task?.steps.find(s=>s.id===task.current_step)
 const counts=task?.counts
 const action=async(name:'retry'|'cancel')=>{setBusy(true);setError('');try{await api(projectPath(project,'/literature/downloads/'+job.id+'/'+name),jsonBody({}));onChanged()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const resume=async()=>{setBusy(true);setError('');try{await api(projectPath(project,'/research-flow/runs/'+job.id+'/resume'),jsonBody({}));onChanged()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const statusIcon=job.status==='running'?<Loader2 size={12} className="spin"/>:job.status==='queued'?<Clock size={12}/>:job.status==='completed'?<Check size={12}/>:['failed','interrupted'].includes(job.status)?<AlertCircle size={12}/>:<Square size={10}/>
 const preview=(url:string,label:string)=>{if(host?.previewFile)host.previewFile(url,label);else window.open(url,'_blank','noopener');onClose()}
 return <article className={'task-run-card task-run-'+job.status} data-task-id={job.id}>
  <button className="task-card-toggle" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>
   <span className="task-card-icon"><Icon size={17}/></span><span className="task-card-identity"><strong title={title}>{title}</strong><span>{task?.type_label||'后台任务'}<time dateTime={job.created}>{time(job.created)}</time></span></span>
   <span className={'task-state task-state-'+job.status}>{statusIcon}{statusNames[job.status]||'等待更新'}</span><ChevronDown size={15} className={expanded?'task-toggle-open':''}/>
  </button>
  <div className="task-card-current"><span>{task?.summary||job.stage}</span>{!['research-flow','simulation'].includes(job.kind)&&task&&task.total_steps>0&&<small>{task.completed_steps}/{task.total_steps} 步骤完成</small>}</div>
  {expanded&&<div className="task-card-detail">
   {!['research-flow','simulation'].includes(job.kind)&&!!task?.steps.length&&<ol className="task-pipeline" aria-label="任务流程" style={{'--task-step-count':task.steps.length} as CSSProperties}>{task.steps.map((step,i)=><li key={step.id} data-state={step.state} aria-current={step.id===task.current_step?'step':undefined} title={step.label+' · '+({done:'已完成',running:'进行中',waiting:'等待中',pending:'未开始',skipped:'未运行',failed:'未完成',cancelled:'已取消'}[step.state])}><span className="task-step-node">{step.state==='done'?<Check size={11}/>:step.state==='failed'?<X size={11}/>:step.state==='skipped'?'–':i+1}</span><span>{step.label}</span></li>)}</ol>}
   {counts&&counts.total>0&&<div className="task-measured-progress"><div><span>{current?.label||'处理进度'}</span><strong>{counts.done} / {counts.total} {counts.unit}</strong></div><progress max={counts.total} value={counts.done} aria-label={current?.label||'处理进度'}/></div>}
   {job.status==='queued'&&job.kind==='literature-download'&&<p className="task-wait-note"><Clock size={13}/>等待本机下载设备领取；设备上线后继续此任务。</p>}
   {task?.legacy&&!task.steps.length&&<p className="task-history-note">历史任务保留了结果，未记录分步执行过程。</p>}
   {job.error&&<p className="task-card-error" role="alert">{job.error}</p>}
   {planReview&&<section className="task-plan-review" aria-label="当前实施计划"><strong>确认实施计划</strong><p>查看计划后，选择继续执行或提交具体修改意见。</p><details><summary>展开完整计划</summary><pre>{interaction.request.data?.plan||interaction.request.data?.plan_preview||interaction.request.description}</pre></details><label>修改意见<textarea aria-label="计划修改意见" rows={3} value={feedback} onChange={e=>setFeedback(e.target.value)} placeholder="需要调整哪些内容…"/></label><div><button disabled={busy} onClick={()=>void reply('approve')}>确认计划并继续</button><button disabled={busy||!feedback.trim()} onClick={()=>void reply('modify')}>提交修改意见</button></div></section>}
   {task?.quality_note&&<p className="task-wait-note">{task.quality_note}</p>}
   {code?.status==='completed'&&<CodeTaskEvidence result={code} project={project} preview={preview}/>}
   {error&&<p className="task-card-error" role="alert">{error}</p>}
   <div className="task-card-actions">{task?.artifacts.map((file,i)=><button key={i} onClick={()=>preview(file.url,file.filename||file.label)}><ArrowUpRight size={13}/>{file.label}</button>)}
    {job.kind==='literature-download'&&['failed','interrupted','cancelled'].includes(job.status)&&<button disabled={busy} onClick={()=>void action('retry')}><RotateCcw size={12}/>重新下载</button>}
    {job.kind==='literature-download'&&pending(job)&&<button disabled={busy} onClick={()=>void action('cancel')}><Square size={10}/>取消</button>}
    {['research-flow','simulation'].includes(job.kind)&&['failed','interrupted'].includes(job.status)&&<button disabled={busy} onClick={()=>void resume()}><RotateCcw size={12}/>从当前阶段继续</button>}
    {job.status==='waiting_service'&&<span className="task-wait-note">服务恢复后会接续本任务</span>}
    {job.status==='waiting_input'&&!planReview&&(job.result?.code_result?.session_id)&&<a href={'/research/?project='+project.id+'&dt_workspace='+project.native_id+'&session='+job.result.code_result.session_id}>打开原会话并回复</a>}
    <span className="task-updated">更新于 {time(job.updated)}</span>
   </div>
   {['research-flow','simulation'].includes(job.kind)&&<WorkflowProgress project={project} job={job} onChanged={onChanged}/>}
   {!!task?.events.length&&<details className="task-event-history"><summary>执行记录 <ChevronRight size={12}/></summary><ol>{task.events.map((event,i)=><li key={i}><time>{time(event.time)}</time><span>{task.steps.find(s=>s.id===event.step)?.label||'任务'} · {({running:'开始',done:'完成',waiting:'等待',completed:'任务完成',failed:'任务未完成',interrupted:'中断',cancelled:'已取消'} as Record<string,string>)[event.state]||event.state}</span></li>)}</ol></details>}
  </div>}
 </article>
}

export function CodeTaskEvidence({result,project,preview}:{result:Record<string,any>;project:Project;preview:(url:string,name:string)=>void}){
 const files=(result.files||[]) as {path:string;read_back?:boolean}[]
 const verification=result.verification||{},checks=Array.isArray(verification.checks)?verification.checks:[]
 const validation=Array.isArray(result.validation)?result.validation:[]
 const recorded=checks.length>0||validation.length>0||Object.keys(verification).length>0
 return <section className="code-task-evidence" aria-label="代码成果与验证依据">
  <h3>本轮代码成果</h3>
  {files.length?<ul>{files.map(file=><li key={file.path}><button onClick={()=>preview('/research/api'+projectPath(project,'/file?path='+encodeURIComponent(file.path)),file.path.split('/').pop()||file.path)}><FileText size={13}/><span>{file.path}</span><ArrowUpRight size={12}/></button><small>{file.read_back?'已保存并回读':'待核对保存'}</small></li>)}</ul>:<p>本次回执没有列出项目文件。</p>}
  <h3>验证依据</h3>
  {recorded?<details><summary>查看执行器回传的验证记录</summary><pre>{JSON.stringify({verification,validation},null,2)}</pre></details>:<p className="task-wait-note">执行器未回传结构化验证记录。保存成功不表示测试或科学验证通过。</p>}
  {result.published_reply&&<details><summary>查看本轮运行说明</summary><pre>{result.published_reply}</pre></details>}
  {result.limitations?.length>0&&<p>已记录的限制：{result.limitations.join('；')}</p>}
  {result.session_id&&<a href={'/research/?project='+project.id+'&dt_workspace='+project.native_id+'&session='+encodeURIComponent(result.session_id)}>回到原会话继续处理</a>}
 </section>
}
