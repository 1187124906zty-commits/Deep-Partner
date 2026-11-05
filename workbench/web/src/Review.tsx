import {useEmbeddedWorkbench} from './EmbeddedHost'
import {useEffect,useRef,useState} from 'react'
import {MessageSquarePlus,Check,History,Send,ArrowUpRight,Copy,X} from 'lucide-react'
import {api,jsonBody,projectPath,type Project} from './api'
import {IconButton,Modal} from './ui'

export type Anchor={area:string;asset:string;title:string;quote?:string;locator:Record<string,any>}
export type ReviewItem=Anchor&{id:string;body:string;color:string;status:string;created:string;updated:string;origin:string}
export type MenuAction={label:string;action:()=>void;disabled?:boolean}
export function ContextMenu({x,y,actions,onClose}:{x:number;y:number;actions:MenuAction[];onClose:()=>void}){
 const ref=useRef<HTMLDivElement>(null)
 useEffect(()=>{const close=(event:Event)=>{if(!ref.current?.contains(event.target as Node))onClose()};const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()};window.addEventListener('pointerdown',close);window.addEventListener('keydown',key);window.addEventListener('blur',onClose);return()=>{window.removeEventListener('pointerdown',close);window.removeEventListener('keydown',key);window.removeEventListener('blur',onClose)}},[onClose])
 return <div ref={ref} className="context-menu" role="menu" style={{left:Math.min(x,window.innerWidth-220),top:Math.min(y,window.innerHeight-actions.length*36-18)}}>{actions.map(a=><button role="menuitem" key={a.label} disabled={a.disabled} onClick={()=>{onClose();a.action()}}>{a.label}</button>)}</div>
}
export function useAnnotations(project:Project,area:string,asset:string,version=0){
 const [items,setItems]=useState<ReviewItem[]>([])
 const refresh=async()=>{if(!asset){setItems([]);return}const r=await api(projectPath(project,'/annotations?area='+area+(asset==='*'?'':'&asset='+encodeURIComponent(asset))));setItems(r.items)}
 useEffect(()=>{let active=true;void refresh().catch(()=>{});const timer=setInterval(()=>{if(active)void refresh().catch(()=>{})},7000);return()=>{active=false;clearInterval(timer)}},[project.id,area,asset,version])
 return {items,refresh}
}
export function QuestionComposer({project,anchor,onClose,onSaved,onError,color='#edc54b'}:{project:Project;anchor:Anchor;onClose:()=>void;onSaved:(item:ReviewItem)=>void;onError:(e:unknown)=>void;color?:string}){
 const host=useEmbeddedWorkbench()
 const [body,setBody]=useState('');const [busy,setBusy]=useState(false)
 const save=async(send=false)=>{setBusy(true);try{const item=await api<ReviewItem>(projectPath(project,'/annotations'),jsonBody({...anchor,body,color}));onSaved(item);if(send){if(host)await host.submitAnnotations(project,[item.id]);else{const result=await api(projectPath(project,'/annotations/submit'),jsonBody({ids:[item.id]}));window.open(result.url,'_blank','noopener')}}onClose()}catch(e){onError(e)}finally{setBusy(false)}}
 return <Modal title="批注" onClose={onClose}><div className="question-composer"><div className="annotation-location">{anchor.title}{anchor.locator.line_start?' · L'+anchor.locator.line_start+(anchor.locator.line_end!==anchor.locator.line_start?'–'+anchor.locator.line_end:''):anchor.locator.page?' · 第'+anchor.locator.page+'页':''}</div>{anchor.quote&&<blockquote>{anchor.quote}</blockquote>}<textarea autoFocus rows={5} aria-label="批注问题" placeholder="希望修改、核对或进一步解释什么？" value={body} onChange={e=>setBody(e.target.value)}/><div className="modal-actions"><button onClick={onClose}>取消</button><button disabled={busy||!body.trim()} onClick={()=>void save()}><MessageSquarePlus size={15}/>记录问题</button><button className="primary" disabled={busy||!body.trim()} onClick={()=>void save(true)}><Send size={15}/>发送</button></div></div></Modal>
}
export function AnnotationRail({project,items,onClose,onLocate,onError,onRefresh}:{project:Project;items:ReviewItem[];onClose:()=>void;onLocate?:(item:ReviewItem)=>void;onError:(e:unknown)=>void;onRefresh:()=>void}){
 const [history,setHistory]=useState(false);const visible=items.filter(x=>history||!['resolved','deleted'].includes(x.status))
 return <aside className="anchored-notes"><header><strong>{history?'批注历史':'此处批注'}</strong><div className="toolbar-spacer"/><IconButton title="查看历史批注" active={history} onClick={()=>setHistory(!history)}><History size={16}/></IconButton><IconButton title="收起批注" onClick={onClose}><X size={17}/></IconButton></header><div className="anchored-note-list">{visible.map(item=><article key={item.id} className={'anchored-note '+item.status}><button className="note-quote" onClick={()=>onLocate?.(item)}>{item.quote||item.title}</button><p>{item.body}</p><footer><time>{new Date(item.created).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}</time>{item.locator.line_start&&<span>L{item.locator.line_start}{item.locator.line_end!==item.locator.line_start?'–'+item.locator.line_end:''}</span>}{item.status==='resolved'?<span>已处理</span>:<IconButton title="标记为已处理" onClick={()=>void api(projectPath(project,'/annotations/'+item.id),jsonBody({status:'resolved'},'PATCH')).then(onRefresh).catch(onError)}><Check size={15}/></IconButton>}{item.locator.session_url&&<a href={item.locator.session_url} target="_blank" rel="noreferrer" title="相关会话"><ArrowUpRight size={15}/></a>}</footer></article>)}{!visible.length&&<div className="notes-empty">暂无批注</div>}</div></aside>
}
