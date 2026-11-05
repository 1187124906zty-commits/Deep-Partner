// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {LibraryPanel} from './Library'
import {api} from './api'

const state=vi.hoisted(()=>({maps:[{asset:'reading/first.pdf',library:'workspace',status:'running',stage:'analyzing'}],readerProps:null as any,notifications:[] as string[]}))
vi.mock('./Reader',()=>({NativeReader:(props:any)=>{state.readerProps=props;return <div data-testid="reader">原文第 {props.target?.locator?.page||1} 页</div>}}))
vi.mock('./PaperContentMap',()=>({PaperContentMap:(props:any)=><section aria-label="内容图谱测试"><span>{props.title}</span><button onClick={()=>props.onSource({page:9,unit_id:'original-unit',quote:'The real source paragraph.'})}>打开图谱原文</button></section>}))
vi.mock('./KnowledgeSources',()=>({KnowledgeSources:(props:any)=><button onClick={()=>props.onFilesChanged?.()}>知识库上传完成</button>}))
vi.mock('./ReferencePanel',()=>({ReferenceMetadata:()=>null}))
vi.mock('./Review',()=>({ContextMenu:()=>null}))
vi.mock('./LiteratureSearch',()=>({LiteratureSearch:()=>null,DownloadQueue:()=>null,queuePapers:vi.fn(),queueMessage:()=>''}))
vi.mock('./api',()=>({base:'',projectPath:(_project:unknown,path:string)=>path,jsonBody:(value:unknown)=>({method:'POST',body:JSON.stringify(value)}),prettySize:(n:number)=>String(n),api:vi.fn(async(path:string)=>{
 if(path==='/literature/items')return {files:[{library:'workspace',name:'reading/first.pdf',metadata:{title:'Attached paper'}}],references:[{id:'citation',title:'Citation without full text',authors:[],year:2025}],downloads:[]}
 if(path==='/literature/folders')return {assignments:{},folders:[],memberships:{}}
 if(path==='/literature/content-maps')return {items:state.maps,auto_enabled:true}
 if(path==='/literature/content-maps/backfill')return {queued:1}
 return {}
})}))
let host:HTMLDivElement,root:Root
beforeEach(()=>{(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host);state.readerProps=null;state.notifications=[];state.maps=[{asset:'reading/first.pdf',library:'workspace',status:'running',stage:'analyzing'}];vi.mocked(api).mockClear()})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
const mount=async()=>{await act(async()=>{root.render(<LibraryPanel project={{id:'p',config:{}} as any} version={0} onError={error=>{throw error}} onUpdate={()=>{}} notify={message=>state.notifications.push(message)}/>);await Promise.resolve()})}
const click=async(text:string)=>{const button=Array.from(host.querySelectorAll('button')).find(item=>item.textContent?.trim()===text)!;expect(button).toBeTruthy();await act(async()=>{button.click();await Promise.resolve()})}

it('provides an entry for an attached PDF and passes the real map locator to NativeReader',async()=>{
 await mount()
 const row=Array.from(host.querySelectorAll('.bibliography-table tbody tr')).find(item=>item.textContent?.includes('Attached paper'))!
 await act(async()=>{row.dispatchEvent(new MouseEvent('click',{bubbles:true}))})
 expect(host.querySelector('.bibliography-detail')?.textContent).toContain('内容图谱')
 expect(host.querySelector('.bibliography-content-map-status')?.textContent).toContain('正在生成')
 await click('内容图谱')
 expect(host.querySelector('[aria-label="内容图谱测试"]')?.textContent).toContain('Attached paper')
 await click('打开图谱原文')
 expect(state.readerProps.target.locator).toEqual({page:9,unit_id:'original-unit',quote:'The real source paragraph.'})
 expect(state.readerProps.asset).toBe('reading/first.pdf')
 expect(state.readerProps.library).toBe('workspace')
 expect(host.textContent).toContain('原文第 9 页')
})

it('shows actual progress and submits the existing-PDF backfill endpoint',async()=>{
 await mount()
 expect(host.querySelector('.library-content-map-summary')?.textContent).toContain('处理中 1')
 expect(host.querySelector('.library-content-map-summary')?.textContent).toContain('正在提炼章节与段落')
 await click('补齐内容图谱')
 expect(vi.mocked(api).mock.calls.some(([path,init])=>path==='/literature/content-maps/backfill'&&init?.method==='POST')).toBe(true)
 expect(state.notifications).toEqual(['已提交已有全文的图谱补齐请求，进度将自动更新'])
 expect(host.querySelector('.library-content-map-summary')?.textContent).not.toContain('已就绪 1')
})

it('does not offer a complete graph entry for a citation with no full text',async()=>{
 await mount()
 const row=Array.from(host.querySelectorAll('.bibliography-table tbody tr')).find(item=>item.textContent?.includes('Citation without full text'))!
 await act(async()=>{row.dispatchEvent(new MouseEvent('click',{bubbles:true}))})
 expect(host.querySelector('.bibliography-detail')?.textContent).toContain('Citation without full text')
 expect(host.querySelector('.bibliography-detail .library-content-map-button')).toBeNull()
})

it('reloads PDF entries and map progress when the knowledge-base upload reports changed files',async()=>{
 await mount()
 const before=vi.mocked(api).mock.calls.filter(([path])=>path==='/literature/items').length
 state.maps=[{asset:'reading/first.pdf',library:'workspace',status:'ready',stage:'ready'}]
 await act(async()=>{host.querySelector('[aria-label="文献库操作"]')!.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,key:'Enter'}));await Promise.resolve()})
 const menu=Array.from(document.querySelectorAll('[role="menuitem"]')).find(e=>e.textContent==='项目知识库') as HTMLElement;await act(async()=>menu.click())
 await click('知识库上传完成')
 expect(vi.mocked(api).mock.calls.filter(([path])=>path==='/literature/items').length).toBe(before+1)
 expect(host.querySelector('.library-content-map-summary')?.textContent).toContain('已就绪 1')
 expect(host.querySelector('.library-content-map-summary')?.textContent).not.toContain('处理中 1')
})
