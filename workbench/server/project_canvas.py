"""A source-bound view of project activity and separately scoped account memory."""
from collections import Counter
from urllib.parse import quote
import asyncio,json,time,uuid
from fastapi import Depends,HTTPException,Request
from .native import actor,call,text_call
from .storage import atomic_json,now


def record_retrieval(store,owner,pid,value):
    root=store.path(owner,pid);path=root/'.workbench/retrieval-events.json'
    event={'id':uuid.uuid4().hex,'time':now(),'query':value.get('query'),'mode':value.get('mode'),'knowledge_base':value.get('knowledge_base'),'source':value.get('source'),'count':len(value.get('items',[])) if isinstance(value.get('items'),list) else None,'items':[{k:row.get(k) for k in ('title','asset','library','url','score')} for row in value.get('items',[])[:20]],'errors':value.get('errors',[]),'scope':'project'}
    with store.lock(pid):
        rows=json.loads(path.read_text()) if path.exists() else [];rows.append(event);atomic_json(path,rows[-200:])
    return value


def belongs_to_project(event,project,session_ids,unique_names):
    payload=event.get('payload') or {};workspace=payload.get('workspace_id') or payload.get('workspace')
    if workspace:return workspace==project['native_id']
    if event.get('session_id'):return event['session_id'] in session_ids
    kb=payload.get('kb_name') or payload.get('knowledge_base') or ''
    if kb in project['config'].get('knowledge_bases',[]):return True
    return bool(kb and kb in unique_names)


def tool_events(session):
    rows=[]
    for message in session.get('messages',[]):
        for index,event in enumerate(message.get('events') or []):
            if event.get('type') not in ('tool_call','tool_result'):continue
            meta=event.get('metadata') or {};tool=meta.get('tool_name') or event.get('tool_name') or meta.get('name')
            arguments=meta.get('arguments') or meta.get('tool_args') or event.get('arguments') or {}
            if isinstance(arguments,str):
                try:arguments=json.loads(arguments)
                except ValueError:arguments={}
            if not tool:continue
            rows.append({'id':str(message.get('id',''))+':'+str(index),'tool':tool,'type':event['type'],'time':event.get('timestamp') or message.get('timestamp') or message.get('created_at'),'session_id':session.get('session_id') or session.get('id'),'query':arguments.get('query') or arguments.get('question'),'knowledge_base':arguments.get('kb_name') or arguments.get('knowledge_base'),'status':meta.get('status') or ('completed' if event['type']=='tool_result' else 'called')})
    return rows[-80:]


def install(app,store,api_path):
    async def fetch(request,path,errors):
        try:return await call(request,'GET',path)
        except HTTPException as e:errors.append({'source':path.split('?')[0],'status':e.status_code});return {}

    @app.get('/research/api/projects/{pid}/canvas')
    async def canvas(request:Request,pid:str,scope:str='project',user=Depends(actor)):
        if scope not in ('project','account'):raise ValueError('画布范围无效')
        owner=user['id'];project=store.get(owner,pid);errors=[];query='?dt_workspace='+quote(project['native_id'])
        sessions,knowledge,overview,runs=await asyncio.gather(fetch(request,'/api/sessions'+query+'&workspace_id='+quote(project['native_id'])+'&limit=100',errors),fetch(request,'/api/knowledge-bases?resource_library=true',errors),fetch(request,'/api/memory/overview',errors),fetch(request,'/api/memory/runs',errors))
        sessions=sessions.get('sessions',[]);ids={s.get('session_id') or s.get('id') for s in sessions}
        all_kbs=knowledge if isinstance(knowledge,list) else [];bound=project['config'].get('knowledge_bases',[]);name_counts=Counter(k.get('name') for k in all_kbs)
        kbs=[k for k in all_kbs if (k.get('id') or k.get('name')) in bound]
        unique_names={k.get('name') for k in kbs if name_counts[k.get('name')]==1}
        labels_path=api_path(owner).with_name('knowledge-names.json');labels=json.loads(labels_path.read_text()) if labels_path.exists() else {}
        kb_details=await asyncio.gather(*(fetch(request,'/api/knowledge-bases/'+quote(k.get('id') or k['name'],safe='')+query,errors) for k in kbs))
        for k,details in zip(kbs,kb_details):
            k.update({key:details[key] for key in ('statistics','status','progress','metadata') if key in details});k['source_name']=k['name'];k['name']=labels.get(k.get('id') or k['name'],k['name'])
        traces=await asyncio.gather(*(fetch(request,'/api/memory/trace/'+surface+'?limit=100',errors) for surface in ('chat','kb','cowriter','partner')))
        raw_events=[e for result in traces for e in result.get('events',[])];events=raw_events if scope=='account' else [e for e in raw_events if belongs_to_project(e,project,ids,unique_names)]
        root=store.path(owner,pid);path=root/'.workbench/retrieval-events.json';retrievals=json.loads(path.read_text()) if path.exists() else []
        for event in events:
            if event.get('kind')=='query':retrievals.append({'id':event['id'],'time':event.get('ts'),'query':event.get('payload',{}).get('query'),'knowledge_base':event.get('payload',{}).get('kb_name'),'source':'DeepTutor RAG','count':None,'scope':'account' if scope=='account' else 'project'})
        tools=[]
        if scope=='project':
            details=await asyncio.gather(*(fetch(request,'/api/sessions/'+quote(s.get('session_id') or s.get('id'))+query,errors) for s in sessions[:5]))
            tools=[row for detail in details for row in tool_events(detail)]
            for row in tools:
                if row.get('query') and any(word in row['tool'].casefold() for word in ('rag','search','knowledge')):retrievals.append({**row,'source':'项目会话工具','scope':'project'})
        from .research_flow import graph as research_graph
        research=research_graph(store,owner,pid)
        from .annotations import history
        annotations=history(store,owner,pid);inventory=store.inventory(owner,pid)
        return {'project':{'id':pid,'name':project['name'],'native_id':project['native_id']},'scope':scope,'checked':now(),'research_graph':research,'sessions':sessions,'tools':tools,'knowledge_bases':kbs,'retrievals':sorted(retrievals,key=lambda r:str(r.get('time') or ''),reverse=True)[:60],'memory':{'scope':'account','docs':overview.get('docs',[]),'runs':runs.get('runs',[])},'trace_events':events[:100],'jobs':store.jobs(owner,pid)[:60],'annotations':{'count':len(annotations['annotations']),'events':annotations['events'][:40],'summary':annotations['summary']},'files':{'count':sum(row['count'] for row in inventory['items']),'types':dict(sum((Counter(row['types']) for row in inventory['items']),Counter()))},'errors':errors}

    @app.get('/research/api/projects/{pid}/canvas/memory/{layer}/{key}')
    async def memory_document(request:Request,pid:str,layer:str,key:str,user=Depends(actor)):
        store.get(user['id'],pid)
        if layer not in ('L2','L3') or key not in ('chat','notebook','quiz','kb','book','partner','cowriter','recent','profile','scope','preferences'):raise KeyError('记忆不存在')
        value=await call(request,'GET','/api/memory/doc/'+layer+'/'+key)
        content=value.get('content','');path=api_path(user['id']).with_name('memory-observations.json');identifier=layer+'/'+key
        with store.lock('memory-observations:'+user['id']):
            rows=json.loads(path.read_text()) if path.exists() else {};versions=rows.get(identifier,[])
            if not versions or versions[-1]['content']!=content:versions.append({'observed_at':now(),'content':content});rows[identifier]=versions[-20:];atomic_json(path,rows)
        return {**value,'scope':'account','versions':versions[-20:]}

    @app.get('/research/api/projects/{pid}/canvas/memory-run/{rid}')
    async def memory_run(request:Request,pid:str,rid:str,user=Depends(actor)):
        store.get(user['id'],pid)
        runs=await call(request,'GET','/api/memory/runs')
        row=next((r for r in runs.get('runs',[]) if r.get('id')==rid),None)
        if row is None:raise KeyError('记忆更新记录不存在')
        return {**row,'scope':'account'}
