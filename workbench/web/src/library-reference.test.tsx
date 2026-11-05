// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {LibraryPanel} from './Library'
import {ReferencePanel} from './ReferencePanel'

const data=vi.hoisted(()=>({references:[{id:'ref-1',number:1,title:'Original hydraulic model',authors:['M. van Genuchten'],year:1980,venue:'Soil Science Society of America Journal',doi:'10.1000/first',attachment:{library:'workspace',asset:'references/first.pdf'}},{id:'ref-2',number:2,title:'Recent moisture study',authors:['A. Researcher'],year:2025,venue:'Cement and Concrete Research',doi:'10.1000/second'}],files:[{library:'workspace',name:'references/first.pdf',size:600},{library:'workspace',name:'reading/unmatched.pdf',size:800}]}))
vi.mock('./Reader',()=>({NativeReader:()=>null}))
vi.mock('./JournalPreview',()=>({JournalPreview:()=>null}))
vi.mock('./api',()=>({base:'',projectPath:(_p:any,s:string)=>s,jsonBody:(v:any,method='POST')=>({method,body:JSON.stringify(v)}),prettySize:(n:number)=>String(n),api:vi.fn(async(path:string)=>{
 if(path==='/literature/items')return data
 if(path==='/literature/folders')return {assignments:{}}
 if(path==='/references')return {items:data.references}
 if(path.includes('/related'))return {items:[],status:'ready',source:'Crossref',providers:[{id:'crossref',name:'Crossref',configured:true}],min_year:2022}
 return {online:false}
})}))
let host:HTMLDivElement,root:Root
beforeEach(()=>{(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
const mount=async(component:React.ReactNode)=>{await act(async()=>{root.render(component);await new Promise(r=>setTimeout(r,0))})}

it('shows bibliography and unattached PDFs together without duplicating the attached paper',async()=>{
 await mount(<LibraryPanel project={{id:'fixture',config:{}} as any} version={0} onError={e=>{throw e}} notify={()=>{}} onUpdate={()=>{}}/>)
 expect(host.querySelectorAll('.bibliography-table tbody tr')).toHaveLength(3)
 expect(host.querySelector('.bibliography-count')?.textContent).toContain('3 篇文献')
 expect(host.querySelector('.bibliography-detail')?.textContent).toContain('Original hydraulic model')
 const input=host.querySelector('[aria-label="搜索文献"]') as HTMLInputElement
 await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'Researcher');input.dispatchEvent(new Event('input',{bubbles:true}))})
 expect(host.querySelectorAll('.bibliography-table tbody tr')).toHaveLength(1)
 expect(host.querySelector('.bibliography-table')?.textContent).toContain('Recent moisture study')
})

it('renders complete citation fields without cramped read-only form controls or a duplicate DOI search',async()=>{
 await mount(<ReferencePanel project={{id:'fixture'} as any} reference={data.references[0]} onClose={()=>{}} onChanged={()=>{}} onError={e=>{throw e}}/>)
 expect(host.querySelector('.reference-details textarea')).toBeNull()
 expect(host.querySelector('.reference-metadata')?.textContent).toContain('Soil Science Society of America Journal')
 expect(host.querySelector('[aria-label="检索引用"]')).toBeNull()
 expect((host.querySelector('[aria-label="相关研究年份"]') as HTMLSelectElement).value).toBe('5')
 expect(host.querySelector('.related-source')?.textContent).toContain('Crossref')
 const replace=Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='替换文献')!
 await act(async()=>replace.click())
 expect(host.querySelector('[aria-label="检索引用"]')).toBeTruthy()
})
