from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
import asyncio
import httpx
import json
import mimetypes
import os
import re
import shutil
import tempfile
import uuid
import zipfile
import threading
from contextvars import ContextVar
from fastapi import FastAPI,Request,Depends,HTTPException,UploadFile,File,Form
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from .response_compression import BufferedResponseCompression
from pydantic import BaseModel,Field
from .storage import Store,Conflict,atomic_json,child,now
from .native import actor,call,headers,BASE
from .manuscripts import TEMPLATES,export_manuscript,plain_document
from .slides import prepare_template,create_minimal,make_deck,render_presentation,plan_with_paper2slides

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))
store=Store(DATA)
pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='research-workbench')
review_timers={}


@asynccontextmanager
async def lifespan(app):
    # Durable flow/parse runners own recovery and process locks across services.
    # Restarting this HTTP process must not interrupt work owned by those runners.
    # Other in-process tasks retain the explicit restart marker.
    with store.db() as db:interrupted=db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') AND kind NOT IN ('literature-download','paper-content-map','research-flow','simulation','cluster-pdf-parse')").fetchall()
    for row in interrupted:store.set_job(row['id'],status='interrupted',stage='已中断，可重新开始',error='服务重新启动，已保存的稿件与文件保留')
    from .writing import read_json
    with store.db() as db:writing_jobs=db.execute("SELECT owner,project FROM jobs WHERE kind='writing' AND status='interrupted'").fetchall()
    for row in writing_jobs:
        folder=store.path(row['owner'],row['project'])/'.workbench/writing/runs'
        for p in folder.glob('*/state.json'):
            run=read_json(p,{})
            if run.get('status') in ('running','queued'):
                run.update(status='interrupted',error='服务已重新启动，可从当前阶段继续')
                atomic_json(p,run)
    related_task=asyncio.create_task(related_daily_updates())
    paper_maps_task=asyncio.create_task(paper_maps_service.loop())
    yield
    related_task.cancel()
    paper_maps_task.cancel()
    await asyncio.gather(paper_maps_task,return_exceptions=True)
    from .neoreader import stop
    stop()


app=FastAPI(title='Research Workbench',version='0.1.0',lifespan=lifespan)
app.add_middleware(BufferedResponseCompression,minimum_size=1000)
quality_request_headers=ContextVar('quality_request_headers',default=None)

@app.middleware('http')
async def quality_request_scope(request:Request,call_next):
    token=quality_request_headers.set(headers(request))
    try:return await call_next(request)
    finally:quality_request_headers.reset(token)


from .account_policy import install as install_account_policy
install_account_policy(app,store,actor)

from .project_progress import install as install_project_progress
install_project_progress(app,store,actor)



@app.exception_handler(KeyError)
async def missing(request,error):return JSONResponse({'detail':str(error).strip("'")},404)


@app.exception_handler(ValueError)
async def invalid(request,error):return JSONResponse({'detail':str(error)},409 if isinstance(error,Conflict) else 400)


@app.get('/health')
def health():return {'ok':True,'version':'0.1.0'}


@app.get('/research/api/me')
async def me(user=Depends(actor)):
    from .workspace_files import account_root
    account_root(store,user['id'])
    return {k:user.get(k) for k in ('id','username','role')}


class ProjectInput(BaseModel):name:str=Field(min_length=1,max_length=100)


@app.get('/research/api/projects')
async def projects(user=Depends(actor)):
    from .standards import prepare_project
    rows=store.list(user['id'])
    for row in rows:prepare_project(store.path(user['id'],row['id']))
    return {'projects':rows}


@app.get('/research/api/bootstrap')
async def bootstrap(request:Request,user=Depends(actor)):
    auth=await call(request,'GET','/api/auth/status')
    return {'auth':auth,'user':await me(user),'projects':(await projects(user))['projects']}


@app.get('/research/llms.txt')
async def llms():
    from .standards import contract
    return PlainTextResponse(contract()+'\n\n使用已登录账户读取 /research/api/projects/{id}/agent-context?task=code|paper|translation|literature|slides，取得项目路径、技能原文、写入接口和结果回执协议。')


@app.get('/research/api/standards')
async def output_standards(user=Depends(actor)):
    from .standards import contract,catalog,VERSION
    return {'version':VERSION,'instructions':contract(),'skills':catalog(),
      'integration':{'schema':'/research/api/schema','projects':'/research/api/projects','context':'/research/api/projects/{id}/agent-context?task=code|paper|translation|literature|slides|review',
        'questions':'/research/api/projects/{id}/annotations','history':'/research/api/projects/{id}/review-history','receipt':'/research/api/projects/{id}/agent-receipt',
        'authentication':'Use the connected DeepTutor account session or its authorized bearer token. Owner checks apply to all project operations.'}}


@app.get('/research/api/schema')
async def integration_schema(user=Depends(actor)):
    value=app.openapi()
    return {**value,'paths':{path:methods for path,methods in value['paths'].items() if path.startswith('/research/api/')}}


@app.get('/research/api/standards/skills/{identifier:path}')
async def output_skill(identifier:str,user=Depends(actor)):
    from .standards import catalog,skill_info,BUNDLE
    item=next((x for x in catalog() if x['id']==identifier),None)
    if item is None:raise KeyError('技能不存在')
    return skill_info(BUNDLE/item['id'])


@app.get('/research/api/projects/{pid}/agent-context')
async def agent_context(pid:str,task:str='review',user=Depends(actor)):
    from .standards import context
    return context(store,user['id'],pid,task)


@app.post('/research/api/projects')
async def create(request:Request,payload:ProjectInput,user=Depends(actor)):
    owner=user['id'];project=store.create(owner,payload.name)
    try:
        from .standards import workspace_instructions,prepare_project
        native=await call(request,'POST','/api/settings/workspace/registrations',json={
          'name':payload.name,'instructions':workspace_instructions(project['id'])})
        project=store.bind_native(owner,project['id'],native['workspace'])
        prepare_project(store.path(owner,project['id']))
    except Exception as error:
        # Keep the local draft with a visible bind error; no hidden orphan duplication.
        project=store.update(owner,project['id'],config={'native_error':str(error)[:400]})
        raise HTTPException(502,'原生工作区未绑定，已保留项目草稿：'+project['id']) from error
    return project


class ProjectUpdate(BaseModel):
    name:str|None=None
    knowledge_bases:list[str]|None=None


class ReaderInput(BaseModel):
    area:str='paper';asset:str='manuscript/main.json';library:str='';title:str='';width:int=1000;theme:str='snow'


@app.get('/research/api/projects/{pid}/literature/classification')
async def literature_classification(pid:str,user=Depends(actor)):
    project=store.get(user['id'],pid);path=store.path(user['id'],pid)/'.workbench/literature-classification.json'
    if path.exists():return json.loads(path.read_text())
    example=project['config'].get('example');kb=next(iter(project['config'].get('knowledge_bases',[])),'')
    source=ROOT/'examples'/str(example)/'manifest.json'
    if example in ('pinn-burgers','fno-darcy') and source.is_file() and kb:
        papers=json.loads(source.read_text(encoding='utf8'))['literature']
        return {'status':'waiting','origin':'source metadata','content':{'concepts':[],'documents':[
          {'asset':kb+'/'+p['stage']+'/'+Path(p['file']).name,'filename':Path(p['file']).name,'title':p['title'],'kind':'论文','purpose':p['stage'],'concepts':[]} for p in papers]}}
    return {'status':'waiting','content':{}}


@app.post('/research/api/projects/{pid}/literature/classification')
async def literature_classify(request:Request,pid:str,user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid);settings_path=api_path(owner)
    settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    if not (settings.get('api_key') and settings.get('model')):await ensure_native_model(request)
    documents=[]
    for kb in project['config'].get('knowledge_bases',[]):
        rows=await call(request,'GET','/api/knowledge-bases/'+quote(kb,safe='')+'/files?dt_workspace='+quote(project['native_id']))
        for item in rows.get('files',[]):
            if item.get('type')=='folder' or not item['name'].lower().endswith(('.pdf','.txt','.md','.epub')):continue
            text=''
            try:
                from .native import text_call
                text=(await text_call(request,'/api/knowledge-bases/'+quote(kb,safe='')+'/file-preview-text/'+quote(item['name'],safe='/')+'?dt_workspace='+quote(project['native_id'])))[:5000]
            except HTTPException:pass
            documents.append({'asset':kb+'/'+item['name'],'name':item['name'],'excerpt':text,'full_text_available':bool(text)})
    if not documents:raise ValueError('本项目尚无可分类的文献')
    native_headers=headers(request);jid=store.job(owner,pid,'literature-classify',{'subject':project['name']+' · '+str(len(documents))+' 份材料'});root=store.path(owner,pid)
    path=root/'.workbench/literature-classification.json';atomic_json(path,{'status':'running','content':{}})
    manuscript=store.manuscript(owner,pid)
    purpose=plain_document(manuscript['content'])[:6500]
    def build():
        from .models import complete
        prompt='结合研究问题与原文片段建立适度粒度的知识分类。采用 SKOS 概念、上位与相关关系；书籍/论文类型、研究用途与主题分开。小型库可平铺并赋共享用途标签，通常2至6个概念，不为每篇文献新建一个类别。缺少全文时如实标 provisional，不能冒充全文判断。只输出JSON：{"concepts":[{"id":"c1","label":"共享概念","description":"边界与用途","broader":[],"related":[]}],"documents":[{"asset":"原asset","title":"原文标题","kind":"论文/书籍/资料","purpose":"研究用途","concepts":["c1"],"rationale":"简明依据","provisional":false}]}。'
        try:
            store.set_job(jid,step='classify',stage='正在根据项目问题整理文献分类')
            raw=complete(settings,native_headers,project['native_id'],prompt,json.dumps({'project':project['name'],'research_context':purpose,'documents':documents},ensure_ascii=False),BASE,True,'literature')
            content=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
            store.set_job(jid,step='check',stage='正在核对分类与来源文献对应关系')
            ids={x['id'] for x in content['concepts']};assets={d['asset'] for d in documents}
            if {d['asset'] for d in content['documents']}!=assets or any(set(d.get('concepts',[]))-ids for d in content['documents']):raise ValueError('分类返回的文献或概念标识不对应')
            store.set_job(jid,step='save',stage='正在保存分类与来源关系')
            atomic_json(path,{'status':'ready','content':content,'updated':now(),'basis':'project question + available source text','generation':'API'})
            return {'documents':len(documents),'concepts':len(ids)}
        except Exception:
            atomic_json(path,{'status':'waiting','content':{},'updated':now()});raise
    run_job(jid,build);return {'job_id':jid}


@app.post('/research/api/projects/{pid}/agent-receipt')
async def agent_receipt(request:Request,pid:str,payload:dict,user=Depends(actor)):
    from .annotations import list_annotations,event,save_annotation
    from .reviews import validate_native_identity,review_identity
    owner=user['id'];root=store.path(owner,pid);project=store.get(owner,pid)
    identity=await validate_native_identity(request,project,payload.get('session_id',''),payload.get('turn_id',''))
    operation_id=review_identity(payload.get('operation_id',''),'操作编号',100)
    if operation_id:identity['operation_id']=operation_id
    existing={a['id']:a for a in list_annotations(store,owner,pid)};ids=payload.get('question_ids',[])
    if not isinstance(ids,list) or set(ids)-existing.keys():raise ValueError('回执中的问题不属于本项目')
    for artifact in payload.get('artifacts',[]):
        path=child(root,artifact['path'])
        if not path.exists():raise ValueError('回执产物不存在：'+artifact['path'])
    record={k:payload.get(k,[]) for k in ('question_ids','artifacts','validation','limitations')}
    record.update(identity)
    record.update(created=now());event(store,owner,pid,'agent.receipt',record)
    if payload.get('resolved'):
        for identifier in ids:save_annotation(store,owner,pid,{'status':'resolved'},identifier)
    from .quality_api import receipt_review
    quality=receipt_review(store,api_path,run_job,owner,pid,payload,headers(request))
    return {'recorded':True,**record,'quality':quality}


@app.get('/research/api/reader-assets/{path:path}')
async def reader_assets(path:str,user=Depends(actor)):
    target=child(ROOT/'vendor/neoread-web',path)
    if not path.startswith(('assets/','pdf-assets/')) or not target.is_file():raise KeyError('阅读资源不存在')
    return FileResponse(target,headers={'Cache-Control':'private, max-age=86400'})


@app.post('/research/api/projects/{pid}/reader')
async def reader_open(request:Request,pid:str,payload:ReaderInput,user=Depends(actor)):
    from .neoreader import open_document,paper_outline
    owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid)
    if payload.area=='paper' and payload.asset=='journal-preview':
        cached=root/'manuscript/exports/期刊排版预览.pdf'
        if not cached.is_file():raise ValueError('请先生成期刊排版预览')
        data=cached.read_bytes();revision=str(cached.stat().st_mtime_ns);title=project['config'].get('target_journal',{}).get('name','期刊')+' · 排版预览';asset='journal-preview'
    elif payload.area=='paper':
        document=store.manuscript(owner,pid);revision=str(document['revision'])+':outline-2:math-layout-5'
        cached=root/'.workbench/reader-current.pdf';meta=cached.with_suffix('.json')
        if not cached.is_file() or not meta.exists() or json.loads(meta.read_text()).get('revision')!=revision:
            data,_,_=await asyncio.to_thread(export_manuscript,root,document,'pdf',False,DATA/'styles')
            data=await asyncio.to_thread(paper_outline,data,document)
            cached.parent.mkdir(parents=True,exist_ok=True);cached.write_bytes(data);atomic_json(meta,{'revision':revision})
        data=cached.read_bytes();title=document['title'];asset='manuscript/main.json'
    elif payload.area=='literature' and payload.library=='workspace':
        file=child(root/'literature',payload.asset)
        if not file.is_file() or file.suffix.lower()!='.pdf':raise ValueError('文献附件不存在')
        data=file.read_bytes();title=payload.title or file.name;asset='workspace/'+payload.asset;revision=str(file.stat().st_mtime_ns)
    elif payload.area=='literature':
        if payload.library not in project['config'].get('knowledge_bases',[]):raise HTTPException(403,'文献不属于本项目关联知识库')
        rows=await call(request,'GET','/api/knowledge-bases/'+quote(payload.library,safe='')+'/files?dt_workspace='+quote(project['native_id']))
        file=next((f for f in rows.get('files',[]) if f['name']==payload.asset and f.get('type')!='folder'),None)
        if not file or not payload.asset.lower().endswith('.pdf'):raise ValueError('选择本知识库中的 PDF 原文')
        route='/api/knowledge-bases/'+quote(payload.library,safe='')+'/files/'+quote(payload.asset,safe='/')+'?dt_workspace='+quote(project['native_id'])
        import httpx
        async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
            response=await client.get(BASE+route,headers=headers(request));response.raise_for_status();data=response.content
        title=payload.title or Path(payload.asset).name;asset=payload.library+'/'+payload.asset
        revision=str(file.get('modified') or file.get('updated') or response.headers.get('last-modified') or len(data))
    else:raise ValueError('阅读区无效')
    return await asyncio.to_thread(open_document,store,owner,pid,payload.area,asset,title,data,revision,headers(request),payload.width,payload.theme)


@app.get('/research/api/projects/{pid}/reader-image')
async def reader_image(pid:str,document_id:str,block_id:str,user=Depends(actor)):
    from .figures import read_registry
    from PIL import Image,ImageChops,ImageStat
    owner=user['id'];store.get(owner,pid);root=store.path(owner,pid)
    if not re.fullmatch('[a-f0-9]{32}',document_id) or not re.fullmatch(r'p[1-9][0-9]*-b[1-9][0-9]*',block_id):raise ValueError('图片定位无效')
    map_path=root/'.workbench/neoread-map.json';mapping=json.loads(map_path.read_text()) if map_path.exists() else {}
    entry=next((v for v in mapping.values() if v['document_id']==document_id),None)
    if not entry:raise KeyError('文献图片不存在')
    analysis=root/'.workbench/neoread/cache'/document_id/'analysis'
    manifest=json.loads((analysis/'manifest.json').read_text()) if (analysis/'manifest.json').exists() else {}
    block=next((b for b in manifest.get('blocks',[]) if b['id']==block_id),{})
    if not block.get('image'):raise KeyError('此处没有可用图片')
    source=child(analysis,block['image'])
    if not source.is_file():raise KeyError('此处图片尚未解析')
    # Match the PDF's actual image to a registered project result, then reuse its editor.
    with Image.open(source) as image:
        ratio=image.width/image.height;reference=image.convert('RGB').resize((80,80));best=None
        for asset in read_registry(root):
            candidate=child(root/'project',asset)
            if not candidate.is_file():continue
            with Image.open(candidate) as other:
                if abs(other.width/other.height-ratio)>max(.06,ratio*.06):continue
                delta=ImageChops.difference(reference,other.convert('RGB').resize((80,80)));error=sum(ImageStat.Stat(delta).mean)/3/255
                if best is None or error<best[0]:best=(error,asset)
        if best and best[0]<.14:return {'path':best[1],'editable':True,'match_error':best[0]}
    target=root/'project/results'/('paper-'+document_id[:8]+'-'+block_id+'.png')
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    return {'path':target.relative_to(root/'project').as_posix(),'editable':False,'source':{'document_id':document_id,'block_id':block_id}}


async def reader_actor(request:Request):
    # NeoRead's opaque browser marker is not a DeepTutor API credential.
    if request.headers.get('authorization','').strip().casefold()=='bearer workbench':
        scope={**request.scope,'headers':[(k,v) for k,v in request.scope['headers'] if k.lower()!=b'authorization']}
        return await actor(Request(scope))
    return await actor(request)


@app.api_route('/research/reader/{pid}/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE','HEAD'])
async def reader_proxy(request:Request,pid:str,path:str,user=Depends(reader_actor)):
    from .neoreader import proxy
    from .annotations import save_annotation,list_annotations
    owner=user['id'];store.get(owner,pid)
    async def annotation_changed(item,path,method,result,body):
        parts=path.split('/');docid=parts[2] if len(parts)>2 else ''
        mapping=json.loads((item['root'].parent/'neoread-map.json').read_text())
        entry=next((v for v in mapping.values() if v['document_id']==docid),None)
        if not entry:return
        identifier=result.get('id') or (parts[4] if len(parts)>4 else '')
        if not identifier:return
        identifier=uuid.uuid5(uuid.NAMESPACE_URL,pid+':neoread:'+identifier).hex
        prior=next((x for x in list_annotations(store,owner,pid) if x['id']==identifier),{})
        native=result if result.get('id') else body
        value={'area':entry['area'],'asset':entry['asset'],'title':entry['title'],'origin':'neoread',
          'quote':native.get('quote',prior.get('quote','')),'body':native.get('note',prior.get('body','')),
          'color':native.get('color',prior.get('color','#edc54b')),
          'locator':{**prior.get('locator',{}),**native.get('location',{}),'document_id':docid,'reader_url':'/research/reader/'+pid+'/', 'source_revision':entry['revision']},
          'status':'deleted' if method=='DELETE' else 'resolved' if native.get('resolved') else 'open'}
        saved=save_annotation(store,owner,pid,value,identifier)
        if saved['body']:
            native_headers=headers(request);native_headers.pop('Authorization',None)
            schedule_review_summary(owner,pid,native_headers)
    return await proxy(store,owner,pid,path,request,annotation_changed)


@app.api_route('/internal/reader-model/{pid}/v1/{path:path}',methods=['GET','POST'])
async def reader_model(request:Request,pid:str,path:str):
    from .neoreader import instances,native_sessions
    import secrets
    item=instances.get(pid)
    if request.client.host not in ('127.0.0.1','::1') or not item or not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+item['token']):raise HTTPException(403,'无效阅读服务')
    if path=='models':return {'object':'list','data':[{'id':'workbench','object':'model','owned_by':'workbench'}]}
    if path!='chat/completions':raise HTTPException(404)
    from .models import complete
    from fastapi.responses import StreamingResponse
    body=await request.json();messages=body.get('messages',[])
    system='\n\n'.join(str(m.get('content','')) for m in messages if m.get('role') in ('system','developer'))
    text='\n\n'.join(str(m.get('content','')) for m in messages if m.get('role') not in ('system','developer'))
    owner=item['owner'];settings_path=api_path(owner);settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    project=store.get(owner,pid)
    if settings.get('api_key') and settings.get('model'):
        from .standards import instructions
        import httpx
        # Preserve the original NeoRead protocol, multimodal input and tool calls.
        prepared={**body,'model':settings['model']};prepared['messages']=[dict(m) for m in messages]
        prepared['messages'].insert(0,{'role':'system','content':instructions('reader','遵循后续 NeoRead 操作的 JSONL、翻译或对话协议。')})
        client=httpx.AsyncClient(timeout=httpx.Timeout(240,read=240),trust_env=False)
        response=await client.send(client.build_request('POST',settings['base_url'].rstrip('/')+'/chat/completions',
          headers={'Authorization':'Bearer '+settings['api_key']},json=prepared),stream=bool(body.get('stream')))
        if not response.is_success:
            raw=await response.aread();await response.aclose();await client.aclose()
            return Response(raw,status_code=response.status_code,media_type='application/json')
        if body.get('stream'):
            async def forward():
                try:
                    async for chunk in response.aiter_bytes():yield chunk
                finally:await response.aclose();await client.aclose()
            return StreamingResponse(forward(),media_type='text/event-stream')
        result=response.json();await response.aclose();await client.aclose();return result
    # Native edit APIs distinguish the instruction from the text to process.
    # NeoRead places both in one user message; passing that as a draft asks the
    # edit agent to rewrite the translation prompt itself.
    native_prompt=system+'\n直接执行本次翻译或阅读任务，返回操作结果；不要改写或优化提示词。'
    native_text=text
    if '只输出 JSONL' in text and '输入资料：' in text:
        operation,encoded=text.rsplit('输入资料：',1)
        try:
            payload,end=json.JSONDecoder().raw_decode(encoded.lstrip())
            native_prompt=system+'\n'+operation+'\n'+encoded.lstrip()[end:]+'\n直接执行上述翻译并输出JSONL，不要重写这些指令。'
            native_text=json.dumps(payload,ensure_ascii=False)
        except ValueError:pass
    try:value=await asyncio.to_thread(complete,settings,native_sessions.get(pid,{}),project['native_id'],native_prompt,native_text,BASE,False,'reader')
    except Exception as error:raise HTTPException(502,str(error)[:450]) from error
    if body.get('stream'):
        async def chunks():
            yield 'data: '+json.dumps({'id':'reader-'+uuid.uuid4().hex,'object':'chat.completion.chunk','choices':[{'index':0,'delta':{'role':'assistant','content':value},'finish_reason':None}]},ensure_ascii=False)+'\n\n'
            yield 'data: '+json.dumps({'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+'\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(chunks(),media_type='text/event-stream')
    return {'id':'reader-'+uuid.uuid4().hex,'object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':value},'finish_reason':'stop'}]}


@app.get('/research/api/examples')
async def examples(user=Depends(actor)):
    if os.environ.get('WORKBENCH_ENABLE_EXAMPLES')!='1':return {'examples':[]}
    from .examples import available
    return {'examples':available(ROOT)}


@app.post('/research/api/examples/{example}/install')
async def example_install(request:Request,example:str,user=Depends(actor)):
    if os.environ.get('WORKBENCH_ENABLE_EXAMPLES')!='1':raise HTTPException(404,'此入口已停用')
    from .examples import available,install,attach_literature
    spec=next((x for x in available(ROOT) if x['id']==example),None)
    if not spec:raise KeyError('示例不存在')
    project=next((p for p in store.list(user['id']) if p['config'].get('example')==example),None)
    if project is None:
        project=await create(request,ProjectInput(name=spec['name']),user)
        manifest=await asyncio.to_thread(install,store,user['id'],project['id'],ROOT,example)
    else:
        manifest=json.loads((ROOT/'examples'/example/'manifest.json').read_text(encoding='utf8'))
    try:return await attach_literature(request,store,user['id'],project['id'],ROOT,manifest)
    except Exception as error:
        project=store.get(user['id'],project['id']);config=project['config'];config['knowledge_error']=str(getattr(error,'detail',error))[:450]
        return store.update(user['id'],project['id'],config=config)


@app.patch('/research/api/projects/{pid}')
async def update(request:Request,pid:str,payload:ProjectUpdate,user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid);config=project['config'];fields={}
    if payload.name:
        await call(request,'PATCH','/api/settings/workspace/registrations/'+project['native_id'],json={'name':payload.name})
        fields['name']=payload.name
    if payload.knowledge_bases is not None:
        # Bind from the authenticated account library; a workspace-filtered list only contains already-bound resources.
        visible=await call(request,'GET','/api/knowledge-bases?resource_library=true')
        allowed={k.get('id',k.get('name')) for k in visible}
        if set(payload.knowledge_bases)-allowed:raise HTTPException(403,'知识库不在当前账户可见范围内')
        config['knowledge_bases']=payload.knowledge_bases
        await call(request,'PATCH','/api/settings/workspace/registrations/'+project['native_id'],json={'resources':{'knowledge_bases':payload.knowledge_bases,'skills':None,'mcp':None}})
    return store.update(owner,pid,config=config,**fields)


@app.post('/research/api/projects/{pid}/import')
async def project_material_import(request:Request,pid:str,file:UploadFile=File(...),user=Depends(actor)):
    owner=user['id'];store.get(owner,pid)
    if not (file.filename or '').lower().endswith('.zip'):raise ValueError('选择带材料清单的研究项目 ZIP')
    data=await file.read(300*1024**2+1)
    if len(data)>300*1024**2:raise ValueError('导入包最大300MiB，大型原始数据请保留集群映射')
    jid=store.job(owner,pid,'material-import',{'source_name':file.filename})
    def build():
        from .material_import import import_bundle
        store.set_job(jid,stage='导入程序、数据与可编辑稿件')
        result=import_bundle(store,owner,pid,data,progress=lambda step,message,counts=None:store.set_job(jid,step=step,stage=message,counts=counts))
        root=store.path(owner,pid);pdf=root/'manuscript/source.pdf'
        if pdf.is_file():
            async def attach():
                project=store.get(owner,pid);scope='?dt_workspace='+quote(project['native_id'])
                rows=await call(request,'GET','/api/knowledge-bases?resource_library=true&dt_workspace='+quote(project['native_id']))
                name=project['name']+' · 原始论文';found=next((v for v in rows if v.get('name')==name),None)
                if not found:found=await call(request,'POST','/api/knowledge-bases'+scope,data={'name':name,'rag_provider':'llamaindex','storage_workspace_id':project['native_id']},files=[('files',('最新作者稿.pdf',pdf.read_bytes(),'application/pdf')),('rel_paths',(None,'最新作者稿.pdf'))])
                config=store.get(owner,pid)['config'];config['knowledge_bases']=list(dict.fromkeys(config.get('knowledge_bases',[])+[found['id']]))
                config['literature_import']={'papers':1,'task_id':found.get('task_id'),'source':'private author import','processed_at':now()};config.pop('knowledge_error',None);store.update(owner,pid,config=config)
                return found.get('task_id')
            try:result['knowledge_task']=asyncio.run(attach())
            except Exception as error:
                message=str(getattr(error,'detail',error))[:400];config=store.get(owner,pid)['config'];config['knowledge_error']=message;store.update(owner,pid,config=config);result['knowledge_error']=message
        return result
    run_job(jid,build);return {'job_id':jid}


@app.get('/research/api/projects/{pid}/files')
async def files(pid:str,path:str='',mode:str='all',user=Depends(actor)):
    if mode not in ('all','images','code'):raise ValueError('文件视图无效')
    return store.inventory(user['id'],pid,path,mode)


@app.get('/research/api/projects/{pid}/file')
async def file_read(pid:str,path:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);target=child(store.path(owner,pid)/'project',path)
    if not target.is_file():raise KeyError('文件不存在')
    return FileResponse(target,filename=target.name,content_disposition_type='inline',headers={'Cache-Control':'private, no-cache'})


@app.post('/research/api/projects/{pid}/files')
async def upload_files(pid:str,path:str=Form(''),files:list[UploadFile]=File(...),user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);root=store.path(owner,pid)/'project';directory=child(root,path,allow_root=True)
    count=0
    for upload in files:
        name=Path(upload.filename or 'file').name
        target=child(root,(directory.relative_to(root)/name).as_posix())
        data=await upload.read(256*1024*1024+1)
        if len(data)>256*1024*1024:raise HTTPException(413,'单个上传文件最大256MiB；大数据使用集群目录')
        store.replace(owner,pid,target,data,'上传替换同名文件');count+=1
    return {'saved':count}


class TextFile(BaseModel):path:str;content:str;expected_modified:float|None=None;reason:str='网页编辑文件'


@app.put('/research/api/projects/{pid}/file')
async def save_file(pid:str,payload:TextFile,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);target=child(store.path(owner,pid)/'project',payload.path)
    if target.exists() and payload.expected_modified is not None and abs(target.stat().st_mtime-payload.expected_modified)>.01:raise Conflict('文件已更新，请重新打开')
    store.replace(owner,pid,target,payload.content.encode(),payload.reason.strip()[:160] or '网页编辑文件');return {'saved':True,'modified':target.stat().st_mtime}


class PathInput(BaseModel):path:str


@app.post('/research/api/projects/{pid}/folders')
async def create_folder(pid:str,payload:PathInput,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);target=child(store.path(owner,pid)/'project',payload.path)
    target.mkdir(parents=True,exist_ok=True);(target/'.gitkeep').touch();return {'created':payload.path}


@app.delete('/research/api/projects/{pid}/file')
async def delete_file(pid:str,path:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);target=child(store.path(owner,pid)/'project',path)
    return {'trash_id':store.discard(owner,pid,target,'手动移入垃圾箱')}


@app.get('/research/api/projects/{pid}/trash')
async def trash(pid:str,user=Depends(actor)):return {'items':store.trash(user['id'],pid)}


@app.post('/research/api/projects/{pid}/trash/{tid}/restore')
async def restore(pid:str,tid:str,user=Depends(actor)):return store.restore(user['id'],pid,tid)


@app.get('/research/api/projects/{pid}/image-context')
async def image_context(pid:str,path:str,user=Depends(actor)):
    from .reviews import image_context
    return await asyncio.to_thread(image_context,store,user['id'],pid,path)


def schedule_review_summary(owner,pid,native_headers):
    from .annotations import list_annotations,set_summary
    key=(owner,pid)
    prior=review_timers.get(key)
    if prior:prior.cancel()
    set_summary(store,owner,pid,'queued')
    def build():
        from .models import complete
        items=[x for x in list_annotations(store,owner,pid) if x['body'].strip() and x['status']!='deleted']
        if not items:set_summary(store,owner,pid,'ready',{'overview':'','questions':[]});return
        path=api_path(owner);settings=json.loads(path.read_text()) if path.exists() else {}
        project=store.get(owner,pid)
        try:
            set_summary(store,owner,pid,'running')
            prompt='根据项目中真实记录的用户批注，归纳本次需要解决的问题及相互关系。忠实保留问题，不添加用户没有提出的要求。按文献、程序、论文、PPT的内容线索整理；每项必须引用原问题id，保留文件/段落/页码线索。只输出JSON：{"overview":"简明连贯概述","groups":[{"title":"问题主题","question_ids":["原id"],"summary":"需处理什么"}]}。'
            source=json.dumps({'project':project['name'],'annotations':items},ensure_ascii=False)
            raw=complete(settings,native_headers,project['native_id'],prompt,source,BASE,True)
            value=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
            valid={x['id'] for x in items}
            if any(set(group.get('question_ids',[]))-valid for group in value.get('groups',[])):raise ValueError('总结引用了不存在的问题')
            set_summary(store,owner,pid,'ready',value)
        except Exception as error:set_summary(store,owner,pid,'waiting',error=str(error)[:400])
    timer=threading.Timer(4,lambda:pool.submit(build));timer.daemon=True;review_timers[key]=timer;timer.start()


@app.get('/research/api/projects/{pid}/annotations')
async def annotations(pid:str,area:str='',asset:str='',user=Depends(actor)):
    from .annotations import list_annotations
    return {'items':list_annotations(store,user['id'],pid,area,asset)}


@app.post('/research/api/projects/{pid}/annotations')
async def annotation_create(request:Request,pid:str,payload:dict,user=Depends(actor)):
    from .annotations import save_annotation
    result=save_annotation(store,user['id'],pid,payload)
    if result['body'].strip():schedule_review_summary(user['id'],pid,headers(request))
    return result


@app.patch('/research/api/projects/{pid}/annotations/{identifier}')
async def annotation_update(request:Request,pid:str,identifier:str,payload:dict,user=Depends(actor)):
    from .annotations import save_annotation,list_annotations
    if not any(x['id']==identifier for x in list_annotations(store,user['id'],pid)):raise KeyError('批注不存在')
    result=save_annotation(store,user['id'],pid,payload,identifier)
    schedule_review_summary(user['id'],pid,headers(request));return result


@app.get('/research/api/projects/{pid}/review-history')
async def review_history(pid:str,user=Depends(actor)):
    from .annotations import history
    return history(store,user['id'],pid)


def review_chat_path(owner,pid,area):
    if area not in ('slides','paper','literature','code'):raise ValueError('会话所属区域无效')
    return store.path(owner,pid)/'.workbench/review-chats'/(area+'.json')


async def sync_review_answers(request,project,path):
    rows=json.loads(path.read_text()) if path.exists() else [];updates={}
    for row in rows:
        if row.get('role')!='assistant' or row.get('content') or not row.get('session_url'):continue
        match=re.match(r'/chat/([A-Za-z0-9_-]+)\?',row['session_url'])
        if not match:continue
        try:
            session=await call(request,'GET','/api/sessions/'+match[1]+'?dt_workspace='+quote(project['native_id']))
            content='\n\n'.join(m['content'] for m in session.get('messages',[]) if m.get('role')=='assistant' and isinstance(m.get('content'),str) and m['content'].strip())
            if content:updates[row['id']]={'content':content,'session':match[1]}
        except HTTPException:continue
    with store.lock('review-chat:'+str(path)):
        current=json.loads(path.read_text()) if path.exists() else []
        if updates:
            for row in current:
                if row['id'] in updates:row.update(updates[row['id']])
            atomic_json(path,current)
        return current


@app.get('/research/api/projects/{pid}/review-chat')
async def review_chat(request:Request,pid:str,area:str,user=Depends(actor)):
    project=store.get(user['id'],pid);path=review_chat_path(user['id'],pid,area)
    return {'messages':await sync_review_answers(request,project,path)}


class ReviewMessage(BaseModel):
    area:str;asset:str;title:str='';quote:str='';locator:dict={};message:str


@app.post('/research/api/projects/{pid}/review-chat')
async def review_chat_send(request:Request,pid:str,payload:ReviewMessage,user=Depends(actor)):
    from .models import complete
    from .annotations import list_annotations,event
    owner=user['id'];project=store.get(owner,pid);path=review_chat_path(owner,pid,payload.area)
    if not payload.message.strip() or len(payload.message)>16000:raise ValueError('填写要讨论的内容')
    rows=await sync_review_answers(request,project,path)
    context={k:getattr(payload,k) for k in ('area','asset','title','quote','locator')}
    context['project_root']=str(store.path(owner,pid))
    recorded_context={**context,'locator':{k:v for k,v in context['locator'].items() if k!='current_draft'}}
    if context['locator'].get('current_draft'):
        draft=store.path(owner,pid)/'.workbench/current-drafts'/(payload.area+'.json');atomic_json(draft,context['locator']['current_draft']);recorded_context['locator']['draft_path']=str(draft);recorded_context['locator']['draft_revision']=context['locator']['current_draft'].get('revision')
    rows.append({'id':uuid.uuid4().hex,'role':'user','content':payload.message,'created':now(),'context':recorded_context});atomic_json(path,rows)
    settings_file=api_path(owner);settings=json.loads(settings_file.read_text()) if settings_file.exists() else {}
    notes=list_annotations(store,owner,pid,payload.area)
    prompt='结合当前材料位置和已有批注，回答或执行用户明确提出的要求。给出直接、简洁的答复。需要修改时落实到当前正式文件，并保留历史；没有完成的修改不得声称完成。'
    content=json.dumps({'current':context,'annotations':[{'id':n['id'],'body':n['body'],'page':n['locator'].get('page'),'asset':n['asset']} for n in notes if n['status']!='deleted'],'messages':rows[-12:]},ensure_ascii=False)
    if settings.get('api_key') and settings.get('model'):
        answer=await asyncio.to_thread(complete,settings,headers(request),project['native_id'],prompt,content,BASE,False,'slides' if payload.area=='slides' else 'review')
        message={'id':uuid.uuid4().hex,'role':'assistant','content':answer,'created':now()}
    else:
        await ensure_native_model(request)
        from .reviews import submit_review
        sent=await submit_review(BASE,headers(request),project,{'id':uuid.uuid4().hex,'attachment':'','capability':'code' if payload.area=='code' else 'chat'},prompt+'\n'+content,'')
        message={'id':uuid.uuid4().hex,'role':'assistant','content':'','created':now(),'session_url':sent['url']}
    rows.append(message);atomic_json(path,rows)
    event(store,owner,pid,'review.chat',{'area':payload.area,'asset':payload.asset,'page':payload.locator.get('page'),'message':payload.message})
    return {'message':message}


class ReviewSubmit(BaseModel):
    ids:list[str]
    attachments:list[dict]=Field(default_factory=list,max_length=10)
    session_id:str|None=None
    operation_id:str|None=Field(default=None,max_length=80,pattern=r'^[A-Za-z0-9_-]+$')


@app.get('/research/api/projects/{pid}/native-session')
async def native_session_identity(request:Request,pid:str,session_id:str,turn_id:str='',user=Depends(actor)):
    from .reviews import validate_native_identity
    project=store.get(user['id'],pid)
    identity=await validate_native_identity(request,project,session_id,turn_id)
    if not identity:raise ValueError('需要会话编号')
    return {**identity,'native_workspace_id':project['native_id']}


@app.post('/research/api/projects/{pid}/annotations/submit')
async def annotations_submit(request:Request,pid:str,payload:ReviewSubmit,user=Depends(actor)):
    from .annotations import list_annotations,question_prompt,save_annotation,event
    from .reviews import submit_review,validate_native_identity
    owner=user['id'];project=store.get(owner,pid);items=[x for x in list_annotations(store,owner,pid) if x['id'] in payload.ids]
    if not items or len(items)!=len(set(payload.ids)):raise ValueError('选择要发送的本项目问题')
    if not project.get('native_id'):raise HTTPException(409,'项目尚未绑定原生工作区')
    await validate_native_identity(request,project,payload.session_id)
    await ensure_native_model(request)
    operation_id=payload.operation_id or uuid.uuid4().hex
    # Association metadata must not change the causal prompt on a retry.
    context_items=[{**item,'locator':{k:v for k,v in item['locator'].items() if k not in
      ('session_url','native_session_id','native_turn_id','operation_id')}} for item in items]
    result=await submit_review(BASE,headers(request),project,{'id':operation_id,'attachment':'','capability':'code' if any(x['area'] in ('code','image') for x in items) else 'chat'},
      question_prompt(project,context_items),'',session_id=payload.session_id or '',operation_id=operation_id,attachments=payload.attachments)
    for item in items:save_annotation(store,owner,pid,{'status':'submitted','locator':{**item['locator'],'session_url':result['url'],
      'native_session_id':result['session_id'],'native_turn_id':result['turn_id'],'operation_id':operation_id}},item['id'])
    event(store,owner,pid,'questions.submitted',{'ids':payload.ids,**result})
    return result


class ImageReview(BaseModel):
    path:str;image:str;instruction:str;plot_program:str='';compute_program:str=''
    crop:dict|None=None;annotations:list[dict]=Field(default_factory=list);send:bool=True


class FigureEdit(BaseModel):
    path:str;revision:int;changes:dict;reason:str='调整图形样式';edit_session:str='';autosave:bool=False


class FigureMessage(BaseModel):
    path:str;message:str=Field(min_length=1,max_length=12000);revision:int=0;selection:list[str]=Field(default_factory=list);changes:dict=Field(default_factory=dict)
    image:str='';edit_session:str='';include_context:bool=True
    session_id:str|None=None
    operation_id:str|None=Field(default=None,max_length=80,pattern=r'^[A-Za-z0-9_-]+$')
    embedded:bool=False


@app.get('/research/api/projects/{pid}/figure/chat')
async def figure_chat_history(pid:str,path:str,user=Depends(actor)):
    store.get(user['id'],pid);child(store.path(user['id'],pid)/'project',path)
    file=store.path(user['id'],pid)/'.workbench/figure-chats'/(uuid.uuid5(uuid.NAMESPACE_URL,path).hex+'.json')
    return {'messages':json.loads(file.read_text()) if file.exists() else []}


@app.get('/research/api/projects/{pid}/figure/session')
async def figure_session(request:Request,pid:str,path:str,session_id:str,user=Depends(actor)):
    store.get(user['id'],pid);root=store.path(user['id'],pid)
    file=root/'.workbench/figure-chats'/(uuid.uuid5(uuid.NAMESPACE_URL,path).hex+'.json')
    records=json.loads(file.read_text()) if file.exists() else []
    if not any('/chat/'+session_id+'?' in m.get('session_url','') for m in records):raise HTTPException(403,'会话不属于此图的问题记录')
    project=store.get(user['id'],pid);result=await call(request,'GET','/api/sessions/'+quote(session_id,safe='')+'?dt_workspace='+quote(project['native_id']))
    return {'messages':result.get('messages',[]),'active_turn':result.get('active_turn'),'updated_at':result.get('updated_at')}


@app.post('/research/api/projects/{pid}/figure/chat')
async def figure_chat(request:Request,pid:str,payload:FigureMessage,user=Depends(actor)):
    from .figures import inspect,preview,merge_styles
    from .annotations import save_annotation,event
    from .models import complete
    owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid)
    if payload.embedded or payload.session_id:
        from .reviews import submit_figure_feedback
        await ensure_native_model(request)
        return await submit_figure_feedback(request,store,owner,pid,project,payload,BASE,headers(request))
    info=await asyncio.to_thread(inspect,store,owner,pid,payload.path)
    record=save_annotation(store,owner,pid,{'area':'image','asset':payload.path,'title':Path(payload.path).name,
      'body':payload.message,'locator':{'objects':payload.selection,'source_revision':payload.revision},'origin':'figure-chat'})
    schedule_review_summary(owner,pid,headers(request))
    file=root/'.workbench/figure-chats'/(uuid.uuid5(uuid.NAMESPACE_URL,payload.path).hex+'.json')
    messages=json.loads(file.read_text()) if file.exists() else []
    messages.append({'id':record['id'],'role':'user','content':payload.message,'created':now(),'objects':payload.selection});atomic_json(file,messages)
    settings_path=api_path(owner);settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    if not payload.include_context:
        answer_text=await asyncio.to_thread(complete,settings,headers(request),project['native_id'],'用户已移除当前文件索引。只根据对话回答，不读取或修改图形。',json.dumps({'message':payload.message,'history':messages[-8:]},ensure_ascii=False),BASE,False,'review')
        answer={'id':uuid.uuid4().hex,'role':'assistant','content':answer_text,'created':now()};result={'message':answer,'mode':'conversation'}
    elif payload.include_context and info.get('ready') and settings.get('api_key') and settings.get('model'):
        if payload.changes:info=await asyncio.to_thread(preview,store,owner,pid,payload.path,payload.changes,payload.revision,payload.edit_session)
        prompt='你是科研图形精修助手。用户当前正在操作真实 Matplotlib 图，不改变数据。根据对象目录和选择，把自然语言修改为有依据的样式增量；文本、字体、字号、颜色、线型、点型、图例、色图、色阶、子图间距等都通过现有属性实现。不能发明对象ID或属性。若要求涉及重新计算数据或当前不支持的图形结构，changes为空并说明需要修改源程序。只输出JSON：{"message":"简短说明实际可预览的改动或限制","changes":{"figure":{"width":英寸,"height":英寸,"font_family":"字体","font_size":字号,"wspace":0.2,"hspace":0.2},"objects":{"原对象ID":{"属性":"值"}}}}。只填写实际修改的属性。位置用move:{dx,dy}，为相对当前图宽高的位移，y向下。线对象属性：color,line_width,line_style,marker,marker_size,alpha,label；text/ticks：text(仅text),font_family,font_size,font_weight,font_style,color,rotation；field：cmap,vmin,vmax,levels(0连续或2至50离散),alpha；colorbar另有label,font_size,tick_font_size,tick_count；legend：font_size,font_family,columns,frame,color,background,alpha,location；axes：x,y,width,height(0至1坐标),grid。数据、单位和研究内容不随意改变。'
        source={'request':payload.message,'selected':payload.selection,'figure':info['figure'],'objects':info['objects'],'history':messages[-8:]}
        raw=await asyncio.to_thread(complete,settings,headers(request),project['native_id'],prompt,json.dumps(source,ensure_ascii=False),BASE,True,'figure')
        value=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()));patch=value.get('changes',{})
        combined=merge_styles(payload.changes,patch)
        await asyncio.to_thread(preview,store,owner,pid,payload.path,combined,payload.revision,payload.edit_session)
        answer={'id':uuid.uuid4().hex,'role':'assistant','content':str(value.get('message','已更新预览，保存后写入工作区。')),'created':now(),'changes':patch}
        result={'message':answer,'changes':combined,'mode':'preview'}
    else:
        await ensure_native_model(request)
        from .reviews import prepare_review,submit_review,image_context
        import base64
        context=await asyncio.to_thread(image_context,store,owner,pid,payload.path)
        image=child(root/'project',payload.path).read_bytes()
        if payload.image:encoded_image=payload.image
        else:
            from PIL import Image
            from io import BytesIO
            output=BytesIO()
            with Image.open(BytesIO(image)) as source:source.save(output,format='PNG')
            encoded_image='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
        prepared,prompt,encoded=await asyncio.to_thread(prepare_review,store,owner,pid,{'path':payload.path,'image':encoded_image,
          'instruction':payload.message,'plot_program':context.get('plot_program',''),'compute_program':context.get('compute_program','')})
        prompt+='\n当前未提交的图形编辑与选择（优先于磁盘旧状态）：'+json.dumps({'objects':payload.selection,'changes':payload.changes,'revision':payload.revision},ensure_ascii=False)
        response=await submit_review(BASE,headers(request),project,prepared,prompt,encoded)
        answer={'id':uuid.uuid4().hex,'role':'assistant','content':'已将此图、选中对象和修改要求交给伙伴。修改与验证过程会保留在关联会话。','created':now(),'session_url':response['url']}
        result={'message':answer,'mode':'code','session_id':response['session_id'],'url':response['url']}
    messages.append(answer);atomic_json(file,messages);event(store,owner,pid,'figure.chat.replied',{'asset':payload.path,'question_id':record['id'],'answer':answer})
    return result


@app.get('/research/api/projects/{pid}/figure')
async def figure_read(pid:str,path:str,edit_session:bool=False,user=Depends(actor)):
    from .figures import inspect,edit_session as start_edit_session
    return await asyncio.to_thread(start_edit_session if edit_session else inspect,store,user['id'],pid,path)


@app.get('/research/api/projects/{pid}/figure/svg')
async def figure_svg(pid:str,path:str,user=Depends(actor)):
    from .figures import inspect
    value=await asyncio.to_thread(inspect,store,user['id'],pid,path)
    if not value.get('ready'):raise KeyError('此图尚无可编辑矢量对象')
    return Response(value['svg'],media_type='image/svg+xml',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(Path(path).stem+'.svg')})


@app.post('/research/api/projects/{pid}/figure/preview')
async def figure_preview(pid:str,payload:FigureEdit,user=Depends(actor)):
    from .figures import preview
    return await asyncio.to_thread(preview,store,user['id'],pid,payload.path,payload.changes,payload.revision,payload.edit_session)


@app.post('/research/api/projects/{pid}/figure/save')
async def figure_save(request:Request,pid:str,payload:FigureEdit,user=Depends(actor)):
    from .figures import save
    result=await asyncio.to_thread(save,store,user['id'],pid,payload.path,payload.changes,payload.revision,payload.reason,payload.edit_session)
    owner=user['id'];root=store.path(owner,pid);refreshing=[]
    if result['updated_references'] and not payload.autosave:
        for format in ('docx','pdf'):
            if (root/'manuscript/exports'/('清稿.'+format)).exists():refreshing.append(await manuscript_export(request,pid,ExportInput(format=format),user))
        if (root/'slides/exports/研究汇报.pptx').exists() and store.get(owner,pid)['config'].get('slides_confirmation'):refreshing.append(await slides_export(request,pid,user))
    return {**result,'refreshing':refreshing}


@app.get('/research/api/figure-runtime')
async def figure_runtime(user=Depends(actor)):
    return PlainTextResponse((ROOT/'server/figure_artists.py').read_text(encoding='utf8'))


@app.get('/research/api/projects/{pid}/trash/{tid}/preview')
async def trash_preview(pid:str,tid:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid)
    with store.db() as db:row=db.execute('SELECT path FROM trash WHERE id=? AND owner=? AND project=?',(tid,owner,pid)).fetchone()
    if row is None:raise KeyError('历史文件不存在')
    target=Path(row['path']).resolve();root=(store.path(owner,pid)/'.trash').resolve()
    if not target.is_relative_to(root) or not target.is_file():raise KeyError('历史文件不存在')
    return FileResponse(target,content_disposition_type='inline')


@app.post('/research/api/projects/{pid}/image-review')
async def image_review(request:Request,pid:str,payload:ImageReview,user=Depends(actor)):
    from .reviews import prepare_review,submit_review
    owner=user['id'];project=store.get(owner,pid)
    record,prompt,image=await asyncio.to_thread(prepare_review,store,owner,pid,payload.model_dump())
    from .annotations import save_annotation
    question=save_annotation(store,owner,pid,{'area':'image','asset':payload.path,'title':Path(payload.path).name,
      'body':payload.instruction,'quote':'','locator':{'crop':payload.crop,'plot_program':payload.plot_program,
        'compute_program':payload.compute_program,'review_image':record.get('attachment'),'source_revision':record['source'].get('modified')},'origin':'image-review'})
    if not payload.send:return {'prepared':True,'id':record['id'],'prompt':prompt,'processed_at':record['processed_at']}
    schedule_review_summary(owner,pid,headers(request))
    result=await submit_review(BASE,headers(request),project,record,prompt,image)
    save_annotation(store,owner,pid,{'status':'submitted','locator':{**question['locator'],'session_url':result['url']}},question['id'])
    record.update(status='sent',**result);atomic_json(store.path(owner,pid)/'review/request.json',record)
    return {**result,'processed_at':record['processed_at'],'sent':True}


@app.get('/research/api/manuscript-templates')
async def templates(user=Depends(actor)):
    provenance=json.loads((ROOT/'templates/manuscripts/source/provenance.json').read_text(encoding='utf8'))
    source_keys={'chinese-mechanics':'chinese-mechanics','chinese':'chinese-user','elsevier':'cas','springer':'springer-aas','chinese-engineering':'chinese-engineering','cirp':'CIRP','rsc':'rsc','rsc-faraday':'rsc-faraday'}
    return {'templates':[{**t,'provenance':provenance.get(source_keys.get(t['id'],''),{}),'adaptation':not t.get('native',True)} for t in TEMPLATES]}



@app.get('/research/api/manuscript-template-preview/{kind}')
async def manuscript_template_preview(kind:str,user=Depends(actor)):
    if kind not in {t['id'] for t in TEMPLATES}:raise KeyError('模板不存在')
    path=DATA/'styles/previews'/(kind+'.png')
    spec=next(t for t in TEMPLATES if t['id']==kind)
    if spec.get('preview_pdf') and not path.is_file():
        import fitz
        path.parent.mkdir(parents=True,exist_ok=True)
        with fitz.open(ROOT/'templates/manuscripts/source'/spec['preview_pdf']) as pdf:pdf[0].get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(path)
    if not path.is_file():raise KeyError('模板预览尚未生成')
    return FileResponse(path)

@app.get('/research/api/manuscript-template-full/{kind}')
async def manuscript_template_full(kind:str,user=Depends(actor)):
    spec=next((t for t in TEMPLATES if t['id']==kind and t.get('primary')),None)
    if spec is None:raise KeyError('模板不存在')
    return FileResponse(ROOT/'templates/manuscripts/source'/spec['preview_pdf'],media_type='application/pdf',content_disposition_type='inline')


@app.get('/research/api/manuscript-template-source/{kind}')
async def manuscript_template_source(kind:str,user=Depends(actor)):
    spec=next((t for t in TEMPLATES if t['id']==kind),None)
    if not spec:raise KeyError('模板不存在')
    if spec.get('generic'):
        from .word_layout import make_reference
        path=make_reference(DATA/'runtime-home/generic-templates',kind,1)
    else:path=ROOT/'templates/manuscripts/source'/spec.get('original_file',spec['source_file'])
    return FileResponse(path,filename=path.name)


@app.get('/research/api/projects/{pid}/manuscript')
async def manuscript(pid:str,user=Depends(actor)):return store.manuscript(user['id'],pid)


@app.get('/research/api/projects/{pid}/references')
async def reference_library(pid:str,user=Depends(actor)):
    doc=store.manuscript(user['id'],pid)
    return {'items':doc.get('references',[]),'revision':doc['revision']}


@app.get('/research/api/projects/{pid}/references/search')
async def reference_search(pid:str,q:str,newest:bool=False,user=Depends(actor)):
    store.get(user['id'],pid)
    from .references import search
    settings=json.loads(api_path(user['id']).read_text()) if api_path(user['id']).exists() else {}
    try:
        from .literature_providers import resolve,PROVIDERS
        return {'items':await search(q,newest,settings=settings),'source':PROVIDERS[resolve(settings)][0]}
    except httpx.HTTPError:raise ValueError('文献检索服务暂不可用，请稍后重试')


@app.post('/research/api/projects/{pid}/references/recommend')
async def reference_recommend(request:Request,pid:str,payload:dict,user=Depends(actor)):
    from .references import text,search
    from .models import complete
    owner=user['id'];project=store.get(owner,pid);doc=store.manuscript(owner,pid)
    ref=next((r for r in doc.get('references',[]) if r['id']==payload.get('id')),None)
    if not ref:raise ValueError('请选择正文中的引用')
    context=next((text(n) for n in doc['content']['content'] if any(c.get('type')=='citation' and c.get('attrs',{}).get('refId')==ref['id'] for c in n.get('content',[]))),None)
    if not context:raise ValueError('该文献未在正文中使用')
    settings_file=api_path(owner);settings=json.loads(settings_file.read_text()) if settings_file.exists() else {}
    if not (settings.get('api_key') and settings.get('model')):await ensure_native_model(request)
    candidates=await search(payload.get('query') or ref.get('title') or ref['raw'],bool(payload.get('newest')),settings=settings)
    if not candidates:raise ValueError('没有查到可核验的候选文献')
    prompt='为科研稿件审阅引用。只能从提供的 Crossref 候选中选择，不编造题录和全文证据。候选只有元数据或摘要，不能声称核验了全文。判断是否足以支持原段落；不足时 selected=-1。若选择替换，谨慎修订引用所在段落，保留全部[数字]引用编号及顺序，不改变已有数值结果，不扩大结论。输出JSON：{"selected":0,"reason":"选择理由与证据限制","paragraph":"修订后的完整段落"}。'
    raw=await asyncio.to_thread(complete,settings,headers(request),project['native_id'],prompt,json.dumps({'reference':ref,'paragraph':context,'request':payload.get('instruction','查找更新或更相关的依据'),'candidates':candidates},ensure_ascii=False),BASE,True,'literature')
    proposal=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()));index=proposal.get('selected',-1)
    if not isinstance(index,int) or index < -1 or index>=len(candidates):raise ValueError('模型返回了未检索到的文献')
    return {'proposal':proposal,'entry':candidates[index] if index>=0 else None,'candidates':candidates,'expected_text':context,'revision':doc['revision'],'evidence':'metadata / available abstract'}


@app.post('/research/api/projects/{pid}/references/replace')
async def reference_replace(pid:str,payload:dict,user=Depends(actor)):
    from .references import replace
    return replace(store,user['id'],pid,payload['id'],payload['entry'],payload['revision'],payload.get('paragraph'),payload.get('expected_text'))


@app.post('/research/api/projects/{pid}/references')
async def reference_add(pid:str,payload:dict,user=Depends(actor)):
    doc=store.manuscript(user['id'],pid)
    if doc['revision']!=payload.get('revision'):raise ValueError('稿件已更新，请重新打开文献面板')
    entry=payload.get('entry',{})
    if not entry.get('title') or not entry.get('doi'):raise ValueError('请选择检索到的文献')
    for ref in doc.get('references',[]):
        if ref.get('doi','').lower()==entry['doi'].lower():return {'document':doc,'reference':ref}
    reference={**entry,'id':'ref-'+uuid.uuid4().hex[:16],'number':len(doc.get('references',[]))+1}
    doc['references']=[*doc.get('references',[]),reference];doc['reason']='加入参考文献：'+entry['title'][:100]
    return {'document':store.save_manuscript(user['id'],pid,doc),'reference':reference}


from .literature_folders import install as install_literature_folders
install_literature_folders(app,store)


@app.put('/research/api/projects/{pid}/manuscript')
async def save_manuscript(pid:str,payload:dict,user=Depends(actor)):return store.save_manuscript(user['id'],pid,payload)


@app.post('/research/api/projects/{pid}/manuscript/assets')
async def asset_upload(pid:str,file:UploadFile=File(...),user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg','.webp','.gif'):raise ValueError('插入PNG、JPG或WebP图片')
    data=await file.read(32*1024*1024+1)
    if len(data)>32*1024*1024:raise HTTPException(413,'图片最大32MiB')
    from PIL import Image
    from io import BytesIO
    with Image.open(BytesIO(data)) as image:image.verify()
    name=uuid.uuid4().hex+suffix;target=store.path(owner,pid)/'manuscript/assets'/name;store.replace(owner,pid,target,data,'上传论文图片')
    return {'src':f'/research/api/projects/{pid}/manuscript/assets/{name}','name':file.filename}


@app.post('/research/api/projects/{pid}/manuscript/import')
async def manuscript_import(pid:str,file:UploadFile=File(...),user=Depends(actor)):
    from .manuscripts import import_manuscript
    owner=user['id'];store.get(owner,pid);data=await file.read(32*1024*1024+1)
    if len(data)>32*1024*1024:raise HTTPException(413,'稿件最大32MiB')
    document=await asyncio.to_thread(import_manuscript,store.path(owner,pid),pid,data,file.filename or 'draft.docx')
    current=store.manuscript(owner,pid)
    # Explicit imports replace the current draft and retain its previous content in trash.
    path=store.path(owner,pid)/'manuscript/main.json'
    if path.exists():store.discard(owner,pid,path,'导入前的稿件')
    current.update(content=document,title=Path(file.filename or '研究稿件').stem,revision=0,comments=[])
    return store.save_manuscript(owner,pid,current)


@app.get('/research/api/projects/{pid}/manuscript/assets/{name}')
async def asset(pid:str,name:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);target=child(store.path(owner,pid)/'manuscript/assets',name)
    if not target.is_file():raise KeyError('图片不存在')
    return FileResponse(target)


@app.get('/research/api/projects/{pid}/manuscript/image-source')
async def manuscript_image_source(pid:str,src:str,user=Depends(actor)):
    from .figures import read_registry,manuscript_links
    owner=user['id'];root=store.path(owner,pid);store.get(owner,pid)
    match=re.fullmatch(r'/research/api/projects/'+re.escape(pid)+r'/manuscript/assets/([^/?#]+)',src)
    if not match:
        from urllib.parse import urlparse,parse_qs
        if not src.startswith('/research/api/projects/'+pid+'/file?'):raise ValueError('图片不属于当前项目')
        asset=parse_qs(urlparse(src).query).get('path',[''])[0];candidate=child(root/'project',asset)
        if not candidate.is_file():raise ValueError('工作台图片已移动')
        return {'path':asset,'editable':asset in read_registry(root)}
    image=child(root/'manuscript/assets',match[1]);data=image.read_bytes()
    for asset in read_registry(root):
        candidate=child(root/'project',asset)
        if candidate.is_file() and (image.name in manuscript_links(root,asset) or candidate.stat().st_size==len(data) and candidate.read_bytes()==data):return {'path':asset,'editable':True}
    target=root/'project/results'/image.name;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():target.write_bytes(data)
    return {'path':target.relative_to(root/'project').as_posix(),'editable':False}


def run_job(jid,callback):
    review_headers=quality_request_headers.get()
    with store.db() as database:job_row=database.execute('SELECT owner,project,kind FROM jobs WHERE id=?',(jid,)).fetchone()
    job_info=dict(job_row) if job_row else {}
    def run():
        try:
            store.set_job(jid,status='running');result=callback()
            if review_headers and isinstance(result,dict) and 'quality' not in result:
                kind=job_info.get('kind');stage={'literature-classify':'landscape','manuscript-export':'writing','manuscript-translate':'translation'}.get(kind)
                if stage:
                    from .quality_api import run_review
                    owner,pid=job_info['owner'],job_info['project'];root=store.path(owner,pid)
                    paths=['.workbench/literature-classification.json'] if stage=='landscape' else ['manuscript/exports/'+result['name']] if kind=='manuscript-export' else ['manuscript/main.json']
                    sources=['manuscript/main.json'] if kind=='manuscript-export' else ['manuscript/source.pdf'] if (root/'manuscript/source.pdf').is_file() else []
                    store.set_job(jid,step='review',stage='产物已保存，正在独立阶段评审')
                    try:quality=run_review(store,api_path,owner,pid,{'operation_id':'job-'+jid,'stage':stage,'artifact_paths':paths,'source_paths':sources,'intended_use':'按当前产物阶段和实际来源评价质量'},review_headers)
                    except Exception as review_error:quality={'decision':'evaluation_failed','can_proceed':False,'automatic_flow':False,'reason':str(review_error)[:500]}
                    result={**result,'quality':quality,'automatic_flow':quality.get('automatic_flow',False)}
            store.set_job(jid,status='completed',stage='已完成',result=result)
        except Exception as error:
            # Provider messages can echo endpoints; never include credentials.
            message=str(error)
            message=re.sub(r'(sk-[A-Za-z0-9_-]{10,})','[已隐藏]',message)
            store.set_job(jid,status='failed',stage='未完成',error=message[-800:])
    pool.submit(run)


class ExportInput(BaseModel):format:str;review:bool=False;language:str='auto';document_id:str='';columns:int=2;template:str='';filename:str='';preview:bool=False


@app.post('/research/api/projects/{pid}/manuscript/export')
async def manuscript_export(request:Request,pid:str,payload:ExportInput,user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid);document=store.manuscript(owner,pid)
    if payload.language not in ('auto','source','translation','reader'):raise ValueError('导出语言无效')
    if payload.columns not in (1,2):raise ValueError('栏数无效')
    chosen_template=payload.template or document.get('template','journal-zh')
    selected=next((t for t in TEMPLATES if t['id']==chosen_template),None)
    if not selected:raise ValueError('模板不存在')
    if selected.get('primary') and payload.format not in ('docx','pdf'):raise ValueError('原生 Word 模板支持 DOCX 或 PDF 导出')
    document={**document,'template':chosen_template}
    payload.columns=payload.columns if payload.columns in selected.get('columns',[1]) else selected['columns'][0]
    native_headers=headers(request);settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {}
    if payload.language=='translation':
        if not document.get('translation'):raise ValueError('尚无译文')
        document={**document,**document['translation'],'template':chosen_template}
    document={**document,'columns':payload.columns}
    if payload.language=='reader' and not re.fullmatch(r'[a-f0-9]{32}',payload.document_id):raise ValueError('选择当前阅读器的译文')
    jid=store.job(owner,pid,'manuscript-preview' if payload.preview else 'manuscript-export',{'subject':document['title'],'format':payload.format})
    def build():
        store.set_job(jid,step='prepare',stage='正在准备稿件与导出语言')
        export_doc=document
        if payload.language=='auto' and next((t for t in TEMPLATES if t['id']==chosen_template),{}).get('language')=='en':
            from .journals import english_document
            export_doc={**english_document(store,owner,pid,document,native_headers,settings,stage=lambda message:store.set_job(jid,stage=message)),'template':chosen_template,'columns':payload.columns}
        if payload.language=='reader':
            from .neoreader import translation_document
            export_doc=translation_document(store,owner,pid,payload.document_id,document)
        if chosen_template.startswith('generic-'):
            from .author_profile import prepare_preview,read_profile
            export_doc=prepare_preview(export_doc,read_profile(api_path,owner),'zh-CN' if chosen_template=='generic-zh' else 'en')
        if payload.review:
            from copy import deepcopy
            from .annotations import list_annotations
            notes=[n for n in list_annotations(store,owner,pid,'paper','manuscript/main.json') if n['status']!='deleted']
            if notes:
                export_doc=deepcopy(export_doc);appendix=[{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'批注记录'}]}]
                for n in sorted(notes,key=lambda n:(n['locator'].get('page',0),n['created'])):
                    location=('第 '+str(n['locator']['page'])+' 页 · ') if n['locator'].get('page') else ''
                    if n['quote']:appendix.append({'type':'paragraph','content':[{'type':'text','text':location+n['quote'],'marks':[{'type':'italic'}]}]})
                    appendix.append({'type':'paragraph','content':[{'type':'text','text':n['body'] or '高亮标记'}]})
                export_doc['content']['content'].extend(appendix)
        store.set_job(jid,step='layout',stage='正在生成稿件版式与文件')
        data,suffix,mime=export_manuscript(store.path(owner,pid),export_doc,payload.format,payload.review,DATA/'styles')
        name=('阅读器译文-' if payload.language=='reader' else '译文-' if payload.language=='translation' else '')+('审阅稿' if payload.review else '清稿')+'.'+suffix
        if payload.filename:
            proposed=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',payload.filename).strip(' .')[:160]
            name=(Path(proposed).stem or '稿件')+'.'+suffix
        target=store.path(owner,pid)/'manuscript/exports'/name
        store.set_job(jid,step='save',stage='正在保存导出文件')
        store.replace(owner,pid,target,data,'根据当前稿件重新导出'+('审阅稿' if payload.review else '清稿'))
        return {'name':name,'url':f'/research/api/projects/{pid}/download?area=manuscript&name='+quote(name),'mime':mime,'revision':document['revision']}
    run_job(jid,build);return {'job_id':jid}


@app.get('/research/api/projects/{pid}/download')
async def download(pid:str,area:str,name:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid)
    if area not in ('manuscript','slides'):raise ValueError('导出位置无效')
    target=child(store.path(owner,pid)/area/'exports',name)
    if not target.is_file():raise KeyError('导出文件不存在')
    return FileResponse(target,filename=target.name)


@app.get('/research/api/projects/{pid}/jobs')
async def jobs(pid:str,user=Depends(actor)):return {'jobs':store.jobs(user['id'],pid)}


@app.get('/research/api/projects/{pid}/jobs/events')
async def job_events(request:Request,pid:str,user=Depends(actor)):
    from .job_stream import progress_events
    store.get(user['id'],pid)
    return StreamingResponse(progress_events(store,user['id'],pid,request.is_disconnected),media_type='text/event-stream',headers={'Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no','Content-Encoding':'identity'})


def template_location(owner,pid,kind):
    store.get(owner,pid);root=store.path(owner,pid)
    if kind=='uploaded':source=root/'slides/template.pptx';output=root/'slides/template-preview'
    elif kind=='group':raise KeyError('私人模板仅限所有者在自己的项目中上传使用')
    else:
        from .presentation_catalog import visual
        spec=visual(kind);source=ROOT/'templates/presentations'/(spec['id']+'.pptx');output=DATA/'template-cache'/spec['id']
    if not source.is_file():raise KeyError('模板尚未准备完成')
    return source,output


@app.get('/research/api/projects/{pid}/slide-templates')
async def slide_templates(pid:str,user=Depends(actor)):
    from .presentation_catalog import catalog,PROFILES
    owner=user['id'];project=store.get(owner,pid);items=[]
    specs=catalog()['templates']+[{'id':'uploaded','name':project['config'].get('template_name','我的项目模板'),'basis':'仅限当前所有者与项目的私人模板','private':True}]
    for spec in specs:
        try:source,output=template_location(owner,pid,spec['id'])
        except KeyError:continue
        manifest=json.loads((output/'manifest.json').read_text()) if (output/'manifest.json').exists() else None
        if manifest and (manifest.get('style_version')!=2 or manifest.get('source_size')!=source.stat().st_size or manifest.get('source_modified')!=source.stat().st_mtime_ns):manifest=None
        items.append({**spec,'manifest':manifest})
    receipt=project['config'].get('slides_confirmation')
    return {'templates':items,'profiles':PROFILES,'layout':catalog()['layout'],'confirmation':receipt,
      'selected':project['config'].get('template','') if project['config'].get('template')!='group' else ''}


class PresentationConfirmation(BaseModel):
    template:str
    profile:str
    action:str='generate'


def confirmed_slides(owner,pid,receipt_id=None):
    project=store.get(owner,pid);receipt=project['config'].get('slides_confirmation')
    if not receipt or (receipt_id is not None and receipt.get('id')!=receipt_id):raise ValueError('请先确认演示模板与汇报类型，再生成PPT')
    if project['config'].get('template')!=receipt['template']:raise ValueError('模板已经改变，请重新确认生成设置')
    source,_=template_location(owner,pid,receipt['template'])
    if receipt.get('template_size')!=source.stat().st_size or receipt.get('template_modified')!=source.stat().st_mtime_ns:raise ValueError('模板文件已更换，请重新确认生成设置')
    return receipt


@app.post('/research/api/projects/{pid}/slides/confirm')
async def confirm_presentation(pid:str,payload:PresentationConfirmation,user=Depends(actor)):
    from .presentation_catalog import profile
    owner=user['id'];project=store.get(owner,pid);profile(payload.profile);source,_=template_location(owner,pid,payload.template)
    root=store.path(owner,pid);path=root/'slides/plan.json'
    plan=json.loads(path.read_text()) if path.is_file() else None
    if payload.action not in ('generate','restyle'):raise ValueError('生成操作无效')
    if payload.action=='restyle' and (not plan or plan.get('audience_profile')!=payload.profile):raise ValueError('汇报类型发生变化，请按新目的重新生成')
    receipt={'id':uuid.uuid4().hex,'template':payload.template,'profile':payload.profile,'confirmed_at':now(),'action':payload.action,
      'template_size':source.stat().st_size,'template_modified':source.stat().st_mtime_ns}
    config=project['config'];config.update(template=payload.template,slides_confirmation=receipt);store.update(owner,pid,config=config)
    if payload.action=='restyle':plan['confirmation_id']=receipt['id'];atomic_json(path,plan)
    return receipt


@app.post('/research/api/projects/{pid}/slide-templates/{kind}/prepare')
async def prepare_slide_template(pid:str,kind:str,user=Depends(actor)):
    owner=user['id'];source,output=template_location(owner,pid,kind);jid=store.job(owner,pid,'template',{'source_name':source.name})
    def build():
        store.set_job(jid,step='parse',stage='正在解析母版、版式与示例页')
        with store.lock('template:'+str(output)):
            manifest=prepare_template(source,output)
        store.set_job(jid,step='save',stage='模板预览与版式记录已保存')
        return {'template':kind,'slides':manifest['slide_count'],'layouts':len(manifest['layouts'])}
    run_job(jid,build);return {'job_id':jid}


@app.post('/research/api/projects/{pid}/slide-templates')
async def upload_template(pid:str,file:UploadFile=File(...),user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid)
    if not (file.filename or '').lower().endswith('.pptx'):raise ValueError('上传可编辑的PPTX模板')
    data=await file.read(100*1024*1024+1)
    if len(data)>100*1024*1024:raise HTTPException(413,'模板最大100MiB')
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(data)) as z:
        if 'ppt/presentation.xml' not in z.namelist():raise ValueError('PPTX文件无效')
    target=store.path(owner,pid)/'slides/template.pptx';store.replace(owner,pid,target,data,'替换PPT模板：'+(file.filename or '上传模板')[:80])
    preview=store.path(owner,pid)/'slides/template-preview'
    if preview.exists():shutil.rmtree(preview)
    config=project['config'];config.update(template='uploaded',template_name=file.filename);config.pop('slides_confirmation',None);store.update(owner,pid,config=config)
    return await prepare_slide_template(pid,'uploaded',user)


class TemplateChoice(BaseModel):template:str


@app.put('/research/api/projects/{pid}/slide-template')
async def choose_template(pid:str,payload:TemplateChoice,user=Depends(actor)):
    project=store.get(user['id'],pid);template_location(user['id'],pid,payload.template)
    config=project['config'];config['template']=payload.template;config.pop('slides_confirmation',None);store.update(user['id'],pid,config=config);return {'selected':payload.template}


@app.patch('/research/api/projects/{pid}/slide-templates/{kind}/roles')
async def template_roles(pid:str,kind:str,payload:dict,user=Depends(actor)):
    if kind!='uploaded':raise ValueError('内置模板的分类保持原样；上传自己的模板后可以调整')
    source,output=template_location(user['id'],pid,kind);manifest=json.loads((output/'manifest.json').read_text())
    from .slides import ROLES
    for key,page in payload.items():
        if key not in ROLES or not isinstance(page,int) or not 1<=page<=manifest['slide_count']:raise ValueError('页面分类无效')
    manifest['examples'].update(payload);atomic_json(output/'manifest.json',manifest);return manifest


@app.get('/research/api/projects/{pid}/slide-preview')
async def slide_preview(pid:str,kind:str='deck',page:int=1,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid)
    if kind=='deck':output=store.path(owner,pid)/'slides/preview'
    else:_,output=template_location(owner,pid,kind)
    if page<1:raise ValueError('页面不存在')
    target=output/f'page-{page}.png'
    if not target.is_file():raise KeyError('预览尚未完成')
    return FileResponse(target)


@app.get('/research/api/projects/{pid}/slides')
async def slides_get(pid:str,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid);path=store.path(owner,pid)/'slides/plan.json'
    return json.loads(path.read_text()) if path.exists() else {'title':store.get(owner,pid)['name'],'sections':[]}


@app.put('/research/api/projects/{pid}/slides')
async def slides_save(pid:str,payload:dict,user=Depends(actor)):
    owner=user['id'];store.get(owner,pid)
    if not isinstance(payload.get('sections'),list):raise ValueError('幻灯片结构无效')
    atomic_json(store.path(owner,pid)/'slides/plan.json',payload);return {'saved':True}


def api_path(owner):return DATA/'credentials'/uuid.uuid5(uuid.NAMESPACE_URL,owner).hex/'api.json'


@app.get('/research/api/api-settings')
async def api_settings(request:Request,user=Depends(actor)):
    path=api_path(user['id']);value=json.loads(path.read_text()) if path.exists() else {}
    from .translation import DEFAULT_PROMPT,PROMPT_SOURCE
    options=await call(request,'GET','/api/settings/llm-options')
    from .literature_providers import available
    return {'base_url':value.get('base_url',''),'model':value.get('model',''),'configured':bool(value.get('api_key')),'native_available':bool(options.get('options')),'literature_configured':bool(value.get('literature_token')),
      'literature_provider':value.get('literature_provider','auto'),'literature_providers':available(value),'scholar_configured':bool(value.get('scholar_api_key')),'wos_configured':bool(value.get('wos_api_key')),'web_search_configured':bool(value.get('web_search_api_key') or value.get('scholar_api_key')),'jcr_configured':bool(value.get('jcr_api_key')),
      'translation_prompt':value.get('translation_prompt') or DEFAULT_PROMPT,'prompt_source':PROMPT_SOURCE,
      **__import__('server.review_transport',fromlist=['public_settings']).public_settings(value)}


class APISettings(BaseModel):base_url:str='';model:str='';api_key:str='';translation_prompt:str='';literature_token:str='';literature_provider:str='auto';scholar_api_key:str='';wos_api_key:str='';web_search_api_key:str='';jcr_api_key:str='';reviewer_mode:str='inherit';reviewer_base_url:str='';reviewer_model:str='';reviewer_api_key:str='';reviewer_supports_vision:bool=False


@app.put('/research/api/api-settings')
async def api_settings_save(payload:APISettings,user=Depends(actor)):
    path=api_path(user['id']);value=json.loads(path.read_text()) if path.exists() else {}
    if payload.base_url and not payload.base_url.startswith('https://'):raise ValueError('API地址使用HTTPS')
    value.update(base_url=payload.base_url.rstrip('/'),model=payload.model)
    value['translation_prompt']=payload.translation_prompt.strip()
    if payload.api_key:value['api_key']=payload.api_key
    if payload.literature_token:value['literature_token']=payload.literature_token
    if payload.literature_provider not in ('auto','crossref','semantic','scholar','wos'):raise ValueError('未知的文献来源')
    value['literature_provider']=payload.literature_provider
    if payload.scholar_api_key:value['scholar_api_key']=payload.scholar_api_key
    if payload.wos_api_key:value['wos_api_key']=payload.wos_api_key
    if payload.web_search_api_key:value['web_search_api_key']=payload.web_search_api_key
    if payload.jcr_api_key:value['jcr_api_key']=payload.jcr_api_key
    if payload.reviewer_mode not in ('inherit','custom'):raise ValueError('未知的评审模型模式')
    if payload.reviewer_base_url and not payload.reviewer_base_url.startswith('https://'):raise ValueError('评审接口地址使用HTTPS')
    value.update(reviewer_mode=payload.reviewer_mode,reviewer_base_url=payload.reviewer_base_url.rstrip('/'),reviewer_model=payload.reviewer_model.strip(),reviewer_supports_vision=payload.reviewer_supports_vision)
    if payload.reviewer_api_key:value['reviewer_api_key']=payload.reviewer_api_key
    if payload.reviewer_mode=='custom':
        from .review_transport import reviewer_settings
        reviewer_settings(value)
    atomic_json(path,value);os.chmod(path,0o600);return {'saved':True,'configured':bool(value.get('api_key'))}


class PlanningInput(BaseModel):instruction:str='';length:str='medium';use_native:bool=True;confirmation_id:str=''


class TranslationInput(BaseModel):target:str='zh-CN';use_native:bool=True;source:str='source'


async def ensure_native_model(request):
    value=await call(request,'GET','/api/settings/llm-options')
    if not value.get('options'):raise ValueError('当前账户尚未分配 DeepTutor 模型，请在后台分配模型，或选择工作台 API 接口')


@app.post('/research/api/projects/{pid}/manuscript/translate')
async def manuscript_translate(request:Request,pid:str,payload:TranslationInput,user=Depends(actor)):
    from .translation import DEFAULT_PROMPT
    from .academic_translation import translate_document
    owner=user['id'];project=store.get(owner,pid);document=store.manuscript(owner,pid)
    if payload.source not in ('source','translation'):raise ValueError('翻译来源无效')
    basis=document
    if payload.source=='translation':
        if not document.get('translation'):raise ValueError('当前没有可用译稿')
        basis={**document,**document['translation'],'revision':document['revision']}
    if len(plain_document(document['content']).strip())<2:raise ValueError('先放入需要翻译的稿件')
    if payload.use_native:await ensure_native_model(request)
    path=api_path(owner);settings=json.loads(path.read_text()) if path.exists() else {}
    if not payload.use_native and not (settings.get('api_key') and settings.get('model')):raise ValueError('先在API设置中配置接口与模型')
    native_headers=headers(request);jid=store.job(owner,pid,'manuscript-translate',{'subject':document['title'],'target':payload.target})
    def build():
        import httpx
        store.set_job(jid,step='translate',stage='正在按段翻译，保留公式与版式')
        def invoke(prompt,body):
            from .standards import instructions
            prompt=instructions('translation',prompt)
            with httpx.Client(timeout=240,trust_env=False) as client:
                if payload.use_native:
                    response=client.post(BASE+'/api/documents/actions/edit?dt_workspace='+quote(project['native_id']),headers=native_headers,
                      json={'text':body,'instruction':prompt,'action':'rewrite'})
                    if not response.is_success:
                        try:message=response.json().get('detail','翻译接口未完成请求')
                        except Exception:message='翻译接口返回 HTTP '+str(response.status_code)
                        raise ValueError(str(message))
                    return response.json()['edited_text']
                response=client.post(settings['base_url'].rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+settings['api_key']},
                  json={'model':settings['model'],'messages':[{'role':'system','content':prompt},{'role':'user','content':body}],
                    'response_format':{'type':'json_object'}})
                response.raise_for_status();return response.json()['choices'][0]['message']['content']
        translated=translate_document(basis,payload.target,invoke,settings.get('translation_prompt') or DEFAULT_PROMPT,progress=lambda done,total:store.set_job(jid,step='translate',stage='正在翻译段落',counts={'done':done,'total':total,'unit':'段'}))
        store.set_job(jid,step='check',stage='正在核对译文与当前稿件版本')
        translated.update(updated=now(),generation_id=uuid.uuid4().hex)
        with store.lock(pid):
            current=store.manuscript(owner,pid)
            translated['stale']=current['content']!=document['content'] or current['title']!=document['title']
            if payload.source=='translation':translated['stale']=current.get('translation',{}).get('content')!=basis['content']
            translated['source_pane']=payload.source
            if current.get('translation'):
                previous=json.dumps(current['translation'],ensure_ascii=False).encode()
                archive=store.path(owner,pid)/'manuscript/translation-previous.json';archive.write_bytes(previous)
                store.discard(owner,pid,archive,'重新翻译，保留上一份译稿及批注')
            store.set_job(jid,step='save',stage='正在保存译稿与原稿对应关系')
            current['translation']=translated;store.save_manuscript(owner,pid,current)
        return {'language':payload.target,'segments':translated['segments'],'source_revision':document['revision']}
    run_job(jid,build);return {'job_id':jid}


@app.post('/research/api/projects/{pid}/slides/plan')
async def generate_plan(request:Request,pid:str,payload:PlanningInput,user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid);document=store.manuscript(owner,pid)
    receipt=confirmed_slides(owner,pid,payload.confirmation_id)
    from .presentation_catalog import generation_context
    template_source,template_preview=template_location(owner,pid,receipt['template'])
    from .slides import inspect_template
    inspected=await asyncio.to_thread(inspect_template,template_source,template_preview)
    selected_context=generation_context(receipt['template'],receipt['profile'],inspected)
    template_reading={k:inspected[k] for k in ('width','height','master_count','palette','examples')}
    template_reading['pages']=[{k:page.get(k) for k in ('page','role','title_box','body_box')} for page in inspected['slides']]
    selected_context+='\n已实际读取的模板结构（坐标和尺寸为EMU，字号为pt）：'+json.dumps(template_reading,ensure_ascii=False)
    if payload.length not in ('short','medium','long'):raise ValueError('汇报长度无效')
    if len(plain_document(document['content']).strip())<30:raise ValueError('先在论文区放入需要汇报的内容')
    if payload.use_native:await ensure_native_model(request)
    path=api_path(owner);api=json.loads(path.read_text()) if path.exists() else {}
    native_headers=headers(request);jid=store.job(owner,pid,'slides-plan',{'subject':document['title']})
    def build():
        store.set_job(jid,step='generate',stage='正在根据研究材料组织汇报内容')
        if payload.use_native:
            # Use the original account's model configuration without exposing its key.
            import httpx
            from . import slides as engine
            from .slides import source_elements
            import sys
            vendor=ROOT/'vendor'
            if str(vendor) not in sys.path:sys.path.insert(0,str(vendor))
            from paper2slides.generator import ContentPlanner,GenerationInput,GenerationConfig,OutputType,SlidesLength,StyleType
            from paper2slides.summary import GeneralContent,OriginalElements
            class NativePlanner(ContentPlanner):
                def __init__(self):pass
                def _truncate(self,value,max_len):return value
                def _fallback_sections(self):raise ValueError('模型返回的汇报结构无法解析；请重试或更换支持JSON输出的模型')
                def _call_multimodal_llm(self,text_prompt,figure_images):
                    from .models import native_edit_payload
                    instruction='根据输入稿件组织中文研究汇报，忠实保留原文证据，不平铺论文目录，不添加制作说明与额外小字。'+selected_context+'\n'+payload.instruction+'\n严格按以下规划要求只输出JSON：\n'+text_prompt
                    with httpx.Client(timeout=240,trust_env=False) as client:
                        r=client.post(BASE+'/api/documents/actions/edit?dt_workspace='+quote(project['native_id']),headers=native_headers,json=native_edit_payload(plain_document(document['content']),__import__('server.standards',fromlist=['instructions']).instructions('slides',instruction)))
                    r.raise_for_status();return r.json()['edited_text']
            config=GenerationConfig(output_type=OutputType.SLIDES,slides_length=SlidesLength(payload.length),style=StyleType.ACADEMIC)
            figures,tables=source_elements(document['content'],store.path(owner,pid))
            summary=plain_document(document['content'])+'\n\n可使用的原稿图表：\n'+'\n'.join(f['id']+': '+f['caption'] for f in figures)+'\n'+'\n'.join(t['id']+': '+json.dumps(t['rows'],ensure_ascii=False) for t in tables)
            result=NativePlanner().plan(GenerationInput(config,GeneralContent(content=summary),OriginalElements()))
            plan=result.to_dict();plan.update(title=document['title'],source_figures=figures,source_tables=tables,planner='HKUDS/Paper2Slides ContentPlanner + DeepTutor native model')
            if not plan.get('sections') or not any(s.get('content','').strip() for s in plan['sections']):raise ValueError('模型没有返回有效的幻灯片正文，请调整要求后重试')
            for i,section in enumerate(plan['sections']):section.setdefault('role','cover' if i==0 else 'ending' if section.get('type')=='ending' else 'content')
        else:
            if not api.get('api_key') or not api.get('model'):raise ValueError('先在API设置中配置接口与模型')
            plan=plan_with_paper2slides(document['content'],document['title'],store.path(owner,pid),api,selected_context+'\n'+payload.instruction,payload.length)
        confirmed_slides(owner,pid,receipt['id'])
        plan.update(confirmation_id=receipt['id'],audience_profile=receipt['profile'],visual_template=receipt['template'],template_inspection=template_reading)
        store.set_job(jid,step='save',stage='正在保存汇报内容计划')
        target=store.path(owner,pid)/'slides/plan.json'
        if target.exists():store.discard(owner,pid,target,'重新规划前的幻灯片')
        atomic_json(target,plan)
        from .quality_api import review_and_revise_plan
        store.set_job(jid,step='review',stage='正在评审汇报内容与来源支持')
        quality=review_and_revise_plan(store,api_path,owner,pid,{'operation_id':'slides-plan-'+jid,'stage':'slides-plan','purpose':receipt['profile'],'artifact_paths':['slides/plan.json'],'source_paths':['manuscript/main.json'],'intended_use':payload.instruction},native_headers)
        current=json.loads(target.read_text())
        return {'slides':len(current['sections']),'planner':current['planner'],'quality':quality,'automatic_flow':quality.get('automatic_flow',False)}
    run_job(jid,build);return {'job_id':jid}


@app.post('/research/api/projects/{pid}/slides/export')
async def slides_export(request:Request,pid:str,user=Depends(actor)):
    owner=user['id'];project=store.get(owner,pid);root=store.path(owner,pid);path=root/'slides/plan.json'
    receipt=confirmed_slides(owner,pid)
    if not path.is_file():raise ValueError('先整理幻灯片内容')
    from .quality_api import latest_gate
    quality_gate=latest_gate(store,owner,pid,'slides-plan',receipt['profile'])
    if not quality_gate['can_proceed']:raise Conflict('内容计划尚未通过当前版本的阶段评分，请先评审、修订或记录作者决定')
    plan=json.loads(path.read_text())
    if plan.get('confirmation_id')!=receipt['id']:raise ValueError('当前内容尚未按已确认的汇报设置生成')
    kind=receipt['template'];source,preview=template_location(owner,pid,kind)
    jid=store.job(owner,pid,'slides-export',{'subject':plan.get('title') or project['name'],'format':'pptx'})
    def build():
        store.set_job(jid,step='build',stage='正在填充可编辑幻灯片版式')
        manifest=json.loads((preview/'manifest.json').read_text()) if (preview/'manifest.json').exists() else None
        if not manifest or manifest.get('style_version')!=2 or manifest.get('source_size')!=source.stat().st_size or manifest.get('source_modified')!=source.stat().st_mtime_ns:manifest=prepare_template(source,preview)
        temp=Path(tempfile.mkdtemp(prefix='deck-',dir=root/'slides'))
        try:
            output=temp/'研究汇报.pptx';report=make_deck(source,manifest,plan,output)
            store.set_job(jid,step='render',stage='正在生成逐页预览')
            renders=temp/'preview';render_presentation(output,renders)
            from .slide_quality import verify_rendered
            store.set_job(jid,step='check',stage='正在检查页面文字、边界与重叠')
            report['render_validation']=verify_rendered(renders/'研究汇报.pdf',report.pop('visible_text'))
            report['visual_template']=kind;report['audience_profile']=receipt['profile']
            confirmed_slides(owner,pid,receipt['id'])
            store.set_job(jid,step='save',stage='正在保存 PowerPoint 与 PDF')
            for name in ['研究汇报.pptx','研究汇报.pdf']:
                file=output if name.endswith('pptx') else renders/'研究汇报.pdf'
                store.replace(owner,pid,root/'slides/exports'/name,file.read_bytes(),'根据当前汇报内容和模板重新导出')
            if json.loads((root/'slides/plan.json').read_text())!=plan:atomic_json(root/'slides/plan.json',plan)
            atomic_json(root/'slides/verification.json',report)
            from .quality_api import run_review
            store.set_job(jid,step='review',stage='正在评审实际导出的汇报文件')
            quality=run_review(store,api_path,owner,pid,{'operation_id':'slides-export-'+jid,'stage':'slides-export','purpose':receipt['profile'],'artifact_paths':['slides/exports/研究汇报.pptx'],'source_paths':['manuscript/main.json'],'intended_use':'按已确认用途审查实际可编辑导出'},headers(request))
            report['quality']=quality
            target=root/'slides/preview'
            if target.exists():shutil.rmtree(target)
            shutil.move(str(renders),str(target));atomic_json(root/'slides/verification.json',report)
            return {**report,'name':'研究汇报.pptx','url':f'/research/api/projects/{pid}/download?area=slides&name='+quote('研究汇报.pptx'),'pdf_url':f'/research/api/projects/{pid}/download?area=slides&name='+quote('研究汇报.pdf')}
        finally:shutil.rmtree(temp)
    run_job(jid,build);return {'job_id':jid}




@app.get('/research/api/storage')
async def account_storage(user=Depends(actor)):
    from .workspace_files import usage
    return await asyncio.to_thread(usage,store,user['id'])


@app.get('/research/api/projects/{pid}/trash/{tid}/diff')
async def readable_history(pid:str,tid:str,user=Depends(actor)):
    from .workspace_files import revision_diff
    return revision_diff(store,user['id'],pid,tid)


from .literature import install as install_literature
install_literature(app,store,api_path,run_job)
from .knowledge_sources import install as install_knowledge_sources
install_knowledge_sources(app,store,api_path)
from .project_canvas import install as install_project_canvas
install_project_canvas(app,store,api_path)
from .research_flow import install as install_research_flow
install_research_flow(app,store,api_path,run_job)

from .download_bridge import install as install_download_bridge
install_download_bridge(app,store,api_path)


@app.post('/research/api/projects/{pid}/image/save')
async def save_raster(pid:str,payload:dict,user=Depends(actor)):
    import base64
    from io import BytesIO
    from PIL import Image
    owner=user['id'];store.get(owner,pid);path=child(store.path(owner,pid)/'project',str(payload.get('path','')))
    if not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.gif'):raise ValueError('选择项目中的图片')
    expected=payload.get('expected_modified')
    if expected is not None and abs(path.stat().st_mtime-float(expected))>.01:raise Conflict('原图已由其他操作更新，请重新打开')
    encoded=str(payload.get('image',''))
    if not encoded.startswith('data:image/png;base64,') or len(encoded)>140*1024**2:raise ValueError('保存需要完整的 PNG 图像')
    data=base64.b64decode(encoded.split(',',1)[1],validate=True)
    with Image.open(BytesIO(data)) as image:
        image.load();output=BytesIO();kind={'.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP','.gif':'GIF'}.get(path.suffix.lower(),'PNG')
        (image.convert('RGB') if kind=='JPEG' else image).save(output,format=kind,quality=95);data=output.getvalue()
    store.replace(owner,pid,path,data,'保存图片标记与编辑');return {'saved':True,'modified':path.stat().st_mtime}

from .related_papers import install as install_related_papers
related_daily_updates=install_related_papers(app,store,api_path,pool)

from .journals import install as install_journals
install_journals(app,store,pool,api_path)
from .author_profile import install as install_author_profile
install_author_profile(app,api_path,store)
from .literature_network import install as install_literature_network
install_literature_network(app,store,api_path)
from .template_discovery import install as install_template_discovery
install_template_discovery(app,store,api_path)
from .knowledge_search import install as install_knowledge_search
install_knowledge_search(app,store)
from .chat_materials import install as install_chat_materials
install_chat_materials(app,store,run_job)
from .integration import install as install_integration
install_integration(app)
from .quality_api import install as install_quality
install_quality(app,store,api_path,run_job)
from .desktop_manifest import install as install_desktop_manifest
install_desktop_manifest(app,actor,call,DATA)

from .writing import install as install_writing
writing_service=install_writing(app,store)
from .paper_maps import install as install_paper_maps
paper_maps_service=install_paper_maps(app,store)


from .research_overview import install as install_research_overview
install_research_overview(app,store,actor)
from .research_outline import install as install_research_outline
install_research_outline(app,store,api_path,run_job)
from .research_updates import install as install_research_updates
install_research_updates(app,store)

if (ROOT/'static').is_dir():
    class ImmutableAssets(StaticFiles):
        async def get_response(self,path,scope):
            response=await super().get_response(path,scope)
            if response.status_code in (200,304):response.headers['Cache-Control']='public, max-age=31536000, immutable'
            return response
    app.mount('/research/assets',ImmutableAssets(directory=ROOT/'static/assets'),name='research-assets')
    if (ROOT/'static/fonts').is_dir():
        app.mount('/research/fonts',StaticFiles(directory=ROOT/'static/fonts'),name='research-fonts')
    @app.get('/research')
    @app.get('/research/{rest:path}')
    async def index(rest:str=''):
        if rest=='api' or rest.startswith('api/'):raise HTTPException(404,'工作台接口不存在')
        return FileResponse(ROOT/'static/index.html',headers={'Cache-Control':'no-store','X-Workbench-Release':'2026.11.01-workspace'})


from .pdf_translation import install as install_pdf_translation
install_pdf_translation(app,store,pool,run_job)
