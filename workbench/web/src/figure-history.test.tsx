// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {FigureCanvas} from './FigureCanvas'

const runtime=vi.hoisted(()=>({scene:null as any,previews:[] as any[]}))
vi.mock('./api',()=>({base:'',projectPath:(_project:any,path:string)=>path,jsonBody:(value:any)=>({body:JSON.stringify(value)}),api:vi.fn(async(path:string,options:any)=>{
 if(path==='/figure/preview'){
  const payload=JSON.parse(options.body);runtime.previews.push(payload.changes)
  return {...runtime.scene,layout:payload.changes.layout||runtime.scene.layout,figure:{...runtime.scene.figure,...payload.changes.figure}}
 }
 return {messages:[]}
})}))

let host:HTMLDivElement,root:Root
const button=(label:string)=>{const node=Array.from(host.querySelectorAll('button')).find(node=>node.getAttribute('aria-label')===label||node.textContent===label);if(!node)throw Error('Missing button '+label);return node}
const click=async(label:string)=>{await act(async()=>{button(label).click()})}
const key=()=>host.querySelector('.figure-editing-frame')!.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',shiftKey:true,bubbles:true}))
const flush=async()=>{await act(async()=>{await vi.advanceTimersByTimeAsync(250)})}
const latestX=()=>runtime.previews.at(-1)?.layout?.cells['axes-0'].x??runtime.scene.layout.cells['axes-0'].x

beforeEach(async()=>{
 vi.useFakeTimers();(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
 vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
 runtime.previews=[];runtime.scene={revision:1,svg:'<svg viewBox="0 0 432 288"><g id="wb-axes-0"><path d="M1,1 L20,20"/></g></svg>',figure:{width:6,height:4,dpi:300,font_family:'Arial',font_size:10},fonts:['Arial'],colormaps:['viridis'],layout:{version:2,rows:1,cols:1,gap_x:0,gap_y:0,cells:{'axes-0':{row:0,col:0,rect:[0,0,1,1],x:.15,y:.15,width:.7,height:.7}}},objects:[{id:'axes-0',kind:'axes',label:'子图 1',parent:'',role:'subplot',bounds:[.15,.15,.7,.7],draggable:true,properties:{x:.15,y:.15,width:.7,height:.7,x_min:0,x_max:1,y_min:0,y_max:1,x_scale:'linear',y_scale:'linear',aspect:'auto',facecolor:'#ffffff',spines:{},matplotlib:{}},schema:[]}]}
 host=document.createElement('div');document.body.append(host);root=createRoot(host)
 await act(async()=>{root.render(<React.StrictMode><FigureCanvas project={{id:'project'} as any} path="results/figure.png" initial={runtime.scene} onClose={()=>{}} onError={e=>{throw e}} notify={()=>{}}/></React.StrictMode>)})
 await click('布局');await click('选择子图 1');runtime.previews=[]
})
afterEach(async()=>{await act(async()=>{root.unmount()});host.remove();vi.clearAllTimers();vi.useRealTimers();vi.unstubAllGlobals()})

describe('figure history during batched input',()=>{
 it('restores the saved state when another UI update precedes a nudge',async()=>{
  await act(async()=>{button('布局').click();key()});await flush()
  expect(latestX()).toBeCloseTo(.17)
  await click('撤销');await flush()
  expect(latestX()).toBeCloseTo(.15)
  expect(button('保存图形').disabled).toBe(true)
 })
 it('accumulates rapid nudges and restores each undo and redo state',async()=>{
  await act(async()=>{key();key()});await flush()
  expect(latestX()).toBeCloseTo(.19)
  await click('撤销');await flush();expect(latestX()).toBeCloseTo(.17)
  await click('重做');await flush();expect(latestX()).toBeCloseTo(.19)
  await click('撤销');await flush();await click('撤销');await flush()
  expect(latestX()).toBeCloseTo(.15)
  expect(button('保存图形').disabled).toBe(true)
 })
})
