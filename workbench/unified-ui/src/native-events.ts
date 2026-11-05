export interface LocalEvent{seq?:number;stream?:string;data?:any;content?:string;text?:string;message?:string}
/** Read the actual Codex/Claude stream envelopes; retain every raw event
 * separately so replay and diagnosis do not depend on presentation parsing. */
export function nativeEventText(event:LocalEvent):string{
 const data=event.data??event
 if(typeof data==='string')return data
 if(typeof data.text==='string')return data.text
 if(typeof data.content==='string')return data.content
 if(data.type==='item.completed'&&data.item?.type==='agent_message')return data.item.text||''
 if(data.item?.type==='command_execution')return data.item.aggregated_output|| (data.type==='item.started'?'$ '+(data.item.command||''):'')
 if(data.type==='assistant'&&Array.isArray(data.message?.content))return data.message.content.filter((block:any)=>block.type==='text').map((block:any)=>block.text||'').join('\n')
 if(data.type==='content_block_delta')return data.delta?.text||''
 if(data.type==='result')return data.result||''
 if(typeof data.message==='string')return data.message
 if(event.stream==='lifecycle'){const labels:Record<string,string>={started:'任务已启动',completed:'任务完成',failed:'任务失败',cancelled:'任务已取消',cancel_requested:'正在停止任务'};return labels[data.type]||data.status||''}
 return ''
}
export function nativeStatusLabel(status:string){return ({queued:'排队中',starting:'正在启动',running:'正在执行',cancelling:'正在停止',completed:'已完成',failed:'执行失败',cancelled:'已取消'} as Record<string,string>)[status]||'任务状态已更新'}
