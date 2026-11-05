import {useState} from 'react'
import {FileText,X} from 'lucide-react'
import StandaloneComposer from '@tutor/components/chat/home/StandaloneComposer'
import {ActivityHeader} from '@/components/activity'
import {api,jsonBody,projectPath,type Project} from '@workbench/api'
import type {Anchor} from '@workbench/Review'
import type {StandaloneComposerSubmission} from '@tutor/components/chat/home/StandaloneComposer'

export default function FeedbackComposer({project,anchor,onError,onClose,submit}:{project:Project;anchor:Anchor;onError:(e:unknown)=>void;onClose?:()=>void;submit:(p:Project,ids:string[],attachments?:StandaloneComposerSubmission['attachments'])=>Promise<void>}){
 const [busy,setBusy]=useState(false),[includeContext,setIncludeContext]=useState(true)
 const send=async(input:StandaloneComposerSubmission)=>{if(busy)return;setBusy(true);try{const selected=includeContext?anchor:{area:anchor.area,asset:'project',title:'项目讨论',locator:{},quote:''};const note=await api(projectPath(project,'/annotations'),jsonBody({...selected,body:input.content,locator:{...selected.locator,resources:{knowledge_bases:input.knowledgeBases,history:input.historyReferences,notebooks:input.notebookReferences}}}));await submit(project,[note.id],input.attachments);onClose?.()}catch(e){onError(e)}finally{setBusy(false)}}
 return <section className="dp-feedback-composer"><ActivityHeader orb={busy?'working':'breathing'} label="问 Agent" settled={!busy}/><p className="dp-feedback-intro">继续当前项目会话，核对这处材料或提出修改。</p><StandaloneComposer onSubmit={input=>void send(input)} onCancelStreaming={()=>{}} isStreaming={busy} hasMessages={false} docked partnerControls={false} agentsAvailable={false} showCapabilityChip={false} inputPlaceholder="和 Agent 讨论这份材料…" inputHeader={includeContext?<div className="dp-context-card"><FileText size={16}/><div><strong>{anchor.title||anchor.asset}</strong><small>{anchor.quote||anchor.asset}</small></div><button aria-label="移除当前材料" onClick={()=>setIncludeContext(false)}><X size={14}/></button></div>:undefined}/></section>
}
