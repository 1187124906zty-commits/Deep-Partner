"""Project-isolated upstream NeoRead runtime and authenticated gateway."""
from pathlib import Path
import asyncio,atexit,gzip,json,os,re,secrets,subprocess,sys,threading,time
import httpx
from fastapi import HTTPException
from fastapi.responses import Response,StreamingResponse
from .storage import atomic_json

ROOT=Path(__file__).resolve().parents[1]
instances={};locks={};native_sessions={}


def paper_outline(data,document):
    """Add source-bound PDF bookmarks from actual manuscript heading objects."""
    import fitz
    pdf=fitz.open(stream=data,filetype='pdf');headings=[]
    def text(node):return node.get('text','')+''.join(text(c) for c in node.get('content',[]))
    def collect(node):
        if node.get('type')=='heading':headings.append((max(1,min(4,int(node.get('attrs',{}).get('level',1)))),text(node).strip()))
        for item in node.get('content',[]):collect(item)
    collect(document['content']);toc=[];start=0;last_level=0
    for level,title in headings:
        if not title:continue
        for index in range(start,len(pdf)):
            matches=pdf[index].search_for(title)
            if matches:
                level=min(level,last_level+1);toc.append([level,title,index+1]);start=index;last_level=level;break
    if toc:pdf.set_toc(toc)
    return pdf.tobytes(garbage=3,deflate=True)


def engine(store,owner,pid):
    store.get(owner,pid)
    with locks.setdefault(pid,threading.Lock()):
        prior=instances.get(pid)
        if prior and prior['process'].poll() is None:return prior
        binary=Path(os.environ.get('WORKBENCH_NEOREAD','/opt/workbench-tools/neoread-server'))
        if not binary.is_file():raise ValueError('NeoRead 阅读服务尚未安装')
        root=store.path(owner,pid)/'.workbench/neoread';root.mkdir(parents=True,exist_ok=True)
        token=secrets.token_hex(32);env=os.environ.copy();env.update(NEOREAD_TOKEN=token,NEOREAD_NODE=sys.executable,NEOREAD_PROCESSOR=str(ROOT/'server/reader_processor.py'))
        log=(root/'service.log').open('ab')
        proc=subprocess.Popen([str(binary),'--data',str(root),'--port','0','--web',str(ROOT/'vendor/neoread-web'),'--connector=false'],env=env,stdout=subprocess.PIPE,stderr=log)
        # Upstream emits one readiness line. Keep its private token server-side.
        line=proc.stdout.readline()
        if not line:raise RuntimeError('NeoRead 启动失败，详见项目 service.log')
        state=json.loads(line);value={'process':proc,'url':state['url'],'token':token,'root':root,'log':log,'owner':owner}
        instances[pid]=value
        # The gateway secret changes whenever this process starts. Refresh the
        # persisted bridge before a cached reader resumes after service restart.
        try:configure_model_bridge(value,pid)
        except Exception:
            instances.pop(pid,None);proc.terminate();raise
        return value


def configure_model_bridge(item,pid):
    return request_engine(item,'PUT','/api/ai/config',json={'primary':'api','models':{'api':'workbench'},'translationModels':{'api':'workbench'},'apiModels':['workbench'],
      'api':{'url':'http://127.0.0.1:47900/internal/reader-model/'+pid+'/v1','protocol':'openai','key':item['token']}})


def stop():
    for item in instances.values():
        if item['process'].poll() is None:item['process'].terminate()
atexit.register(stop)


def request_engine(item,method,path,**kwargs):
    with httpx.Client(timeout=120,trust_env=False) as client:
        response=client.request(method,item['url']+path,headers={'Authorization':'Bearer '+item['token'],'Origin':item['url']},**kwargs)
    if not response.is_success:
        try:message=response.json().get('error') or response.text
        except Exception:message=response.text
        raise ValueError(message[:350])
    return response.json()


def prepare_translation(item):
    """Verify the current model bridge once through NeoRead's native probe."""
    config=request_engine(item,'GET','/api/ai/config')
    if config.get('capabilities',{}).get('api:workbench',{}).get('text'):return
    result=request_engine(item,'POST','/api/ai/test/api?model=workbench&capability=text&timeoutSeconds=90',json={})
    if not result.get('text'):raise ValueError('当前模型的文字连接检测未通过：'+str(result.get('error') or '没有返回文字')[:250])


def translation_document(store,owner,pid,document_id,document):
    """Export the currently saved native translation, independently of preset drafts."""
    from io import BytesIO
    from zipfile import ZipFile
    import base64,mimetypes
    from .manuscripts import import_manuscript
    item=engine(store,owner,pid);mapping=json.loads((item['root'].parent/'neoread-map.json').read_text())
    if not any(e['document_id']==document_id and e['area']=='paper' for e in mapping.values()):raise ValueError('译文不属于当前稿件')
    with httpx.Client(timeout=60,trust_env=False) as client:
        r=client.get(item['url']+'/api/documents/'+document_id+'/translations/export?format=zip',headers={'Authorization':'Bearer '+item['token'],'Origin':item['url']})
    if not r.is_success:raise ValueError('当前阅读器还没有可导出的已完成译文')
    with ZipFile(BytesIO(r.content)) as archive:
        markdown=archive.read('translation.md').decode('utf8')
        for name in archive.namelist():
            if name.startswith('assets/'):
                mime=mimetypes.guess_type(name)[0] or 'image/png';data=archive.read(name)
                markdown=markdown.replace(']('+name+')','](data:'+mime+';base64,'+base64.b64encode(data).decode()+')')
    tree=import_manuscript(store.path(owner,pid),pid,markdown.encode(),'translation.md','reader-'+document_id)
    return {**document,'content':tree,'comments':[],'translation_origin':'native-reader'}


def open_document(store,owner,pid,area,asset,title,data,revision,native_headers,width=1000,theme='snow'):
    item=engine(store,owner,pid);native_sessions[pid]=native_headers
    mapping=item['root'].parent/'neoread-map.json'
    with locks[pid]:
        saved=json.loads(mapping.read_text()) if mapping.exists() else {};key=area+':'+asset;entry=saved.get(key)
        request_engine(item,'PUT','/api/preferences/guide',json={'onboarded':True,'seenVersion':'0.9.5'})
        if not saved:
            request_engine(item,'PUT','/api/settings',json={'autoTranslatePDF':False,'autoTranslateMaxPages':0,'autoGenerateOverview':False,'documentTabs':False})
        if not entry:
            result=request_engine(item,'POST','/api/documents',files={'file':(title if title.lower().endswith('.pdf') else title+'.pdf',data,'application/pdf')},data={'library':'papers'})
            doc=result.get('document',result);request_engine(item,'POST','/api/documents/'+doc['id']+'/reparse',json={});entry={'document_id':doc['id'],'area':area,'asset':asset,'title':title,'revision':revision};saved[key]=entry
        elif entry.get('revision')!=revision or not (item['root']/'cache'/entry['document_id']/'analysis/manifest.json').is_file() or json.loads((item['root']/'cache'/entry['document_id']/'analysis/manifest.json').read_text()).get('parserVersion',0)<3:
            # Upstream preserves document ID and its annotations while reparsing.
            doc=next(d for d in request_engine(item,'GET','/api/documents') if d['id']==entry['document_id'])
            # The library's immutable source name is resolved by its own document record.
            source=item['root']/'papers'/(doc['id']+'.pdf')
            if not source.is_file():
                matches=list((item['root']/'papers').glob(doc['id']+'*'));source=next((p for p in matches if p.is_file()),source)
            if not source.is_file():raise ValueError('NeoRead 原文路径不存在，未替换已有批注')
            if source.read_bytes()!=data:store.replace(owner,pid,source,data,'更新阅读原文，保留旧版及批注')
            request_engine(item,'POST','/api/documents/'+doc['id']+'/reparse',json={})
            entry['revision']=revision
        atomic_json(mapping,saved)
        settings=request_engine(item,'GET','/api/settings') or {}
        settings.update(readingSession={'documentIds':[entry['document_id']],'activeId':entry['document_id']},documentTabs=True,autoTranslatePDF=False,autoTranslateMaxPages=0,autoGenerateOverview=False)
        settings['readerLayout']={**settings.get('readerLayout',{}),'navigationOpen':width>760,'assistantOpen':False,'navigationWidth':17,'sourceWidth':54,'stacked':width<900}
        mode='dark' if theme in ('dark','glass') else 'sepia' if theme=='light' else 'light'
        settings.update(mode=mode,appearance=mode,pdfDarkContrast='soft',pdfDarkImageMode='preserve',reducedMotion=True)
        settings['documentZooms']={**settings.get('documentZooms',{}),entry['document_id']:'width'}
        request_engine(item,'PUT','/api/settings',json=settings)
        configure_model_bridge(item,pid)
    return {**entry,'url':'/research/reader/'+pid+'/#token=workbench','engine':'NeoRead','parser':'PyMuPDF4LLM semantic layout; original PDF vectors and PDF.js rendering'}


def rewrite_text(text,prefix,token):
    text=text.replace('/pub/'+token+'/',prefix+'/pub/workbench/')
    text=text.replace('return"/"+','return"'+prefix+'/"+')
    text=text.replace('this.links.setViewer(this.viewer)','window.__workbenchReader=this,this.links.setViewer(this.viewer)')
    text=text.replace('maxCanvasPixels:4*1024*1024,maxCanvasDim:4096','maxCanvasPixels:16*1024*1024,maxCanvasDim:8192')
    # Built Vite modules use absolute URLs for API, fonts and PDF workers.
    return re.sub(r'(?P<q>[\"\'`(])/(?P<part>api/|pub/|assets/|pdf-assets/|samples/)',lambda m:m['q']+prefix+'/'+m['part'],text)


EMBED_STYLE='''<style>
.app-shell>.sidebar,.app-shell>.app-sidebar,.sidebar-rail,.library-navigation{display:none!important}
.app-shell{grid-template-columns:minmax(0,1fr)!important}.app-shell>.main{min-width:0}
.document-tabbar{display:none!important}.app[data-has-tabs]{padding-top:0!important}.reader-shell{min-height:0!important}
.neoread-toolbar{min-height:46px!important;height:46px!important}.reader-tab-panel{padding-top:0!important}
.neoread-toolbar button[aria-label="返回书库"]{display:none!important}
</style>'''


async def proxy(store,owner,pid,path,request,on_annotation):
    item=await asyncio.to_thread(engine,store,owner,pid);prefix='/research/reader/'+pid
    from .native import headers as native_headers
    native_sessions[pid]=native_headers(request)
    if request.method=='POST' and re.fullmatch(r'api/documents/[a-f0-9]{32}/(?:processing|translations(?:/range)?|assistance)',path):
        action=json.loads(await request.body() or b'{}').get('action') if path.endswith('/assistance') else None
        if not path.endswith('/assistance') or action in ('start','resume','retranslate'):
            await asyncio.to_thread(prepare_translation,item)
    upstream='/'+path
    if upstream.startswith('/pub/workbench/'):upstream=upstream.replace('/pub/workbench/','/pub/'+item['token']+'/',1)
    query=request.url.query
    if path=='api/settings' and 'startup=1' in query:
        # A long-lived server's startup snapshot precedes the gateway's open action.
        query='&'.join(part for part in query.split('&') if part!='startup=1')
    url=item['url']+upstream+('?' +query if query else '')
    body=await request.body();headers={'Authorization':'Bearer '+item['token'],'Origin':item['url']}
    for name in ('content-type','range','if-none-match'):
        if request.headers.get(name):headers[name]=request.headers[name]
    client=httpx.AsyncClient(timeout=httpx.Timeout(240,read=None),trust_env=False)
    response=await client.send(client.build_request(request.method,url,content=body,headers=headers),stream=True)
    content_type=response.headers.get('content-type','')
    if 'text/event-stream' in content_type:
        async def stream():
            try:
                async for chunk in response.aiter_bytes():yield chunk
            finally:await response.aclose();await client.aclose()
        return StreamingResponse(stream(),status_code=response.status_code,media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    raw=await response.aread();await response.aclose();await client.aclose()
    if response.is_success and '/annotations' in path and request.method in ('POST','PATCH','DELETE'):
        try:await on_annotation(item,path,request.method,json.loads(raw) if raw else {},json.loads(body) if body else {})
        except Exception as error:
            from .annotations import event
            event(store,owner,pid,'reader.annotation-sync-error',{'error':str(error)[:200],'path':path})
    if any(t in content_type for t in ('javascript','text/','json','svg')):
        text=rewrite_text(raw.decode('utf8'),prefix,item['token'])
        if 'text/html' in content_type:
            script=reader_bridge_script(prefix,pid)
            text=text.replace('</head>',EMBED_STYLE+'<style>'+Path(__file__).with_name('reader_embed.css').read_text(encoding='utf8')+'</style><script>'+script+'</script></head>')
        # Never deliver engine credentials through serialized AI config.
        text=text.replace(item['token'],'workbench');raw=text.encode('utf8')
    kept={k:v for k,v in response.headers.items() if k.lower() in ('content-type','content-range','accept-ranges','cache-control')}
    if len(raw)>2000 and 'gzip' in request.headers.get('accept-encoding','') and any(t in content_type for t in ('javascript','text/','json','svg')):
        raw=gzip.compress(raw,compresslevel=4);kept.update({'Content-Encoding':'gzip','Vary':'Accept-Encoding'})
    return Response(raw,status_code=response.status_code,headers=kept)


def reader_bridge_script(prefix,pid):
    """DOM bridge for the native reader's existing image preview action."""
    return Path(__file__).with_name('reader_bridge.js').read_text(encoding='utf8').replace('PREFIX',json.dumps(prefix)).replace('PID',json.dumps(pid))
