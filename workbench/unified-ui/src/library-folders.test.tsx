import React,{act} from 'react'
import {createRoot,Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {LibraryPanel} from '@workbench/Library'

const state=vi.hoisted(()=>({organization:{revision:1,assignments:{},folders:[{id:'reaction',name:'反应传输',kind:'topic'},{id:'inverse',name:'贝叶斯反演',kind:'topic'}],memberships:{'workspace/reading/a.pdf':['reaction']}}}))
vi.mock('@workbench/KnowledgeSources',()=>({KnowledgeSources:()=>null}))
vi.mock('@workbench/Reader',()=>({NativeReader:()=>null}))
vi.mock('./ThemeSelect',()=>({default:({children,value,onChange,...props}:any)=><select {...props} value={value} onChange={onChange}>{children}</select>}))
vi.mock('@workbench/api',()=>({base:'',projectPath:(_p:any,path:string)=>path,prettySize:String,jsonBody:(value:any,method='POST')=>({method,body:JSON.stringify(value)}),api:vi.fn(async(path:string,options?:any)=>{
 if(path==='/literature/items')return {references:[],files:[{library:'workspace',name:'reading/a.pdf',metadata:{title:'反应模型'}},{library:'workspace',name:'reading/b.pdf',metadata:{title:'待整理资料'}}]}
 if(path==='/literature/folders')return state.organization
 return {}
})}))
let host:HTMLDivElement,root:Root
beforeEach(()=>{(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
const mount=async()=>{await act(async()=>{root.render(<LibraryPanel project={{id:'project',name:'研究',config:{}} as any} version={0} onError={e=>{throw e}} notify={()=>{}} onUpdate={()=>{}}/>);await new Promise(r=>setTimeout(r,0))})}
it('shows saved project folders and filters actual library memberships',async()=>{
 await mount();const select=host.querySelector('[aria-label="主题文件夹"]') as HTMLSelectElement
 expect(select.textContent).toContain('反应传输');expect(select.textContent).toContain('贝叶斯反演')
 await act(async()=>{select.value='reaction';select.dispatchEvent(new Event('change',{bubbles:true}))})
 expect(host.querySelectorAll('.bibliography-table tbody tr')).toHaveLength(1)
 expect(host.querySelector('.bibliography-table')?.textContent).toContain('反应模型')
 expect(host.querySelector('.bibliography-table')?.textContent).not.toContain('待整理资料')
})
it('keeps the unclassified collection visible without inventing a topic',async()=>{
 await mount();const select=host.querySelector('[aria-label="主题文件夹"]') as HTMLSelectElement
 await act(async()=>{select.value='__unfiled__';select.dispatchEvent(new Event('change',{bubbles:true}))})
 expect(host.querySelectorAll('.bibliography-table tbody tr')).toHaveLength(1)
 expect(host.querySelector('.bibliography-table')?.textContent).toContain('待整理资料')
})
