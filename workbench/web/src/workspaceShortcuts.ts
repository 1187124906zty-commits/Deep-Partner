import {useEffect,useRef,type RefObject} from 'react'

type Shortcuts={zoom?:(factor:number,point?:{x:number;y:number})=>void;reset?:()=>void;save?:()=>void;undo?:()=>void;redo?:()=>void;find?:()=>void;escape?:()=>void;pan?:(down:boolean)=>void;remove?:()=>void;page?:(direction:number)=>void}
export function useWorkspaceShortcuts(root:RefObject<HTMLElement|null>,actions:Shortcuts){
 const latest=useRef(actions);latest.current=actions
 useEffect(()=>{const element=root.current;if(!element)return
  const editable=(target:EventTarget|null)=>target instanceof Element&&!!target.closest('input,textarea,select,[contenteditable=true]')
  const wheel=(event:WheelEvent)=>{if(!(event.ctrlKey||event.metaKey)||!latest.current.zoom)return;event.preventDefault();event.stopPropagation();const rect=element.getBoundingClientRect();latest.current.zoom(Math.exp(-event.deltaY*.005),{x:event.clientX-rect.left,y:event.clientY-rect.top})}
  const key=(event:KeyboardEvent)=>{const a=latest.current,command=event.ctrlKey||event.metaKey,k=event.key.toLowerCase();if(command&&['+','=','-','0','s','f'].includes(k)){const action=k==='s'?a.save:k==='f'?a.find:k==='0'?a.reset:k==='-'?()=>a.zoom?.(1/1.15):()=>a.zoom?.(1.15);if(action){event.preventDefault();event.stopPropagation();action()};return}if(editable(event.target))return
   if(command&&k==='z'){event.preventDefault();event.stopPropagation();event.shiftKey?a.redo?.():a.undo?.()}
   else if(command&&k==='y'){event.preventDefault();event.stopPropagation();a.redo?.()}
   else if(event.code==='Space'&&a.pan){event.preventDefault();a.pan(true)}
   else if(k==='escape'){a.pan?.(false);a.escape?.()}
   else if((k==='delete'||k==='backspace')&&a.remove){event.preventDefault();a.remove()}
   else if(['pageup','pagedown','arrowleft','arrowright'].includes(k)&&a.page){event.preventDefault();a.page(k==='pageup'||k==='arrowleft'?-1:1)}
  }
  const up=(event:KeyboardEvent)=>{if(event.code==='Space')latest.current.pan?.(false)}
  const blur=()=>latest.current.pan?.(false)
  element.addEventListener('wheel',wheel,{passive:false});element.addEventListener('keydown',key);window.addEventListener('keyup',up);window.addEventListener('blur',blur)
  return()=>{element.removeEventListener('wheel',wheel);element.removeEventListener('keydown',key);window.removeEventListener('keyup',up);window.removeEventListener('blur',blur)}
 })
}
