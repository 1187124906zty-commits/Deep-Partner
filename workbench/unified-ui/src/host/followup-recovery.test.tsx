import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {QuizFollowupProvider,useQuizFollowupController,useFollowupThread} from '@/context/QuizFollowupContext'
import {resumableFollowup} from './followup-recovery'
const clients=vi.hoisted(()=>({rows:[] as any[],ack:null as null|((v:boolean)=>void)}))
vi.mock('react-i18next',()=>({useTranslation:()=>({t:(s:string)=>s})}))
vi.mock('@/lib/notebook-api',()=>({updateNotebookEntry:vi.fn()}))
vi.mock('@/features/chat/transport/UnifiedTurnClient',()=>({UnifiedTurnClient:class{
 connected=true;send=vi.fn();disconnect=vi.fn();connect=vi.fn();setResumeState=vi.fn();handler:any;
 constructor(onEvent:any){this.handler=onEvent;clients.rows.push(this)}
 sendAwaitingAck=vi.fn(()=>new Promise<boolean>(resolve=>{clients.ack=resolve}))
}}))
let controller:any,state:any,root:Root,host:HTMLDivElement
function Capture(){controller=useQuizFollowupController();state=useFollowupThread('thread');return null}
beforeEach(async()=>{clients.rows=[];(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host);await act(async()=>root.render(<QuizFollowupProvider><Capture/></QuizFollowupProvider>))})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
it('restores the actual active turn and replays from zero, preserving file attachments',async()=>{
 expect(resumableFollowup({active_turns:[{id:'t',status:'waiting_input',last_seq:99}]})).toEqual({id:'t',status:'waiting_input'})
 await act(async()=>controller.hydrateThread('thread','session',[{role:'user',content:'Read this',attachments:[{type:'file',filename:'source.pdf',url:'/api/a'}]}],{id:'t',status:'running'}))
 expect(state.activeTurnId).toBe('t');expect(state.messages[0].attachments[0].filename).toBe('source.pdf')
 expect(clients.rows[0].send).toHaveBeenCalledWith({type:'subscribe_turn',turn_id:'t',after_seq:0})
 const event={type:'content',content:'once',source:'assistant',stage:'',metadata:{},turn_id:'t',seq:1}
 await act(async()=>{clients.rows[0].handler(event);clients.rows[0].handler(event)})
 expect(state.messages.at(-1).content).toBe('once')
})
it('waits for terminal cancellation rather than treating an accepted request as stopped',async()=>{
 await act(async()=>controller.hydrateThread('thread','session',[{role:'assistant',content:'Working',events:[]}],{id:'t',status:'running'}))
 const client=clients.rows[0]
 await act(async()=>controller.cancelTurn('thread'))
 expect(state.isStreaming).toBe(true);expect(state.currentStage).toBe('cancelling');expect(client.disconnect).not.toHaveBeenCalled()
 await act(async()=>clients.ack!(true));expect(state.isStreaming).toBe(true)
 await act(async()=>client.handler({type:'done',content:'',source:'runtime',stage:'',metadata:{status:'cancelled'},turn_id:'t',seq:4}))
 expect(state.isStreaming).toBe(false);expect(state.messages.at(-1).events.at(-1).metadata.status).toBe('cancelled')
 expect(client.disconnect).toHaveBeenCalledTimes(1)
})
