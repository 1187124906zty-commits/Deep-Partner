import {useEffect,useRef,useState} from 'react'
import {ChevronLeft,ChevronRight,Minus,Plus} from 'lucide-react'
export function PdfPreview({url,title}:{url:string;title:string}){
 const container=useRef<HTMLDivElement>(null),viewer=useRef<any>(undefined);const [pages,setPages]=useState(0),[page,setPage]=useState(1),[error,setError]=useState('')
 useEffect(()=>{let disposed=false,task:any,instance:any
  void (async()=>{try{const assets='/research/api/reader-assets/assets/';const core=await import(/* @vite-ignore */ assets+'pdf-B0s6D7Gr.js');core.GlobalWorkerOptions.workerSrc=assets+'pdf.worker.min-Dswkl-cV.mjs';const ui=await import(/* @vite-ignore */ assets+'pdf_viewer-B1341VgR.js');if(disposed||!container.current)return
   if(!document.getElementById('workbench-pdf-css')){const style=document.createElement('link');style.id='workbench-pdf-css';style.rel='stylesheet';style.href=assets+'pdf_viewer-DM_hRQ9e.css';document.head.append(style)}
   const bus=new ui.E(),links=new ui.P({eventBus:bus,externalLinkTarget:2});container.current.replaceChildren();const element=document.createElement('div');element.className='pdfViewer';container.current.append(element)
   instance=new ui.b({container:container.current,viewer:element,eventBus:bus,linkService:links,textLayerMode:1,annotationMode:2,removePageBorders:true});viewer.current=instance;links.setViewer(instance)
   bus.on('pagesinit',()=>{if(!disposed)instance.currentScaleValue='page-width'});bus.on('pagechanging',(value:any)=>{if(!disposed)setPage(value.pageNumber)})
   task=core.getDocument({url,cMapUrl:'/research/api/reader-assets/pdf-assets/cmaps/',cMapPacked:true,standardFontDataUrl:'/research/api/reader-assets/pdf-assets/standard_fonts/',wasmUrl:'/research/api/reader-assets/pdf-assets/wasm/'})
   const pdf=await task.promise;if(disposed)return;setPages(pdf.numPages);instance.setDocument(pdf);links.setDocument(pdf)
  }catch(e){if(!disposed)setError((e as Error).message)}})()
  return()=>{disposed=true;instance?.setDocument(null);void task?.destroy();viewer.current=undefined}
 },[url])
 const go=(value:number)=>{if(viewer.current)viewer.current.currentPageNumber=Math.max(1,Math.min(pages,value))}
 return <section className="template-pdf-preview" aria-label={title}><header><strong>{title}</strong><div className="toolbar-spacer"/><button aria-label="上一页" disabled={page<=1} onClick={()=>go(page-1)}><ChevronLeft size={15}/></button><input aria-label="预览页码" type="number" min={1} max={pages||1} value={page} onChange={e=>go(Number(e.target.value))}/><span>/ {pages||'…'}</span><button aria-label="下一页" disabled={!pages||page>=pages} onClick={()=>go(page+1)}><ChevronRight size={15}/></button><button aria-label="缩小预览" onClick={()=>{if(viewer.current)viewer.current.currentScale*=.9}}><Minus size={14}/></button><button aria-label="放大预览" onClick={()=>{if(viewer.current)viewer.current.currentScale*=1.1}}><Plus size={14}/></button></header><div className="template-pdf-stage"><div ref={container} className="template-pdf-container"/></div>{error&&<p role="alert">{error}</p>}</section>
}
