import {useEffect,useRef} from 'react'
import {EditorContent,useEditor} from '@tiptap/react'
import type {JSONContent} from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import {TableRow,TableHeader,TableCell} from '@tiptap/extension-table'
import {AcademicTable} from './AcademicTable'
import {AcademicInlineMath,AcademicBlockMath} from './academicMath'
import Subscript from '@tiptap/extension-subscript'
import Superscript from '@tiptap/extension-superscript'
import {RefreshCw} from 'lucide-react'
import {PaperTitle} from './ui'
import {Citation,FigureImage,PendingEdits,clearPending} from './manuscriptExtensions'
import {AnnotationMark} from './annotationMark'

export type Translation={title:string;content:JSONContent;comments:any[];language:string;template:string;generation_id?:string;stale?:boolean;updated?:string;source_revision:number;origin?:string}
export function TranslationPane({value,onChange,onTranslate,onScroll,template,savedTick=0,onCitation,onContextMenu}:{value:Translation;author:any;onChange:(v:Translation)=>void;onTranslate:()=>void;onScroll:(e:React.UIEvent<HTMLDivElement>)=>void;template:any;savedTick?:number;onCitation?:(id:string)=>void;onContextMenu?:(event:React.MouseEvent,editor:any)=>void}){
 const latest=useRef(value);latest.current=value;const changed=useRef(onChange);changed.current=onChange;const savedTitle=useRef(value.title)
 const editor=useEditor({extensions:[StarterKit,Citation,PendingEdits,AnnotationMark,FigureImage,AcademicTable.configure({resizable:true}),TableRow,TableHeader,TableCell,Subscript,Superscript,AcademicInlineMath,AcademicBlockMath],content:value.content,immediatelyRender:false,editorProps:{attributes:{class:'manuscript-editor','aria-label':'译文正文',spellcheck:'false'},handleClickOn:(_v,_p,n)=>{if(n.type.name==='citation'){onCitation?.(n.attrs.refId);return true}return false}},onUpdate:({editor})=>changed.current({...latest.current,content:editor.getJSON()})})
 useEffect(()=>{editor?.chain().setContent(value.content,{emitUpdate:false}).setMeta('addToHistory',false).run();clearPending(editor);savedTitle.current=value.title},[editor,value.generation_id])
 useEffect(()=>{clearPending(editor);savedTitle.current=value.title},[savedTick])
 if(!editor)return null
 return <section className="translation-pane quiet-translation"><header className="quiet-language-label"><span>{value.language==='en'?'English':'中文译文'}</span>{value.origin==='preset'&&<small>预置示例</small>}<div className="toolbar-spacer"/>{value.stale&&<button title="根据当前原文重新翻译" onClick={onTranslate}><RefreshCw size={12}/>更新译文</button>}</header><div className="translation-scroll" onScroll={onScroll} onContextMenu={e=>onContextMenu?.(e,editor)} data-scroll-pane="translation"><article className={'paper-sheet template-'+value.template} style={{'--paper-title-size':(template?.title_size||20)+'pt','--paper-title-weight':template?.title_bold===false?400:700,'--paper-heading-size':(template?.heading||14)+'pt','--paper-font':template?.font,'--paper-cjk':template?.font_cjk||'SimSun','--heading-cjk':template?.heading_cjk||'SimHei','--paper-size':(template?.size||11)+'pt','--paper-leading':template?.line_pt?template.line_pt+'pt':template?.leading||1.5} as React.CSSProperties}><div className={value.title!==savedTitle.current?'pending-title':''}><PaperTitle typography={value.template+JSON.stringify(template)} label="译稿标题" value={value.title} onChange={title=>changed.current({...latest.current,title})}/></div><EditorContent editor={editor}/></article></div></section>
}
