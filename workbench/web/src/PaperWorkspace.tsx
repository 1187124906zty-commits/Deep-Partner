import {useRef,useState} from 'react'
import {ManuscriptPanel} from './Manuscript'
import {NativeReader} from './Reader'
import type {Project} from './api'

export function PaperWorkspace(props:{project:Project;author:any;onError:(e:unknown)=>void;notify:(s:string)=>void;version:number;registerSave:(fn:()=>Promise<void>)=>void;target?:any}){
 const [mode,setMode]=useState('edit');const save=useRef<()=>Promise<void>>(async()=>{})
 const choose=async(next:string)=>{try{await save.current();setMode(next);if(next==='read')props.registerSave(async()=>{})}catch(e){props.onError(e)}}
 return <div className="paper-workspace">{mode==='edit'?<ManuscriptPanel {...props} onRead={()=>void choose('read')} registerSave={fn=>{save.current=fn;props.registerSave(fn)}}/>:<NativeReader {...props} onBack={()=>void choose('edit')}/>}</div>
}
