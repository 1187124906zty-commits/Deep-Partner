export function textSelectionBlocks(container:HTMLElement){
 const selection=window.getSelection();if(!selection?.rangeCount||selection.isCollapsed)return []
 const range=selection.getRangeAt(0)
 return Array.from(container.querySelectorAll<HTMLElement>('[data-block]')).flatMap(element=>{
  if(!range.intersectsNode(element))return []
  const before=document.createRange();before.selectNodeContents(element)
  let start=0,end=element.textContent?.length||0
  if(element.contains(range.startContainer)){before.setEnd(range.startContainer,range.startOffset);start=before.toString().length}
  if(element.contains(range.endContainer)){before.selectNodeContents(element);before.setEnd(range.endContainer,range.endOffset);end=before.toString().length}
  return [{id:element.dataset.block,start,end}]
 })
}
export function paintTranslatedAnnotations(container:HTMLElement,annotations:any[],prefix:string){
 const registry=(CSS as any).highlights,HighlightType=(globalThis as any).Highlight
 if(!registry||!HighlightType)return ()=>{}
 const style=document.createElement('style'),names:string[]=[];document.head.append(style)
 const textPoint=(element:HTMLElement,offset:number):[Node,number]|null=>{const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT);let node:Node|null;while((node=walker.nextNode())){const size=node.textContent?.length||0;if(offset<=size)return [node,offset];offset-=size}return null}
 for(const [index,note] of annotations.entries()){
  if(!note.locator.translation||['deleted','resolved'].includes(note.status))continue
  const ranges=[]
  for(const block of note.locator.blocks||[]){const element=container.querySelector<HTMLElement>('[data-block='+JSON.stringify(block.id)+']');if(!element)continue;const start=textPoint(element,block.start),end=textPoint(element,block.end);if(start&&end){const range=document.createRange();range.setStart(...start);range.setEnd(...end);ranges.push(range)}}
  if(!ranges.length)continue
  const name=prefix+'-'+index;registry.set(name,new HighlightType(...ranges));names.push(name)
  style.textContent+='::highlight('+name+'){background-color:'+note.color+'66;color:inherit}'
 }
 return ()=>{for(const name of names)registry.delete(name);style.remove()}
}
