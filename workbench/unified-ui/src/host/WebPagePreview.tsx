import {useEffect,useState} from 'react'
import {ExternalLink,Globe,Loader2,BookOpen} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function WebPagePreview({url}:{url:string}){
 const [mode,setMode]=useState<'page'|'reading'>('page'),[content,setContent]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 useEffect(()=>{setContent('');setError('');setMode('page')},[url])
 const read=async()=>{setMode('reading');if(content||busy)return;setBusy(true);setError('');try{const response=await fetch('/research/dify/api/web-evidence?url='+encodeURIComponent(url),{credentials:'same-origin'});const data=await response.json();if(!response.ok||data.status!=='ready')throw new Error(data.detail||data.error?.message||'该页面暂不能读取正文，请打开原网页');setContent(typeof data.content==='string'?data.content:JSON.stringify(data.content,null,2))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="dp-web-preview" aria-label="网页预览"><header><Globe size={15}/><span title={url}>{new URL(url).hostname}</span><a href={url} target="_blank" rel="noreferrer"><ExternalLink size={13}/>浏览器打开</a></header><nav aria-label="网页查看方式"><button aria-pressed={mode==='page'} onClick={()=>setMode('page')}>原网页</button><button aria-pressed={mode==='reading'} onClick={()=>void read()}><BookOpen size={13}/>阅读正文</button></nav>{mode==='page'?<><small>如原站限制嵌入，可切换“阅读正文”查看公开内容。</small><iframe title={'网页 '+new URL(url).hostname} src={url} sandbox="allow-scripts allow-same-origin allow-forms allow-popups" referrerPolicy="no-referrer"/></>:<article>{busy?<p role="status"><Loader2 size={16} className="animate-spin"/>正在读取公开网页…</p>:error?<p role="alert">{error}</p>:<ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>}</article>}</section>
}
