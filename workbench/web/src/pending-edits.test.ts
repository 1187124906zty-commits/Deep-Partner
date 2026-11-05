// @vitest-environment jsdom
import {afterEach,expect,it} from 'vitest'
import {Editor} from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import {Citation,FigureImage,PendingEdits,pendingEditsKey,clearPending} from './manuscriptExtensions'
let editor:Editor
afterEach(()=>editor?.destroy())
it('shows unsaved insertion in red without serializing any color or review markup',()=>{
 editor=new Editor({element:document.createElement('div'),extensions:[StarterKit,PendingEdits],content:'<p>原文</p>'})
 clearPending(editor);editor.commands.insertContentAt(3,'新');editor.commands.insertContentAt(4,'文');editor.commands.insertContentAt(5,'字')
 expect(pendingEditsKey.getState(editor.state).find()).toHaveLength(1)
 expect(editor.view.dom.querySelector('.pending-edit')?.textContent).toBe('新文字')
 expect(JSON.stringify(editor.getJSON())).not.toMatch(/pending-edit|color|insertion/)
 const before=editor.getJSON();clearPending(editor)
 expect(editor.view.dom.querySelector('.pending-edit')).toBeNull();expect(editor.getJSON()).toEqual(before)
})
it('preserves clickable citation identity and image width across editor save and reload',()=>{
 editor=new Editor({element:document.createElement('div'),extensions:[StarterKit,Citation,FigureImage],content:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'依据'},{type:'citation',attrs:{refId:'ref-1',number:1}}]},{type:'image',attrs:{src:'/figure.png',width:62,align:'right',title:'原图'}}]}})
 expect(editor.getText()).toContain('[1]');expect(editor.getHTML()).toContain('data-reference-id="ref-1"');expect(editor.getHTML()).toContain('width: 62%')
})
