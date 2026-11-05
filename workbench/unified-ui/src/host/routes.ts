/** The physical entry stays /research/ on Web and / on the desktop. */
export function logicalPath(search:string):string{
  const q=new URLSearchParams(search)
  if(q.get('surface')==='settings')return '/settings/'+encodeURIComponent(q.get('settings_section')||'general')
  const id=q.get('session')
  return id?`/chat/${encodeURIComponent(id)}`:'/chat'
}
export function hostHref(raw:string,current:string,entry:string):string{
  const base=new URL(current),target=new URL(raw,base)
  if(target.origin!==base.origin)return target.toString()
  if(target.pathname===entry)return target.pathname+target.search+target.hash
  if(!/^\/(chat(?:\/[^/]+)?|settings(?:\/.*)?)\/?$/.test(target.pathname))return target.pathname+target.search+target.hash
  const q=new URLSearchParams(base.search)
  if(!target.pathname.startsWith('/settings'))q.delete('session')
  q.delete('surface');q.delete('settings_section')
  target.searchParams.forEach((value,key)=>q.set(key,value))
  if(target.pathname.startsWith('/settings')){q.set('surface','settings');q.set('settings_section',target.pathname.split('/')[2]||'general')}
  else {const id=target.pathname.match(/^\/chat\/([^/]+)/)?.[1];q.delete('view');q.delete('area');q.delete('file');if(id)q.set('session',decodeURIComponent(id));else q.set('view','chat')}
  return entry+(q.size?'?'+q:'')+target.hash
}
export function projectHref(entry:string,project:{id:string;native_id:string},session?:string|null):string{
  const q=new URLSearchParams({project:project.id,dt_workspace:project.native_id})
  if(session)q.set('session',session)
  return entry+'?'+q
}
