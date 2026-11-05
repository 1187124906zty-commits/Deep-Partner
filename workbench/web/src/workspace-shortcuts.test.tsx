// @vitest-environment jsdom
import React,{act,useRef} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {useWorkspaceShortcuts} from './workspaceShortcuts'

let root:Root|undefined,host:HTMLDivElement
afterEach(async()=>{if(root)await act(async()=>root!.unmount());host?.remove();root=undefined})
async function surface(){
 (globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
 const actions={zoom:vi.fn(),reset:vi.fn(),save:vi.fn(),undo:vi.fn(),redo:vi.fn(),pan:vi.fn(),find:vi.fn()}
 function Fixture(){const ref=useRef<HTMLDivElement>(null);useWorkspaceShortcuts(ref,actions);return <div ref={ref} tabIndex={0}><input aria-label="text"/></div>}
 host=document.createElement('div');document.body.append(host);root=createRoot(host);await act(async()=>{root!.render(<Fixture/>)})
 return {element:host.firstElementChild!,actions,input:host.querySelector('input')!}
}
describe('workspace keyboard and wheel conventions',()=>{
 it('zooms on Ctrl+wheel while leaving an ordinary wheel event available for scrolling',async()=>{
  const {element,actions}=await surface();const ordinary=new WheelEvent('wheel',{deltaY:100,bubbles:true,cancelable:true});element.dispatchEvent(ordinary);expect(actions.zoom).not.toHaveBeenCalled();expect(ordinary.defaultPrevented).toBe(false)
  const controlled=new WheelEvent('wheel',{deltaY:100,ctrlKey:true,bubbles:true,cancelable:true});element.dispatchEvent(controlled);expect(controlled.defaultPrevented).toBe(true);expect(actions.zoom).toHaveBeenCalledOnce();expect(actions.zoom.mock.calls[0][0]).toBeLessThan(1)
 })
 it('preserves text undo and supports canvas undo, redo, save, fit, search and temporary panning',async()=>{
  const {element,actions,input}=await surface();const send=(target:Element,key:string,extra={})=>target.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,ctrlKey:true,...extra}))
  send(input,'z');expect(actions.undo).not.toHaveBeenCalled();send(element,'z');expect(actions.undo).toHaveBeenCalledOnce();send(element,'z',{shiftKey:true});send(element,'y');expect(actions.redo).toHaveBeenCalledTimes(2)
  send(input,'s');expect(actions.save).toHaveBeenCalledOnce();send(element,'0');expect(actions.reset).toHaveBeenCalledOnce();send(element,'f');expect(actions.find).toHaveBeenCalledOnce()
  send(element,' ',{ctrlKey:false,code:'Space'});expect(actions.pan).toHaveBeenLastCalledWith(true);window.dispatchEvent(new KeyboardEvent('keyup',{key:' ',code:'Space'}));expect(actions.pan).toHaveBeenLastCalledWith(false)
 })
})
