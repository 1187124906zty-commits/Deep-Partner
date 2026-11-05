import {createContext,useContext,useMemo} from 'react'
import {AssistantRuntimeProvider,MessagePrimitive,ThreadPrimitive,useExternalStoreRuntime,type ThreadMessageLike} from '@assistant-ui/react'
import {BookOpen,Check,ChevronDown,Clock3,FileText,Loader2,TriangleAlert} from 'lucide-react'
import MarkdownRenderer from '@/components/common/MarkdownRenderer'
import {AskUserOptions,extractMessageSegments,leadingTraceEvents} from '@/components/chat/home/AskUserOptions'
import {hasPendingAskUser} from '@/lib/ask-user-state'
import type {FollowupMessage} from '@/context/QuizFollowupContext'
import type {StreamEvent} from '@/features/chat/model/protocol'
import {useDitoTasks} from './DitoTasks'
import './research-thread.css'

type Reply={text?:string;answers?:{questionId:string;text:string}[]}
const ReplyContext=createContext<(value:Reply)=>void|boolean|Promise<void|boolean>>(()=>false)
const convertMessage=(message:ThreadMessageLike)=>message
type Props={questionKey:string;messages:FollowupMessage[];isStreaming:boolean;activeTurnId:string|null;error:string|null;stage?:string;onSubmitUserReply:(value:Reply)=>void|boolean|Promise<void|boolean>}
const publicTypes=new Set(['tool_call','tool_result','progress','sources','error','done','wait_for_input'])

export function publicActivity(events:StreamEvent[]){
 const calls=new Map<string,{id:string;name:string;title:string;state:string;result?:any}>();let latest='';let failed=false
 for(const [i,e] of events.entries()){
  if(!publicTypes.has(e.type))continue
  const meta=e.metadata||{},name=String(meta.tool_name||meta.tool||e.content||'工具'),id=String(meta.tool_call_id||meta.call_id||name+':'+i)
  if(e.type==='progress'&&meta.trace_kind==='call_status'&&meta.label){const label=String(meta.label);latest=({'Exploring':'核对当前研究材料','Context exploration':'读取本轮相关材料','Tool call':'调用研究工具'} as Record<string,string>)[label]||label}
  if(e.type==='tool_call'){
   const args=meta.args as Record<string,unknown>|undefined
   const operation=String(args?.research_operation||args?.action||'')
   const title=({inspect:'回读研究依据',update:'修订研究记录与任务',overview:'读取研究主线和已有认识',outline:'整理研究大纲',context:'读取当前研究背景',evidence:'查找文献与知识库依据',deliver:'保存研究成果'} as Record<string,string>)[operation]||({research_workbench:'处理项目研究材料',search:'查找资料',read_file:'阅读材料'} as Record<string,string>)[name]||'执行研究工具'
   calls.set(id,{id,name,title,state:'running'});latest=title
  }
  if(e.type==='tool_result'){
   let result:any;try{result=JSON.parse(e.content)}catch{result=null}
   const candidates=[...calls.values()].filter(c=>c.name===name&&c.state==='running')
   const call=calls.get(id)||(candidates.length===1?candidates[0]:undefined)
   if(call){call.state=result?.error||result?.status==='failed'||meta.success===false?'failed':'returned';call.result=result}
  }
  if(e.type==='error')failed=true
 }
 return {calls:[...calls.values()],latest,failed}
}

function ActivityPart({data}:{data:any}){
 const value=publicActivity(data.events||[]),{project}=useDitoTasks()
 if(!value.calls.length&&!value.latest)return null
 return <details className="research-message-activity"><summary><ChevronDown size={12}/>{value.calls.length?'已调用 '+value.calls.length+' 项研究工具':value.latest}</summary><ol>{value.calls.map(c=><li key={c.id}>{c.state==='failed'?<TriangleAlert size={12}/>:c.state==='returned'?<Check size={12}/>:<Clock3 size={12}/>}<div><span>{c.title}</span><small>{c.state==='returned'?'已取得工具结果':c.state==='failed'?'未完成，查看后续处理':'已发起'}</small>{c.result?.path&&['applied','saved','completed'].includes(c.result.status)&&<a href={'/research/api/projects/'+project.id+'/file?path='+encodeURIComponent(c.result.path)} onClick={e=>{e.preventDefault();window.dispatchEvent(new CustomEvent('deeppartner:preview-file',{detail:{type:'document',filename:c.result.path.split('/').pop(),url:e.currentTarget.href}}))}}><FileText size={12}/>{c.result.status==='applied'?'打开研究修订':'打开已保存成果'}</a>}</div></li>)}</ol></details>
}
function QuotePart({data}:{data:any}){
 const raw=String(data.text||'');const title=raw.match(/(?:当前材料|当前项目|材料名称)：([^\n]+)/)?.[1]||'所选材料'
 return <details className="research-message-quote"><summary><BookOpen size={12}/>{title}</summary><pre>{raw}</pre></details>
}
function AskPart({data}:{data:any}){const submit=useContext(ReplyContext);return <AskUserOptions data={data} onSubmit={submit}/>}
function AttachmentPart({data}:{data:any}){
 const files=(data.files||[]).filter((f:any)=>f.type!=='quote');if(!files.length)return null
 return <div className="research-message-files">{files.map((f:any,i:number)=>{const url=f.url||(f.base64?'data:'+(f.mime_type||'application/octet-stream')+';base64,'+f.base64:undefined);return url?<a key={i} href={url} target="_blank" rel="noreferrer">{f.type==='image'||f.mime_type?.startsWith('image/')?<img src={url} alt={f.filename||'图片'}/>:<FileText size={15}/>}<span>{f.filename||'附件'}</span></a>:<span key={i}>{f.filename||'附件已发送'}</span>})}</div>
}
function TextPart({text}:{text:string}){return <MarkdownRenderer content={text} variant="compact"/>}
const parts={Text:TextPart,data:{by_name:{'native-quote':QuotePart,'native-activity':ActivityPart,'native-ask-user':AskPart,'native-files':AttachmentPart,'native-steering':({data}:{data:any})=><p className="research-message-steering">补充：{data.messages.join('\n')}</p>}}}

export default function ResearchThreadMessages({questionKey,messages,isStreaming,activeTurnId,error,stage,onSubmitUserReply}:Props){
 const visible=messages.filter(m=>m.role!=='system')
 const converted=useMemo(()=>visible.map((message,index)=>{
  const last=index===visible.length-1,streaming=last&&isStreaming,events=message.events||[],segments=message.role==='assistant'?extractMessageSegments(events,message.content,{streaming}):[]
  const content:any[]=[]
  if(message.role==='user'){
   for(const text of message.quotes||[])content.push({type:'data',name:'native-quote',data:{text}})
   if((message as any).attachments?.length)content.push({type:'data',name:'native-files',data:{files:(message as any).attachments}})
   content.push({type:'text',text:message.content})
  }else{
   const before=leadingTraceEvents(events,segments);if(before.length)content.push({type:'data',name:'native-activity',data:{events:before}})
   if(segments.length){
    for(const s of segments){if(s.kind==='text'&&s.text)content.push({type:'text',text:s.text});else if(s.kind==='ask_user')content.push({type:'data',name:'native-ask-user',data:s.data});else if(s.kind==='trace')content.push({type:'data',name:'native-activity',data:{events:s.events}});else if(s.kind==='user_input')content.push({type:'data',name:'native-steering',data:{messages:s.messages}})}
   }else if(message.content)content.push({type:'text',text:message.content})
  }
  const final=events.findLast(e=>e.type==='done'),waiting=hasPendingAskUser(events,activeTurnId)
  const status=waiting?{type:'requires-action',reason:'interrupt'}:streaming?{type:'running'}:final?.metadata.status==='cancelled'?{type:'incomplete',reason:'cancelled'}:final?.metadata.status==='failed'||error&&last?{type:'incomplete',reason:'error'}:{type:'complete',reason:'stop'}
  return {id:questionKey+':'+index,role:message.role,content,...(message.role==='assistant'?{status}:{})} as ThreadMessageLike
 }),[messages,isStreaming,error,questionKey,activeTurnId])
 const runtime=useExternalStoreRuntime({messages:converted,convertMessage,isRunning:isStreaming,activeRunId:activeTurnId||undefined,isDisabled:true,unstable_enableToolInvocations:false,onNew:async()=>{throw new Error('请使用当前研究输入框发送')}})
 const last=visible.at(-1),pending=visible.some(m=>hasPendingAskUser(m.events,activeTurnId)),activity=publicActivity(last?.events||[])
 const done=(last?.events||[]).findLast(e=>e.type==='done'),stopped=done?.metadata.status==='cancelled'
 return <AssistantRuntimeProvider runtime={runtime}><ReplyContext.Provider value={onSubmitUserReply}><ThreadPrimitive.Root className="research-thread"><ThreadPrimitive.Messages>{({message})=><MessagePrimitive.Root className={message.role==='user'?'research-user-message':'research-assistant-message'}><MessagePrimitive.Parts components={parts}/></MessagePrimitive.Root>}</ThreadPrimitive.Messages>{(isStreaming||pending||done)&&<div className="research-run-status" role="status">{pending?<Clock3 size={13}/>:isStreaming?<Loader2 size={13} className="animate-spin"/>:stopped?<Clock3 size={13}/>:<Check size={13}/>}<span>{stage==='cancelling'?'已请求停止，等待执行端确认':pending?'需要你决定，回答后继续当前任务':isStreaming?activity.latest||'正在研究当前材料':stopped?'执行端已确认停止':'本轮已结束'}</span></div>}</ThreadPrimitive.Root></ReplyContext.Provider></AssistantRuntimeProvider>
}
