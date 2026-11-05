import {useEffect,useState,useRef} from 'react'
import {PenLine,BookOpen,ChevronDown,X,Loader2,ExternalLink} from 'lucide-react'
import {api,jsonBody,projectPath,type Project} from '@workbench/api'
import ThemeSelect from '../ThemeSelect'
import {readWritingMode,storeWritingMode,type WritingMode} from './writing-mode'

type Journal={id:string;name:string;publisher?:string;issn?:string[];homepage?:string}
type Run={id:string;phase:string;status:string;stage:string;request?:string;stage_history?:{stage:string;completed:string}[];stage_plan?:string[];intent?:{goal:string};outputs?:{url?:string};error?:string}
export default function WritingToolbar({project}:{project:Project|null}){
 const [mode,setMode]=useState<WritingMode>(()=>readWritingMode(project?.native_id||''))
 const [journal,setJournal]=useState<Journal|null>(null),[opened,setOpened]=useState(false),[query,setQuery]=useState(''),[candidates,setCandidates]=useState<Journal[]>([]),[searching,setSearching]=useState(false),[error,setError]=useState(''),[run,setRun]=useState<Run|null>(null),[stages,setStages]=useState<[string,string][]>([]),[workflow,setWorkflow]=useState('')
 const projectRef=useRef(project?.id),saving=useRef(false),[savingSettings,setSavingSettings]=useState(false);projectRef.current=project?.id
 const load=async()=>{
  if(!project)return
  const value=await api<any>(projectPath(project,'/writing'))
  if(projectRef.current!==project.id||saving.current)return
  setJournal(value.settings.journal||null);setRun(value.runs[0]||null);setStages(value.stages);setWorkflow(value.workflow?.workflow_url||'')
  const state:WritingMode={mode:value.settings.mode,phase:value.settings.phase};setMode(state);storeWritingMode(project.native_id,state)
 }
 useEffect(()=>{setMode(readWritingMode(project?.native_id||''));void load().catch(e=>setError(e.message));const timer=setInterval(()=>{if(!document.hidden)void load().catch(()=>{})},5000);return()=>clearInterval(timer)},[project?.id])
 useEffect(()=>{if(!opened)return;const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpened(false)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[opened])
 useEffect(()=>{
  if(!opened||query.trim().length<2){setCandidates([]);return}
  let alive=true;const timer=setTimeout(()=>{setSearching(true);void api<any>('/journals/search?q='+encodeURIComponent(query)).then(v=>{if(alive){setCandidates(v.items||[]);setError('')}}).catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setSearching(false)})},350)
  return()=>{alive=false;clearTimeout(timer)}
 },[query,opened])
 const save=async(change:Partial<WritingMode>&{journal?:Journal})=>{
  if(!project)return
  if(saving.current)return
  saving.current=true;setSavingSettings(true)
  try{await api(projectPath(project,'/writing/settings'),jsonBody(change,'PUT'));if(projectRef.current!==project.id)return;const next={mode:change.mode||mode.mode,phase:change.phase||mode.phase};setMode(next);storeWritingMode(project.native_id,next);setError('');if(change.journal){setJournal(change.journal);setOpened(false)}}catch(e){setError((e as Error).message)}finally{saving.current=false;setSavingSettings(false)}
 }
 const running=run&&['running','queued'].includes(run.status)
 const index=run?stages.findIndex(([id])=>id===run.stage):-1
 return <div className="dp-writing-toolbar">
  <div className="dp-writing-controls" aria-busy={savingSettings}><PenLine size={14}/><ThemeSelect disabled={savingSettings} aria-label="工作模式" value={mode.mode} onChange={e=>void save({mode:e.target.value as WritingMode['mode']})}><option value="writing">写作模式</option><option value="research">研究对话</option></ThemeSelect>
  {mode.mode==='writing'&&<><ThemeSelect disabled={savingSettings} aria-label="写作阶段" value={mode.phase} onChange={e=>void save({phase:e.target.value as WritingMode['phase']})}><option value="auto">自动理解任务</option><option value="draft">初稿</option><option value="submission">投稿</option><option value="revision">返修</option></ThemeSelect><button className="dp-writing-journal" aria-label="选择目标期刊" disabled={savingSettings} aria-expanded={opened} onClick={()=>setOpened(!opened)}><BookOpen size={13}/><span>{journal?.name||'目标期刊'}</span><ChevronDown size={12}/></button></>}
  </div>
  {mode.mode==='writing'&&run&&<div className="dp-writing-progress" role="status">{running?<Loader2 size={13} className="animate-spin"/>:<PenLine size={13}/>}<span>{({draft:'初稿',submission:'投稿',revision:'返修'} as Record<string,string>)[run.phase]||'理解任务'} · {run.status==='completed'?'成果已保存':run.status==='failed'||run.status==='interrupted'?'执行未完成':stages[index]?.[1]||run.stage}</span>{run.outputs?.url&&<button onClick={()=>window.dispatchEvent(new CustomEvent('deeppartner:preview-file',{detail:{type:'file',url:run.outputs!.url,filename:'写作成果.md'}}))}>查看成果</button>}{running&&<button onClick={()=>project&&void api(projectPath(project,'/writing/runs/'+run.id+'/cancel'),jsonBody({})).then(load)}>停止</button>}{['failed','interrupted'].includes(run.status)&&<button onClick={()=>project&&void api(projectPath(project,'/writing/runs/'+run.id+'/resume'),jsonBody({})).then(load).catch(e=>setError(e.message))}>继续当前阶段</button>}{workflow&&<a href={workflow} target="_blank" rel="noreferrer" aria-label="查看写作工作流"><ExternalLink size={12}/></a>}</div>}
  {mode.mode==='writing'&&running&&<ol className="dp-writing-steps" aria-label="写作工作流阶段">{stages.filter(([id])=>!run.stage_plan||run.stage_plan.includes(id)).map(([id,label])=><li key={id} data-state={stages.findIndex(([key])=>key===id)<index?'done':id===run.stage?'running':'pending'} title={label}>{label}</li>)}</ol>}
  {mode.mode==='writing'&&run&&<details className="dp-writing-inspect"><summary>查看本次写作任务</summary><p>{run.request||run.intent?.goal}</p><ol>{stages.filter(([id])=>!run.stage_plan||run.stage_plan.includes(id)).map(([id,label])=><li key={id}>{label} · {run.stage_history?.some(row=>row.stage===id)?'已完成':id===run.stage&&run.status==='running'?'正在执行':'尚未完成'}</li>)}</ol>{run.error&&<p role="alert">{run.error}</p>}</details>}
  {opened&&<section className="dp-writing-journal-picker" aria-label="期刊选择"><div><strong>目标期刊</strong><button aria-label="关闭期刊选择" onClick={()=>setOpened(false)}><X size={15}/></button></div><input aria-label="检索目标期刊" autoFocus placeholder="输入期刊名称或 ISSN" value={query} onChange={e=>setQuery(e.target.value)}/>{searching&&<p role="status">正在检索期刊…</p>}<ul>{candidates.map(j=><li key={j.id}><button onClick={()=>void save({journal:j})}><strong>{j.name}</strong><small>{j.publisher} · {j.issn?.join(' / ')}</small></button></li>)}</ul><p>选定后自动检索并保存期刊指南与可用标杆资料。未选择时，Agent 根据任务继续执行。</p></section>}
  {error&&<small role="alert" className="dp-writing-error">{error}</small>}
 </div>
}
