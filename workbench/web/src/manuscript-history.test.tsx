// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {ManuscriptPanel} from './Manuscript'

const backend=vi.hoisted(()=>({document:null as any}))
vi.mock('./api',()=>({base:'',projectPath:(_p:any,s:string)=>s,jsonBody:(v:any,method='POST')=>({method,body:JSON.stringify(v)}),api:vi.fn(async(path:string,options:any)=>{
 if(path==='/manuscript-templates')return {templates:[{id:'chinese',size:11,title_size:22}]}
 if(path==='/manuscript'&&options?.method==='PUT'){backend.document={...JSON.parse(options.body),revision:backend.document.revision+1};return structuredClone(backend.document)}
 if(path==='/manuscript')return structuredClone(backend.document)
 return {items:[],messages:[]}
})}))
let host:HTMLDivElement,root:Root,editor:any
beforeEach(async()=>{
 (globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}});localStorage.clear()
 backend.document={title:'Fixture manuscript',template:'chinese',revision:4,comments:[],content:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'First sentence. Second sentence.'}]},{type:'paragraph',content:[{type:'text',text:'This paragraph must remain intact.'}]}]}}
 host=document.createElement('div');document.body.append(host);root=createRoot(host)
 await act(async()=>{root.render(<ManuscriptPanel project={{id:'fixture'} as any} author={{id:'fixture'}} onError={e=>{throw e}} notify={()=>{}} version={0} registerSave={()=>{}}/>);await new Promise(resolve=>setTimeout(resolve,50))})
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,50))});editor=(host.querySelector('[contenteditable=true]') as any)?.editor
 expect(editor).toBeTruthy()
})
afterEach(async()=>{await act(async()=>{root.unmount()});host.remove();vi.unstubAllGlobals();localStorage.clear()})

describe('author manuscript history',()=>{
 it('does not make loading the entire paper an undoable edit',()=>{expect(editor.can().undo()).toBe(false)})
 it('deletes one sentence and recovers it with undo after saving, without touching other paragraphs',async()=>{
  const original=editor.getText()
  await act(async()=>{editor.chain().setTextSelection({from:1,to:17}).deleteSelection().run()})
  expect(editor.getText()).toContain('This paragraph must remain intact.');expect(editor.getText()).not.toContain('First sentence.')
  const save=Array.from(host.querySelectorAll('button')).find(b=>b.textContent?.includes('保存修改'))!
  await act(async()=>{save.click()})
  await act(async()=>{editor.chain().undo().run()})
  expect(editor.getText()).toBe(original)
  expect(host.querySelector('[aria-label="撤销论文编辑"]')).toBeTruthy()
 })
})
