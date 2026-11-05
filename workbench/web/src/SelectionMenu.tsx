import {useEffect,useRef} from 'react'
import {createPortal} from 'react-dom'
import {Copy,MessageSquare,Highlighter,Sparkles} from 'lucide-react'
export const annotationColors=[['黄色','#facc15'],['绿色','#86d5a3'],['蓝色','#93c5fd'],['粉色','#f9a8d4'],['紫色','#c4b5fd']]
export function SelectionMenu({x,y,onClose,onHighlight,onNote,onAsk,onCopy}:{x:number;y:number;onClose:()=>void;onHighlight:(color:string)=>void;onNote:()=>void;onAsk:()=>void;onCopy:()=>void}){
 const ref=useRef<HTMLDivElement>(null)
 useEffect(()=>{const close=(e:Event)=>{if(!ref.current?.contains(e.target as Node))onClose()},key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()};document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key)}},[onClose])
 const act=(fn:()=>void)=>{fn();onClose()}
 return createPortal(<div ref={ref} role="menu" aria-label="选文操作" className="selection-context-menu" style={{left:Math.max(8,Math.min(x,innerWidth-240)),top:Math.max(8,Math.min(y,innerHeight-220))}} onMouseDown={e=>e.preventDefault()}><div className="selection-menu-colors"><Highlighter size={16}/>{annotationColors.map(([name,color])=><button key={color} role="menuitem" aria-label={name+'高亮'} title={name+'高亮'} style={{backgroundColor:color}} onClick={()=>act(()=>onHighlight(color))}/>)}</div><button role="menuitem" onClick={()=>act(onNote)}><MessageSquare size={15}/>写批注</button><button role="menuitem" onClick={()=>act(onAsk)}><Sparkles size={15}/>问 Dito</button><button role="menuitem" onClick={()=>act(onCopy)}><Copy size={15}/>复制</button></div>,document.body)
}
