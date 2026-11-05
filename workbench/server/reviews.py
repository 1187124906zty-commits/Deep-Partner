"""Image provenance and native DeepTutor hand-off for figure refinement."""
from pathlib import Path
from io import BytesIO
from http.cookies import SimpleCookie
from urllib.parse import quote
import asyncio,base64,json,re,uuid
from PIL import Image
from fastapi import HTTPException
from .storage import child,atomic_json,now


def image_context(store,owner,pid,path):
    root=store.path(owner,pid);program=root/'project';file=child(program,path)
    if not file.is_file():raise KeyError('图片不存在')
    index=root/'review/asset-index.json';links=json.loads(index.read_text()) if index.exists() else {}
    from .figures import read_registry,manuscript_links
    registered=read_registry(root).get(path,{})
    known={**links.get(path,{}),**{k:v for k,v in registered.items() if k in ('plot_program','compute_program')}}
    from .references import text as node_text
    manuscript=store.manuscript(owner,pid);blocks=manuscript.get('content',{}).get('content',[]);embedded=manuscript_links(root,path);usages=[];section='';sections={}
    for j,block in enumerate(blocks):
        if block.get('type')=='heading':section=node_text(block)
        sections[j]=section
    section=''
    from urllib.parse import urlparse,parse_qs
    for i,node in enumerate(blocks):
        if node.get('type')=='heading':section=node_text(node)
        if node.get('type')!='image':continue
        src=node.get('attrs',{}).get('src','');direct=parse_qs(urlparse(src).query).get('path',[''])[0]
        if direct!=path and src.split('/')[-1] not in embedded:continue
        caption=node.get('attrs',{}).get('title','')
        if i+1<len(blocks) and re.match(r'^(?:Fig(?:ure)?\.?|图)\s*\d+',node_text(blocks[i+1]),re.I):caption=node_text(blocks[i+1])
        number=re.match(r'^(?:Fig(?:ure)?\.?|图)\s*(\d+)',caption,re.I)
        sentences=[(j,node_text(n)) for j,n in enumerate(blocks) if j!=i+1 and n.get('type')=='paragraph' and number and re.search(r'(?:Fig(?:ure)?s?\.?|图)\s*'+re.escape(number[1])+r'\b',node_text(n),re.I)]
        for j,sentence in sentences or [(i,'')]:
            if not any(u['block']==j and u['caption']==caption for u in usages):usages.append({'section':sections[j],'image_section':section,'caption':caption,'sentence':sentence,'block':j,'figure_block':i})
    usages.sort(key=lambda u:u['block'])
    programs=[];matches=[]
    for candidate in program.rglob('*'):
        if not candidate.is_file() or candidate.suffix.lower() not in ('.py','.m','.r','.jl','.ipynb','.sh'):continue
        if any(p in ('.git','.venv','node_modules','__pycache__') for p in candidate.relative_to(program).parts):continue
        relative=candidate.relative_to(program).as_posix();programs.append(relative)
        if len(matches)<12 and candidate.stat().st_size<1024*1024:
            text=candidate.read_text(encoding='utf8',errors='replace')
            if file.name in text:matches.append(relative)
        if len(programs)>=300:break
    with Image.open(file) as image:width,height=image.size
    return {'path':path,'absolute_path':str(file),'width':width,'height':height,'size':file.stat().st_size,
            'usages':usages,'modified':file.stat().st_mtime,'programs':sorted(programs),'references':matches,
            'plot_program':known.get('plot_program',''),'compute_program':known.get('compute_program',''),
            'updated':known.get('updated'),'last_request':known.get('instruction','')}


def prepare_review(store,owner,pid,payload):
    root=store.path(owner,pid);context=image_context(store,owner,pid,payload['path'])
    instruction=payload.get('instruction','').strip()
    if not instruction:raise ValueError('填写希望伙伴修改的内容')
    program=root/'project'
    links={k:payload.get(k,'').strip() for k in ('plot_program','compute_program')}
    for value in links.values():
        if value and not child(program,value).is_file():raise ValueError('关联程序不在当前项目中')
    encoded=payload.get('image','')
    if not encoded.startswith('data:image/png;base64,'):raise ValueError('审阅图片需要PNG格式')
    data=base64.b64decode(encoded.split(',',1)[1],validate=True)
    if len(data)>24*1024*1024:raise ValueError('审阅图片过大，请缩小截图范围')
    with Image.open(BytesIO(data)) as image:image.verify()
    review=root/'review';review.mkdir(exist_ok=True)
    stem=re.sub(r'[^A-Za-z0-9_\-\u4e00-\u9fff]','_',Path(payload['path']).stem)[:70] or 'figure'
    attachment=review/(stem+'-review.png')
    store.replace(owner,pid,attachment,data,instruction[:140])
    record={'id':uuid.uuid4().hex,'source':context,'instruction':instruction,'crop':payload.get('crop'),
            'annotations':payload.get('annotations',[]),'attachment':str(attachment),**links,'processed_at':now(),'status':'prepared'}
    target=review/'request.json';store.replace(owner,pid,target,json.dumps(record,ensure_ascii=False,indent=2).encode(),instruction[:140])
    index=review/'asset-index.json';all_links=json.loads(index.read_text()) if index.exists() else {}
    all_links[payload['path']]={**links,'instruction':instruction,'updated':now()};atomic_json(index,all_links)
    text='请根据这张图的审阅标记和要求精修当前研究项目。\n\n'+instruction+'\n\n原图索引：'+context['absolute_path']
    if links['plot_program']:text+='\n绘图程序：'+str(child(program,links['plot_program']))
    if links['compute_program']:text+='\n计算程序：'+str(child(program,links['compute_program']))
    text+='\n审阅附件：'+str(attachment)+'\n审阅记录：'+str(target)
    text+='\n修改应落实到相关程序和当前图，保留科学数据与单位。正式目录只放最新版，替换前将旧文件移到工作台垃圾箱，并简明记录修改原因与处理时间。'
    return record,text,base64.b64encode(data).decode()


def review_identity(value, name, maximum=160):
    if value in (None,''):return ''
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,'+str(maximum)+r'}',value):
        raise ValueError(name+'无效')
    return value


async def validate_native_identity(request,project,session_id='',turn_id=''):
    """Resolve only through the caller's authenticated, project-scoped native store."""
    from .native import call
    session_id=review_identity(session_id,'会话编号');turn_id=review_identity(turn_id,'执行编号')
    if turn_id and not session_id:raise ValueError('执行编号需要对应的会话编号')
    if not session_id:return {}
    if not project.get('native_id'):raise HTTPException(409,'项目尚未绑定原生工作区')
    session=await call(request,'GET','/api/sessions/'+quote(session_id,safe='')+'?dt_workspace='+quote(project['native_id'],safe=''))
    actual=session.get('id') or session.get('session_id')
    if actual!=session_id:raise HTTPException(404,'会话不属于当前项目工作区')
    workspace=session.get('workspace_id',(session.get('preferences') or {}).get('workspace_id'))
    if workspace is not None and workspace!=project['native_id']:
        raise HTTPException(404,'会话不属于当前项目工作区')
    if turn_id:
        known={session.get('active_turn_id')}
        for key in ('active_turn','active_turns','turns'):
            values=session.get(key) or []
            if isinstance(values,dict):values=[values]
            for turn in values:
                if isinstance(turn,dict):known.add(turn.get('id') or turn.get('turn_id'))
        for message in session.get('messages',[]):
            known.add((message.get('metadata') or {}).get('turn_id'))
            for event in message.get('events') or []:
                if isinstance(event,dict):known.add(event.get('turn_id'))
        if turn_id not in known:raise HTTPException(404,'执行不属于当前项目会话')
    return {'session_id':session_id,**({'turn_id':turn_id} if turn_id else {})}


async def submit_review(base,native_headers,project,record,text,image,*,session_id='',operation_id='',attachments=None):
    from .standards import instructions
    text=instructions('code' if record.get('capability')=='code' or image else 'review',text)
    from websockets.asyncio.client import connect
    session_id=review_identity(session_id,'会话编号')
    operation_id=review_identity(operation_id or record.get('operation_id') or record['id'],'操作编号',80)
    url=base.replace('https://','wss://').replace('http://','ws://')+'/ws?dt_workspace='+quote(project['native_id'],safe='')
    # Native WS authentication consumes dt_token cookies, not Authorization
    # headers. Keep bearer values out of the WS URL and server access logs.
    cookie=native_headers.get('Cookie','')
    scheme,_,token=native_headers.get('Authorization','').partition(' ')
    if scheme.lower()=='bearer' and token:
        cookies=SimpleCookie();cookies.load(cookie);cookies['dt_token']=token
        cookie=cookies.output(header='',sep=';').strip()
    payload={'type':'start_turn','protocol_version':'2.0','content':text,'capability':record.get('capability','code' if image else 'chat'),
      'client_submission_id':'workbench-review-'+operation_id,'workspace_id':project['native_id'],
      'attachments':[{'type':'image','filename':Path(record['attachment']).name,'mime_type':'image/png','base64':image}] if image else []}
    if attachments:
        for attachment in attachments:
            if not isinstance(attachment,dict) or attachment.get('type') not in ('image','file','document','audio'):raise ValueError('附件类型无效')
            if len(str(attachment.get('base64','')))>28*1024**2:raise ValueError('附件过大')
        payload['attachments'].extend(attachments)
    if session_id:payload['session_id']=session_id
    async with connect(url,origin=native_headers['Origin'],additional_headers={'Cookie':cookie},open_timeout=15,max_size=8*1024*1024) as socket:
        await socket.send(json.dumps(payload))
        accepted_session='';accepted_turn=''
        async with asyncio.timeout(40):
            while True:
                event=json.loads(await socket.recv())
                if event.get('type') in ('protocol_error','error'):raise ValueError(event.get('message') or event.get('content') or '伙伴未接收审阅请求')
                accepted_session=event.get('session_id') or accepted_session
                accepted_turn=event.get('turn_id') or accepted_turn
                if accepted_session and accepted_turn:
                    if session_id and accepted_session!=session_id:raise ValueError('原生执行返回了不同的会话')
                    return {'session_id':accepted_session,'turn_id':accepted_turn,'operation_id':operation_id,
                      'url':'/chat/'+quote(accepted_session,safe='')+'?dt_workspace='+quote(project['native_id'],safe='')}


async def submit_figure_feedback(request,store,owner,pid,project,payload,base,native_headers):
    """Keep canvas drafts as figure evidence and continue the native conversation."""
    from .annotations import save_annotation,event
    from .figures import inspect,preview
    if not project.get('native_id'):raise HTTPException(409,'项目尚未绑定原生工作区')
    await validate_native_identity(request,project,payload.session_id)
    operation_id=review_identity(payload.operation_id or uuid.uuid4().hex,'操作编号',80)
    root=store.path(owner,pid)
    draft={'objects':payload.selection,'changes':payload.changes,'revision':payload.revision,
           'edit_session':payload.edit_session,'include_context':payload.include_context}
    if payload.include_context:
        info=await asyncio.to_thread(inspect,store,owner,pid,payload.path)
        if info.get('ready'):
            # Use the existing renderer to check the exact draft/revision/session.
            await asyncio.to_thread(preview,store,owner,pid,payload.path,payload.changes,payload.revision,payload.edit_session)
        context=await asyncio.to_thread(image_context,store,owner,pid,payload.path)
        encoded_image=payload.image
        if not encoded_image:
            output=BytesIO()
            with Image.open(child(root/'project',payload.path)) as source:source.save(output,format='PNG')
            encoded_image='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
        prepared,prompt,encoded=await asyncio.to_thread(prepare_review,store,owner,pid,{
          'path':payload.path,'image':encoded_image,'instruction':payload.message,
          'plot_program':context.get('plot_program',''),'compute_program':context.get('compute_program',''),
          'annotations':[draft]})
        prompt+='\n当前未保存的图形编辑与选择（优先于磁盘旧状态）：'+json.dumps(draft,ensure_ascii=False)
        prepared['capability']='code'
    else:
        # Explicitly removed context stays removed: no screenshot, object index or draft is sent.
        child(root/'project',payload.path)
        prepared={'id':operation_id,'attachment':'','capability':'chat'}
        prompt='用户已移除当前文件索引。只根据当前会话和以下问题回答，不读取或修改图形。\n'+payload.message
        encoded=''
    question_id=uuid.uuid5(uuid.NAMESPACE_URL,owner+'/'+pid+'/figure-feedback/'+operation_id).hex
    question=save_annotation(store,owner,pid,{'area':'image','asset':payload.path,'title':Path(payload.path).name,
      'body':payload.message,'locator':{'objects':payload.selection,'source_revision':payload.revision,
        'changes':payload.changes,'edit_session':payload.edit_session,'operation_id':operation_id,
        'include_context':payload.include_context},'origin':'figure-chat'},question_id)
    result=await submit_review(base,native_headers,project,prepared,prompt,encoded,
      session_id=payload.session_id or '',operation_id=operation_id)
    save_annotation(store,owner,pid,{'status':'submitted','locator':{**question['locator'],
      'native_session_id':result['session_id'],'native_turn_id':result['turn_id'],'session_url':result['url']}},question_id)
    event(store,owner,pid,'figure.feedback.submitted',{'asset':payload.path,'question_id':question_id,
      'source_revision':payload.revision,'objects':payload.selection,**result})
    return {**result,'mode':'code' if payload.include_context else 'conversation','question_id':question_id}
