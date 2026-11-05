"""Source PDFs and their verified metadata in the owning project workspace."""
from pathlib import Path
from difflib import SequenceMatcher
import asyncio, hashlib, json, re
import httpx
from urllib.parse import quote
from fastapi import Depends,File,Form,HTTPException,Request,UploadFile
from fastapi.responses import FileResponse
from .native import actor,call,BASE,headers
from .storage import atomic_json,child,now


def read_index(root):
    p=root/'.workbench/literature-index.json'
    return json.loads(p.read_text()) if p.exists() else {}


async def identity(data,name,settings,native_context=None,expected=None):
    import fitz
    from .references import search
    try:
        with fitz.open(stream=data,filetype='pdf') as pdf:
            if not len(pdf):raise ValueError('PDF 没有页面')
            excerpt='\n'.join(pdf[i].get_text() for i in range(min(2,len(pdf))))
            title=(pdf.metadata or {}).get('title','')
            candidates=[]
            for block in pdf[0].get_text('dict').get('blocks',[]):
                spans=[s for line in block.get('lines',[]) for s in line.get('spans',[]) if s.get('text','').strip()]
                value=' '.join(s['text'] for s in spans).strip()
                if spans and 15<len(value)<600 and not re.search(r'arxiv:|https?://',value,re.I) and block['bbox'][1]<pdf[0].rect.height*.45:candidates.append((max(s['size'] for s in spans),value))
            if candidates and (not title or len(title)<12):title=max(candidates)[1]
            if not title or len(title)<12 or re.search(r'microsoft|untitled|latex',title,re.I):
                lines=[v.strip() for v in excerpt.splitlines() if len(v.strip())>20]
                title=next(iter(lines),Path(name).stem)
            preview=pdf[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).tobytes('png')
    except Exception as e:raise ValueError('附件不是可阅读的完整 PDF') from e
    if expected:
        from .literature_providers import doi_key,title_key
        compact=re.sub(r'\s+','',excerpt).casefold();expected_doi=doi_key(expected.get('doi'));expected_arxiv=str(expected.get('arxiv') or '').removeprefix('arXiv:')
        title_match=bool(title_key(expected.get('title')) and (title_key(expected['title']) in title_key(excerpt) or SequenceMatcher(None,title_key(title),title_key(expected['title'])).ratio()>.86))
        identifier_match=bool(expected_doi and expected_doi in compact or expected_arxiv and expected_arxiv in compact)
        if not identifier_match and not title_match:raise ValueError('已下载 PDF 的首页与选中题录不一致，已保留本机和集群文件，未加入用户文献库')
        from .bibliography_metadata import pdf_author_names
        if expected_doi and (not title_match or not expected.get('authors')):
            from .bibliography_metadata import resolve
            resolved=await resolve(expected,excerpt)
            if resolved.get('metadata_status')=='verified':expected=resolved
        return {**expected,'authors':pdf_author_names(expected.get('authors',[]),excerpt),'uploaded':now(),'identity_status':'matched','verified':True,'match_method':'选中题录与下载 PDF 的 DOI/arXiv/首页标题核对','match_evidence':'identifier' if identifier_match else 'title'},preview
    doi=re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',excerpt,re.I)
    arxiv=re.search(r'(?:arxiv[:_ /-]*)(\d{4}\.\d{4,5})(?:v\d+)?',excerpt+' '+name,re.I)
    query=doi[0].rstrip('.,;)') if doi else title
    record={'title':title,'identity_status':'unmatched','uploaded':now(),'query':query,'authors':[]}
    if doi:
        from .bibliography_metadata import resolve
        direct=await resolve({**record,'doi':query},excerpt)
        if direct.get('metadata_status')=='verified':return {**direct,'identity_status':'matched','match_method':'PDF DOI 与 Crossref 原始题录匹配'},preview
    if arxiv:
        try:
            import xml.etree.ElementTree as ET
            async with httpx.AsyncClient(timeout=25,trust_env=False) as client:
                response=await client.get('https://export.arxiv.org/api/query',params={'id_list':arxiv[1]});response.raise_for_status()
            ns={'a':'http://www.w3.org/2005/Atom'};entry=ET.fromstring(response.text).find('a:entry',ns)
            if entry is not None:
                record.update(title=' '.join(entry.findtext('a:title',default='',namespaces=ns).split()),authors=[a.findtext('a:name',default='',namespaces=ns) for a in entry.findall('a:author',ns)],year=int(entry.findtext('a:published',default='0000',namespaces=ns)[:4]),arxiv=arxiv[1],url='https://arxiv.org/abs/'+arxiv[1],venue='arXiv',source='arXiv API',verified=True,identity_status='matched',match_method='arXiv 标识与原始元数据匹配')
                return record,preview
        except Exception:pass
    try:
        candidates=await search(query,settings=settings)
        if candidates:
            selected=0;reason='DOI 一致' if doi else '标题相似度匹配'
            if native_context or settings.get('api_key'):
                from .models import complete
                native_headers,native_id=native_context or ({},'')
                prompt='根据PDF首页提取的原始文本，从联网检索返回的真实题录中确认同一篇论文。核对标题、作者、DOI与年份。只能选择候选整数索引，不是同一篇则selected=-1，不能用相似主题冒充附件身份。只输出JSON：{"selected":0,"reason":"身份核验依据"}。'
                raw=await asyncio.to_thread(complete,settings,native_headers,native_id,prompt,json.dumps({'filename':name,'pdf_excerpt':excerpt[:9000],'doi_in_pdf':doi[0] if doi else '', 'candidates':candidates},ensure_ascii=False),BASE,True,'literature')
                value=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()));selected=value.get('selected',-1);reason=str(value.get('reason',''))[:800]
                record['match_method']='联网题录 + 当前账户模型校验'
            if isinstance(selected,int) and 0<=selected<len(candidates):
                candidate=candidates[selected]
                if doi and candidate.get('doi','').lower()==doi[0].rstrip('.,;)').lower() or not doi and SequenceMatcher(None,re.sub(r'\W','',title.lower()),re.sub(r'\W','',candidate['title'].lower())).ratio()>.65:
                    record.update(candidate,identity_status='matched',match_reason=reason)
    except Exception:record['identity_status']='pending'
    return record,preview


async def save_pdf(store,owner,pid,name,data,folder,settings,native_context=None,expected=None,provenance=None):
    root=store.path(owner,pid)
    folder=folder.strip('/').strip() or 'reading'
    dest=child(root/'literature',folder+'/'+Path(name).name)
    record,preview=await identity(data,name,settings,native_context,expected)
    if provenance:record['transfer']=provenance
    store.replace(owner,pid,dest,data,'更新文献附件')
    key=dest.relative_to(root/'literature').as_posix()
    thumb=root/'.workbench/literature-previews'/(hashlib.sha256(key.encode()).hexdigest()+'.png')
    thumb.parent.mkdir(parents=True,exist_ok=True);thumb.write_bytes(preview)
    with store.lock(pid):
        index=read_index(root);index[key]={**record,'preview':str(thumb.relative_to(root)),'size':len(data),'modified':dest.stat().st_mtime};atomic_json(root/'.workbench/literature-index.json',index)
    from .paper_maps import enqueue_after_ingest
    enqueue_after_ingest(store,owner,pid,key,record)
    from .research_tool_flow import enqueue_parse
    parsing=enqueue_parse(store,owner,pid,key)
    return {'name':key,'library':'workspace','metadata':record,'attachment':True,'parsing':parsing}


def install(app,store,api_path,run_job=None):
    @app.get('/research/api/projects/{pid}/literature/items')
    async def items(request:Request,pid:str,user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid);rows=[]
        for key,metadata in read_index(root).items():
            if not child(root/'literature',key).is_file():continue
            rows.append({'name':key,'library':'workspace','type':'file','size':metadata.get('size',0),'modified':metadata.get('modified'),'metadata':metadata,'attachment':True})
        for kb in project['config'].get('knowledge_bases',[]):
            result=await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'/files?dt_workspace='+quote(project['native_id']))
            digests={v.get('digest','')[:12] for v in read_index(root).values() if v.get('digest')}
            rows.extend({**r,'library':kb,'attachment':True} for r in result.get('files',[]) if r.get('type')!='folder' and not any(Path(r.get('name','')).name.startswith(digest+'-') for digest in digests))
        refs=store.manuscript(owner,pid).get('references',[])
        for ref in refs:
            hit=next((r for r in rows if (ref.get('doi') and ref['doi'].lower()==r.get('metadata',{}).get('doi','').lower()) or (ref.get('arxiv') and ref['arxiv'] in r['name']) or (ref.get('title') and ref['title'].lower()==r.get('metadata',{}).get('title','').lower())),None)
            if hit:ref['attachment']={'asset':hit['name'],'library':hit['library'],'preview':True}
        from .bibliography_metadata import read_cache,overlay
        cache=read_cache(root)
        for row in rows:row['metadata']=overlay(row.get('metadata',{}),cache)
        with store.db() as db:pending=db.execute("SELECT status,result FROM jobs WHERE owner=? AND project=? AND kind='literature-download' AND status IN ('queued','running')",(owner,pid)).fetchall()
        downloads=[{'identifier':json.loads(row['result']).get('identifier'),'status':row['status']} for row in pending]
        from .bibliography_metadata import more_complete_authors
        references=[overlay(ref,cache) for ref in refs]
        for ref in references:
            attachment=ref.get('attachment') or {}
            hit=next((r for r in rows if r['name']==attachment.get('asset') and r['library']==attachment.get('library')),None)
            if hit:ref['authors']=more_complete_authors(ref.get('authors',[]),hit.get('metadata',{}).get('authors',[]))
        return {'files':rows,'references':references,'downloads':downloads}

    @app.post('/research/api/projects/{pid}/literature/identify')
    async def identify(pid:str,user=Depends(actor)):
        from .bibliography_metadata import key,read_cache,resolve
        import time
        owner=user['id'];store.get(owner,pid);root=store.path(owner,pid);cache=read_cache(root)
        uploaded=read_index(root)
        entries={key(e):e for e in [*store.manuscript(owner,pid).get('references',[]),*uploaded.values()] if key(e)}
        pdf_sources={key(e):root/'literature'/asset for asset,e in uploaded.items() if key(e) and asset.lower().endswith('.pdf')}
        needed=dict(list((k,e) for k,e in entries.items() if time.time()-cache.get(k,{}).get('checked',0)>7*86400)[:100])
        if not needed or run_job is None:return {'pending':len(needed),'job_id':None}
        with store.lock('metadata:'+pid):
            with store.db() as db:active=db.execute("SELECT id FROM jobs WHERE owner=? AND project=? AND kind='literature-metadata' AND status IN ('queued','running')",(owner,pid)).fetchone()
            if active:return {'job_id':active['id'],'pending':len(needed)}
            jid=store.job(owner,pid,'literature-metadata',{'subject':str(len(needed))+' 篇文献'})
        def build():
            async def gather():
                semaphore=asyncio.Semaphore(3);finished=0
                async with httpx.AsyncClient(timeout=12,trust_env=False) as client:
                    async def one(k,entry):
                        nonlocal finished
                        async with semaphore:
                            excerpt=''
                            if k in pdf_sources:
                                try:
                                    import fitz
                                    with fitz.open(pdf_sources[k]) as pdf:excerpt='\n'.join(pdf[i].get_text() for i in range(min(2,len(pdf))))[:15000]
                                except (OSError,ValueError):pass
                            value=await resolve(entry,excerpt,client=client)
                        with store.lock(pid):
                            current=read_cache(root);current[k]={'checked':time.time(),'record':value};atomic_json(root/'.workbench/bibliography-metadata.json',current)
                        finished+=1;store.set_job(jid,step='identify',stage='识别题录与作者',counts={'done':finished,'total':len(needed),'unit':'篇'})
                    await asyncio.gather(*(one(k,e) for k,e in list(needed.items())[:100]))
                return {'identified':finished}
            result=asyncio.run(gather());store.set_job(jid,step='save',stage='保存题录');return result
        run_job(jid,build);return {'job_id':jid,'pending':len(needed)}

    @app.post('/research/api/projects/{pid}/literature/upload')
    async def upload(request:Request,pid:str,files:list[UploadFile]=File(...),folder:str=Form('reading'),user=Depends(actor)):
        owner=user['id'];store.get(owner,pid);settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {};saved=[]
        for file in files:
            if not (file.filename or '').lower().endswith('.pdf'):raise ValueError('文献上传支持 PDF')
            data=await file.read(100*1024**2+1)
            if len(data)>100*1024**2:raise ValueError('单篇 PDF 最大 100 MiB')
            saved.append(await save_pdf(store,owner,pid,file.filename,data,folder,settings,(headers(request),store.get(owner,pid)['native_id'])))
        return {'items':saved}


    @app.post('/research/api/projects/{pid}/literature/match')
    async def rematch(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid);asset=str(payload.get('asset',''));source=child(root/'literature',asset)
        if not source.is_file():raise ValueError('文献附件不存在')
        settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {}
        metadata,preview=await identity(source.read_bytes(),source.name,settings,(headers(request),project['native_id']))
        with store.lock(pid):
            index=read_index(root);previous=index.get(asset,{})
            index[asset]={**previous,**metadata,'uploaded':previous.get('uploaded') or now(),'size':source.stat().st_size,'modified':source.stat().st_mtime};atomic_json(root/'.workbench/literature-index.json',index)
        return {'metadata':index[asset]}

    @app.get('/research/api/projects/{pid}/literature/file')
    async def file(pid:str,asset:str,user=Depends(actor)):
        store.get(user['id'],pid);path=child(store.path(user['id'],pid)/'literature',asset)
        if not path.is_file():raise KeyError('文献附件不存在')
        return FileResponse(path,content_disposition_type='inline')

    @app.get('/research/api/projects/{pid}/literature/preview')
    async def preview(request:Request,pid:str,asset:str,library:str='workspace',user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid)
        key=hashlib.sha256((library+':'+asset).encode()).hexdigest();target=root/'.workbench/literature-previews'/(key+'.png')
        if not target.is_file():
            if library=='workspace':data=child(root/'literature',asset).read_bytes()
            else:
                if library not in project['config'].get('knowledge_bases',[]):raise HTTPException(403,'文献不属于当前项目')
                import httpx
                async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
                    r=await client.get(BASE+'/api/knowledge-bases/'+quote(library,safe='')+'/files/'+quote(asset,safe='/')+'?dt_workspace='+quote(project['native_id']),headers=headers(request));r.raise_for_status();data=r.content
            import fitz
            with fitz.open(stream=data,filetype='pdf') as pdf:
                target.parent.mkdir(parents=True,exist_ok=True);pdf[0].get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(target)
        return FileResponse(target,headers={'Cache-Control':'private, max-age=300'})