export type Rect={x:number;y:number;width:number;height:number}
export function clippedRect(bounds:number[],offset={x:0,y:0}):Rect|null{
 const [bx,by,bw,bh]=bounds
 if(![bx,by,bw,bh,offset.x,offset.y].every(Number.isFinite))return null
 const x=Math.max(0,bx+offset.x),y=Math.max(0,by+offset.y)
 const right=Math.min(1,bx+offset.x+bw),bottom=Math.min(1,by+offset.y+bh)
 return right>x&&bottom>y?{x,y,width:right-x,height:bottom-y}:null
}
export function cellRect(layout:any,cell:any):number[]{
 if(cell.rect)return cell.rect
 const w=(1-(layout.cols-1)*(layout.gap_x||0))/layout.cols,h=(1-(layout.rows-1)*(layout.gap_y||0))/layout.rows
 return [cell.col*(w+(layout.gap_x||0)),cell.row*(h+(layout.gap_y||0)),w*(cell.colspan||1),h*(cell.rowspan||1)]
}
export function logicalSelection(object:any,objects:any[]):{id:string;axis?:string}{
 if(!object)return {id:'figure'}
 if(object.kind==='spine'||object.kind==='ticks'||['xlabel','ylabel','zlabel'].includes(object.role)){
  const parent=objects.find(o=>o.id===object.parent)
  if(parent?.kind==='axes')return {id:parent.id,axis:object.role==='top'||object.role==='bottom'||object.role?.startsWith('x')?'x':object.role?.startsWith('z')?'z':'y'}
  if(object.id.startsWith('colorbar-'))return {id:object.id.replace(/-(label|ticks)$/,'')}
 }
 if(object.role==='legend-text')return {id:object.id.replace(/-text\d+$/,'')}
 return {id:object.id}
}
