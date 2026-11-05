// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {PaperContentMap} from './PaperContentMap'
import {api} from './api'
import {fitKeyContentCanvas,layoutContentKeyPoints,type ContentMapState,type PaperContentMapData} from './paperContentMap'

vi.mock('./api',()=>({projectPath:(_project:unknown,path:string)=>path,jsonBody:(value:unknown)=>({method:'POST',body:JSON.stringify(value)}),api:vi.fn()}))
const originalAbstract='Competitive transport of chloride and sulfate is controlled by binding and pore connectivity.\n\nWe compare three transport conditions using matched initial concentrations. The complete final sentence must remain available.'
const map:PaperContentMapData={source:{title:'Competition in reactive transport'},abstract:{text:originalAbstract,complete:true,source_ids:['abstract']},keywords:['竞争结合','传输通道'],nodes:[
 {id:'paper',kind:'paper',label:'结合竞争怎样改变离子传输',content:'论文讨论结合竞争与孔隙通道的不同作用。'},
 {id:'intro',parent_id:'paper',kind:'section',section_type:'introduction',label:'已有输运模型无法区分竞争机制'},
 {id:'p1',parent_id:'intro',kind:'paragraph',section_type:'introduction',label:'结合竞争解释浓度变化',content:'此段将竞争结合与自由离子浓度相联系。',keywords:['结合竞争'],source_ids:['paragraph'],source_quotes:[{source_id:'paragraph',quote:'Binding competition changes free-ion concentration.'}]},
 {id:'element',parent_id:'p1',kind:'element',section_type:'introduction',label:'相同初始浓度的比较约束',source_ids:['no-page']},
 {id:'methods',parent_id:'paper',kind:'section',section_type:'methods',label:'以耦合模型分离两类效应',source_ids:['paragraph']},
],edges:[{id:'link',from:'p1',to:'methods',relation:'提出要求',explanation:'竞争结合需要在模型中与孔隙变化分别表述。',source_ids:['paragraph'],basis:'inferred'}],source_units:[
 {id:'abstract',text:originalAbstract,page:1,section_title:'Abstract'},
 {id:'paragraph',text:'Binding competition changes free-ion concentration. This is the complete original paragraph, including its comparison condition.',page:7,section_title:'1. Introduction'},
 {id:'no-page',text:'This source has no verified page.',page:null,section_title:'Introduction'},
],story:{author_question:'如何区分结合和孔隙影响？',promise_evidence:[{question:'区分两类机制',method:'耦合模型',evidence:'匹配浓度的对照实验',conclusion:'两类作用依条件改变',node_ids:['p1','methods'],source_ids:['paragraph']}]}}
let host:HTMLDivElement,root:Root
const source=vi.fn(),notify=vi.fn(),onError=vi.fn()
beforeEach(()=>{(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.mocked(api).mockReset();source.mockReset();notify.mockReset();onError.mockReset()})
afterEach(async()=>{vi.useRealTimers();await act(async()=>root.unmount());host.remove()})
async function mount(state:ContentMapState,asset='reading/paper.pdf'){vi.mocked(api).mockResolvedValue(state);await act(async()=>{root.render(<PaperContentMap project={{id:'project'} as any} asset={asset} library="workspace" title="Citation title" onBack={()=>{}} onSource={source} onError={onError} notify={notify}/>);await Promise.resolve()})}
async function click(text:string){const button=Array.from(host.querySelectorAll('button')).find(element=>element.textContent?.trim()===text);expect(button,'button '+text).toBeTruthy();await act(async()=>{button!.click();await Promise.resolve()})}

it('starts with chapter nodes and expands true paragraphs and their elements one level at a time',async()=>{
 await mount({status:'ready',map})
 expect(host.querySelectorAll('[data-node-id]')).toHaveLength(3)
 expect(host.querySelector('[data-node-id="p1"]')).toBeNull()
 await act(async()=>{(host.querySelector('[aria-label="展开 已有输运模型无法区分竞争机制"]') as HTMLButtonElement).click()})
 expect(host.querySelector('[data-node-id="p1"]')).toBeTruthy()
 expect(host.querySelector('[data-node-id="element"]')).toBeNull()
 await act(async()=>{(host.querySelector('[aria-label="展开 结合竞争解释浓度变化"]') as HTMLButtonElement).click()})
 expect(host.querySelector('[data-node-id="element"]')).toBeTruthy()
 await act(async()=>{(host.querySelector('[aria-label="折叠到章节"]') as HTMLButtonElement).click()})
 expect(host.querySelector('[data-node-id="p1"]')).toBeNull()
})

it('displays every word of the extracted original abstract without substituting node explanations',async()=>{
 await mount({status:'ready',map})
 await click('完整摘要')
 expect(host.querySelector('.content-map-original-abstract')?.textContent).toBe(originalAbstract)
 expect(host.querySelector('.content-map-abstract')?.textContent).toContain('摘要原文')
 expect(host.querySelector('.content-map-original-abstract')?.textContent).not.toContain('论文讨论结合竞争')
})

it('shows the clicked keyword’s supporting sentence and full paragraph context directly, with PDF as a secondary locator',async()=>{
 await mount({status:'ready',map})
 await act(async()=>{(host.querySelector('[aria-label="展开 已有输运模型无法区分竞争机制"]') as HTMLButtonElement).click()})
 await act(async()=>{(host.querySelector('[data-node-id="p1"] .content-map-node-label') as HTMLButtonElement).click()})
 const detail=host.querySelector('.content-map-detail')!
 expect(detail.querySelector('.content-map-source-quotes blockquote')?.textContent).toBe(map.nodes[2].source_quotes![0].quote)
 expect(detail.querySelector('.content-map-source-context p')?.textContent).toBe(map.source_units![1].text)
 expect(detail.querySelector('.content-map-source-context mark')?.textContent).toBe(map.nodes[2].source_quotes![0].quote)
 expect(detail.querySelector('.content-map-source-quotes')?.closest('details')).toBeNull()
 expect(detail.textContent).toContain('竞争结合需要在模型中与孔隙变化分别表述。')
 const open=Array.from(detail.querySelectorAll('button')).find(button=>button.textContent==='打开原文第 7 页')!
 await act(async()=>open.click())
 expect(source).toHaveBeenCalledWith({page:7,unit_id:'paragraph',quote:map.source_units![1].text,bounds:undefined})
 await act(async()=>{(host.querySelector('[aria-label="展开 结合竞争解释浓度变化"]') as HTMLButtonElement).click();})
 await act(async()=>{(host.querySelector('[data-node-id="element"] .content-map-node-label') as HTMLButtonElement).click()})
 expect((host.querySelector('.content-map-pdf-locator') as HTMLButtonElement).disabled).toBe(true)
 expect(host.querySelector('.content-map-evidence')?.textContent).toContain('对应原文段落')
 expect(source).toHaveBeenCalledTimes(1)
})

it('shows selected content relations and follows the connected semantic node',async()=>{
 await mount({status:'ready',map})
 await act(async()=>{(host.querySelector('[data-node-id="methods"] .content-map-node-label') as HTMLButtonElement).click()})
 await click('内容关系')
 expect(host.querySelector('[aria-label="论文内容关系画布"]')?.textContent).toContain('提出要求')
 const neighbor=Array.from(host.querySelectorAll('[aria-label="论文内容关系画布"] .content-map-node-label')).find(button=>button.textContent?.includes('结合竞争解释浓度变化'))!
 await act(async()=>neighbor.click())
 expect(host.querySelector('.content-map-detail h2')?.textContent).toBe('结合竞争解释浓度变化')
 expect(host.querySelector('.content-map-source-quotes blockquote')?.textContent).toBe(map.nodes[2].source_quotes![0].quote)
 expect(host.querySelectorAll('.content-map-relation-label rect')).toHaveLength(1)
 expect(host.querySelector('.content-map-relation-label text')?.textContent).toBe('提出要求')
})

it('opens a supplied key-argument overview and keeps the complete hierarchy available separately',async()=>{
 await mount({status:'ready',map:{...map,story:{...map.story,key_node_ids:['p1','methods']}}})
 expect(host.querySelector('[aria-label="论文关键论证画布"]')).toBeTruthy()
 expect(Array.from(host.querySelectorAll('[data-node-id]')).map(node=>(node as HTMLElement).dataset.nodeId).sort()).toEqual(['methods','p1','paper'])
 expect(host.querySelector('[data-node-id="intro"]')).toBeNull()
 expect(host.querySelector('.content-map-detail')).toBeNull()
 await act(async()=>{(host.querySelector('[data-node-id="p1"] .content-map-node-label') as HTMLButtonElement).click()})
 expect(host.querySelector('.content-map-detail h2')?.textContent).toBe('结合竞争解释浓度变化')
 expect(host.querySelector('.content-map-source-quotes blockquote')?.textContent).toBe(map.nodes[2].source_quotes![0].quote)
 await click('思维导图')
 expect(host.querySelector('[aria-label="论文内容思维画布"]')).toBeTruthy()
 expect(host.querySelector('[data-node-id="intro"]')).toBeTruthy()
 expect(host.querySelectorAll('.content-map-canvas-lines marker[markerUnits="userSpaceOnUse"]')).toHaveLength(1)
 expect(host.querySelectorAll('.content-map-canvas-lines g>path[marker-end]')).toHaveLength(0)
})

it.each(['思维导图','内容关系'])('supports zoom, keyboard pan, wheel zoom and reset on the %s canvas',async(tab)=>{
 await mount({status:'ready',map})
 if(tab==='内容关系'){
  await act(async()=>{(host.querySelector('[data-node-id="methods"] .content-map-node-label') as HTMLButtonElement).click()})
  await click(tab)
 }
 const canvas=host.querySelector('.content-map-canvas') as HTMLDivElement,initialScale=Number(canvas.dataset.scale)
 const plus=host.querySelector('[aria-label="放大画布"]') as HTMLButtonElement
 await act(async()=>plus.click())
 expect(Number(canvas.dataset.scale)).toBeGreaterThan(initialScale)
 const beforePan=Number(canvas.dataset.panX)
 await act(async()=>{canvas.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))})
 expect(Number(canvas.dataset.panX)).toBe(beforePan-48)
 const beforeWheel=Number(canvas.dataset.scale)
 await act(async()=>{canvas.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,clientX:200,clientY:140,bubbles:true,cancelable:true}))})
 expect(Number(canvas.dataset.scale)).toBeGreaterThan(beforeWheel)
 await act(async()=>{(host.querySelector('[aria-label="重置画布"]') as HTMLButtonElement).click()})
 expect(Number(canvas.dataset.scale)).toBeCloseTo(initialScale)
 expect(host.querySelector('[aria-label="画布缩放比例"]')).toBeNull()
})

it('does not trigger generation on GET and reflects the actual queued state after a request',async()=>{
 await mount({status:'missing',map:null})
 expect(host.textContent).toContain('尚未生成')
 expect(vi.mocked(api).mock.calls.every(([,init])=>!init?.method)).toBe(true)
 vi.mocked(api).mockResolvedValue({status:'queued',stage:'queued',job_id:'job-real',map:null})
 await click('生成完整内容图谱')
 expect(host.textContent).toContain('等待生成')
 expect(host.textContent).toContain('等待处理')
 expect(host.querySelector('.content-map-canvas')).toBeNull()
 expect(notify).toHaveBeenCalledWith('内容图谱已加入队列')
 expect(vi.mocked(api).mock.calls.some(([,init])=>init?.method==='POST'&&JSON.parse(init.body as string).asset==='reading/paper.pdf')).toBe(true)
})

it('polls active jobs and promotes only the returned ready result',async()=>{
 vi.useFakeTimers()
 await mount({status:'queued',stage:'queued',map:null})
 vi.mocked(api).mockResolvedValue({status:'ready',map})
 vi.mocked(api).mockResolvedValueOnce({status:'running',stage:'analyzing',map:null})
 await act(async()=>{(host.querySelector('[aria-label="刷新图谱状态"]') as HTMLButtonElement).click();await Promise.resolve()})
 expect(host.textContent).toContain('正在提炼章节与段落')
 await act(async()=>{await vi.advanceTimersByTimeAsync(3000)})
 expect(host.querySelector('.content-map-status')).toBeNull()
 expect(host.querySelectorAll('[data-node-id]')).toHaveLength(3)
})

it('preserves a failed retry and reports the failure without a success notification',async()=>{
 await mount({status:'failed',error:'模型调用未完成',map:null})
 vi.mocked(api).mockRejectedValue(new Error('当前模型不可用'))
 await click('重试生成')
 expect(host.textContent).toContain('生成失败')
 expect(host.querySelector('[role="alert"]')?.textContent).toContain('当前模型不可用')
 expect(notify).not.toHaveBeenCalled()
 expect(onError).toHaveBeenCalledTimes(1)
 const request=vi.mocked(api).mock.calls.find(([,init])=>init?.method==='POST')!
 expect(JSON.parse(request[1]!.body as string)).not.toHaveProperty('force')
})

it.each([['failed','重试生成'],['interrupted','继续生成']])('resumes saved sections for %s without forcing a replacement job',async(status,action)=>{
 await mount({status,error:status==='interrupted'?'工作进程已停止':'模型调用未完成',map:null})
 if(status==='interrupted'){
  expect(host.textContent).toContain('生成已中断')
  expect(host.textContent).toContain('工作进程已停止')
 }
 vi.mocked(api).mockResolvedValue({status:'queued',stage:'从已保存章节继续',map:null})
 await click(action)
 const request=vi.mocked(api).mock.calls.find(([,init])=>init?.method==='POST')!
 expect(JSON.parse(request[1]!.body as string)).toEqual({asset:'reading/paper.pdf',library:'workspace'})
 expect(host.textContent).toContain('从已保存章节继续')
 expect(host.textContent).toContain('等待生成')
})

it('keeps a loaded map quiet, with no status, category, count, coverage or interaction hints and an initially closed source panel',async()=>{
 const actualMap:PaperContentMapData={...map,schema_version:1,coverage:{total_units:12,mapped_units:10,unmapped_unit_ids:['u11','u12'],paragraph_boundary_status:'tei_paragraphs',needs_review:['引言第二段缺少段内内容要素。']}}
 await mount({status:'needs_review',map:actualMap})
 expect(host.querySelector('.content-map-status')).toBeNull()
 expect(host.querySelector('.content-map-coverage')).toBeNull()
 expect(host.querySelector('.content-map-detail')).toBeNull()
 expect(host.querySelector('.content-map-diagram-hint')).toBeNull()
 expect(host.querySelector('.content-map-canvas-help')).toBeNull()
 expect(host.querySelector('.content-map-node-label small')).toBeNull()
 expect(host.querySelector('.content-map-toolbar small')).toBeNull()
 expect(host.textContent).not.toContain('需要复核')
 expect(host.textContent).not.toContain('个内容节点')
 expect(host.textContent).not.toContain('原文段落结构')
 await act(async()=>{(host.querySelector('[data-node-id="methods"] .content-map-node-label') as HTMLButtonElement).click()})
 expect(host.querySelector('.content-map-detail')).toBeTruthy()
 expect(host.querySelector('.content-map-parent')).toBeNull()
 expect(host.querySelector('.content-map-detail .content-map-keywords')).toBeNull()
 await act(async()=>{(host.querySelector('[aria-label="收起原文详情"]') as HTMLButtonElement).click()})
 expect(host.querySelector('.content-map-detail')).toBeNull()
})

it.each(['stale','needs_review'])('keeps the existing %s map visible and exposes regeneration as an icon without a generic status bar',async(status)=>{
 await mount({status,map})
 expect(host.querySelector('.content-map-status')).toBeNull()
 expect(host.querySelector('.content-map-canvas')).toBeTruthy()
 vi.mocked(api).mockResolvedValue({status:'queued',map:null})
 await act(async()=>{(host.querySelector('[aria-label="重新生成图谱"]') as HTMLButtonElement).click();await Promise.resolve()})
 const request=vi.mocked(api).mock.calls.find(([,init])=>init?.method==='POST')!
 expect(JSON.parse(request[1]!.body as string).force).toBe(true)
})

it('retains the complete scientific wording and role style class without substituting shorter keywords',async()=>{
 const label='不考虑水化产物溶解引起的孔隙率变化，会高估硫酸盐侵蚀引起的试件膨胀'
 const roleMap:PaperContentMapData={...map,nodes:map.nodes.map(node=>node.id==='paper'?{...node,argument_role:'question' as const}:node.id==='methods'?{...node,label,keywords:['增孔'],argument_role:'evidence' as const}:node)}
 await mount({status:'ready',map:roleMap})
 const node=host.querySelector('[data-node-id="methods"]') as HTMLElement
 expect(node.classList.contains('role-evidence')).toBe(true)
 expect(node.querySelector('.content-map-node-label span')?.textContent).toBe(label)
 expect(node.style.width).toBe('240px')
 expect(Number.parseInt(node.style.height)).toBeGreaterThanOrEqual(84)
 expect((host.querySelector('[data-node-id="paper"]') as HTMLElement).style.width).toBe('260px')
})

it('offers no complete generation for a citation without a PDF and leaves missing abstract explicit',async()=>{
 await mount({status:'missing',map:null},'reference-record')
 expect(host.textContent).toContain('请先下载或导入 PDF 全文')
 expect(Array.from(host.querySelectorAll('button')).some(button=>button.textContent==='生成完整内容图谱')).toBe(false)
 await act(async()=>root.unmount());root=createRoot(host)
 await mount({status:'needs_review',map:{...map,abstract:{text:'',complete:false,status:'missing'}}})
 await click('完整摘要')
 expect(host.textContent).toContain('未提取到摘要原文')
 expect(host.querySelector('.content-map-original-abstract')).toBeNull()
})

it('starts and resets the key overview at a whole-graph fit, then centers a node only after an explicit click',async()=>{
 const actual={...map,story:{...map.story,key_node_ids:['p1','methods']}},layout=layoutContentKeyPoints(actual)
 await mount({status:'ready',map:actual})
 const canvas=host.querySelector('[aria-label="论文关键论证画布"]') as HTMLElement,expected=fitKeyContentCanvas(layout,760,480)
 expect(Number(canvas.dataset.scale)).toBeCloseTo(expected.scale)
 expect(Number(canvas.dataset.panX)).toBeCloseTo(expected.x)
 expect(Number(canvas.dataset.panY)).toBeCloseTo(expected.y)
 expect(host.querySelector('.content-map-detail')).toBeNull()
 await act(async()=>{(host.querySelector('[data-node-id="methods"] .content-map-node-label') as HTMLButtonElement).click()})
 const target=layout.positions.find(position=>position.node.id==='methods')!
 expect(Number(canvas.dataset.panX)).toBeCloseTo(760/2-(target.x+240/2)*expected.scale)
 expect(host.querySelector('.content-map-detail')).toBeTruthy()
 await act(async()=>{(host.querySelector('[aria-label="重置画布"]') as HTMLButtonElement).click()})
 expect(Number(canvas.dataset.panX)).toBeCloseTo(expected.x)
 expect(Number(canvas.dataset.panY)).toBeCloseTo(expected.y)
})

it('shows supplied evaluation separately and never invents a total for unscored visual or interaction items',async()=>{
 const evaluation={items:[{id:'key_selection',label:'关键节点取舍',score:12,max:12,reason:'节点对应实际问题、比较、认识和边界。'},{id:'collisions',label:'线路与文字清晰度',score:null,max:12,reason:'等待实际画面评阅。'}],content_score:65,content_max:65,visual_score:null,interaction_score:null,summary:'内容复读已完成。'}
 await mount({status:'ready',map:{...map,evaluation}})
 expect(host.querySelector('.content-map-evaluation')).toBeNull()
 expect(host.querySelector('.content-map-canvas')?.textContent).not.toContain('65')
 await click('评分')
 expect(host.querySelector('.content-map-score-totals')?.textContent).toContain('内容 65 / 65')
 expect(host.querySelector('.content-map-score-totals')?.textContent).toContain('视觉与交互 未评')
 expect(host.querySelector('table')?.textContent).toContain('节点对应实际问题、比较、认识和边界。')
 expect(host.querySelector('table')?.textContent).toContain('未评')
 expect(host.querySelector('.content-map-evaluation')?.textContent).not.toContain('/ 100')
})

it('handles structured evaluation issues and a null content score without crashing or fabricating a score',async()=>{
 const evaluation={items:[],content_score:null,content_max:65,issues:[{severity:'medium',reason:'判断范围需要明确。',suggestion:'在节点中补充比较条件。'},'另一项待确认内容。']}
 await mount({status:'ready',map:{...map,evaluation}})
 await click('评分')
 expect(host.querySelector('.content-map-score-totals')?.textContent).toContain('内容 未评')
 expect(host.querySelector('.content-map-evaluation')?.textContent).toContain('判断范围需要明确。')
 expect(host.querySelector('.content-map-evaluation')?.textContent).toContain('在节点中补充比较条件。')
 expect(host.querySelector('.content-map-evaluation')?.textContent).toContain('另一项待确认内容。')
 expect(host.querySelector('.content-map-evaluation')?.textContent).not.toContain('null /')
})
