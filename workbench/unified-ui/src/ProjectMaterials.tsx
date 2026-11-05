import {createContext,useContext,useState,useEffect,type ReactNode} from 'react'
import {api,projectPath,type Project} from '@workbench/api'

type MaterialReceipt={items:{name:string;path:string;searchable:boolean;knowledge_status:string}[];saved:number;searchable:number;knowledge_task?:string;knowledge_error?:string;project:Project}
const Context=createContext<Project|null>(null)
export function ProjectMaterialsProvider({project,children}:{project:Project;children:ReactNode}){return <Context.Provider value={project}>{children}</Context.Provider>}
export function useProjectMaterials(){
 const project=useContext(Context)
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[indexing,setIndexing]=useState(false)
 const upload=async(files:File[])=>{
  if(!project||!files.length)return null
  setBusy(true);setError('');setMessage('正在保存到项目…')
  try{
   const data=new FormData();files.forEach(file=>data.append('files',file))
   const result=await api<MaterialReceipt>(projectPath(project,'/attachments'),{method:'POST',body:data})
   setMessage(`已保存 ${result.saved} 份材料${result.searchable?'，可检索文本已就绪':''}${result.knowledge_task?'；知识库正在建立索引':''}`)
   if(result.knowledge_task)setIndexing(true)
   if(result.knowledge_error)setError('附件已保存；语义索引暂未完成，可先用项目全文检索。')
   window.dispatchEvent(new CustomEvent('deeppartner:project-updated',{detail:result.project}))
   window.dispatchEvent(new CustomEvent('workbench:artifact-updated'))
   return result
  }catch(e){setMessage('');setError((e as Error).message);return null}finally{setBusy(false)}
 }
 useEffect(()=>{
  if(!project||!indexing)return
  let closed=false
  const timer=setInterval(()=>void api<any>(projectPath(project,'/attachments')).then(result=>{
   if(closed)return
   if(result.index?.status==='ready'&&result.index?.statistics?.rag_initialized){setIndexing(false);setMessage('材料已保存，知识库索引已就绪')}
   if(['failed','error'].includes(result.index?.status)){setIndexing(false);setError('语义索引未完成；材料已保留，可使用全文检索。')}
  }).catch(()=>{}),3000)
  return()=>{closed=true;clearInterval(timer)}
 },[project?.id,indexing])
 return {project,upload,busy,message,error}
}
