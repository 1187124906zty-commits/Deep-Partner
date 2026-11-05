import {InlineMath,BlockMath} from '@tiptap/extension-mathematics'
import katex from 'katex'

/** Format a render copy; the source LaTeX remains the editable document value. */
export function academicMath(value:string){
 const labels=new Set(['obs','ref','diff','ini','init','out','phys','min','max','full','data','env'])
 const clean=value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g,'').replace(/([_^])\{([A-Za-z]+(?:,[A-Za-z]+)*)\}/g,(_source,side:string,body:string)=>side+'{'+body.split(',').map(v=>labels.has(v)?'\\mathrm{'+v+'}':v).join(',')+'}').replace(/(?<!\\mathrm)\{RMSE\}/g,'\\mathrm{RMSE}').replace(/\\text\{(sin|cos|tan|tanh|sinh|cosh|exp|ln|log|max|min)\}/g,(_source,name:string)=>'\\'+name+' ').replace(/(?<!\\operatorname)\{arg\s*\\,\s*min\}/g,'{\\operatorname{arg\\,min}}')
 const shown=clean.replace(/\\mathbf\b/g,'\\boldsymbol').replace(/\\begin\{matrix\}([\s\S]*?)\\end\{matrix\}/g,(source,body:string)=>{
  if(/\\begin\{/.test(body))return source
  const rows=body.split(/\\\\/).map(r=>r.trim()).filter(Boolean),cells=rows.map(row=>row.split('&'))
  if(cells.every(row=>row.length===2&&row[1].trim().startsWith('=')))return '\\begin{array}{l}'+cells.map(row=>'\\displaystyle '+row.join(' ')).join('\\\\')+'\\end{array}'
  if(cells.every(row=>row.length===2&&/^\s*\\(?:text|mathrm)\{/.test(row[1])))return '\\begin{array}{ll}'+rows.map(row=>'\\displaystyle '+row).join('\\\\')+'\\end{array}'
  return source
 })
 return /\\begin\{(?:array|matrix|cases|aligned)\}/.test(shown)?'{\\def\\arraystretch{1.3}'+shown+'}':shown
}

function nodeView(extension:any,block:boolean){
 return ({node,getPos}:any)=>{
  let current=node
  const wrapper=document.createElement(block?'div':'span')
  wrapper.className='tiptap-mathematics-render'+(block?' tiptap-mathematics-render--block':' tiptap-mathematics-render--inline')
  wrapper.dataset.type=block?'block-math':'inline-math'
  wrapper.contentEditable='false'
  const render=()=>{wrapper.dataset.latex=current.attrs.latex;katex.render(academicMath(current.attrs.latex),wrapper,{...extension.options.katexOptions,displayMode:block,throwOnError:false,trust:false})}
  const click=(event:Event)=>{if(!extension.options.onClick)return;event.preventDefault();event.stopPropagation();const pos=getPos();if(typeof pos==='number')extension.options.onClick(current,pos)}
  wrapper.addEventListener('click',click);render()
  return {dom:wrapper,update(next:any){if(next.type!==current.type)return false;current=next;render();return true},destroy(){wrapper.removeEventListener('click',click)}}
 }
}

export const AcademicInlineMath=InlineMath.extend({addNodeView(){return nodeView(this,false)}})
export const AcademicBlockMath=BlockMath.extend({addNodeView(){return nodeView(this,true)}})
