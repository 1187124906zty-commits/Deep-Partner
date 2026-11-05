"""Persist chat uploads in the project and append searchable documents to its KB."""
from pathlib import Path
from urllib.parse import quote
import asyncio,hashlib,json,mimetypes
from fastapi import Depends,File,HTTPException,Request,UploadFile
from .native import actor,call
from .storage import atomic_json,child,now

TEXT={'.txt','.md','.markdown','.py','.m','.r','.c','.cpp','.h','.js','.ts','.tsx','.json','.yaml','.yml','.toml','.tex','.csv','.log','.sh','.sbatch','.rs','.jl','.xml','.html','.css'}
DOCUMENTS=TEXT|{'.pdf','.docx','.pptx','.xlsx','.xls','.epub'}
locks={}

def extract_text(data,name):
    from io import BytesIO
    suffix=Path(name).suffix.lower()
    if suffix in TEXT:return data.decode('utf8',errors='replace')[:2_000_000]
    if suffix=='.pdf':
        import fitz
        with fitz.open(stream=data,filetype='pdf') as pdf:return '\n\n'.join(page.get_text() for page in list(pdf)[:500])[:2_000_000]
    if suffix=='.docx':
        from docx import Document
        doc=Document(BytesIO(data));return '\n\n'.join([p.text for p in doc.paragraphs]+[' | '.join(cell.text for cell in row.cells) for table in doc.tables for row in table.rows])[:2_000_000]
    if suffix=='.pptx':
        from pptx import Presentation
        return '\n\n'.join(shape.text for slide in Presentation(BytesIO(data)).slides for shape in slide.shapes if shape.has_text_frame)[:2_000_000]
    return ''

def save_material(store,owner,pid,name,data):
    root=store.path(owner,pid);store.get(owner,pid);name=Path(name.replace('\\','/')).name
    if not name or name.startswith('.') or name in {'AGENTS.md','CLAUDE.md'}:raise ValueError('请上传研究材料，项目运行配置请通过项目文件管理')
    digest=hashlib.sha256(data).hexdigest();relative='attachments/'+digest[:12]+'/'+name
    target=child(root/'project',relative)
    with store.lock(pid):
        index_path=root/'.workbench/chat-materials.json';index=json.loads(index_path.read_text()) if index_path.exists() else {}
        key=digest+':'+name
        if key in index and target.is_file():return {**index[key],'duplicate':True}
        store.replace(owner,pid,target,data,'从研究对话上传材料')
        entry={'name':name,'path':relative,'digest':digest,'bytes':len(data),'uploaded':now(),'searchable':False,'knowledge_status':'not-applicable'}
        try:
            text=extract_text(data,name)
            if text.strip():
                cache=root/'.workbench/attachment-text'/(''+digest+'.txt');cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(text,encoding='utf8')
                entry.update(searchable=True,text_path=str(cache.relative_to(root)),knowledge_status='queued')
        except Exception:entry['extraction_error']='文本暂未提取，原始附件已保留'
        if Path(name).suffix.lower()=='.pdf':
            import fitz
            from .literature import read_index
            asset='uploads/'+digest[:12]+'-'+name;dest=child(root/'literature',asset)
            store.replace(owner,pid,dest,data,'对话附件自动加入文献库')
            with fitz.open(stream=data,filetype='pdf') as pdf:
                title=(pdf.metadata or {}).get('title') or Path(name).stem
                thumb=root/'.workbench/literature-previews'/(digest+'.png');thumb.parent.mkdir(parents=True,exist_ok=True)
                if len(pdf):pdf[0].get_pixmap(matrix=fitz.Matrix(.7,.7),alpha=False).save(thumb)
            literature=read_index(root);literature[asset]={'title':title,'authors':[],'identity_status':'uploaded','uploaded':now(),'size':len(data),'modified':dest.stat().st_mtime,'preview':str(thumb.relative_to(root)),'source':'chat-upload','digest':digest}
            atomic_json(root/'.workbench/literature-index.json',literature);entry['literature_asset']=asset
            from .paper_maps import enqueue_after_ingest
            enqueue_after_ingest(store,owner,pid,asset,literature[asset])
        index[key]=entry;atomic_json(index_path,index)
    return entry

def install(app,store,run_job):
    @app.post('/research/api/projects/{pid}/attachments')
    async def upload(request:Request,pid:str,files:list[UploadFile]=File(...),user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid)
        if not 1<=len(files)<=30:raise ValueError('一次可上传1至30份材料')
        entries=[]
        for file in files:
            data=await file.read(100*1024**2+1)
            if len(data)>100*1024**2:raise HTTPException(413,'单份材料最大100MiB')
            entry=await asyncio.to_thread(save_material,store,owner,pid,file.filename or 'attachment',data)
            if entry.get('literature_asset') and not entry.get('duplicate'):
                from .literature import identity,read_index
                metadata,preview=await identity(data,file.filename,{})
                root=store.path(owner,pid)
                with store.lock(pid):
                    literature=read_index(root);asset=entry['literature_asset'];literature[asset]={**literature[asset],**metadata};atomic_json(root/'.workbench/literature-index.json',literature)
                from .paper_maps import enqueue_after_ingest
                enqueue_after_ingest(store,owner,pid,entry['literature_asset'],metadata)
                from .research_tool_flow import enqueue_parse
                entry['cluster_parsing']=enqueue_parse(store,owner,pid,entry['literature_asset'])
            entries.append(entry)
        # A completed native indexing job and a saved upload are distinct states.
        queued=[entry for entry in entries if entry['searchable'] and entry['knowledge_status'] in ('queued','failed')]
        task=None;error=None
        if queued:
            async with locks.setdefault(pid,asyncio.Lock()):
                try:
                    project=store.get(owner,pid);scope='?dt_workspace='+quote(project['native_id']);config=project['config'];kb=config.get('attachment_knowledge_base')
                    if not kb:
                        created=await call(request,'POST','/api/knowledge-bases'+scope,data={'name':'项目资料-'+pid[:10],'rag_provider':'llamaindex','storage_workspace_id':project['native_id']})
                        kb=created['id'];config['attachment_knowledge_base']=kb;config['knowledge_bases']=list(dict.fromkeys(config.get('knowledge_bases',[])+[kb]));store.update(owner,pid,config=config)
                        await call(request,'PATCH','/api/settings/workspace/registrations/'+project['native_id'],json={'resources':{'knowledge_bases':config['knowledge_bases'],'skills':None,'mcp':None}})
                    upload_files=[]
                    root=store.path(owner,pid)
                    for entry in queued:
                        # PDFs use their originals; other supported materials use
                        # extracted Markdown so code is indexed as readable text.
                        pdf=Path(entry['name']).suffix.lower()=='.pdf'
                        path=child(root/'project',entry['path']) if pdf else child(root,entry['text_path'])
                        name=entry['digest'][:12]+'-'+entry['name']+('' if pdf else '.md')
                        upload_files.extend([('files',(name,path.read_bytes(),'application/pdf' if pdf else 'text/markdown')),('rel_paths',(None,name))])
                    result=await call(request,'POST','/api/knowledge-bases/'+quote(kb,safe='')+'/upload'+scope,files=upload_files,data={'image_analysis':'false'})
                    task=result.get('task_id')
                    for entry in queued:entry.update(knowledge_status='indexing',knowledge_base=kb,task_id=task)
                except Exception as exc:
                    error=str(getattr(exc,'detail',exc))[:600]
                    for entry in queued:entry.update(knowledge_status='failed',knowledge_error=error)
                with store.lock(pid):
                    path=store.path(owner,pid)/'.workbench/chat-materials.json';index=json.loads(path.read_text())
                    for entry in entries:index[entry['digest']+':'+entry['name']]={k:v for k,v in entry.items() if k!='duplicate'}
                    atomic_json(path,index)
        return {'items':entries,'saved':len(entries),'searchable':sum(e['searchable'] for e in entries),'knowledge_task':task,'knowledge_error':error,'project':store.get(owner,pid)}

    @app.get('/research/api/projects/{pid}/attachments')
    async def status(request:Request,pid:str,user=Depends(actor)):
        project=store.get(user['id'],pid);path=store.path(user['id'],pid)/'.workbench/chat-materials.json'
        entries=list(json.loads(path.read_text()).values()) if path.exists() else []
        kb=project['config'].get('attachment_knowledge_base');readiness=None
        if kb:
            try:readiness=await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'/indexing-readiness?dt_workspace='+quote(project['native_id']))
            except HTTPException as exc:readiness={'ready':False,'message':str(exc.detail)}
        metadata=None
        if kb:
            try:
                native=await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'?dt_workspace='+quote(project['native_id']))
                durable=await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'/indexing-run?dt_workspace='+quote(project['native_id']))
                run=durable.get('run') or {};statistics=native.get('statistics',{})
                complete=(native.get('status')=='ready' and statistics.get('rag_initialized') and run.get('state')=='completed'
                          and not statistics.get('needs_reindex') and not native.get('metadata',{}).get('needs_reindex')
                          and int(native.get('metadata',{}).get('last_indexed_count',0))>=int(statistics.get('raw_documents',1)))
                state='ready' if complete else 'indexing' if run.get('state') in ('running','queued','completed') else run.get('state') or native.get('status')
                metadata={'status':state,'statistics':statistics,'progress':native.get('progress'),'run_state':run.get('state')}
                if complete:
                    for entry in entries:
                        if entry.get('knowledge_status')=='indexing':entry['knowledge_status']='ready'
                elif native.get('status') in ('failed','error') or run.get('state') in ('failed','error','interrupted','cancelled'):
                    for entry in entries:
                        if entry.get('knowledge_status')=='indexing':entry['knowledge_status']='failed'
                with store.lock(pid):atomic_json(path,{entry['digest']+':'+entry['name']:entry for entry in entries})
            except HTTPException:pass
        return {'items':entries,'knowledge_base':kb,'readiness':readiness,'index':metadata}