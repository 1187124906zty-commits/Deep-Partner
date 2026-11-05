// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {ImageInspector} from './ImageInspector'

const backend=vi.hoisted(()=>({saves:[] as any[],finish:undefined as undefined|(()=>void),delay:false}))
vi.mock('./api',()=>({base:'',prettySize:(n:number)=>String(n),projectPath:(_p:any,s:string)=>s,jsonBody:(v:any)=>({body:JSON.stringify(v)}),api:vi.fn(async(path:string,options:any)=>{
 if(path.startsWith('/figure?'))return {ready:false}
 if(path.startsWith('/image-context?'))return {modified:1,references:[],usages:[],width:1000,height:600}
 if(path==='/image/save'){
  backend.saves.push(JSON.parse(options.body))
  if(backend.delay)await new Promise<void>(resolve=>{backend.finish=resolve})
  return {modified:2}
 }
 return {messages:[]}
})}))

let host:HTMLDivElement,root:Root,closed:ReturnType<typeof vi.fn>,errors:ReturnType<typeof vi.fn>,stroke:ReturnType<typeof vi.fn>
const click=async(label:string)=>{const button=host.querySelector<HTMLButtonElement>('[aria-label="'+label+'"]');expect(button).toBeTruthy();await act(async()=>{button!.click()})}
const draw=async()=>{
 const canvas=host.querySelector('canvas')!;expect(canvas).toBeTruthy()
 await act(async()=>{
  canvas.dispatchEvent(new MouseEvent('pointerdown',{clientX:80,clientY:80,button:0,buttons:1,bubbles:true}))
  canvas.dispatchEvent(new MouseEvent('pointermove',{clientX:180,clientY:130,button:0,buttons:1,bubbles:true}))
  canvas.dispatchEvent(new MouseEvent('pointerup',{clientX:180,clientY:130,button:0,buttons:0,bubbles:true}))
 })
}

beforeEach(async()=>{
 vi.useFakeTimers();(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;backend.saves=[];backend.finish=undefined;backend.delay=false;closed=vi.fn();errors=vi.fn();stroke=vi.fn()
 vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
 vi.stubGlobal('Image',class{width=1000;height=600;onload:(()=>void)|null=null;onerror:(()=>void)|null=null;set src(_v:string){Promise.resolve().then(()=>this.onload?.())}})
 const context=new Proxy({stroke}, {get:(target:any,key:string)=>key in target?target[key]:(()=>{})})
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(context as any)
 vi.spyOn(HTMLCanvasElement.prototype,'toDataURL').mockReturnValue('data:image/png;base64,aW1hZ2U=')
 HTMLCanvasElement.prototype.setPointerCapture=()=>{}
 host=document.createElement('div');document.body.append(host);root=createRoot(host)
 await act(async()=>{root.render(<React.StrictMode><ImageInspector project={{id:'fixture'} as any} path="data/fixture.png" onClose={closed} onError={errors} notify={()=>{}}/></React.StrictMode>);await Promise.resolve()})
 await act(async()=>{await Promise.resolve()})
})
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.restoreAllMocks();vi.clearAllTimers();vi.useRealTimers();vi.unstubAllGlobals()})

describe('raster editing regressions',()=>{
 it.each(['画笔','箭头标记'])('%s finishes its drawing without unmounting the image canvas',async(tool)=>{
  await click(tool);await draw()
  expect(host.querySelector('[aria-label="图像画布"]')).toBeTruthy();expect(stroke).toHaveBeenCalled();expect(errors).not.toHaveBeenCalled()
  await click('撤销标记');expect(host.querySelector('[aria-label="图像画布"]')).toBeTruthy()
 })
 it('saves a drawing before closing even when the autosave delay has not elapsed',async()=>{
  backend.delay=true;await click('箭头标记');await draw();await click('关闭图片')
  expect(backend.saves).toHaveLength(1);expect(backend.saves[0].expected_modified).toBe(1);expect(closed).not.toHaveBeenCalled()
  await act(async()=>backend.finish?.());expect(closed).toHaveBeenCalledOnce();expect(errors).not.toHaveBeenCalled()
 })
})
