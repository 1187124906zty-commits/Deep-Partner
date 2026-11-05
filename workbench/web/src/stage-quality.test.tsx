// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {StageQuality} from './StageQuality'

const backend=vi.hoisted(()=>({review:null as any,calls:[] as any[]}))
vi.mock('./api',()=>({projectPath:(_p:any,s:string)=>s,jsonBody:(v:any)=>({method:'POST',body:JSON.stringify(v)}),api:vi.fn(async(path:string,options:any)=>{
 if(path.endsWith('/override')){backend.calls.push({path,body:JSON.parse(options.body)});return {...backend.review,decision:'author_override',can_proceed:true}}
 return {items:[structuredClone(backend.review)]}
})}))
let host:HTMLDivElement,root:Root
beforeEach(()=>{
 (globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
 backend.review={review_id:'stored-review',decision:'needs_revision',can_proceed:false,score_percent:50,dimensions:[],hard_checks:[],issues:[],stale:false}
 backend.calls=[];host=document.createElement('div');document.body.append(host);root=createRoot(host)
})
afterEach(async()=>{await act(async()=>{root.unmount()});host.remove()})
async function render(){await act(async()=>{root.render(<StageQuality project={{id:'fixture'} as any} onError={e=>{throw e}}/>);await Promise.resolve()})}

it('records an author decision against a loaded historical review without paying for another evaluation',async()=>{
 await render()
 const reason=host.querySelector<HTMLTextAreaElement>('[aria-label="带偏差继续的原因"]')!
 await act(async()=>{
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(reason,'接受当前限制用于内部讨论')
  reason.dispatchEvent(new Event('input',{bubbles:true}))
  host.querySelector<HTMLInputElement>('input[type="checkbox"]')!.click()
 })
 const button=Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='记录并继续')!
 expect(button.disabled).toBe(false)
 await act(async()=>{button.click();await Promise.resolve()})
 expect(backend.calls).toHaveLength(1)
 expect(backend.calls[0].path).toBe('/quality/reviews/stored-review/override')
 expect(backend.calls[0].body).toMatchObject({confirmed:true,reason:'接受当前限制用于内部讨论'})
})

it('shows an obsolete passing review as stale and requires re-review before an author decision',async()=>{
 backend.review={...backend.review,stale:true,decision:'passed',score_percent:100}
 await render()
 expect(host.textContent).toContain('产物、来源或规则已更新，需重新评审')
 expect(host.textContent).not.toContain('满足当前阶段要求')
 expect(host.querySelector('[aria-label="带偏差继续的原因"]')).toBeNull()
})
