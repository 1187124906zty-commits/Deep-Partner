export type ContentMapSourceQuote={source_id:string;quote:string;start_char?:number;end_char?:number}
export type ContentMapNode={id:string;parent_id?:string|null;kind:string;section_type?:string;label:string;content?:string;keywords?:string[];source_ids?:string[];source_quotes?:ContentMapSourceQuote[];key_point?:boolean;argument_role?:'question'|'gap'|'approach'|'evidence'|'finding'|'scope';order?:number;depth?:number}
export type ContentMapEdge={id:string;from:string;to:string;relation:string;explanation?:string;source_ids?:string[];basis?:'explicit'|'inferred';show_label?:boolean}
export type ContentSourceUnit={id:string;text:string;page?:number|null;bounds?:Record<string,number>|null;section_title?:string;kind?:string}
export type ContentSourceLocator={page:number;bounds?:Record<string,number>|null;unit_id:string;quote:string}
export type StoryPoint={text?:string;means?:string;end?:string;explanation?:string;question?:string;method?:string;evidence?:string;conclusion?:string;status?:string;node_ids?:string[];source_ids?:string[]}
export type ContentMapEvaluation={rule_version?:string;items:{id:string;label:string;score?:number|null;max:number;reason?:string;node_ids?:string[];edge_ids?:string[]}[];content_score?:number|null;content_max?:number;visual_score?:number|null;interaction_score?:number|null;issues?:(string|{severity?:string;reason?:string;suggestion?:string;node_ids?:string[];edge_ids?:string[]})[];summary?:string;author_acceptance?:string}
export type PaperContentMapData={
 evaluation?:ContentMapEvaluation;schema_version?:number|string;source:{title?:string;asset?:string;library?:string;doi?:string;pages?:number};
 abstract?:{text?:string;source_ids?:string[];complete?:boolean;status?:string};keywords?:string[];
 nodes:ContentMapNode[];edges:ContentMapEdge[];source_units?:ContentSourceUnit[];
 story?:{key_node_ids?:string[];author_question?:string;main_claim?:string;organization_summary?:string;means_ends?:StoryPoint[];promise_evidence?:StoryPoint[];learning_points?:(string|StoryPoint)[]};
 coverage?:{total_units?:number;mapped_units?:number;needs_review?:string[];source_unit_count?:number;mapped_unit_count?:number;unmapped_unit_ids?:string[];paragraph_boundary_status?:string;review_items?:unknown[];[key:string]:unknown};generated_at?:string;
}
export type ContentMapState={status:string;job_id?:string|null;stage?:string;error?:string|null;map?:PaperContentMapData|null}
export type ContentMapIndexItem={asset:string;library:string;title?:string;status:string;stage?:string;error?:string|null;job_id?:string|null}

export const contentMapPending=(status:string)=>status==='queued'||status==='running'
export const contentMapStatus=(status:string)=>(({missing:'尚未生成',queued:'等待生成',running:'正在生成',ready:'已就绪',failed:'生成失败',interrupted:'生成已中断',needs_review:'需要复核',stale:'原文已更新'} as Record<string,string>)[status]||'状态待确认')
export function contentMapStage(stage?:string){
 if(!stage)return ''
 return ({queued:'等待处理',pending:'等待处理',extracting:'正在读取全文',parsing:'正在解析原文',source:'正在整理原文',source_extraction:'正在整理原文',analyzing:'正在提炼章节与段落',generating:'正在提炼章节与段落',mapping:'正在建立内容关系',validating:'正在核对原文依据',saving:'正在保存图谱',completed:'已完成',ready:'已完成',failed:'处理失败',interrupted:'处理中断'} as Record<string,string>)[stage]||(/[\u3400-\u9fff]/.test(stage)?stage:'正在处理全文内容')
}

export function contentMapReviewReasons(coverage?:PaperContentMapData['coverage']){
 const reasons=[...(coverage?.needs_review||[]),...(coverage?.review_items||[]).map(item=>typeof item==='string'?item:typeof item==='object'&&item&&'message' in item?String(item.message):'存在需要结合原文复核的内容。')]
 return [...new Set(reasons)]
}
export function contentMapParagraphBoundary(status?:string){
 if(status==='tei_paragraphs')return '结构解析已保留原文段落结构。'
 if(status==='verified')return '段落边界已核对。'
 if(status==='needs_review')return '原文按 PDF 版面提取，段落边界需结合原文复核。'
 return '原文段落边界尚需结合原文核对。'
}

export function contentMapIndex(nodes:ContentMapNode[]){
 const byId=new Map(nodes.map(node=>[node.id,node])),children=new Map<string,ContentMapNode[]>()
 const roots:ContentMapNode[]=[]
 for(const node of nodes){
  if(!node.parent_id||node.parent_id===node.id||!byId.has(node.parent_id))roots.push(node)
  else children.set(node.parent_id,[...(children.get(node.parent_id)||[]),node])
 }
 const order=(a:ContentMapNode,b:ContentMapNode)=>(a.order??0)-(b.order??0)
 roots.sort(order);children.forEach(list=>list.sort(order))
 return {byId,children,roots}
}

export function initialExpandedNodes(nodes:ContentMapNode[]){return new Set(nodes.filter(node=>node.kind==='paper').map(node=>node.id))}

export const CONTENT_NODE_WIDTH=240,CONTENT_NODE_HEIGHT=72
const COLUMN_STEP=350,ROW_STEP=104,CANVAS_MARGIN=32,PORT_GAP=7
export type ContentCanvasPoint={x:number;y:number}
export type PositionedContentNode={node:ContentMapNode;x:number;y:number;depth:number;childCount:number;view_id?:string;width?:number;height?:number;note?:string}
export type ContentCanvasLink={id?:string;from:string;to:string;from_view?:string;to_view?:string;relation?:string;basis?:string;show_label?:boolean}
export type ContentLabelBox={x:number;y:number;width:number;height:number;text:string}
export type ContentCanvasStroke={points:ContentCanvasPoint[];path:string;arrow?:boolean;kind?:'split_bus'|'split_stem'|'merge_bus'|'merge_stem';edge_ids?:string[]}
export type RoutedContentLink=ContentCanvasLink&ContentCanvasStroke&{labelPosition:ContentCanvasPoint;labelBox?:ContentLabelBox;arrow?:boolean}
export type ContentCanvasLayout={positions:PositionedContentNode[];links:ContentCanvasLink[];routes:RoutedContentLink[];trunks?:ContentCanvasStroke[];junctions?:ContentCanvasPoint[];width:number;height:number}

export function contentNodePhrase(node:ContentMapNode){return node.label.trim()}

const contentPath=(points:ContentCanvasPoint[])=>points.map((point,index)=>(index?'L ':'M ')+point.x+' '+point.y).join(' ')
export const contentPositionId=(position:PositionedContentNode)=>position.view_id||position.node.id
export function contentNodeSize(node:ContentMapNode){
 const question=node.argument_role==='question',width=question?260:CONTENT_NODE_WIDTH,charactersPerLine=Math.floor((width-28)/14),lines=Math.max(1,Math.ceil(Array.from(node.label.trim()).length/charactersPerLine))
 return {width,height:Math.max(question?82:CONTENT_NODE_HEIGHT,lines*20+24)}
}
export const contentPositionSize=(position:PositionedContentNode)=>({width:position.width||contentNodeSize(position.node).width,height:position.height||contentNodeSize(position.node).height})

// Hierarchy branches join a single, explicitly drawn parent trunk. No arrow
// is used for parent-child structure; arrowheads are reserved for relations.
export function routeContentLinks(positions:PositionedContentNode[],links:ContentCanvasLink[]):RoutedContentLink[]{
 const byId=new Map(positions.map(position=>[contentPositionId(position),position]))
 return links.flatMap(link=>{
  const from=byId.get(link.from_view||link.from),to=byId.get(link.to_view||link.to)
  if(!from||!to)return []
  const fromSize=contentPositionSize(from),toSize=contentPositionSize(to),trunk=from.x+fromSize.width+52,ty=to.y+toSize.height/2
  const points=[{x:trunk,y:ty},{x:to.x-PORT_GAP,y:ty}]
  return [{...link,points,path:contentPath(points),labelPosition:{x:0,y:0},arrow:false}]
 })
}

function treeTrunks(positions:PositionedContentNode[],links:ContentCanvasLink[]){
 const byId=new Map(positions.map(position=>[position.node.id,position])),children=new Map<string,PositionedContentNode[]>()
 for(const link of links){const child=byId.get(link.to);if(child)children.set(link.from,[...(children.get(link.from)||[]),child])}
 const trunks:ContentCanvasStroke[]=[],junctions:ContentCanvasPoint[]=[]
 children.forEach((group,parentId)=>{
  const parent=byId.get(parentId);if(!parent)return
  const parentSize=contentPositionSize(parent),x=parent.x+parentSize.width+52,py=parent.y+parentSize.height/2,ys=group.map(child=>child.y+contentPositionSize(child).height/2)
  const stem=[{x:parent.x+parentSize.width+PORT_GAP,y:py},{x,y:py}];trunks.push({points:stem,path:contentPath(stem)})
  if(group.length>1){const main=[{x,y:Math.min(...ys)},{x,y:Math.max(...ys)}];trunks.push({points:main,path:contentPath(main)});junctions.push(...ys.map(y=>({x,y})))}
 })
 return {trunks,junctions}
}

export function layoutContentTree(nodes:ContentMapNode[],expanded:Set<string>,scope=''){
 const index=contentMapIndex(nodes),positions:PositionedContentNode[]=[],links:{from:string;to:string}[]=[],seen=new Set<string>(),rowStep=Math.max(ROW_STEP,...nodes.map(node=>contentNodeSize(node).height+30))
 let row=0,maxDepth=0
 const visit=(node:ContentMapNode,depth:number):number=>{
  if(seen.has(node.id))return Math.max(0,row-1)*rowStep+CANVAS_MARGIN
  seen.add(node.id);maxDepth=Math.max(maxDepth,depth)
  const children=(index.children.get(node.id)||[]).filter(child=>!seen.has(child.id))
  const visible=expanded.has(node.id)?children:[]
  const childY=visible.map(child=>{links.push({from:node.id,to:child.id});return visit(child,depth+1)})
  const centerY=childY.length?(childY[0]+childY[childY.length-1])/2:row++*rowStep+CANVAS_MARGIN+CONTENT_NODE_HEIGHT/2,nodeSize=contentNodeSize(node)
  positions.push({node,x:depth*COLUMN_STEP+CANVAS_MARGIN,y:centerY-nodeSize.height/2,depth,childCount:children.length});return centerY
 }
 const root=scope?index.byId.get(scope):undefined
 for(const node of root?[root]:index.roots)visit(node,0)
 return {positions,links,routes:routeContentLinks(positions,links),...treeTrunks(positions,links),width:Math.max(...positions.map(position=>position.x+contentPositionSize(position).width),0)+CANVAS_MARGIN,height:Math.max(180,...positions.map(position=>position.y+contentPositionSize(position).height+CANVAS_MARGIN))}
}

function relationLabelBox(relation:string,centerX:number,lineY:number):ContentLabelBox{
 const text=Array.from(relation).length>14?Array.from(relation).slice(0,13).join('')+'…':relation,width=Math.max(48,Math.min(206,Array.from(text).length*13+20))
 return {x:centerX-width/2,y:lineY-40,width,height:26,text}
}

export function layoutContentRelations(nodes:ContentMapNode[],edges:ContentMapEdge[],selected:string):ContentCanvasLayout{
 const byId=contentMapIndex(nodes).byId,focus=byId.get(selected),links=relatedContentEdges(edges,selected).filter(edge=>byId.has(edge.from)&&byId.has(edge.to))
 if(!focus)return {positions:[],links:[],routes:[],width:360,height:220}
 const incoming=links.filter(edge=>edge.to===selected&&edge.from!==selected),outgoing=links.filter(edge=>edge.from===selected)
 const compare=(a:ContentMapEdge,b:ContentMapEdge)=>{
  const aId=a.from===selected?a.to:a.from,bId=b.from===selected?b.to:b.from
  return (byId.get(aId)?.order??0)-(byId.get(bId)?.order??0)||a.relation.localeCompare(b.relation,'zh')||a.id.localeCompare(b.id)
 }
 incoming.sort(compare);outgoing.sort(compare)
 const rowStep=Math.max(104,...[focus,...links.map(edge=>byId.get(edge.from===selected?edge.to:edge.from)!)].map(node=>contentNodeSize(node).height+30)),rows=Math.max(incoming.length,outgoing.length,1),gutter=Math.max(84,...links.filter(edge=>edge.show_label!==false).map(edge=>relationLabelBox(edge.relation,0,0).width+84)),focusSize=contentNodeSize(focus),leftWidth=Math.max(CONTENT_NODE_WIDTH,...incoming.map(edge=>contentNodeSize(byId.get(edge.from)!).width)),hubX=CANVAS_MARGIN+(incoming.length?leftWidth+gutter:0),focusY=CANVAS_MARGIN+(rows-1)*rowStep/2+CONTENT_NODE_HEIGHT/2,hubView='focus:'+selected
 const positions:PositionedContentNode[]=[{node:focus,view_id:hubView,x:hubX,y:focusY-focusSize.height/2,depth:1,childCount:0}],routes:RoutedContentLink[]=[],trunks:ContentCanvasStroke[]=[],junctions:ContentCanvasPoint[]=[]
 const relationColumn=(items:ContentMapEdge[],direction:'incoming'|'outgoing')=>{
  if(!items.length)return
  const isIncoming=direction==='incoming',trunkX=isIncoming?hubX-36:hubX+focusSize.width+36,ys:number[]=[]
  items.forEach((edge,index)=>{
   const otherId=isIncoming?edge.from:edge.to,other=byId.get(otherId)!,otherSize=contentNodeSize(other),x=isIncoming?CANVAS_MARGIN+leftWidth-otherSize.width:hubX+focusSize.width+gutter,centerY=CANVAS_MARGIN+(rows-items.length)*rowStep/2+index*rowStep+CONTENT_NODE_HEIGHT/2,viewId=direction+':'+index+':'+edge.id
   positions.push({node:other,view_id:viewId,x,y:centerY-otherSize.height/2,depth:isIncoming?0:2,childCount:0});ys.push(centerY)
   const points=isIncoming?[{x:x+otherSize.width+PORT_GAP,y:centerY},{x:trunkX,y:centerY}]:[{x:trunkX,y:centerY},{x:x-PORT_GAP,y:centerY}]
   const centerX=(points[0].x+points[1].x)/2,labelBox=edge.show_label===false?undefined:relationLabelBox(edge.relation,centerX,centerY)
   routes.push({...edge,from_view:isIncoming?viewId:hubView,to_view:isIncoming?hubView:viewId,points,path:contentPath(points),labelBox,labelPosition:{x:centerX,y:centerY-23},arrow:!isIncoming})
  })
  const stem=isIncoming?[{x:trunkX,y:focusY},{x:hubX-PORT_GAP,y:focusY}]:[{x:hubX+focusSize.width+PORT_GAP,y:focusY},{x:trunkX,y:focusY}]
  trunks.push({points:stem,path:contentPath(stem),arrow:isIncoming})
  if(items.length>1){const main=[{x:trunkX,y:Math.min(...ys)},{x:trunkX,y:Math.max(...ys)}];trunks.push({points:main,path:contentPath(main)});junctions.push(...ys.map(y=>({x:trunkX,y})))}
 }
 relationColumn(incoming,'incoming');relationColumn(outgoing,'outgoing')
 return {positions,links,routes,trunks,junctions,width:Math.max(...positions.map(position=>position.x+contentPositionSize(position).width))+CANVAS_MARGIN,height:Math.max(180,...positions.map(position=>position.y+contentPositionSize(position).height+CANVAS_MARGIN))}
}

export function keyContentNodes(map:PaperContentMapData){
 const byId=contentMapIndex(map.nodes).byId,ids=map.story?.key_node_ids?.length?map.story.key_node_ids:map.nodes.filter(node=>node.key_point).map(node=>node.id)
 return [...new Set(ids)].map(id=>byId.get(id)).filter((node):node is ContentMapNode=>!!node&&node.kind!=='paper')
}
// A bounded vertical layout for a small, unlabelled key-argument DAG. Split
// and merge groups get one explicit bus, so a shared conclusion is drawn once.
export function layoutCompactKeyDag(map:PaperContentMapData):ContentCanvasLayout|null{
 const root=map.nodes.find(node=>node.kind==='paper'),selected=keyContentNodes(map)
 if(!root||!selected.length||selected.length+1>16)return null
 const nodes=[root,...selected],ids=new Set(nodes.map(node=>node.id)),byId=new Map(nodes.map(node=>[node.id,node])),edges=map.edges.filter(edge=>ids.has(edge.from)&&ids.has(edge.to))
 if(!edges.length||edges.some(edge=>edge.show_label!==false))return null
 const outgoing=new Map<string,ContentMapEdge[]>(),incoming=new Map<string,ContentMapEdge[]>(),degree=new Map(nodes.map(node=>[node.id,0])),depth=new Map<string,number>([[root.id,0]])
 for(const edge of edges){outgoing.set(edge.from,[...(outgoing.get(edge.from)||[]),edge]);incoming.set(edge.to,[...(incoming.get(edge.to)||[]),edge]);degree.set(edge.to,(degree.get(edge.to)||0)+1)}
 const queue=nodes.filter(node=>degree.get(node.id)===0).map(node=>node.id)
 if(queue.length!==1||queue[0]!==root.id)return null
 let visited=0
 while(queue.length){const id=queue.shift()!;visited++;for(const edge of outgoing.get(id)||[]){depth.set(edge.to,Math.max(depth.get(edge.to)||0,(depth.get(id)||0)+1));degree.set(edge.to,degree.get(edge.to)!-1);if(degree.get(edge.to)===0)queue.push(edge.to)}}
 if(visited!==nodes.length||edges.some(edge=>depth.get(edge.to)!==depth.get(edge.from)!+1))return null
 const layers:ContentMapNode[][]=[]
 for(const node of nodes){const level=depth.get(node.id)!;layers[level]||=[];layers[level].push(node)}
 if(layers.length>5||layers.some(layer=>layer.length>4))return null
 // Each transition may split or merge, but this narrow layout deliberately
 // falls back for a many-to-many group rather than route an arbitrary graph.
 if(edges.some(edge=>(outgoing.get(edge.from)?.length||0)>1&&(incoming.get(edge.to)?.length||0)>1))return null
 const pivot=layers.reduce((largest,layer,index)=>layer.length>layers[largest].length?index:largest,0),centers=new Map<string,number>(),columnStep=Math.max(...nodes.map(node=>contentNodeSize(node).width))+74
 layers[pivot].forEach((node,index)=>centers.set(node.id,CANVAS_MARGIN+CONTENT_NODE_WIDTH/2+index*columnStep))
 const place=(layer:ContentMapNode[],neighbors:(id:string)=>string[])=>{
  const desired=layer.map(node=>{const values=neighbors(node.id).map(id=>centers.get(id)).filter((value):value is number=>value!==undefined);return {node,x:values.length?values.reduce((sum,value)=>sum+value,0)/values.length:CANVAS_MARGIN+CONTENT_NODE_WIDTH/2}})
  for(let index=1;index<desired.length;index++){const previous=desired[index-1],item=desired[index],gap=(contentNodeSize(previous.node).width+contentNodeSize(item.node).width)/2+58;item.x=Math.max(item.x,previous.x+gap)}
  const delta=(desired.reduce((sum,item)=>sum+item.x,0)-layer.reduce((sum,node)=>{const values=neighbors(node.id).map(id=>centers.get(id)).filter((value):value is number=>value!==undefined);return sum+(values.length?values.reduce((a,b)=>a+b,0)/values.length:CANVAS_MARGIN+CONTENT_NODE_WIDTH/2)},0))/Math.max(1,desired.length)
  desired.forEach(item=>centers.set(item.node.id,item.x-delta))
 }
 for(let level=pivot-1;level>=0;level--)place(layers[level],id=>(outgoing.get(id)||[]).map(edge=>edge.to))
 for(let level=pivot+1;level<layers.length;level++)place(layers[level],id=>(incoming.get(id)||[]).map(edge=>edge.from))
 const left=Math.min(...nodes.map(node=>centers.get(node.id)!-contentNodeSize(node).width/2)),shift=CANVAS_MARGIN-left,rowY:number[]=[]
 let row=CANVAS_MARGIN
 layers.forEach((layer,level)=>{rowY[level]=row;row+=Math.max(...layer.map(node=>contentNodeSize(node).height))+82})
 const positions:PositionedContentNode[]=nodes.map(node=>({node,x:centers.get(node.id)!+shift-contentNodeSize(node).width/2,y:rowY[depth.get(node.id)!],depth:depth.get(node.id)!,childCount:0})),positionById=new Map(positions.map(position=>[position.node.id,position])),routes:RoutedContentLink[]=[],trunks:ContentCanvasStroke[]=[],junctions:ContentCanvasPoint[]=[],handled=new Set<ContentMapEdge>(),strokeGroups:{points:ContentCanvasPoint[];group:string}[]=[]
 const center=(id:string)=>centers.get(id)!+shift,bottom=(id:string)=>positionById.get(id)!.y+contentNodeSize(byId.get(id)!).height+PORT_GAP,top=(id:string)=>positionById.get(id)!.y-PORT_GAP
 const route=(edge:ContentMapEdge,points:ContentCanvasPoint[],arrow:boolean,group:string)=>{routes.push({...edge,points,path:contentPath(points),arrow,labelPosition:{x:0,y:0}});strokeGroups.push({points,group});handled.add(edge)}
 const trunk=(points:ContentCanvasPoint[],kind:ContentCanvasStroke['kind'],group:string,groupEdges:ContentMapEdge[],arrow=false)=>{trunks.push({points,path:contentPath(points),kind,arrow,edge_ids:groupEdges.map(edge=>edge.id)});strokeGroups.push({points,group})}
 for(const [id,groupEdges] of outgoing)if(groupEdges.length>1){
  const group='split:'+id,x=center(id),ys=groupEdges.map(edge=>top(edge.to)),busY=(bottom(id)+Math.min(...ys))/2,xs=groupEdges.map(edge=>center(edge.to))
  trunk([{x,y:bottom(id)},{x,y:busY}],'split_stem',group,groupEdges)
  trunk([{x:Math.min(x,...xs),y:busY},{x:Math.max(x,...xs),y:busY}],'split_bus',group,groupEdges)
  for(const edge of groupEdges){const tx=center(edge.to);route(edge,[{x:tx,y:busY},{x:tx,y:top(edge.to)}],true,group);junctions.push({x:tx,y:busY})}
 }
 for(const [id,groupEdges] of incoming)if(groupEdges.length>1){
  const group='merge:'+id,x=center(id),ys=groupEdges.map(edge=>bottom(edge.from)),busY=(Math.max(...ys)+top(id))/2,xs=groupEdges.map(edge=>center(edge.from))
  for(const edge of groupEdges){const sx=center(edge.from);route(edge,[{x:sx,y:bottom(edge.from)},{x:sx,y:busY}],false,group);junctions.push({x:sx,y:busY})}
  trunk([{x:Math.min(x,...xs),y:busY},{x:Math.max(x,...xs),y:busY}],'merge_bus',group,groupEdges)
  trunk([{x,y:busY},{x,y:top(id)}],'merge_stem',group,groupEdges,true)
 }
 for(const edge of edges)if(!handled.has(edge)){const sx=center(edge.from),tx=center(edge.to),sy=bottom(edge.from),ty=top(edge.to),mid=(sy+ty)/2,points=sx===tx?[{x:sx,y:sy},{x:tx,y:ty}]:[{x:sx,y:sy},{x:sx,y:mid},{x:tx,y:mid},{x:tx,y:ty}];route(edge,points,true,'single:'+edge.id)}
 // Reject rather than hide or cross an edge if a different small DAG does not
 // fit these ordered split/merge lanes.
 const segments=(points:ContentCanvasPoint[])=>points.slice(1).map((b,index)=>({a:points[index],b}))
 const intersects=(a:ContentCanvasPoint,b:ContentCanvasPoint,c:ContentCanvasPoint,d:ContentCanvasPoint)=>{const ah=a.y===b.y,ch=c.y===d.y;if(ah&&ch)return a.y===c.y&&Math.max(Math.min(a.x,b.x),Math.min(c.x,d.x))<=Math.min(Math.max(a.x,b.x),Math.max(c.x,d.x));if(!ah&&!ch)return a.x===c.x&&Math.max(Math.min(a.y,b.y),Math.min(c.y,d.y))<=Math.min(Math.max(a.y,b.y),Math.max(c.y,d.y));const h=ah?{a,b}:{a:c,b:d},v=ah?{a:c,b:d}:{a,b};return v.a.x>=Math.min(h.a.x,h.b.x)&&v.a.x<=Math.max(h.a.x,h.b.x)&&h.a.y>=Math.min(v.a.y,v.b.y)&&h.a.y<=Math.max(v.a.y,v.b.y)}
 for(const stroke of strokeGroups)for(const {a,b} of segments(stroke.points))for(const position of positions){const size=contentPositionSize(position),l=position.x,r=l+size.width,t=position.y,bottom=t+size.height;if(a.x===b.x?a.x>=l&&a.x<=r&&Math.max(a.y,b.y)>=t&&Math.min(a.y,b.y)<=bottom:a.y>=t&&a.y<=bottom&&Math.max(a.x,b.x)>=l&&Math.min(a.x,b.x)<=r)return null}
 for(let i=0;i<strokeGroups.length;i++)for(let j=i+1;j<strokeGroups.length;j++)if(strokeGroups[i].group!==strokeGroups[j].group)for(const a of segments(strokeGroups[i].points))for(const b of segments(strokeGroups[j].points))if(intersects(a.a,a.b,b.a,b.b))return null
 return {positions,links:edges,routes,trunks,junctions,width:Math.max(...positions.map(position=>position.x+contentPositionSize(position).width))+CANVAS_MARGIN,height:Math.max(...positions.map(position=>position.y+contentPositionSize(position).height))+CANVAS_MARGIN}
}

export function layoutContentKeyPoints(map:PaperContentMapData):ContentCanvasLayout{
 const compact=layoutCompactKeyDag(map);if(compact)return compact
 const root=map.nodes.find(node=>node.kind==='paper')||{id:'__key_paper__',kind:'paper',label:map.source.title||'论文主题'},points=keyContentNodes(map).filter(node=>node.id!==root.id),keyIds=new Set(points.map(node=>node.id)),byId=new Map(points.map(node=>[node.id,node])),rank=new Map(points.map((node,index)=>[node.id,index]))
 const edges=map.edges.filter(edge=>keyIds.has(edge.from)&&keyIds.has(edge.to)),outgoing=new Map<string,ContentMapEdge[]>()
 for(const edge of edges)outgoing.set(edge.from,[...(outgoing.get(edge.from)||[]),edge])
 outgoing.forEach(list=>list.sort((a,b)=>(rank.get(a.to)||0)-(rank.get(b.to)||0)))
 if(!edges.length){
  const nodes=[root,...points.map((node,index)=>({...node,parent_id:node.parent_id&&keyIds.has(node.parent_id)?node.parent_id:root.id,order:index}))]
  return layoutContentTree(nodes,new Set(nodes.map(node=>node.id)))
 }
 const rootView='key-root:'+root.id,display:ContentMapNode[]=[{...root,id:rootView,parent_id:null}],original=new Map<string,ContentMapNode>([[rootView,root]]),edgeForView=new Map<string,ContentMapEdge>(),visitedEdges=new Set<ContentMapEdge>(),seenNodes=new Set<string>(),copies=new Map<string,number>()
 const visit=(id:string,parent:string,via?:ContentMapEdge,path=new Set<string>())=>{
  const node=byId.get(id);if(!node)return
  const copy=(copies.get(id)||0)+1;copies.set(id,copy);const viewId='key-view:'+id+':'+copy
  display.push({...node,id:viewId,parent_id:parent,order:rank.get(id)||0});original.set(viewId,node);seenNodes.add(id);if(via)edgeForView.set(viewId,via)
  if(path.has(id))return
  const nextPath=new Set(path);nextPath.add(id)
  for(const edge of outgoing.get(id)||[])if(!visitedEdges.has(edge)){visitedEdges.add(edge);visit(edge.to,viewId,edge,nextPath)}
 }
 const roots=points.filter(node=>!edges.some(edge=>edge.to===node.id))
 for(const node of roots)if(!seenNodes.has(node.id))visit(node.id,rootView)
 for(const node of points)if(!seenNodes.has(node.id))visit(node.id,rootView)
 // Unroll convergence and cycles into repeated views; each scientific relation
 // remains present once, rather than silently dropping an inconvenient edge.
 for(const edge of edges)if(!visitedEdges.has(edge)){visitedEdges.add(edge);const sourceView=display.find(node=>original.get(node.id)?.id===edge.from)?.id||rootView;visit(edge.to,sourceView,edge,new Set([edge.from]))}
 const columnStep=Math.max(...display.map(node=>contentNodeSize(node).width))+52+Math.max(0,...edges.filter(edge=>edge.show_label!==false).map(edge=>relationLabelBox(edge.relation,0,0).width))+48
 const internal=layoutContentTree(display,new Set(display.map(node=>node.id))),positions=internal.positions.map(position=>({...position,x:CANVAS_MARGIN+position.depth*columnStep})),links=internal.links,routes=routeContentLinks(positions,links).map(route=>{
  const edge=edgeForView.get(route.to),semanticFrom=original.get(route.from)!,semanticTo=original.get(route.to)!,first=route.points[0],last=route.points[route.points.length-1]
  return {...route,...(edge||{}),from:edge?.from||semanticFrom.id,to:edge?.to||semanticTo.id,from_view:route.from,to_view:route.to,arrow:!!edge,labelBox:edge&&edge.show_label!==false?relationLabelBox(edge.relation,(first.x+last.x)/2,first.y):undefined}
 }),resultPositions=positions.map(position=>({...position,view_id:position.node.id,node:original.get(position.node.id)!,note:(copies.get(original.get(position.node.id)!.id)||0)>1?'同一判断的独立论证路径':undefined}))
 return {positions:resultPositions,links:routes.map(route=>({id:route.id,from:route.from,to:route.to,from_view:route.from_view,to_view:route.to_view,relation:route.relation})),routes,...treeTrunks(positions,links),width:Math.max(...positions.map(position=>position.x+contentPositionSize(position).width))+CANVAS_MARGIN,height:internal.height}
}

export type ContentCanvasView={x:number;y:number;scale:number}
export function zoomContentCanvas(view:ContentCanvasView,scale:number,anchor:ContentCanvasPoint):ContentCanvasView{
 const next=Math.max(.2,Math.min(2.5,scale)),ratio=next/view.scale
 return {scale:next,x:anchor.x-(anchor.x-view.x)*ratio,y:anchor.y-(anchor.y-view.y)*ratio}
}
export function fitKeyContentCanvas(layout:Pick<ContentCanvasLayout,'width'|'height'>,width:number,height:number):ContentCanvasView{
 const scale=Math.max(.85,Math.min(1,(width-32)/layout.width,(height-32)/layout.height))
 return {scale,x:(width-layout.width*scale)/2,y:(height-layout.height*scale)/2}
}
export function fitContentCanvas(layout:Pick<ContentCanvasLayout,'width'|'height'>,width:number,height:number):ContentCanvasView{
 const scale=Math.max(.55,Math.min(1,(width-48)/layout.width,(height-64)/layout.height))
 return {scale,x:Math.max(24,(width-layout.width*scale)/2),y:Math.max(36,(height-layout.height*scale)/2)}
}

export function nodeSourceEvidence(node:ContentMapNode,units:ContentSourceUnit[]=[]){
 const byId=new Map(units.map(unit=>[unit.id,unit])),groups=new Map<string,{unit:ContentSourceUnit;quotes:string[]}>()
 for(const item of node.source_quotes||[]){const unit=byId.get(item.source_id);if(unit&&item.quote.trim()){const group=groups.get(unit.id)||{unit,quotes:[]};if(!group.quotes.includes(item.quote))group.quotes.push(item.quote);groups.set(unit.id,group)}}
 for(const id of node.source_ids||[]){const unit=byId.get(id);if(unit&&!groups.has(id))groups.set(id,{unit,quotes:[]})}
 return [...groups.values()]
}

export function sourceQuoteSegments(text:string,quotes:string[]){
 const ranges=quotes.map(quote=>({start:text.indexOf(quote),end:text.indexOf(quote)+quote.length})).filter(range=>range.start>=0&&range.end>range.start).sort((a,b)=>a.start-b.start),merged:{start:number;end:number}[]=[]
 for(const range of ranges){const prior=merged[merged.length-1];if(prior&&range.start<=prior.end)prior.end=Math.max(prior.end,range.end);else merged.push({...range})}
 const segments:{text:string;highlight:boolean}[]=[];let cursor=0
 for(const range of merged){if(range.start>cursor)segments.push({text:text.slice(cursor,range.start),highlight:false});segments.push({text:text.slice(range.start,range.end),highlight:true});cursor=range.end}
 if(cursor<text.length)segments.push({text:text.slice(cursor),highlight:false})
 return segments
}

export function revealContentNode(nodes:ContentMapNode[],expanded:Set<string>,id:string){
 const byId=contentMapIndex(nodes).byId,next=new Set(expanded),seen=new Set<string>()
 let node=byId.get(id)
 while(node?.parent_id&&!seen.has(node.parent_id)){seen.add(node.parent_id);next.add(node.parent_id);node=byId.get(node.parent_id)}
 return next
}
export function sourcesFor(ids:string[]|undefined,units:ContentSourceUnit[]=[]){const wanted=new Set(ids||[]);return units.filter(unit=>wanted.has(unit.id))}
export function sourceLocator(unit:ContentSourceUnit):ContentSourceLocator|null{return typeof unit.page==='number'&&Number.isFinite(unit.page)&&unit.page>=1?{page:unit.page,bounds:unit.bounds,unit_id:unit.id,quote:unit.text}:null}
export function relatedContentEdges(edges:ContentMapEdge[],id:string){return edges.filter(edge=>edge.from===id||edge.to===id)}
