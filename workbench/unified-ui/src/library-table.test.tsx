import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import {LibraryTable} from '@workbench/LibraryTable'
let root:Root,host:HTMLDivElement
beforeEach(()=>{(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host)})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})
it('sorts actual rows and exposes detail selection to the keyboard without expanding a row',async()=>{
 const selected=vi.fn(),rows=[{key:'b',metadata:{title:'B method',authors:['One','Two','Three'],year:2024},category:'reading'},{key:'a',metadata:{title:'A method',authors:['Four'],year:2020},category:'reading'}]
 await act(async()=>root.render(<LibraryTable rows={rows} selection="" checked={{}} pending={()=>undefined} onSelect={selected} onOpen={()=>{}} onDownload={()=>{}} onCheck={()=>{}} onContext={()=>{}}/>))
 expect(host.textContent).toContain('One 等');expect(host.textContent).not.toContain('Three')
 await act(async()=>(host.querySelector('[aria-label="按文献排序"]') as HTMLButtonElement).click())
 const first=host.querySelector('tbody tr')!;expect(first.textContent).toContain('A method')
 await act(async()=>first.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})))
 expect(selected).toHaveBeenCalledWith(rows[1]);expect(host.querySelectorAll('tbody tr')).toHaveLength(2)
})
