import {expect,it} from 'vitest'
import {CONTENT_NODE_WIDTH,CONTENT_NODE_HEIGHT,contentNodePhrase,contentNodeSize,contentPositionId,contentPositionSize,keyContentNodes,layoutCompactKeyDag,layoutContentKeyPoints,contentMapParagraphBoundary,contentMapPending,contentMapReviewReasons,contentMapStatus,fitContentCanvas,fitKeyContentCanvas,initialExpandedNodes,layoutContentRelations,layoutContentTree,nodeSourceEvidence,relatedContentEdges,revealContentNode,sourceLocator,sourceQuoteSegments,sourcesFor,zoomContentCanvas,type ContentCanvasLayout,type ContentCanvasPoint,type ContentMapEdge,type ContentMapNode} from './paperContentMap'

const nodes:ContentMapNode[]=[
 {id:'paper',kind:'paper',label:'离子竞争传输机制'},
 {id:'intro',parent_id:'paper',kind:'section',label:'竞争效应与建模问题',order:1},
 {id:'method',parent_id:'paper',kind:'section',label:'耦合离子输运模型',order:2},
 {id:'paragraph',parent_id:'intro',kind:'paragraph',label:'已有模型未分辨结合与扩散',order:1},
 {id:'gap',parent_id:'paragraph',kind:'element',label:'结合竞争与传输通道缺少区分',order:1},
]

it('shows paper and chapter nodes initially and expands only the requested branch',()=>{
 const expanded=initialExpandedNodes(nodes)
 expect(layoutContentTree(nodes,expanded).positions.map(item=>item.node.id)).toEqual(['intro','method','paper'])
 expanded.add('intro')
 expect(layoutContentTree(nodes,expanded).positions.map(item=>item.node.id)).toContain('paragraph')
 expect(layoutContentTree(nodes,expanded).positions.map(item=>item.node.id)).not.toContain('gap')
 expanded.add('paragraph')
 const layout=layoutContentTree(nodes,expanded)
 expect(layout.positions.some(item=>item.node.id==='gap')).toBe(true)
 expect(layout.links).toContainEqual({from:'paragraph',to:'gap'})
 expect(new Set(layout.positions.map(item=>item.x+':'+item.y)).size).toBe(layout.positions.length)
})

it('reveals ancestors for a search result and scopes the diagram to a real chapter',()=>{
 const expanded=revealContentNode(nodes,new Set(),'gap')
 expect([...expanded]).toEqual(['paragraph','intro','paper'])
 const chapter=layoutContentTree(nodes,expanded,'intro')
 expect(chapter.positions.map(item=>item.node.id)).toEqual(['gap','paragraph','intro'])
 expect(chapter.positions.every(item=>item.node.id!=='method')).toBe(true)
})

it('locates the real source page and never invents a page from node order',()=>{
 const units=[{id:'u-7',text:'The original paragraph in its entirety.',page:8,bounds:{x:.1,y:.2,width:.8,height:.1}},{id:'u-no-page',text:'A paragraph without a reliable page.',page:null}]
 expect(sourcesFor(['u-7','missing'],units)).toEqual([units[0]])
 expect(sourceLocator(units[0])).toEqual({page:8,unit_id:'u-7',quote:units[0].text,bounds:units[0].bounds})
 expect(sourceLocator(units[1])).toBeNull()
 expect(sourceLocator({id:'invalid',text:'',page:NaN})).toBeNull()
})

it('keeps incoming and outgoing content relations without confusing tree parents with evidence',()=>{
 const edges=[{id:'one',from:'gap',to:'method',relation:'回应',basis:'explicit' as const},{id:'two',from:'paragraph',to:'gap',relation:'限定',basis:'inferred' as const},{id:'other',from:'intro',to:'paper',relation:'承接'}]
 expect(relatedContentEdges(edges,'gap').map(edge=>edge.id)).toEqual(['one','two'])
})

it('reads backend review reasons and distinguishes preserved TEI paragraphs from verified boundaries',()=>{
 const coverage={total_units:8,mapped_units:6,needs_review:['两段引言之间缺少承接关系。'],review_items:[{message:'一个实验尚未挂接原文。'},'两段引言之间缺少承接关系。']}
 expect(contentMapReviewReasons(coverage)).toEqual(['两段引言之间缺少承接关系。','一个实验尚未挂接原文。'])
 expect(contentMapParagraphBoundary('tei_paragraphs')).toBe('结构解析已保留原文段落结构。')
 expect(contentMapParagraphBoundary('tei_paragraphs')).not.toContain('已核对')
 expect(contentMapParagraphBoundary('needs_review')).toContain('PDF 版面提取')
})

it('labels interrupted work explicitly and does not treat it as an active queue',()=>{
 expect(contentMapStatus('interrupted')).toBe('生成已中断')
 expect(contentMapPending('interrupted')).toBe(false)
})

function assertClearCanvas(layout:ContentCanvasLayout,checkLabels=false){
 const boxes=layout.positions.map(position=>{const size=contentPositionSize(position);return {id:contentPositionId(position),left:position.x,top:position.y,right:position.x+size.width,bottom:position.y+size.height}}),labels=layout.routes.flatMap(route=>route.labelBox?[{id:route.id||route.from+'>'+route.to,left:route.labelBox.x,top:route.labelBox.y,right:route.labelBox.x+route.labelBox.width,bottom:route.labelBox.y+route.labelBox.height}]:[])
 const violations:string[]=[]
 const inside=(point:ContentCanvasPoint,box:typeof boxes[number])=>point.x>=box.left&&point.x<=box.right&&point.y>=box.top&&point.y<=box.bottom
 const overlap=(a:typeof boxes[number],b:typeof boxes[number])=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top
 const segmentBox=(a:ContentCanvasPoint,b:ContentCanvasPoint,box:typeof boxes[number])=>a.x===b.x?a.x>=box.left&&a.x<=box.right&&Math.max(a.y,b.y)>=box.top&&Math.min(a.y,b.y)<=box.bottom:a.y>=box.top&&a.y<=box.bottom&&Math.max(a.x,b.x)>=box.left&&Math.min(a.x,b.x)<=box.right
 const segments=(points:ContentCanvasPoint[])=>points.slice(1).map((b,index)=>({a:points[index],b}))
 const intersects=(a:ContentCanvasPoint,b:ContentCanvasPoint,c:ContentCanvasPoint,d:ContentCanvasPoint)=>{
  const aHorizontal=a.y===b.y,cHorizontal=c.y===d.y
  if(aHorizontal&&cHorizontal)return a.y===c.y&&Math.max(Math.min(a.x,b.x),Math.min(c.x,d.x))<=Math.min(Math.max(a.x,b.x),Math.max(c.x,d.x))
  if(!aHorizontal&&!cHorizontal)return a.x===c.x&&Math.max(Math.min(a.y,b.y),Math.min(c.y,d.y))<=Math.min(Math.max(a.y,b.y),Math.max(c.y,d.y))
  const h=aHorizontal?{a,b}:{a:c,b:d},v=aHorizontal?{a:c,b:d}:{a,b}
  return v.a.x>=Math.min(h.a.x,h.b.x)&&v.a.x<=Math.max(h.a.x,h.b.x)&&h.a.y>=Math.min(v.a.y,v.b.y)&&h.a.y<=Math.max(v.a.y,v.b.y)
 }
 for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)if(overlap(boxes[i],boxes[j]))violations.push('overlapping boxes '+boxes[i].id+' / '+boxes[j].id)
 for(const stroke of [...layout.routes,...(layout.trunks||[])])for(const {a,b} of segments(stroke.points)){
  if(a.x!==b.x&&a.y!==b.y)violations.push('route must use orthogonal safe segments')
  for(const box of boxes)if(segmentBox(a,b,box))violations.push('line crosses '+box.id)
 }
 for(const route of [...layout.routes,...(layout.trunks||[])]){
  expect(route.points.length).toBeGreaterThanOrEqual(2)
  if(route.arrow){
   const tip=route.points[route.points.length-1],prior=route.points[route.points.length-2]
   if(boxes.some(box=>inside(tip,box)))violations.push('arrow tip inside a node')
   const dx=Math.sign(tip.x-prior.x),dy=Math.sign(tip.y-prior.y),arrow={id:'arrow',left:Math.min(tip.x,tip.x-dx*8-dy*4,tip.x-dx*8+dy*4),right:Math.max(tip.x,tip.x-dx*8-dy*4,tip.x-dx*8+dy*4),top:Math.min(tip.y,tip.y-dy*8+dx*4,tip.y-dy*8-dx*4),bottom:Math.max(tip.y,tip.y-dy*8+dx*4,tip.y-dy*8-dx*4)}
   for(const box of [...boxes,...labels])if(overlap(arrow,box))violations.push('arrowhead overlaps '+box.id)
   if(checkLabels)for(const other of layout.routes)if(other!==route)for(const {a,b} of segments(other.points))if(segmentBox(a,b,arrow))violations.push('arrowhead overlaps another route')
  }
 }
 if(checkLabels){
  expect(labels).toHaveLength(layout.routes.filter(route=>!!route.relation&&route.show_label!==false).length)
  if(layout.routes.some(route=>route.relation&&route.show_label!==false))expect(labels.length).toBeGreaterThan(0)
  for(const label of labels){
   for(const box of boxes)if(overlap(label,box))violations.push('label overlaps node '+box.id)
   for(const route of [...layout.routes,...(layout.trunks||[])])for(const {a,b} of segments(route.points))if(segmentBox(a,b,label))violations.push('label overlaps route '+label.id)
  }
  for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++)if(overlap(labels[i],labels[j]))violations.push('labels overlap')
  for(let i=0;i<layout.routes.length;i++)for(let j=i+1;j<layout.routes.length;j++)for(const a of segments(layout.routes[i].points))for(const b of segments(layout.routes[j].points))if(intersects(a.a,a.b,b.a,b.b))violations.push('routes cross or share a collinear segment')
 }
 expect(violations).toEqual([])
}

it('lays out a fully expanded hierarchy with non-overlapping boxes, clear routes and arrows outside every target',()=>{
 const many:ContentMapNode[]=[{id:'theme',kind:'paper',label:'竞争传输'}]
 for(let section=0;section<8;section++){
  const sectionId='section-'+section;many.push({id:sectionId,parent_id:'theme',kind:'section',label:'章节 '+section,order:section})
  for(let paragraph=0;paragraph<6;paragraph++){
   const id=sectionId+'-p'+paragraph;many.push({id,parent_id:sectionId,kind:'paragraph',label:'段落 '+paragraph,order:paragraph})
   for(let element=0;element<2;element++)many.push({id:id+'-e'+element,parent_id:id,kind:'element',label:'概念 '+element,order:element})
  }
 }
 const layout=layoutContentTree(many,new Set(many.map(node=>node.id)))
 expect(layout.positions).toHaveLength(153)
 assertClearCanvas(layout)
})

it('gives dense incoming, outgoing, bidirectional and self relations separate horizontal lanes and non-overlapping labels',()=>{
 const related:ContentMapNode[]=[{id:'focus',kind:'paragraph',label:'结合竞争'},...Array.from({length:12},(_,i)=>({id:'n'+i,kind:'element',label:'概念 '+i}))]
 const edges:ContentMapEdge[]=related.slice(1).flatMap((node,index)=>index<7?[{id:'incoming-'+index,from:node.id,to:'focus',relation:'支持'}]:[{id:'outgoing-'+index,from:'focus',to:node.id,relation:'限定'}])
 edges[0].relation='温度加速扩散与化学反应'
 edges.push({id:'reverse',from:'focus',to:'n0',relation:'回应'},{id:'parallel',from:'n0',to:'focus',relation:'比较'},{id:'loop',from:'focus',to:'focus',relation:'解释'})
 const layout=layoutContentRelations(related,edges,'focus')
 expect(layout.routes).toHaveLength(edges.length)
 expect(layout.routes.every(route=>route.points.length===2&&route.points[0].y===route.points[1].y)).toBe(true)
 assertClearCanvas(layout,true)
})

it('keeps the zoom anchor fixed in world coordinates and bounds the scale without shrinking a large graph into one screen',()=>{
 const initial={x:31,y:42,scale:.8},anchor={x:200,y:160},zoomed=zoomContentCanvas(initial,1.6,anchor)
 expect((anchor.x-zoomed.x)/zoomed.scale).toBeCloseTo((anchor.x-initial.x)/initial.scale)
 expect((anchor.y-zoomed.y)/zoomed.scale).toBeCloseTo((anchor.y-initial.y)/initial.scale)
 expect(zoomContentCanvas(initial,10,anchor).scale).toBe(2.5)
 expect(zoomContentCanvas(initial,.01,anchor).scale).toBe(.2)
 expect(fitContentCanvas({width:3000,height:10000},700,500).scale).toBe(.55)
})

it('keeps complete scientific labels unchanged and preserves exact source sentences with their original context',()=>{
 const unit={id:'p1',text:'Prior context. Exact supporting sentence. Following context.',page:4}
 const node:ContentMapNode={id:'concept',kind:'element',label:'This long explanatory sentence belongs in the detail panel rather than inside the mind map node.',keywords:['竞争结合','扩散通道'],source_ids:['p1'],source_quotes:[{source_id:'p1',quote:'Exact supporting sentence.'}]}
 expect(contentNodePhrase(node)).toBe(node.label)
 expect(contentNodeSize(node).width).toBe(240)
 expect(contentNodeSize(node).height).toBeGreaterThan(72)
 expect(nodeSourceEvidence(node,[unit])).toEqual([{unit,quotes:['Exact supporting sentence.']}])
 const segments=sourceQuoteSegments(unit.text,['Exact supporting sentence.'])
 expect(segments.map(segment=>segment.text).join('')).toBe(unit.text)
 expect(segments.filter(segment=>segment.highlight).map(segment=>segment.text)).toEqual(['Exact supporting sentence.'])
 expect(nodeSourceEvidence({...node,source_quotes:[]},[unit])).toEqual([{unit,quotes:[]}])
})

it('keeps selected key arguments in a compact primary tree while retaining their original semantic IDs',()=>{
 const map={source:{title:'竞争输运'},nodes,edges:[],story:{key_node_ids:['gap','method','gap','missing']}}
 expect(keyContentNodes(map).map(node=>node.id)).toEqual(['gap','method'])
 const layout=layoutContentKeyPoints(map)
 expect(layout.positions.map(position=>position.node.id)).toEqual(['gap','method','paper'])
 expect(layout.positions.find(position=>position.node.id==='gap')?.node.label).toBe('结合竞争与传输通道缺少区分')
 expect(nodes.find(node=>node.id==='gap')?.parent_id).toBe('paragraph')
 expect(layout.routes.every(route=>route.arrow===false)).toBe(true)
 expect(layout.trunks?.length).toBe(2)
 assertClearCanvas(layout)
})

it('preserves all directed key relations including a convergent claim, with clear capsules and no crossing branches',()=>{
 const keyNodes:ContentMapNode[]=[{id:'paper',kind:'paper',label:'作者问题'},{id:'prior',kind:'paragraph',label:'已有预测能描述膨胀'},{id:'omission',kind:'analysis',label:'省略导致相反偏差'},{id:'high',parent_id:'omission',kind:'comparison',label:'忽略增孔导致高估'},{id:'low',parent_id:'omission',kind:'comparison',label:'忽略供钙导致低估'},{id:'claim',kind:'conclusion',label:'供钙和增孔竞争控制膨胀'}]
 const edges:ContentMapEdge[]=[{id:'p-o',from:'prior',to:'omission',relation:'暴露省略'},{id:'o-h',from:'omission',to:'high',relation:'关闭增孔'},{id:'o-l',from:'omission',to:'low',relation:'关闭供钙'},{id:'h-c',from:'high',to:'claim',relation:'支持竞争解释'},{id:'l-c',from:'low',to:'claim',relation:'支持竞争解释'}]
 const map={source:{title:'预测偏差'},nodes:keyNodes,edges,story:{key_node_ids:keyNodes.slice(1).map(node=>node.id)}}
 const layout=layoutContentKeyPoints(map)
 expect(layout.routes.filter(route=>route.arrow).map(route=>route.id).sort()).toEqual(edges.map(edge=>edge.id).sort())
 expect(layout.positions.filter(position=>position.node.id==='claim')).toHaveLength(2)
 expect(new Set(layout.positions.map(contentPositionId)).size).toBe(layout.positions.length)
 assertClearCanvas(layout,true)
})

it('keeps the relation center compact and suppresses only labels explicitly marked show_label false',()=>{
 const focus:ContentMapNode={id:'focus',kind:'analysis',argument_role:'finding',label:'钙离子补给与孔隙增加的相对作用决定膨胀'}
 const peers:ContentMapNode[]=Array.from({length:4},(_,index)=>({id:'peer-'+index,kind:'comparison',argument_role:'evidence',label:'不考虑溶解引起的孔隙变化，会高估膨胀'}))
 const edges:ContentMapEdge[]=peers.map((node,index)=>({id:'r-'+index,from:'focus',to:node.id,relation:'对照显示',show_label:false}))
 const layout=layoutContentRelations([focus,...peers],edges,'focus'),center=layout.positions.find(position=>position.node.id==='focus')!
 expect(contentPositionSize(center)).toEqual(contentNodeSize(focus))
 expect(layout.routes).toHaveLength(4)
 expect(layout.routes.every(route=>!route.labelBox)).toBe(true)
 expect(layout.trunks?.length).toBe(2)
 assertClearCanvas(layout,true)
 edges[0].show_label=true
 const labeled=layoutContentRelations([focus,...peers],edges,'focus')
 expect(labeled.routes.filter(route=>route.labelBox)).toHaveLength(1)
 assertClearCanvas(labeled,true)
})

it('centers the initial key overview at a readable fit and keeps large graphs at a minimum of 85 percent',()=>{
 const layout={width:1384,height:360},view=fitKeyContentCanvas(layout,1600,900)
 expect(view.scale).toBe(1)
 expect(view.x+layout.width*view.scale/2).toBe(800)
 expect(view.y+layout.height*view.scale/2).toBe(450)
 const smaller=fitKeyContentCanvas(layout,1240,900)
 expect(smaller.scale).toBeGreaterThanOrEqual(.85)
 expect(smaller.x).toBeGreaterThanOrEqual(0)
 expect(smaller.x+layout.width*smaller.scale).toBeLessThanOrEqual(1240)
 const large=fitKeyContentCanvas({width:5000,height:3000},1600,900)
 expect(large.scale).toBe(.85)
 expect(large.x+5000*large.scale/2).toBe(800)
 expect(large.y+3000*large.scale/2).toBe(450)
})

it('lays out the eight key judgments once in four vertical rows, retaining all eight edges and one explicit convergence bus',()=>{
 const nodes:ContentMapNode[]=[
  {id:'paper',kind:'paper',argument_role:'question',label:'钙溶出与温度变化如何影响硫酸盐侵蚀引起的膨胀'},
  {id:'model',kind:'analysis',argument_role:'approach',label:'仅忽略溶解引起的孔隙变化，或完全忽略钙溶出，对照膨胀预测'},
  {id:'tempcompare',kind:'comparison',argument_role:'approach',label:'比较10°C和23°C条件下的试件膨胀'},
  {id:'overestimate',kind:'comparison',argument_role:'evidence',label:'不考虑溶解引起的孔隙变化，会高估试验中的膨胀'},
  {id:'underestimate',kind:'comparison',argument_role:'evidence',label:'完全忽略钙溶出，会低估试验中的膨胀'},
  {id:'competition',kind:'conclusion',argument_role:'finding',label:'钙溶出对膨胀的影响取决于钙离子补给与孔隙增加的相对作用'},
  {id:'temperature',kind:'comparison',argument_role:'evidence',label:'同一砂浆在23°C下的膨胀大于10°C'},
  {id:'limit',kind:'conclusion',argument_role:'scope',label:'模型低估低温下的膨胀，仍需补充温度相关的化学过程'},
 ]
 const pairs=[['paper','model'],['paper','tempcompare'],['model','overestimate'],['model','underestimate'],['overestimate','competition'],['underestimate','competition'],['tempcompare','temperature'],['temperature','limit']]
 const edges:ContentMapEdge[]=pairs.map(([from,to],index)=>({id:'key-'+(index+1),from,to,relation:'论证联系',show_label:false})),map={source:{title:'硫酸盐侵蚀膨胀'},nodes,edges,story:{key_node_ids:nodes.slice(1).map(node=>node.id)}}
 const layout=layoutContentKeyPoints(map)
 expect(layoutCompactKeyDag(map)).not.toBeNull()
 expect(layout.positions).toHaveLength(8)
 expect(new Set(layout.positions.map(position=>position.node.id)).size).toBe(8)
 expect(layout.links.map(edge=>edge.id).sort()).toEqual(edges.map(edge=>edge.id).sort())
 expect(layout.routes.map(edge=>edge.id).sort()).toEqual(edges.map(edge=>edge.id).sort())
 expect(layout.positions.filter(position=>position.node.id==='competition')).toHaveLength(1)
 expect([0,1,2,3].map(depth=>layout.positions.filter(position=>position.depth===depth).length)).toEqual([1,2,3,2])
 const mergeBus=layout.trunks!.filter(stroke=>stroke.kind==='merge_bus'),mergeStem=layout.trunks!.filter(stroke=>stroke.kind==='merge_stem')
 expect(mergeBus).toHaveLength(1)
 expect(mergeStem).toHaveLength(1)
 expect(mergeBus[0].edge_ids).toEqual(['key-5','key-6'])
 expect(mergeStem[0].arrow).toBe(true)
 expect(layout.routes.filter(route=>route.to==='competition').every(route=>route.arrow===false)).toBe(true)
 expect(layout.width).toBeLessThanOrEqual(1050)
 expect(layout.height).toBeGreaterThanOrEqual(560)
 expect(layout.height).toBeLessThanOrEqual(660)
 expect(fitKeyContentCanvas(layout,1440,814).scale).toBe(1)
 assertClearCanvas(layout,true)
 // A visible relationship label deliberately selects the existing layout.
 edges[0].show_label=true
 expect(layoutCompactKeyDag(map)).toBeNull()
})

it('keeps a gap role at the ordinary node size while distinguishing the root question size',()=>{
 const gap:ContentMapNode={id:'gap',kind:'analysis',argument_role:'gap',label:'省略钙溶出无法区分两种作用的相反影响'}
 expect(contentNodeSize(gap).width).toBe(240)
 expect(contentNodeSize(gap).height).toBe(72)
 expect(contentNodePhrase(gap)).toBe(gap.label)
 expect(contentNodeSize({...gap,argument_role:'question'}).width).toBe(260)
})
