/** Read the real session snapshot; never skip unseen events using server last_seq. */
export function resumableFollowup(detail:any):{id:string;status:string}|undefined{
 const active=detail.active_turns?.[0]||detail.active_turn
 const id=active?.turn_id||active?.id||detail.active_turn_id,status=String(active?.status||detail.status||'')
 return id&&['queued','running','waiting_input'].includes(status)?{id,status}:undefined
}
