import {api,base,projectPath,type Job,type Project} from './api'

/** A single live channel; polling is used only while the stream is unavailable. */
export function subscribeProjectJobs(project:Project,onJobs:(jobs:Job[])=>void){
 let closed=false,pending=false,timer:ReturnType<typeof setInterval>|undefined
 const load=async()=>{if(closed||pending)return;pending=true;try{const value=await api<{jobs:Job[]}>(projectPath(project,'/jobs'));if(!closed)onJobs(value.jobs)}catch{}finally{pending=false}}
 const stopFallback=()=>{if(timer!==undefined){clearInterval(timer);timer=undefined}}
 const fallback=()=>{if(closed||timer!==undefined)return;void load();timer=setInterval(()=>void load(),2000)}
 const source=typeof EventSource==='undefined'?null:new EventSource(base+projectPath(project,'/jobs/events'),{withCredentials:true})
 if(source){source.addEventListener('jobs',event=>{if(closed)return;try{const value=JSON.parse((event as MessageEvent).data);if(Array.isArray(value.jobs))onJobs(value.jobs)}catch{}});source.onopen=stopFallback;source.onerror=fallback}else fallback()
 const refresh=()=>void load();window.addEventListener('workbench:jobs-updated',refresh)
 return()=>{closed=true;source?.close();stopFallback();window.removeEventListener('workbench:jobs-updated',refresh)}
}
