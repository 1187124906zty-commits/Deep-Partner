export function selectPosition(rect:{left:number;top:number;bottom:number;width:number},viewport:{width:number;height:number}){
 const width=Math.min(Math.max(rect.width,180),viewport.width-16)
 const below=Math.max(0,viewport.height-rect.bottom-12),above=Math.max(0,rect.top-12)
 const down=below>=Math.min(220,above),maxHeight=Math.min(320,down?below:above)
 return {left:Math.max(8,Math.min(rect.left,viewport.width-width-8)),top:down?rect.bottom+6:Math.max(8,rect.top-maxHeight-6),width,maxHeight}
}
