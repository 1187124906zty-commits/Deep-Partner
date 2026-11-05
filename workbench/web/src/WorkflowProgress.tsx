import {useEffect,useState} from 'react'
import {api,jsonBody,projectPath,type Job,type Project} from './api'
import './workflow-progress.css'

type Progress={id:string;status:string;summary:string;request:{kind:string;query:string;instruction:string;input_paths:string[];assets:string[]};
 stages:{id:string;label:string;status:string;can_pause:boolean;pause_before:boolean;checkpoint_passed:boolean;receipt?:{at?:string}}[];
 control:{revision:number;pause_requested:boolean;pause_before:string[]};pause_effect:string;
 external:Record<string,string>;coverage:{asset:string;pages:number[]}[];files:{path:string;read_back:boolean}[];
 error:string;recovery:{reason?:string;attempts?:number;retry_after?:number};actions:{pause:boolean;resume:boolean;checkpoints:boolean}}
const labels:Record<string,string>={done:'已完成',waiting:'等待继续',running:'正在执行',failed:'未完成',pending:'尚未开始'}
type Rules={standard_version:string;rule_sources:{scope:string;review:string;selected_skills:{id:string;when_to_use:string}[]}}

export function WorkflowProgress({project,job,onChanged}:{project:Project;job:Job;onChanged:()=>void}){
 const [open,setOpen]=useState(false),[value,setValue]=useState<Progress|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const [rules,setRules]=useState<Rules|null>(null)
 const base=projectPath(project,'/research-flow/runs/'+job.id)
 useEffect(()=>{if(!open)return;let active=true;void api<Progress>(base+'/progress').then(v=>{if(active){setValue(v);setError('')}}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[open,base,job.updated,job.status])
 const control=async(action:'pause'|'checkpoints'|'resume',stages?:string[])=>{
  if(!value)return
  setBusy(true);setError('')
  try{
   await api(base+(action==='resume'?'/resume':'/control'),jsonBody(action==='resume'?{}:{action,pause_before:stages,expected_revision:value.control.revision}))
   setValue(await api<Progress>(base+'/progress'));onChanged()
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <details className="workflow-progress" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary>流程与控制</summary>
  {open&&!value&&!error&&<p role="status">正在读取实际任务…</p>}
  {open&&value&&<>
   <p className="workflow-request"><strong>当前任务</strong><span>{value.request.query||value.request.instruction}</span></p>
   <ol aria-label="实际工作流阶段">{value.stages.map(step=><li key={step.id} data-state={step.status}>
    <span className="workflow-stage-mark" aria-hidden="true">{step.status==='done'?'✓':step.status==='running'?'●':'○'}</span>
    <span className="workflow-stage-title">{step.label}<small>{labels[step.status]||step.status}</small></span>
    {value.actions.checkpoints&&step.can_pause&&step.status==='pending'&&<label><input type="checkbox" checked={step.pause_before} disabled={busy||step.checkpoint_passed} onChange={e=>void control('checkpoints',e.target.checked?[...value.control.pause_before,step.id]:value.control.pause_before.filter(id=>id!==step.id))}/>开始前停留</label>}
    {!value.actions.checkpoints&&step.receipt?.at&&<time>{new Date(step.receipt.at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</time>}
   </li>)}</ol>
   <div className="workflow-control-actions">
    {value.actions.pause&&<button disabled={busy||value.control.pause_requested} onClick={()=>void control('pause')}>{value.control.pause_requested?'等待当前调用返回':'暂停后续步骤'}</button>}
    {value.actions.resume&&<button disabled={busy} onClick={()=>void control('resume')}>继续原任务</button>}
   </div>
   {(value.actions.pause||value.status==='paused')&&<p className="workflow-control-note">{value.pause_effect}</p>}
   {value.recovery.reason&&<p>当前等待：{value.recovery.reason}{value.recovery.retry_after?'；下次核对 '+new Date(value.recovery.retry_after*1000).toLocaleTimeString('zh-CN'):''}</p>}
   {(value.request.input_paths.length>0||value.request.assets.length>0)&&<p>输入材料：{[...value.request.input_paths,...value.request.assets].join('、')}</p>}
   {value.coverage.length>0&&<details><summary>实际阅读范围</summary>{value.coverage.map(row=><p key={row.asset}>{row.asset}：第 {row.pages.join('、')} 页</p>)}</details>}
   {value.files.length>0&&<details><summary>已保存产物</summary>{value.files.map(file=><p key={file.path}>{file.path} · {file.read_back?'已回读':'待核对'}</p>)}</details>}
   {Object.keys(value.external).length>0&&<details><summary>执行器状态与任务编号</summary><dl>{Object.entries(value.external).map(([key,text])=><div key={key}><dt>{key}</dt><dd>{text}</dd></div>)}</dl></details>}
   <details onToggle={e=>{if(e.currentTarget.open&&!rules)void api<Rules>(projectPath(project,'/agent-context?task='+(({code:'code',read:'reader',slides:'slides',figure:'figure',simulate:'code'} as Record<string,string>)[value.request.kind]||'literature'))).then(setRules).catch(e=>setError(e.message))}}><summary>当前适用规范</summary>{rules&&<><p>规范版本：{rules.standard_version}</p><p>{rules.rule_sources.scope}</p><p>{rules.rule_sources.review}</p>{rules.rule_sources.selected_skills.map(skill=><p key={skill.id}>{skill.id}：{skill.when_to_use}</p>)}</>}</details>
  </>}
  {error&&<p role="alert">{error}</p>}
 </details>
}
