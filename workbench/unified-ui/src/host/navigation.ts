import {useMemo,useSyncExternalStore} from 'react'
import {hostHref,logicalPath} from './routes'
export const entryPath=window.location.pathname.endsWith('/')?window.location.pathname:window.location.pathname.replace(/[^/]*$/,'')||'/'
const listeners=new Set<()=>void>()
let projectRoutes=new Map<string,string>()
export function setProjectRouteIndex(projects:{id:string;native_id:string}[]){projectRoutes=new Map(projects.map(project=>[project.native_id,project.id]))}
let snapshot=window.location.pathname+window.location.search+window.location.hash
const notify=()=>{snapshot=window.location.pathname+window.location.search+window.location.hash;listeners.forEach(f=>f())}
window.addEventListener('popstate',notify)
export function toHostHref(url:string){const resolved=hostHref(url,window.location.href,entryPath);const target=new URL(resolved,location.href);if(target.origin===location.origin&&target.pathname===entryPath){const workspace=target.searchParams.get('dt_workspace');if(workspace&&projectRoutes.has(workspace))target.searchParams.set('project',projectRoutes.get(workspace)!);return target.pathname+target.search+target.hash}return resolved}
export function navigate(url:string,replace=false){const destination=toHostHref(url);if(/^https?:/.test(destination)&&new URL(destination).origin!==location.origin){location.assign(destination);return}if(!destination.startsWith(entryPath+'?')&&destination!==entryPath&& !destination.startsWith(entryPath+'#')){location.assign(destination);return}history[replace?'replaceState':'pushState'](null,'',destination);notify()}
export function useLocationSnapshot(){return useSyncExternalStore(cb=>{listeners.add(cb);return()=>listeners.delete(cb)},()=>snapshot,()=>snapshot)}
const router={push:(url:string,_options?:{scroll?:boolean})=>navigate(url),replace:(url:string,_options?:{scroll?:boolean})=>navigate(url,true),back:()=>history.back(),forward:()=>history.forward(),refresh:()=>notify(),prefetch:async(_url?:string)=>{}}
export function useRouter(){useLocationSnapshot();return router}
export function useSearchParams(){const value=useLocationSnapshot();return useMemo(()=>new URL(value,location.origin).searchParams,[value])}
export function usePathname(){const q=useSearchParams();return logicalPath(q.toString())}
export function useParams<T=Record<string,string>>():T{const q=useSearchParams();return {sessionId:q.get('session')||undefined,section:q.get('settings_section')||undefined} as T}
export function notFound():never{throw new Error('此内容不存在或当前账户无法访问。')}
export function redirect(url:string):never{navigate(url,true);throw new Error('Navigating')}
