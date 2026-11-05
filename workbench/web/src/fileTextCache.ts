/** Keep a small, versioned working set so reopening a file is immediate. */
const textCache=new Map<string,string>()
const maxBytes=8*1024*1024
let total=0
export const fileTextKey=(url:string,modified:number)=>url+'&version='+modified
export const cachedFileText=(key:string)=>textCache.get(key)
export function rememberFileText(key:string,text:string){
 if(text.length*2>maxBytes)return
 const old=textCache.get(key);if(old!==undefined)total-=old.length*2
 textCache.delete(key);textCache.set(key,text);total+=text.length*2
 while(total>maxBytes||textCache.size>12){const first=textCache.keys().next().value!;total-=textCache.get(first)!.length*2;textCache.delete(first)}
}
function clear(){textCache.clear();total=0}
if(typeof window!=='undefined'){window.addEventListener('deeppartner:auth-required',clear);window.addEventListener('deeppartner:authenticated',clear)}
