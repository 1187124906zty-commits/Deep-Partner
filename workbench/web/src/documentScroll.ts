type Block={top:number;height:number}
export function matchedBlockPosition(offset:number,source:Block[],target:Block[]){
 if(!source.length||!target.length)return 0
 let index=source.findIndex(block=>block.top+block.height>offset)
 if(index<0)index=source.length-1
 const a=source[index],b=target[Math.min(index,target.length-1)]
 const fraction=Math.max(0,Math.min(1,(offset-a.top)/Math.max(1,a.height)))
 return b.top+fraction*b.height
}
export function syncDocumentPanes(source:HTMLElement,target:HTMLElement){
 const positions=(pane:HTMLElement)=>Array.from(pane.querySelector('.manuscript-editor')?.children||[]).map(el=>({top:el.getBoundingClientRect().top-pane.getBoundingClientRect().top+pane.scrollTop,height:el.getBoundingClientRect().height}))
 target.scrollTop=Math.max(0,matchedBlockPosition(source.scrollTop+24,positions(source),positions(target))-24)
}
