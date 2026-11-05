/** Preserve Dito's explicit hand-back using the deployed protocol's nullable answerer. */
export function nativeTurnCommand<T extends {type?:string;session_id?:unknown;answer_by?:unknown;workspace_id?:unknown}>(message:T,workspaceId?:string):T{
 if(message.type!=='start_turn')return message
 let copy=message
 if(message.session_id===null){copy={...copy};delete copy.session_id}
 if(message.answer_by==='')copy={...copy,answer_by:null}
 if(workspaceId&&!message.workspace_id)copy={...copy,workspace_id:workspaceId}
 return copy
}
