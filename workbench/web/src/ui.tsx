import {useEffect,useRef,type ReactNode} from 'react'
import {X,Loader2} from 'lucide-react'
export function IconButton({title,onClick,children,active=false,disabled=false,pressed}:{title:string;onClick:()=>void;children:ReactNode;active?:boolean;disabled?:boolean;pressed?:boolean}){
 return <button className={'icon-button'+(active?' active':'')} title={title} aria-label={title} aria-pressed={pressed} disabled={disabled} onClick={onClick}>{children}</button>
}
export function Modal({title,onClose,children,wide=false}:{title:string;onClose:()=>void;children:ReactNode;wide?:boolean}){
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[onClose])
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><section role="dialog" aria-modal="true" aria-label={title} className={'modal'+(wide?' modal-wide':'')}><header><h2>{title}</h2><IconButton title="关闭" onClick={onClose}><X size={19}/></IconButton></header>{children}</section></div>
}
export function BusyOverlay({label='正在加载',detail=''}:{label?:string;detail?:string}){return <div className="activity-veil" role="status" aria-live="polite"><div className="activity-orbit"><span/><Loader2 size={23} className="spin"/></div><strong>{label}</strong>{detail&&<small>{detail}</small>}<div className="activity-dots"><i/><i/><i/></div></div>}
export function Loading(){return <div className="loading activity-host"><BusyOverlay label="正在加载内容"/></div>}
export function PaperTitle({value,onChange,label,readOnly=false,typography}:{value:string;onChange:(v:string)=>void;label:string;readOnly?:boolean;typography?:string}){
 const ref=useRef<HTMLTextAreaElement>(null)
 const resize=()=>{const node=ref.current;if(node){node.style.height='auto';node.style.height=node.scrollHeight+'px'}}
 useEffect(resize,[value,typography])
 useEffect(()=>{const node=ref.current;if(!node)return;let width=0;const observer=new ResizeObserver(rows=>{const next=rows[0].contentRect.width;if(next!==width){width=next;resize()}});observer.observe(node);return()=>observer.disconnect()},[])
 return <textarea ref={ref} rows={1} className="paper-title-input" aria-label={label} value={value} readOnly={readOnly} onChange={e=>onChange(e.target.value)}/>
}
export function Empty({children,action}:{children:ReactNode;action?:ReactNode}){return <div className="empty"><div>{children}</div>{action}</div>}
export function Download({href,children}:{href:string;children:ReactNode}){return <a className="button" href={href} download>{children}</a>}
