export type Project={id:string;name:string;native_id:string;root:string;config:Record<string,any>}
export type TaskStep={id:string;label:string;state:'pending'|'waiting'|'running'|'done'|'skipped'|'failed'|'cancelled';started?:string;finished?:string}
export type TaskProgress={version:number;workflow:string;type_label:string;title:string;subject:string;steps:TaskStep[];current_step:string|null;completed_steps:number;total_steps:number;summary:string;waiting:boolean;legacy?:boolean;counts?:{done:number;total:number;unit:string}|null;events:{step:string|null;state:string;time:string}[];artifacts:{label:string;url:string;filename?:string}[];quality_note?:string;context?:Record<string,any>}
export type Job={id:string;kind:string;status:string;stage:string;created?:string;updated?:string;result:Record<string,any>;error:string;task?:TaskProgress}
export const base='/research/api'
export async function api<T=any>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch(base+path,{credentials:'same-origin',...init,headers:{...(init?.body instanceof FormData?{}:{'Content-Type':'application/json'}),...init?.headers}})
  if(!response.ok){let message='操作未完成';try{message=(await response.json()).detail||message}catch{};if(response.status===401){if(document.documentElement.dataset.deeppartnerHost==='true')window.dispatchEvent(new CustomEvent('deeppartner:auth-required'));else window.location.href='/login?next='+encodeURIComponent('/research/')}throw new Error(message)}
  return response.json()
}
export async function native<T=any>(path:string,project:Project,init?:RequestInit):Promise<T>{
  const join=path.includes('?')?'&':'?';const response=await fetch(path+join+'dt_workspace='+encodeURIComponent(project.native_id),{credentials:'same-origin',...init,headers:{...(init?.body instanceof FormData?{}:{'Content-Type':'application/json'}),...init?.headers}})
  if(!response.ok){let message='DeepTutor暂时未完成操作';try{message=(await response.json()).detail||message}catch{};throw new Error(message)}
  return response.json()
}
export const prettySize=(n:number)=>n>=1024**3?(n/1024**3).toFixed(1)+' GB':n>=1024**2?(n/1024**2).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':n+' B'
export const projectPath=(p:Project,suffix='')=>'/projects/'+p.id+suffix
export function jsonBody(body:unknown,method='POST'):RequestInit{return {method,body:JSON.stringify(body)}}
