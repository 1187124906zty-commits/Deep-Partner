export type WritingMode={mode:'writing'|'research';phase:'auto'|'draft'|'submission'|'revision'}
export const defaultWritingMode:WritingMode={mode:'research',phase:'auto'}
export function readWritingMode(workspace:string):WritingMode{
 try{return {...defaultWritingMode,...JSON.parse(localStorage.getItem('deeppartner.writing.'+workspace)||'{}')}}catch{return defaultWritingMode}
}
export function storeWritingMode(workspace:string,value:WritingMode){localStorage.setItem('deeppartner.writing.'+workspace,JSON.stringify(value))}
export function writingTurnCommand<T extends {type?:string;capability?:string|null;config?:Record<string,unknown>;llm_selection?:unknown}>(message:T,workspace:string):T & {config?:Record<string,unknown>}{
 if(message.type!=='start_turn')return message
 if(message.capability&&message.capability!=='chat')return message
 const state=readWritingMode(workspace)
 const requested=message.config?.partner_mode
 const mode=requested==='research'||requested==='writing'?requested:state.mode
 const phase=requested==='research'?'auto':message.config?.partner_writing_phase||state.phase
 return {...message,config:{...message.config,partner_mode:mode,partner_writing_phase:phase,
  ...(message.llm_selection?{partner_llm_selection:message.llm_selection}:{})}}
}
