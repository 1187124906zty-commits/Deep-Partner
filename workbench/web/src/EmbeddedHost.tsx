import {createContext,useContext,useEffect,useId,useRef,type ReactNode} from 'react'
import type {Project} from './api'
import type {Anchor} from './Review'
export interface EmbeddedWorkbenchHost {
  previewFile?:(url:string,filename:string)=>void
  renderLocalTaskForm?:(project:Project,onStarted:()=>void)=>ReactNode
  sessionId:string|null
  notify?:(message:string)=>void
  submitAnnotations:(project:Project,ids:string[],attachments?:{type:string;filename?:string;base64?:string;mime_type?:string}[])=>Promise<void>
  renderFeedback?:(props:{project:Project;anchor:Anchor;onError:(e:unknown)=>void;onClose?:()=>void})=>ReactNode
  submitFigure:(project:Project,request:{path:string;message:string;selection:string[];changes:Record<string,any>;revision:number;image:string;include_context:boolean;edit_session:string})=>Promise<void>
  registerSave:(save:()=>Promise<void>)=>void
  setDitoLocation?:(key:string,location:{project:Project;anchor:Anchor;priority:number;capture?:()=>Promise<string>|string}|null)=>void
  openDito?:(project:Project,anchor?:Anchor)=>void
}
const Context=createContext<EmbeddedWorkbenchHost|null>(null)
export function EmbeddedWorkbenchProvider({value,children}:{value:EmbeddedWorkbenchHost;children:ReactNode}){return <Context.Provider value={value}>{children}</Context.Provider>}
export function useEmbeddedWorkbench(){return useContext(Context)}
export function useDitoLocation(project:Project,anchor:Anchor,priority=10,capture?:()=>Promise<string>|string){
 const host=useEmbeddedWorkbench(),key=useId(),captureRef=useRef(capture);captureRef.current=capture
 const value=JSON.stringify(anchor)
 useEffect(()=>{host?.setDitoLocation?.(key,{project,anchor:JSON.parse(value),priority,capture:capture?()=>captureRef.current?.()||'':undefined})},[host?.setDitoLocation,key,project.id,value,priority,!!capture])
 useEffect(()=>()=>host?.setDitoLocation?.(key,null),[host?.setDitoLocation,key])
}
