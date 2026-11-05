import type {MessageAttachment} from '@/features/chat/ChatStateAdapter'
import {apiUrl} from '@/lib/api'

export default function ChatAttachmentPreviews({attachments,onOpen}:{attachments?:MessageAttachment[];onOpen?:(attachment:MessageAttachment)=>void}){
 const images=(attachments||[]).filter(file=>file.type==='image'||file.mime_type?.startsWith('image/'))
 if(!images.length)return null
 return <div className="dp-chat-image-previews">{images.map((file,index)=>{
  const src=file.url?(/^(https?:|blob:|data:)/.test(file.url)?file.url:apiUrl(file.url)):file.base64?(file.base64.startsWith('data:')?file.base64:`data:${file.mime_type||'image/png'};base64,${file.base64}`):null
  return src&&<button key={file.filename||index} aria-label={'查看图片 '+(file.filename||index+1)} onClick={()=>onOpen?.(file)}><img src={src} alt={file.filename||'上传的图片'}/></button>
 })}</div>
}
