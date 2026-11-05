import {useEffect,useState} from 'react'
import {FileCode,Link,HelpCircle} from 'lucide-react'
import {api,projectPath,type Project} from './api'

export function ImageProvenance({project,path}:{project:Project;path:string}){
 const [data,setData]=useState<any>();useEffect(()=>{void api(projectPath(project,'/image-context?path='+encodeURIComponent(path))).then(setData).catch(()=>{})},[project.id,path])
 return <details className="image-provenance"><summary><Link size={13}/>来源与使用位置{data?.usages?.length>0&&<small>{data.usages.length}</small>}</summary>{data&&<div><p><FileCode size={13}/><strong>绘图程序</strong><code>{data.plot_program||'未知来源'}</code></p>{data.compute_program&&<p><strong>计算程序</strong><code>{data.compute_program}</code></p>}<small>{data.width} × {data.height} 像素 · {path}</small>{data.usages?.length?data.usages.map((u:any,i:number)=><article key={i}><strong>{u.section||'论文正文'}</strong><span>{u.caption||'图片 '+(i+1)}</span><blockquote>{u.sentence||'此处直接放置图片，尚无正文索引句。'}</blockquote></article>):<p className="muted">当前稿件尚未引用这张图片。</p>}</div>}</details>
}
