import {Table} from '@tiptap/extension-table'

export const AcademicTable=Table.extend({addAttributes(){return {...this.parent?.(),equation:{default:false,parseHTML:(e:HTMLElement)=>e.dataset.equation==='true',renderHTML:(a:any)=>a.equation?{'data-equation':'true'}:{}}}}})
