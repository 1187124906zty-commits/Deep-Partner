import {useEffect,useRef,type ComponentProps} from 'react'
import OriginalComposer from '@tutor/components/chat/home/ChatComposer'
import {useProductPolicy} from './ProductPolicy'
import {useProjectMaterials} from '../ProjectMaterials'
import {classifyFile} from '@/lib/doc-attachments'
import WritingToolbar from './WritingToolbar'
export default function ResearchChatComposer(props:ComponentProps<typeof OriginalComposer>){
 const {upgradeRequired,onUpgrade}=useProductPolicy()
 const materials=useProjectMaterials(),pending=useRef<Promise<void>>(Promise.resolve())
 const add=(files:File[])=>{
  props.onAddFiles(files)
  const accepted=files.filter(file=>classifyFile(file)&&file.size<=100*1024**2)
  pending.current=pending.current.then(async()=>{
   const result=await materials.upload(accepted)
   const kb=result?.project.config.attachment_knowledge_base
   if(kb&&!props.selectedKnowledgeBases.includes(kb))props.onToggleKB(kb)
  })
  return pending.current
 }
 const addRef=useRef(add);addRef.current=add
 useEffect(()=>{
  if(!materials.project)return
  const filesFrom=(event:DragEvent|ClipboardEvent)=>Array.from(('dataTransfer' in event?event.dataTransfer:event.clipboardData)?.files||[])
  const target=(event:Event)=>(event.target as Element)?.closest?.('.dp-chat-pane')
  const over=(event:DragEvent)=>{if(target(event)&&event.dataTransfer?.types.includes('Files')){event.preventDefault();if(event.dataTransfer)event.dataTransfer.dropEffect='copy'}}
  const dropped=(event:DragEvent)=>{if(!target(event))return;const files=filesFrom(event);if(files.length){event.preventDefault();event.stopImmediatePropagation();void addRef.current(files)}}
  const pasted=(event:ClipboardEvent)=>{if(!target(event))return;const files=filesFrom(event);if(files.length){event.preventDefault();event.stopImmediatePropagation();void addRef.current(files)}}
  window.addEventListener('dragover',over,true);window.addEventListener('drop',dropped,true);window.addEventListener('paste',pasted,true)
  return()=>{window.removeEventListener('dragover',over,true);window.removeEventListener('drop',dropped,true);window.removeEventListener('paste',pasted,true)}
 },[materials.project?.id])
 const blocked=upgradeRequired&&!props.isStreaming
 return <div className="dp-composer-policy"><WritingToolbar project={materials.project}/>{(materials.busy||materials.message)&&<small className="dp-upload-status" role="status">{materials.busy?'正在保存材料…':materials.message}</small>}{materials.error&&<div className="dp-attachment-error" role="alert">{materials.error}</div>}<div inert={blocked||undefined} aria-hidden={blocked||undefined}><OriginalComposer {...props} onAddFiles={files=>void add(files)} queueWhileStreaming={upgradeRequired?false:props.queueWhileStreaming} onSend={content=>{if(!materials.busy&&(!upgradeRequired||(props.isStreaming&&props.awaitingUserReply)))props.onSend(content)}}/></div>{blocked&&<div className="dp-composer-upgrade" role="status"><p>请手动升级 DeepPartner 后开始新任务。当前会话和成果仍可查看。</p><button onClick={onUpgrade}>查看版本</button></div>}</div>
}
