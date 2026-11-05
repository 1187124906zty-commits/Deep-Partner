import {useEmbeddedWorkbench} from './EmbeddedHost'
import {useEffect,useState} from 'react'
import {CheckCircle2,Loader2} from 'lucide-react'
import {api,jsonBody,projectPath,type Project,type Job} from './api'
import {Modal} from './ui'

const stages=[['ingestion','材料解析'],['idea','问题界定'],['landscape','文献与现状'],['concept','研究方案'],['evidence','证据与结果'],['code','科研程序'],['figure','图表'],['writing','稿件'],['translation','翻译'],['slides-plan','PPT 内容计划'],['slides-export','PPT 导出'],['review','审查意见'],['delivery','最终交付']]
const purposes=[['group','组会讨论'],['conference','学术报告'],['project','项目汇报'],['proposal','开题报告'],['defense','学位答辩'],['literature','文献研读']]
const defaults:Record<string,string>={'writing':'manuscript/main.json','translation':'manuscript/main.json','slides-plan':'slides/plan.json','slides-export':'slides/exports/研究汇报.pptx'}
const decisions:Record<string,string>={passed:'满足当前阶段要求',needs_revision:'需要修订',blocked:'关键条件未满足',insufficient_evidence:'仍缺评审依据',needs_evidence:'仍缺评审依据',needs_author:'需要作者判断',author_override:'作者已决定带偏差继续',stale:'产物、来源或规则已更新，需重新评审',not_reviewed:'尚未评审'}

export function StageQuality({project,onError,initialStage='writing',initialPurpose='group'}:{project:Project;onError:(e:unknown)=>void;initialStage?:string;initialPurpose?:string}){
 const [stage,setStage]=useState(initialStage),[purpose,setPurpose]=useState(initialPurpose),[paths,setPaths]=useState(defaults[initialStage]||''),[sources,setSources]=useState(initialStage.startsWith('slides-')?'manuscript/main.json':''),[use,setUse]=useState(''),[reviews,setReviews]=useState<any[]>([]),[busy,setBusy]=useState(''),[result,setResult]=useState<any>(),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false)
 const load=async()=>{const value=await api(projectPath(project,'/quality/reviews?stage='+encodeURIComponent(stage)+(stage.startsWith('slides-')?'&purpose='+purpose:'')));setReviews(value.reviews||value.items||[])}
 useEffect(()=>{void load().catch(onError)},[project.id,stage,purpose])
 const run=async()=>{setBusy('正在读取原材料并独立评审');try{
  const started=await api(projectPath(project,'/quality/reviews'),jsonBody({operation_id:crypto.randomUUID(),stage,purpose:stage.startsWith('slides-')?purpose:'',artifact_paths:paths.split('\n').map(x=>x.trim()).filter(Boolean),source_paths:sources.split('\n').map(x=>x.trim()).filter(Boolean),intended_use:use}))
  for(let i=0;i<120;i++){
   const value=await api<{jobs:Job[]}>(projectPath(project,'/jobs'));const job=value.jobs.find(x=>x.id===started.job_id)
   if(job?.status==='completed'){setResult(job.result);await load();return}
   if(job&&['failed','interrupted'].includes(job.status))throw new Error(job.error||'评审未完成，原产物已保留')
   await new Promise(resolve=>setTimeout(resolve,3000))
  }
  throw new Error('评审仍在运行，可在任务列表中查看同一任务')
 }catch(e){onError(e)}finally{setBusy('')}}
 const override=async()=>{const selected=result||reviews[0];if(!selected)return;setBusy('正在记录作者决定');try{const r=await api(projectPath(project,'/quality/reviews/'+(selected.review_id||selected.id)+'/override'),jsonBody({operation_id:crypto.randomUUID(),confirmed,reason}));setResult(r);await load();setConfirmed(false);setReason('')}catch(e){onError(e)}finally{setBusy('')}}
 const current=result||reviews[0]
 return <div className="stage-quality"><div className="settings-provider-grid"><label>当前阶段<select value={stage} disabled={Boolean(busy)} onChange={e=>{setStage(e.target.value);setPaths(defaults[e.target.value]||'');setResult(undefined)}}>{stages.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>{stage.startsWith('slides-')&&<label>汇报用途<select value={purpose} onChange={e=>{setPurpose(e.target.value);setResult(undefined)}}>{purposes.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>}</div><label>产物路径（项目相对路径，每行一个）<textarea rows={2} value={paths} onChange={e=>setPaths(e.target.value)} placeholder="project/src/model.py"/></label><label>原始材料路径（每行一个）<textarea rows={2} value={sources} onChange={e=>setSources(e.target.value)} placeholder="manuscript/main.json"/></label><label>本阶段的用途与范围<textarea rows={2} value={use} onChange={e=>setUse(e.target.value)} placeholder="说明本阶段需要回答的问题与适用范围"/></label><button className="primary" disabled={Boolean(busy)||!paths.trim()} onClick={()=>void run()}>{busy?<Loader2 size={14} className="spin"/>:<CheckCircle2 size={14}/>} {busy||'评审当前产物'}</button>{current&&<section className="quality-result"><h4>{decisions[current.stale?'stale':current.decision]||current.decision||'阶段评审'}</h4><p>{current.score_percent??current.overall?.score??current.overall?.percent??current.overall_percent??'—'} </p>{(current.dimensions||current.scores||[]).map((d:any)=><article key={d.id}><strong>{d.label||d.id} · {d.score===null?'未评':d.score+' / 4'}</strong><p>{d.reason}</p>{d.evidence_refs?.length>0&&<small>{d.evidence_refs.map((e:any)=>e.path+' '+JSON.stringify(e.locator||'')).join('；')}</small>}</article>)}{(current.hard_checks||current.checks||[]).map((c:any)=><p key={c.id}><strong>{c.id}</strong>：{c.status}{c.verified===false?'（尚未独立验证）':''}</p>)}{(current.issues||[]).map((issue:any,i:number)=><article key={issue.id||i}><strong>{issue.severity} · {issue.reason||issue.message}</strong><p>{issue.requested_change}</p></article>)}{current.evaluator?.visual_review_performed===false&&<p>本次模型仅检查文本；页面视觉由实际渲染和相应工具另行检查。</p>}{current.can_proceed===false&&!current.stale&&<details><summary>作者决定</summary><p>记录带偏差继续的原因，原始评分与失败项保留。</p><textarea aria-label="带偏差继续的原因" value={reason} onChange={e=>setReason(e.target.value)}/><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已查看当前版本的评分与未通过项</label><button disabled={Boolean(busy)||!confirmed||reason.trim().length<3} onClick={()=>void override()}>记录并继续</button></details>}<details><summary>完整依据与版本记录</summary><pre>{JSON.stringify(current,null,2)}</pre></details></section>}</div>
}

export function StageQualityButton({project,onError,stage,purpose}:{project:Project;onError:(e:unknown)=>void;stage:string;purpose?:string}){
 const embedded=useEmbeddedWorkbench()
 const [open,setOpen]=useState(false)
 if(embedded)return null
 return <><button onClick={()=>setOpen(true)}><CheckCircle2 size={14}/>阶段评分</button>{open&&<Modal title="阶段评分" wide onClose={()=>setOpen(false)}><StageQuality project={project} onError={onError} initialStage={stage} initialPurpose={purpose}/></Modal>}</>
}
