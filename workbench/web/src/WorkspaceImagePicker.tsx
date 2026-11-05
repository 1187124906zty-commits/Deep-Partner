import {useEffect,useState} from 'react'
import {Folder,ChevronRight,Upload,ArrowLeft,Image} from 'lucide-react'
import {api,base,projectPath,type Project} from './api'
import {Modal,Empty,Loading} from './ui'

export function WorkspaceImagePicker({project,onClose,onSelect,onUpload,onError}:{project:Project;onClose:()=>void;onSelect:(src:string)=>void;onUpload:()=>void;onError:(e:unknown)=>void}){
 const [path,setPath]=useState('results'),[rows,setRows]=useState<any[]|null>(null)
 useEffect(()=>{setRows(null);void api(projectPath(project,'/files?path='+encodeURIComponent(path))).then(v=>setRows(v.items)).catch(onError)},[path,project.id])
 return <Modal title="选择工作台图片" onClose={onClose} wide><div className="workspace-image-picker"><nav><button onClick={()=>setPath(path.split('/').slice(0,-1).join('/'))}><ArrowLeft size={14}/>上一级</button><button onClick={()=>setPath('')}>项目文件</button><ChevronRight size={13}/><span>{path||'根目录'}</span><div className="toolbar-spacer"/><button onClick={onUpload}><Upload size={14}/>从电脑上传</button></nav>{rows===null?<Loading/>:<div className="workspace-image-grid">{rows.filter(r=>r.kind==='folder'||/\.(png|jpe?g|webp|gif)$/i.test(r.name)).map(r=><button key={r.path} onClick={()=>r.kind==='folder'?setPath(r.path):onSelect(base+projectPath(project,'/file?path='+encodeURIComponent(r.path)))}>{r.kind==='folder'?<Folder size={36}/>:<img loading="lazy" src={base+projectPath(project,'/file?path='+encodeURIComponent(r.path))} alt={r.name}/>}<strong>{r.name}</strong></button>)}</div>}{rows&&!rows.some(r=>r.kind==='folder'||/\.(png|jpe?g|webp|gif)$/i.test(r.name))&&<Empty>此文件夹没有图片</Empty>}</div></Modal>
}
