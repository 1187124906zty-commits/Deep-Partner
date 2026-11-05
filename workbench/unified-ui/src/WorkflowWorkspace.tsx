import {useCallback,useEffect,useState} from 'react'
import {Activity,ArrowUpRight,BookOpen,Check,ChevronRight,FileText,FolderCode,RefreshCw,Search} from 'lucide-react'
import {api,projectPath,type Job,type Project} from '@workbench/api'
import {TaskCard} from '@workbench/TaskCenter'
import type {WorkbenchArea} from '@workbench/App'
import './workflow-workspace.css'

type Group='active'|'attention'|'done'|'closed'
type Overview={project:{id:string;name:string};observed_at:string;limit:number;counts:Record<Group,number>;
 jobs:(Job&{group:Group})[];routes:{id:string;label:string;steps:{id:string;label:string;can_pause:boolean}[]}[];
 rules:{version:string;content:string;scope:string;review:string}}
const states:Record<string,string>={running:'执行中',queued:'排队中',waiting_service:'等待服务',waiting_input:'需要回复',paused:'已暂停',failed:'未完成',interrupted:'已中断',completed:'已完成',cancelled:'已取消'}
const filters:[Group|'all',string][]=[['attention','待处理'],['active','进行中'],['done','已完成'],['all','全部']]

export default function WorkflowWorkspace({project,onChat,onArea}:{project:Project;onChat:()=>void;onArea:(area:WorkbenchArea)=>void}){
 const [data,setData]=useState<Overview|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false)
 const [tab,setTab]=useState<'tasks'|'routes'|'rules'>('tasks'),[filter,setFilter]=useState<Group|'all'>('all'),[query,setQuery]=useState(''),[selected,setSelected]=useState(()=>new URLSearchParams(location.search).get('task')||'')
 const refresh=useCallback(async()=>{setLoading(true);try{setData(await api<Overview>(projectPath(project,'/workflow-overview')));setError('')}catch(e){setError((e as Error).message)}finally{setLoading(false)}},[project.id])
 useEffect(()=>{void refresh();const timer=setInterval(()=>{if(!document.hidden)void refresh()},5000);const changed=()=>void refresh();window.addEventListener('workbench:jobs-updated',changed);return()=>{clearInterval(timer);window.removeEventListener('workbench:jobs-updated',changed)}},[refresh])
 const rows=(data?.jobs||[]).filter(job=>(filter==='all'||job.group===filter)&&(!query||(job.task?.subject||job.task?.title||job.stage).toLowerCase().includes(query.toLowerCase())))
 const current=rows.find(job=>job.id===selected)||rows[0]
 return <main className="workflow-workspace" aria-label="项目工作流">
  <header className="workflow-heading"><div><h1>研究进展</h1><p>查看正在推进的工作，以及需要你决定的下一步。</p></div><button onClick={()=>void refresh()} disabled={loading} aria-label="刷新工作流"><RefreshCw size={16}/></button></header>
  <nav className="workflow-tabs" aria-label="工作流视图">{([['tasks','任务'],['routes','流程说明'],['rules','执行规范']] as const).map(([id,label])=><button key={id} aria-current={tab===id?'page':undefined} onClick={()=>setTab(id)}>{label}</button>)}<span>{data?'更新于 '+new Date(data.observed_at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}):'正在读取项目'}</span></nav>
  {error&&<p className="workflow-page-error" role="alert">{error}<button onClick={()=>void refresh()}>重试</button></p>}
  {tab==='tasks'&&<>
   <div className="workflow-list-tools"><nav aria-label="任务状态筛选">{filters.map(([id,label])=><button key={id} aria-pressed={filter===id} onClick={()=>setFilter(id)}>{label}<span>{id==='all'?data?.jobs.length||0:data?.counts[id]||0}</span></button>)}</nav><label><Search size={15}/><input aria-label="查找工作流任务" placeholder="查找任务" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
   {rows.length>0?<div className="workflow-master-detail"><div className="workflow-run-list" role="list" aria-label="研究任务">{rows.map(job=><button key={job.id} role="listitem" data-workflow-id={job.id} aria-current={current?.id===job.id?'true':undefined} onClick={()=>setSelected(job.id)}><span className={'workflow-status-dot is-'+job.group} aria-hidden="true">{job.status==='completed'?<Check size={12}/>:<Activity size={12}/>}</span><span className="workflow-run-text"><strong>{job.task?.subject||job.task?.title||job.stage}</strong><small>{job.task?.type_label||job.kind}<span>{job.task?.summary||job.stage}</span></small></span><span className="workflow-run-state">{states[job.status]||job.status}</span><ChevronRight size={14}/></button>)}</div><section className="workflow-run-detail" aria-label="选中任务详情">{current&&<TaskCard key={current.id} project={project} job={current} defaultOpen onChanged={()=>void refresh()} onClose={()=>{}}/>}</section></div>:<div className="workflow-empty"><h2>{query?'没有匹配的任务':filter==='all'?'从一个研究问题开始':'当前没有这类任务'}</h2><p>{filter==='all'&&!query?'在对话中提出需求，文献检索、代码验证和写作任务会在这里留下真实进度。':'切换状态或清除关键词，可以查看其他工作。'}</p>{filter==='all'&&!query&&<div className="workflow-entry-list"><button onClick={onChat}><Activity size={18}/><span><strong>提出或继续研究问题</strong><small>带着当前项目的材料进入对话</small></span><ArrowUpRight size={16}/></button><button onClick={()=>onArea('literature')}><BookOpen size={18}/><span><strong>阅读与比较文献</strong><small>从原文、页码与证据出发</small></span><ArrowUpRight size={16}/></button><button onClick={()=>onArea('code')}><FolderCode size={18}/><span><strong>检查程序与运行结果</strong><small>回到项目文件与已保存的实现</small></span><ArrowUpRight size={16}/></button><button onClick={()=>onArea('paper')}><FileText size={18}/><span><strong>继续修改当前稿件</strong><small>保留正文、来源与修改历史</small></span><ArrowUpRight size={16}/></button></div>}</div>}
   {data&&data.jobs.length===data.limit&&<p className="workflow-footnote">显示最近 {data.limit} 项；正在执行和等待处理的任务优先保留。</p>}
  </>}
  {tab==='routes'&&data&&<section className="workflow-route-guide"><p>阶段由程序与实际任务确定。带停留标记的步骤可以在开始前暂停；外部求解内部阶段显示实际回执。</p>{data.routes.map(route=><article key={route.id}><h2>{route.label}</h2><ol>{route.steps.map(step=><li key={step.id}><span>{step.label}</span>{step.can_pause&&<small>可设停留点</small>}</li>)}</ol></article>)}</section>}
  {tab==='rules'&&data&&<section className="workflow-rules"><p className="workflow-rule-version">当前规范 {data.rules.version}</p><h2>任务范围</h2><p>{data.rules.scope}</p><h2>检查与评审</h2><p>{data.rules.review}</p><details><summary>阅读完整规范</summary><pre>{data.rules.content}</pre></details><p className="workflow-footnote">这是当前执行规范。各任务中的原始需求、执行回执与作者决定单独保留。</p></section>}
 </main>
}
