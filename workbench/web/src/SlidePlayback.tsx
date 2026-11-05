import {useEffect,useRef} from 'react'
import {ChevronLeft,ChevronRight,X} from 'lucide-react'

export function SlidePlayback({sections,page,onPage,image,onClose}:{sections:{title:string;content:string}[];page:number;onPage:(page:number)=>void;image?:string;onClose:()=>void}){
 const dialog=useRef<HTMLDivElement>(null)
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.focus();return()=>previous?.focus()},[])
 const section=sections[page]
 if(!section)return null
 return <div className="slide-playback" role="dialog" aria-modal="true" aria-label="PPT 播放" ref={dialog} tabIndex={-1} onKeyDown={e=>{
   if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();onPage(Math.min(sections.length-1,page+1))}
   if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();onPage(Math.max(0,page-1))}
   if(e.key==='Home'){e.preventDefault();onPage(0)}
   if(e.key==='End'){e.preventDefault();onPage(sections.length-1)}
   if(e.key==='Escape'){e.preventDefault();e.stopPropagation();onClose()}
   if(e.key==='Tab'){
     const buttons=Array.from(dialog.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')||[])
     const index=buttons.indexOf(document.activeElement as HTMLButtonElement)
     e.preventDefault();buttons[(index+(e.shiftKey?-1:1)+buttons.length)%buttons.length]?.focus()
   }
 }}>
   <header><span>{section.title}</span><button aria-label="退出播放" onClick={onClose}><X size={19}/></button></header>
   <div className="slide-playback-stage">{image?<img src={image} alt={section.title}/>:<article><h1>{section.title}</h1><p>{section.content}</p></article>}</div>
   <footer><span>方向键翻页 · Esc 退出</span><button aria-label="播放上一页" disabled={page===0} onClick={()=>onPage(page-1)}><ChevronLeft size={20}/></button><output aria-live="polite">{page+1} / {sections.length}</output><button aria-label="播放下一页" disabled={page===sections.length-1} onClick={()=>onPage(page+1)}><ChevronRight size={20}/></button></footer>
 </div>
}
