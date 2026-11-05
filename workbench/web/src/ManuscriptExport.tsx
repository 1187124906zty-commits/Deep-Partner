import {useEffect,useRef,useState} from 'react'
import {ArrowLeft,Check,Download,Eye,FileText,FolderOpen,Loader2} from 'lucide-react'
import {api,base,jsonBody,projectPath,type Project} from './api'
import {IconButton} from './ui'
import {PdfPreview} from './PdfPreview'
type Props={project:Project;onClose:()=>void;onError:(e:unknown)=>void;notify:(s:string)=>void;beforeAction?:()=>Promise<void>;readerId?:string;readerTranslated?:boolean}
export function ManuscriptExport({project,onClose,onError,notify,beforeAction,readerId,readerTranslated}:Props){
 const [templates,setTemplates]=useState<any[]>([]),[document,setDocument]=useState<any>(),[selected,setSelected]=useState('journal-zh'),[chooseOpen,setChooseOpen]=useState(true)
 const [language,setLanguage]=useState('source'),[format,setFormat]=useState('docx'),[review,setReview]=useState(false),[filename,setFilename]=useState('稿件'),[destination,setDestination]=useState('')
 const [view,setView]=useState<{url:string;title:string}>(),[busy,setBusy]=useState(''),[download,setDownload]=useState(''),[saved,setSaved]=useState('')
 const webHandle=useRef<any>(undefined),desktop=location.hostname==='127.0.0.1'
 const desktopCall=async(path:string,body:any)=>{const response=await fetch('/desktop/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw new Error(value.error||'保存操作未完成');return value}
 useEffect(()=>{void Promise.all([api('/manuscript-templates'),api(projectPath(project,'/manuscript'))]).then(([styles,doc])=>{setTemplates(styles.templates.filter((t:any)=>t.primary));setDocument(doc);setFilename((doc.title||'稿件').replace(/[<>:"/\\|?*]/g,'_').slice(0,120));setSelected(styles.templates.some((t:any)=>t.primary&&t.id===doc.template)?doc.template:/[\u4e00-\u9fff]/.test(doc.title)?'journal-zh':'journal-en')}).catch(onError)},[project.id])
 const choose=(id:string)=>{setSelected(id);setDownload('');setSaved('');const target=id==='journal-en'?'en':'zh-CN';setLanguage(document?.translation?.language===target?'translation':'source');setView({url:base+'/manuscript-template-full/'+id,title:id==='journal-en'?'Journal template 全文':'中文期刊模板全文'})}
 const chooseLocation=async()=>{
  try{
   if(desktop){const value=await desktopCall('choose-export',{filename:filename+'.'+format,path:destination});if(value.path)setDestination(value.path);return value.path||''}
   if((window as any).showSaveFilePicker){webHandle.current=await (window as any).showSaveFilePicker({suggestedName:filename+'.'+format,types:[{description:format.toUpperCase(),accept:{[format==='pdf'?'application/pdf':'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:['.'+format]}}]});setDestination(webHandle.current.name);return webHandle.current.name}
   return ''
  }catch(e){if((e as Error).name!=='AbortError')onError(e);return ''}
 }
 const run=async(preview=false)=>{
  if(busy)return
  let target=destination
  if(!preview&&desktop&&!target){target=await chooseLocation();if(!target)return}
  setBusy(preview?'正在生成预览':'正在导出稿件');setDownload('');setSaved('')
  try{
   await beforeAction?.()
   const response=await api(projectPath(project,'/manuscript/export'),jsonBody({template:selected,format:preview?'pdf':format,filename:preview?'稿件预览.pdf':filename+'.'+format,columns:templates.find(t=>t.id===selected)?.columns[0]||1,language,document_id:readerId||'',review,preview}))
   let result:any
   for(let i=0;i<240;i++){const rows=await api(projectPath(project,'/jobs'));const job=rows.jobs.find((j:any)=>j.id===response.job_id);if(job?.status==='failed')throw new Error(job.error);if(job?.status==='completed'){result=job.result;break}if(job?.stage)setBusy(job.stage);await new Promise(resolve=>setTimeout(resolve,1000))}
   if(!result)throw new Error('文件仍在生成，可从任务中继续查看')
   if(preview){setView({url:result.url,title:'稿件预览'});return}
   if(desktop){const output=await desktopCall('save-export',{url:result.url,path:target});setSaved(output.path);notify('稿件已保存')}
   else if(webHandle.current){const response=await fetch(result.url);if(!response.ok)throw new Error('导出文件读取失败');const writer=await webHandle.current.createWritable();await writer.write(await response.blob());await writer.close();setSaved(webHandle.current.name);webHandle.current=undefined}
   else{setDownload(result.url);const a=window.document.createElement('a');a.href=result.url;a.download=filename+'.'+format;a.click()}
  }catch(e){onError(e)}finally{setBusy('')}
 }
 const updateFormat=(value:string)=>{setFormat(value);setDownload('');setSaved('');webHandle.current=undefined;if(destination)setDestination(destination.replace(/\.[^\\/.]+$/,'.'+value))}
 return <div className="manuscript-export-planner activity-host"><div className="reading-toolbar"><IconButton title="返回稿件" onClick={onClose}><ArrowLeft size={16}/></IconButton><h1>稿件导出</h1></div><div className="manuscript-export-body"><section className="manuscript-export-options"><button className="adapted-template-toggle" aria-expanded={chooseOpen} onClick={()=>setChooseOpen(!chooseOpen)}><FileText size={18}/>已适配期刊模板<span>{chooseOpen?'收起':'选择'}</span></button>{chooseOpen&&<div className="export-template-list">{templates.map(t=><article key={t.id} className={selected===t.id?'selected':''}><button className="export-template-choice" aria-pressed={selected===t.id} onClick={()=>choose(t.id)}><img src={base+'/manuscript-template-preview/'+t.id} alt={t.name}/><span>{t.name}</span>{selected===t.id&&<Check size={17}/>}</button><button className="template-full-trigger" onClick={()=>setView({url:base+'/manuscript-template-full/'+t.id,title:t.name+' 全文'})}><Eye size={14}/>预览模板全文</button></article>)}</div>}<label>文件名<input aria-label="导出文件名" value={filename} onChange={e=>{setFilename(e.target.value);setSaved('')}}/></label><label>文件格式<select aria-label="导出格式" value={format} onChange={e=>updateFormat(e.target.value)}><option value="docx">Word DOCX</option><option value="pdf">PDF</option></select></label><label>稿件语言<select aria-label="导出语言" value={language} onChange={e=>setLanguage(e.target.value)}><option value="source">原稿</option><option value="translation" disabled={!document?.translation}>{document?.translation?.language==='en'?'英文译稿':'中文译稿'}{document?.translation?.stale?'（待更新）':''}</option>{readerId&&<option value="reader" disabled={!readerTranslated}>阅读器译文</option>}</select></label><label>保存位置<div className="export-destination">{desktop?<input aria-label="导出保存位置" value={destination} onChange={e=>setDestination(e.target.value)} placeholder="完整文件路径"/>:<span>{destination||'浏览器下载目录'}</span>}<button title="选择保存位置" aria-label="选择保存位置" onClick={()=>void chooseLocation()}><FolderOpen size={17}/></button></div></label><label className="export-review-option"><input type="checkbox" checked={review} onChange={e=>setReview(e.target.checked)}/>包含批注与修订</label><div className="manuscript-export-actions"><button disabled={!!busy} onClick={()=>void run(true)}><Eye size={16}/>预览稿件</button><button className="primary" disabled={!!busy||!filename.trim()} onClick={()=>void run()}>{busy?<Loader2 size={16} className="spin"/>:<Download size={16}/>}导出</button></div>{busy&&<div className="export-status" role="status">{busy}</div>}{saved&&<div className="export-receipt" role="status"><Check size={16}/><span>{saved}</span></div>}{download&&<a className="button" href={download} download={filename+'.'+format}><Download size={15}/>下载文件</a>}</section><div className="manuscript-export-preview">{view?<PdfPreview url={view.url} title={view.title}/>:<PdfPreview url={base+'/manuscript-template-full/'+selected} title={selected==='journal-en'?'Journal template 全文':'中文期刊模板全文'}/>}</div></div></div>
}
