// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {LiteratureSearch} from './LiteratureSearch'
import {JournalPreview} from './JournalPreview'
import {api} from './api'

const rows=vi.hoisted(()=>[{key:'paper-a',title:'Verified transport study',doi:'10.1234/a',year:2025},{key:'paper-b',title:'Related transport method',doi:'10.1234/b',year:2024}])
vi.mock('./Reader',()=>({NativeReader:()=>null}))
vi.mock('./AuthorProfile',()=>({AuthorProfile:()=>null}))
vi.mock('./api',()=>({base:'/research/api',native:vi.fn(async()=>[]),projectPath:(_p:any,s:string)=>s,jsonBody:(v:any,method='POST')=>({method,body:JSON.stringify(v)}),api:vi.fn(async(path:string)=>{
 if(path==='/search/sources')return {papers:[{id:'crossref',name:'Crossref',configured:true}],web:{name:'Public search',configured:true}}
 if(path.startsWith('/literature/search?'))return {items:rows,source:'Crossref',page:1,has_more:false}
 if(path==='/literature/download-batch')return {queued:2,skipped:[],rejected:[]}
 if(path==='/knowledge/search')return {items:[{title:'Source page',excerpt:'Transport uses the original document text.',url:'/research/source'}],source:'项目全文关键词检索',documents_scanned:1,scope:'当前项目'}
 if(path==='/author-profile')return {name:'',affiliation:'',email:''}
 if(path==='/journals/search')return {generic_templates:[{id:'generic-zh',generic:true,name:'通用中文学术稿',template:{supported:true,columns:[1,2]}},{id:'generic-en',generic:true,name:'通用英文学术稿',template:{supported:true,columns:[1,2]}}]}
 return {}
})}))
let host:HTMLDivElement,root:Root
beforeEach(()=>{vi.clearAllMocks();(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
const mount=async(node:React.ReactNode)=>{await act(async()=>{root.render(node);await new Promise(r=>setTimeout(r,0))})}
it('selects paper records and sends a batch without asking the reader to type DOIs',async()=>{
 await mount(<LiteratureSearch project={{id:'test',config:{}} as any} initialQuery="transport" onClose={()=>{}} notify={()=>{}} onError={e=>{throw e}}/>)
 await act(async()=>{host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,0))})
 expect(host.querySelectorAll('.literature-online-results article')).toHaveLength(2)
 await act(async()=>{(host.querySelector('[aria-label="全选本页检索结果"]') as HTMLInputElement).click()})
 const download=Array.from(host.querySelectorAll('button')).find(b=>b.textContent?.includes('批量下载所选'))!
 expect(download.disabled).toBe(false)
 await act(async()=>{download.click();await new Promise(r=>setTimeout(r,0))})
 const sent=(vi.mocked(api).mock.calls.find(([path])=>path==='/literature/download-batch')?.[1] as RequestInit).body as string
 expect(JSON.parse(sent)).toEqual({entries:rows,folder:'reading'})
 expect(host.querySelector('[role="status"]')?.textContent).toContain('已排队 2 篇')
 expect(host.querySelector('[aria-label="下载文献标识"]')).toBeNull()
})
it('opens on a generic manuscript even when a project previously targeted a journal',async()=>{
 await mount(<JournalPreview project={{id:'test',config:{target_journal:{name:'旧期刊'}}} as any} onClose={()=>{}} notify={()=>{}} onError={e=>{throw e}}/>)
 expect(host.querySelector('.journal-confirm-panel h2')?.textContent).toBe('通用中文学术稿')
 expect((host.querySelector('[aria-label="搜索目标期刊"]') as HTMLInputElement).value).toBe('')
 expect(host.textContent).toContain('联系邮箱尚未保存')
 expect(host.querySelector('.preview-author-summary time')?.textContent).toContain('预览日期')
 expect(host.querySelector('[aria-pressed="true"]')?.textContent).toContain('单栏')
})
it('searches source passages in project scope without sending them to the web or download queue',async()=>{
 await mount(<LiteratureSearch project={{id:'test',config:{knowledge_bases:[]}} as any} initialQuery="transport" onClose={()=>{}} notify={()=>{}} onError={e=>{throw e}}/>)
 await act(async()=>{Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='项目知识库')!.click();await new Promise(r=>setTimeout(r,0))})
 await act(async()=>{host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,0))})
 expect(host.querySelector('.literature-online-results')?.textContent).toContain('original document text')
 const sent=(vi.mocked(api).mock.calls.find(([path])=>path==='/knowledge/search')?.[1] as RequestInit).body as string
 expect(JSON.parse(sent)).toEqual({query:'transport',mode:'fulltext-keyword',knowledge_base:'',limit:10})
 expect(host.querySelector('.literature-batch-actions')).toBeNull()
})
