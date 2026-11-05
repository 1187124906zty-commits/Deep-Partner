import {Extension,Node,mergeAttributes} from '@tiptap/core'
import {Plugin,PluginKey} from '@tiptap/pm/state'
import {Decoration,DecorationSet} from '@tiptap/pm/view'
import Image from '@tiptap/extension-image'

export const pendingEditsKey=new PluginKey('pendingEdits')
export const PendingEdits=Extension.create({name:'pendingEdits',addProseMirrorPlugins(){return [new Plugin({key:pendingEditsKey,state:{init:()=>DecorationSet.empty,apply(tr,previous){if(tr.getMeta(pendingEditsKey)==='clear')return DecorationSet.empty;let next=previous.map(tr.mapping,tr.doc);if(!tr.docChanged||tr.getMeta('preventUpdate'))return next;const added:Decoration[]=[];tr.mapping.maps.forEach((map,index)=>{map.forEach((_oldStart,_oldEnd,start,end)=>{const rest=tr.mapping.slice(index+1);const a=rest.map(start,1),b=rest.map(end,-1);if(b>a)added.push(Decoration.inline(Math.max(0,a),Math.min(tr.doc.content.size,b),{class:'pending-edit'}))})});const ranges=next.add(tr.doc,added).find().sort((a,b)=>a.from-b.from);const merged:{from:number;to:number}[]=[];for(const range of ranges){const last=merged[merged.length-1];if(last&&range.from<=last.to)last.to=Math.max(last.to,range.to);else merged.push({from:range.from,to:range.to})}return DecorationSet.create(tr.doc,merged.filter(r=>r.to>r.from).map(r=>Decoration.inline(r.from,r.to,{class:'pending-edit'})))}},props:{decorations:state=>pendingEditsKey.getState(state)}})]}})
export function clearPending(editor:any){editor?.view.dispatch(editor.state.tr.setMeta(pendingEditsKey,'clear'))}

export const Citation=Node.create({name:'citation',group:'inline',inline:true,atom:true,selectable:true,
 addAttributes(){return {refId:{default:''},number:{default:1}}},
 parseHTML(){return [{tag:'span[data-reference-id]',getAttrs:element=>({refId:element.getAttribute('data-reference-id'),number:Number(element.getAttribute('data-reference-number'))})}]},
 renderHTML({HTMLAttributes}){return ['span',{'data-reference-id':HTMLAttributes.refId,'data-reference-number':HTMLAttributes.number,class:'citation-anchor',role:'button',tabindex:0},'['+HTMLAttributes.number+']']},
 renderText({node}){return '['+node.attrs.number+']'}})

export const FigureImage=Image.extend({
 addAttributes(){return {...this.parent?.(),width:{default:90,parseHTML:e=>Number(e.getAttribute('data-width')||90),renderHTML:a=>({'data-width':a.width})},align:{default:'center',parseHTML:e=>e.getAttribute('data-align')||'center',renderHTML:a=>({'data-align':a.align})},captionPosition:{default:'bottom',parseHTML:e=>e.getAttribute('data-caption-position')||'bottom',renderHTML:a=>({'data-caption-position':a.captionPosition})}}},
 renderHTML({HTMLAttributes}){const {width,align,captionPosition}=HTMLAttributes;return ['figure',{'data-type':'manuscript-image',style:'width:'+Math.max(10,Math.min(100,Number(HTMLAttributes['data-width']||width||90)))+'%;margin-left:'+(HTMLAttributes['data-align']==='left'?'0':'auto')+';margin-right:'+(HTMLAttributes['data-align']==='right'?'0':'auto'),class:HTMLAttributes['data-caption-position']==='top'?'caption-top':''},['img',mergeAttributes(HTMLAttributes,{style:'width:100%'})],...(HTMLAttributes.title?([['figcaption',{},HTMLAttributes.title]] as any):[])] as any}
})
