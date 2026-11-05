// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest'
import {Editor} from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import {Table,TableRow,TableCell,TableHeader} from '@tiptap/extension-table'
import {Mathematics} from '@tiptap/extension-mathematics'
import {TrackChangesExtension,getTrackedChanges} from 'tiptap-track-changes'
import {FigureImage} from './Manuscript'

let editors:Editor[]=[]
afterEach(()=>{editors.forEach(e=>e.destroy());editors=[]})
function editor(content:any={type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'原文'}]}]}){
 const e=new Editor({element:document.createElement('div'),extensions:[StarterKit,FigureImage,Table,TableRow,TableHeader,TableCell,Mathematics,TrackChangesExtension.configure({author:{id:'qa',name:'审阅者',color:'#36745b'},mode:'edit'})],content});editors.push(e);return e
}
describe('editable research manuscript',()=>{
 it('keeps insertions across JSON save/load and accepts them as editable text',()=>{
  const e=editor();e.commands.setSuggestMode();e.view.someProp('handleTextInput',handler=>handler(e.view,3,3,'新增',()=>e.state.tr));const saved=e.getJSON();expect(getTrackedChanges(e).some(c=>c.type==='insertion')).toBe(true)
  const restored=editor(saved);expect(getTrackedChanges(restored).some(c=>c.text.includes('新增'))).toBe(true);restored.commands.acceptAll();expect(getTrackedChanges(restored)).toHaveLength(0);expect(restored.getText()).toContain('原文新增')
 })
 it('rejects a recorded deletion and recovers its original content',()=>{
  const e=editor();e.commands.setSuggestMode();e.commands.setTextSelection({from:1,to:3});e.view.someProp('handleKeyDown',handler=>handler(e.view,new KeyboardEvent('keydown',{key:'Backspace'})));expect(getTrackedChanges(e).some(c=>c.type==='deletion')).toBe(true);e.commands.rejectAll();expect(e.getText()).toBe('原文');expect(getTrackedChanges(e)).toHaveLength(0)
 })
 it('loads native math, an editable table and a figure caption without changing their content',()=>{
  const doc={type:'doc',content:[{type:'blockMath',attrs:{latex:'D\\nabla^2c'}},{type:'table',content:[{type:'tableRow',content:[{type:'tableCell',content:[{type:'paragraph',content:[{type:'text',text:'D / m² s⁻¹'}]}]}]}]},{type:'image',attrs:{src:'/research/api/projects/qa/manuscript/assets/figure.png',alt:'原图',title:'图1 传输示意'}}]}
  const e=editor(doc);expect(e.getHTML()).toContain('<figcaption>图1 传输示意</figcaption>');expect(e.getHTML()).toContain('<table');expect(e.getJSON().content?.[0].attrs?.latex).toBe('D\\nabla^2c');expect(e.getText()).toContain('D / m² s⁻¹')
  const restored=editor(e.getJSON());expect(restored.getHTML()).toContain('图1 传输示意')
 })
 it('records Chinese IME composition input as an insertion',()=>{
  const e=editor();e.commands.setSuggestMode();e.view.dispatch(e.state.tr.insertText('数据',3).setMeta('composition',1));expect(getTrackedChanges(e).some(c=>c.type==='insertion'&&c.text==='数据')).toBe(true)
 })
})
