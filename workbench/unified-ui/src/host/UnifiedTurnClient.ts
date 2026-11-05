import {UnifiedTurnClient as SourceClient} from '@tutor/features/chat/transport/UnifiedTurnClient'
import type {StreamEvent} from '@/features/chat/model/protocol'
import {canSendCommand} from './protocol-policy'
import {nativeTurnCommand} from './turn-command'
import {writingTurnCommand} from './writing-mode'
/** Keep the original transport, cursor, acknowledgements and replay intact.
 * Only admission of a new turn is prevented for an incompatible fixed UI. */
export class UnifiedTurnClient extends SourceClient{
 private readonly emit:(event:StreamEvent)=>void
 constructor(onEvent:(event:StreamEvent)=>void,onClose?:()=>void){super(onEvent,onClose);this.emit=onEvent}
 private admit(message:Parameters<SourceClient['send']>[0]){
  if(typeof message.type==='string'&&canSendCommand(message.type))return true
  this.emit({type:'error',source:'host',stage:'',content:'请手动升级 DeepPartner 后开始新任务。',timestamp:Date.now()/1000,metadata:{reason:'frontend_upgrade_required',retryable:false,turn_terminal:true,status:'failed'}})
  return false
 }
 override send(message:Parameters<SourceClient['send']>[0]){const workspace=new URL(location.href).searchParams.get('dt_workspace')||'';if(this.admit(message))super.send(nativeTurnCommand(writingTurnCommand(message,workspace),workspace||undefined))}
 override sendAwaitingAck(message:Parameters<SourceClient['sendAwaitingAck']>[0]){const workspace=new URL(location.href).searchParams.get('dt_workspace')||'';return this.admit(message)?super.sendAwaitingAck(nativeTurnCommand(writingTurnCommand(message,workspace),workspace||undefined)):Promise.resolve(false)}
}
