"""Durable, owner-scoped paper organization maps, queued by literature ingestion."""
from __future__ import annotations
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
from urllib.parse import quote

import httpx
from fastapi import Depends,HTTPException,Request
from .native import actor,headers,BASE
from .storage import atomic_json,child,now

RULE_VERSION='paper-content-map-20261104.2'
SERVICE=None
JOB_KIND='paper-content-map'


def source_key(asset,library='workspace'):
    return hashlib.sha256((library+'\n'+asset).encode()).hexdigest()[:24]


def read_json(path,default=None):
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else deepcopy(default)


def enqueue_after_ingest(store,owner,pid,asset,metadata=None,library='workspace',source_path=None):
    """All ingress paths call this after the source and its identity are saved."""
    if not str(asset).lower().endswith('.pdf'):return None
    if SERVICE is None:return None
    if store.get(owner,pid).get('config',{}).get('research_flow_managed'):return None
    return SERVICE.enqueue(owner,pid,asset,library=library,metadata=metadata,source_path=source_path)


class PaperMaps:
    def __init__(self,store):
        self.store=store
        self.tasks={}
        self.closing=False

    def folder(self,owner,pid):return self.store.path(owner,pid)/'.workbench/paper-maps'

    def entry(self,owner,pid,asset,library='workspace'):
        self.store.get(owner,pid)
        return self.folder(owner,pid)/'entries'/(source_key(asset,library)+'.json')

    def job_path(self,owner,pid,jid):return self.folder(owner,pid)/'jobs'/(jid+'.json')

    def source_path(self,owner,pid,asset,library='workspace'):
        self.store.get(owner,pid)
        root=self.store.path(owner,pid)
        if library=='workspace':return child(root/'literature',asset)
        project=self.store.get(owner,pid)
        if library not in project['config'].get('knowledge_bases',[]):raise HTTPException(403,'文献不属于当前项目')
        return self.folder(owner,pid)/'sources'/(source_key(asset,library)+'.pdf')

    @staticmethod
    def signature(path):return {'bytes':path.stat().st_size,'modified_ns':path.stat().st_mtime_ns}

    def status(self,owner,pid,asset,library='workspace'):
        source=self.source_path(owner,pid,asset,library)
        path=self.entry(owner,pid,asset,library);entry=read_json(path,{})
        if not entry:return {'asset':asset,'library':library,'status':'missing','map':None}
        graph=read_json(path.with_suffix('.map.json'))
        status=entry['status']
        if source.is_file() and entry.get('signature')!=self.signature(source):status='stale'
        if graph and graph.get('rule_version')!=RULE_VERSION and status in ('ready','needs_review'):status='stale'
        return {k:v for k,v in {**entry,'status':status,'map':graph}.items() if k not in ('capability','source_path')}

    def enqueue(self,owner,pid,asset,*,library='workspace',metadata=None,source_path=None,force=False,model_selection=None):
        project=self.store.get(owner,pid);path=self.entry(owner,pid,asset,library)
        source=Path(source_path) if source_path else self.source_path(owner,pid,asset,library)
        if not source.is_file():raise ValueError('论文全文尚未保存，无法建立内容图谱')
        if source.suffix.lower()!='.pdf':raise ValueError('内容图谱需要论文 PDF 全文')
        signature=self.signature(source);prior=read_json(path,{})
        with self.store.lock('paper-map:'+pid+':'+source_key(asset,library)):
            if not force and prior.get('signature')==signature and prior.get('status') in ('queued','running','ready','needs_review'):
                if metadata and prior.get('status')=='queued':
                    job_path=self.job_path(owner,pid,prior['job_id']);state=read_json(job_path,{})
                    state['metadata']={**state.get('metadata',{}),**metadata};atomic_json(job_path,state)
                    prior['title']=metadata.get('title') or prior.get('title');atomic_json(path,prior)
                return {k:v for k,v in prior.items() if k!='source_path'}
            if prior.get('status') in ('queued','running'):return {k:v for k,v in prior.items() if k!='source_path'}
            if not force and prior.get('signature')==signature and prior.get('status') in ('failed','interrupted'):
                previous_path=self.job_path(owner,pid,prior['job_id']);previous=read_json(previous_path,{})
                if previous:
                    previous.update(status='queued',error='',capability=secrets.token_urlsafe(40))
                    if model_selection is not None:previous['model_selection']=model_selection
                    atomic_json(previous_path,previous);prior.update(status='queued',stage='从已保存章节继续',error='',updated=now());atomic_json(path,prior)
                    self.store.set_job(prior['job_id'],status='queued',stage=prior['stage'],error='')
                    return prior
            policy=project['config'].get('paper_content_maps',{})
            selection=model_selection if model_selection is not None else policy.get('model_selection')
            jid=self.store.job(owner,pid,JOB_KIND,{'subject':(metadata or {}).get('title') or Path(asset).stem,'asset':asset,'library':library})
            state={'id':jid,'owner':owner,'project_id':pid,'workspace_id':project['native_id'],'asset':asset,'library':library,
                'source_path':str(source),'signature':signature,'metadata':metadata or {},'model_selection':selection,
                'capability':secrets.token_urlsafe(40),'created':now(),'status':'queued','stage':'parse','parts':[],
                'rule_version':RULE_VERSION}
            atomic_json(self.job_path(owner,pid,jid),state)
            entry={'asset':asset,'library':library,'title':(metadata or {}).get('title') or Path(asset).stem,'job_id':jid,
                'status':'queued','stage':'等待提取论文结构','signature':signature,'updated':now(),'error':''}
            atomic_json(path,entry)
            return entry

    def update(self,state,status,stage,**extra):
        state.update(status=status,stage=stage,updated=now(),**extra)
        atomic_json(self.job_path(state['owner'],state['project_id'],state['id']),state)
        path=self.entry(state['owner'],state['project_id'],state['asset'],state['library'])
        entry=read_json(path,{})
        entry.update(status=status,stage=stage,updated=now(),error=extra.get('error',''))
        atomic_json(path,entry)
        self.store.set_job(state['id'],status='completed' if status in ('ready','needs_review') else status,
            step=state.get('phase','organize'),stage=stage,error=extra.get('error',''),
            result={'subject':entry.get('title'), 'asset':state['asset'],'library':state['library'],'map_status':status,
                    'done':len(state.get('parts',[])),'total':state.get('part_count',0)})

    async def call_model(self,state,prompt,payload,part):
        location=Path('/opt/workbench-tools/writing/agent-url')
        if not location.is_file():raise ValueError('原生论文图谱模型服务尚未配置')
        body={'job_id':state['id'],'capability':state['capability'],'prompt':prompt,'payload':payload,'part':part}
        async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
            response=await client.post(location.read_text().strip()+'/paper-map/generate',json=body)
            if not response.is_success:raise ValueError('图谱模型生成未完成：'+response.text[:500])
        value=response.json()
        from .writing import decode_json
        result=decode_json(value['text'])
        if not isinstance(result,dict):raise ValueError('模型未返回内容图谱对象')
        return result

    async def build(self,row):
        state=read_json(self.job_path(row['owner'],row['project'],row['id']))
        if not state:return
        try:
            from .paper_map_core import extract_source,build_prompt,normalize_map
            root=self.store.path(row['owner'],row['project'])
            state['phase']='parse';self.update(state,'running','正在读取全文并定位章节与段落')
            source=await asyncio.to_thread(extract_source,root,state['asset'],state['metadata'],state['library'],source_path=state['source_path'])
            state['source_signature']=source['source']['signature']
            packet_path=self.folder(row['owner'],row['project'])/'jobs'/row['id']/'source.json';atomic_json(packet_path,source)
            state['group_chars']=state.get('group_chars') or (24000 if state.get('part_count') else 12000)
            units=source['units'];groups=[];current=[];size=0
            for unit in units:
                if current and size+len(unit['text'])>state['group_chars']:
                    groups.append(current);current=[];size=0
                current.append(unit);size+=len(unit['text'])
            if current:groups.append(current)
            state['part_count']=len(groups)+1
            sections=source.get('sections',[])
            for index,group in enumerate(groups):
                result_path=packet_path.parent/('part-'+str(index)+'.json')
                if result_path.is_file():continue
                state['phase']='organize';self.update(state,'running','正在提炼内容组织 '+str(index+1)+' / '+str(len(groups)))
                unit_ids=[u['id'] for u in group];section_ids=list(dict.fromkeys(u.get('section_id') for u in group))
                part={'unit_ids':unit_ids,'section_ids':section_ids}
                prompt,payload=build_prompt(source,part=part)
                result=await self.call_model(state,prompt,payload,'section-'+str(index+1))
                atomic_json(result_path,result)
                state['parts']=list(dict.fromkeys(state.get('parts',[])+[index]))
                self.update(state,'running','已保存内容组织 '+str(index+1)+' / '+str(len(groups)))
            nodes=[];edges=[]
            for index in range(len(groups)):
                value=read_json(packet_path.parent/('part-'+str(index)+'.json'))
                nodes.extend(value.get('nodes',[]));edges.extend(value.get('edges',[]))
            unique_nodes={}
            for node in nodes:
                if node.get('kind')=='paper':continue
                if node['id'] in unique_nodes:
                    prior=unique_nodes[node['id']]
                    if node.get('kind')!='section' and prior!=node:raise ValueError('不同内容重复使用同一节点身份：'+node['id'])
                    prior['source_ids']=list(dict.fromkeys(prior.get('source_ids',[])+node.get('source_ids',[])))
                else:unique_nodes[node['id']]=node
            nodes=list(unique_nodes.values())
            edges=[{**edge,'id':'local-'+str(i+1)} for i,edge in enumerate(edges)]
            known={n['id'] for n in nodes}
            root_title=source['source'].get('title') or state['metadata'].get('title') or Path(state['asset']).stem
            root_node={'id':'paper','parent_id':'','kind':'paper','section_type':'other','label':root_title,'content':root_title,'keywords':[],'source_ids':[],'order':0,'depth':0}
            for node in nodes:
                if not node.get('parent_id') or node['parent_id'] not in known:node['parent_id']='paper'
            nodes=[root_node]+nodes
            story_path=packet_path.parent/'story.json'
            if story_path.is_file():story=read_json(story_path)
            else:
                state['phase']='connect';self.update(state,'running','正在连接问题 方法 证据与结论')
                prompt='你是科研论文组织分析者。依据全文各节已提炼的内容图谱重建作者的研究问题、主线、手段目的和承诺兑现；这是原文内容分析，不是评审打分。只输出JSON：{"story":{"author_question":"","main_claim":"","organization_summary":"","means_ends":[{"means":"","end":"","explanation":"","node_ids":[],"source_ids":[]}],"promise_evidence":[{"question":"","method":"","evidence":"","conclusion":"","node_ids":[],"question_node_ids":[],"method_node_ids":[],"evidence_node_ids":[],"conclusion_node_ids":[],"source_ids":[],"status":"supported|partial|not_found"}],"learning_points":[{"text":"","node_ids":[],"source_ids":[]}]},"edges":[{"id":"cross-1","from":"已存在node id","to":"已存在node id","relation":"中文具体关系","explanation":"内容为何相接","source_ids":[],"basis":"explicit|inferred"}],"keywords":[]}。不能创造节点，不能以模块清单代替科学关系；实际证据不足、段落组织松散按原文保留。不复制摘要；原摘要已完整保存。'
                payload={'source':source['source'],'abstract':source['abstract'],'nodes':nodes,'existing_edges':edges,'section_outline':sections}
                story=await self.call_model(state,prompt,payload,'whole-paper');atomic_json(story_path,story)
            state['phase']='save';self.update(state,'running','正在核对原文覆盖与内容关系')
            root_node['label']=story.get('story',{}).get('topic_phrase') or root_title
            root_node['content']=story.get('story',{}).get('main_claim') or root_title
            root_node['keywords']=story.get('keywords',[])[:2]
            combined={'nodes':nodes,'edges':edges+story.get('edges',[]),'story':story.get('story',{}),'keywords':story.get('keywords',[])}
            graph=normalize_map(source,combined)
            graph['generated_at']=now();graph['rule_version']=RULE_VERSION
            graph['source_units']=deepcopy(source['units'])
            source_path=Path(state['source_path'])
            if self.signature(source_path)!=state['signature']:raise ValueError('论文全文已更新，保留旧结果并请按当前版本重新生成')
            entry_path=self.entry(state['owner'],state['project_id'],state['asset'],state['library'])
            atomic_json(entry_path.with_suffix('.map.json'),graph)
            needs=bool(graph.get('coverage',{}).get('unmapped_unit_ids') or graph.get('coverage',{}).get('needs_review'))
            self.update(state,'needs_review' if needs else 'ready','内容图谱已保存'+('，部分位置需要复核' if needs else ''))
        except asyncio.CancelledError:
            self.update(state,'interrupted','处理已中断，已完成章节保留');raise
        except Exception as exc:self.update(state,'failed','内容图谱未完成',error=str(exc)[:1200])

    async def loop(self):
        # Each saved part is a checkpoint. A restart resumes the unfinished part.
        with self.store.db() as db:rows=db.execute("SELECT id,owner,project FROM jobs WHERE kind=? AND status IN ('running','interrupted')",(JOB_KIND,)).fetchall()
        for row in rows:self.store.set_job(row['id'],status='queued',stage='从已保存章节继续')
        try:
            while True:
                self.tasks={k:v for k,v in self.tasks.items() if not v.done()}
                self.active={k:v for k,v in getattr(self,'active',{}).items() if k in self.tasks}
                active_projects={v[0] for v in self.active.values()}
                if len(self.tasks)<2:
                    with self.store.db() as db:rows=db.execute("SELECT id,owner,project FROM jobs WHERE kind=? AND status='queued' ORDER BY created",(JOB_KIND,)).fetchall()
                    for row in rows:
                        if row['project'] in active_projects:continue
                        self.store.set_job(row['id'],status='running',stage='开始读取论文')
                        task=asyncio.create_task(self.build(dict(row)));self.tasks[row['id']]=task
                        self.active={k:v for k,v in getattr(self,'active',{}).items() if k in self.tasks};self.active[row['id']]=(row['project'],task)
                        active_projects.add(row['project'])
                        if len(self.tasks)>=2:break
                await asyncio.sleep(2)
        finally:
            for task in self.tasks.values():task.cancel()
            if self.tasks:await asyncio.gather(*self.tasks.values(),return_exceptions=True)


def install(app,store):
    global SERVICE
    service=SERVICE=PaperMaps(store)

    @app.get('/research/api/projects/{pid}/literature/content-map')
    async def content_map(pid:str,asset:str,library:str='workspace',user=Depends(actor)):
        return service.status(user['id'],pid,asset,library)

    @app.post('/research/api/projects/{pid}/literature/content-map')
    async def generate(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];asset=str(payload.get('asset',''));library=str(payload.get('library','workspace'))
        from .literature import read_index
        path=service.source_path(owner,pid,asset,library)
        if library!='workspace' and not path.is_file():
            project=store.get(owner,pid)
            async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
                data=await client.get(BASE+'/api/knowledge-bases/'+quote(library,safe='')+'/files/'+quote(asset,safe='/'),params={'dt_workspace':project['native_id']},headers=headers(request))
                data.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data.content)
        return service.enqueue(owner,pid,asset,library=library,metadata=read_index(store.path(owner,pid)).get(asset,{}),force=bool(payload.get('force')),model_selection=payload.get('model_selection'))

    @app.get('/research/api/projects/{pid}/literature/content-maps')
    async def maps(pid:str,user=Depends(actor)):
        store.get(user['id'],pid)
        folder=service.folder(user['id'],pid)/'entries'
        return {'items':[{k:val for k,val in service.status(user['id'],pid,v['asset'],v['library']).items() if k!='map'} for p in folder.glob('*.json') if not p.name.endswith('.map.json') for v in [read_json(p)]],'auto_enabled':True}

    @app.post('/research/api/projects/{pid}/literature/content-maps/backfill')
    async def backfill(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid);from .literature import read_index
        only_library=payload.get('library')
        if only_library is not None and only_library!='workspace' and only_library not in project['config'].get('knowledge_bases',[]):raise HTTPException(403,'文献不属于当前项目')
        if payload.get('model_selection') is not None:
            config=project['config'];config['paper_content_maps']={**config.get('paper_content_maps',{}),'model_selection':payload['model_selection']};store.update(owner,pid,config=config)
        items=[]
        for asset,metadata in read_index(store.path(owner,pid)).items():
            if only_library not in (None,'workspace'):continue
            if asset.lower().endswith('.pdf') and service.source_path(owner,pid,asset).is_file():items.append(service.enqueue(owner,pid,asset,metadata=metadata,model_selection=payload.get('model_selection')))
        async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
            for kb in project['config'].get('knowledge_bases',[]):
                if only_library is not None and kb!=only_library:continue
                r=await client.get(BASE+'/api/knowledge-bases/'+quote(kb,safe='')+'/files',params={'dt_workspace':project['native_id']},headers=headers(request));r.raise_for_status()
                for entry in r.json().get('files',[]):
                    asset=entry.get('name','')
                    if not asset.lower().endswith('.pdf'):continue
                    # Native duplicate copies of already registered PDFs need one map.
                    digest_name=Path(asset).name
                    if any(digest_name.startswith(str(v.get('digest',''))[:12]+'-') for v in read_index(store.path(owner,pid)).values() if v.get('digest')):continue
                    path=service.source_path(owner,pid,asset,kb)
                    if not path.is_file():
                        data=await client.get(BASE+'/api/knowledge-bases/'+quote(kb,safe='')+'/files/'+quote(asset,safe='/'),params={'dt_workspace':project['native_id']},headers=headers(request));data.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data.content)
                    items.append(service.enqueue(owner,pid,asset,library=kb,metadata=entry.get('metadata',{}),model_selection=payload.get('model_selection')))
        return {'items':items,'queued':sum(x['status']=='queued' for x in items),'total':len(items),'auto_enabled':True}

    @app.get('/internal/paper-map-jobs/{jid}')
    @app.get('/research/internal/paper-map-jobs/{jid}')
    async def internal_job(request:Request,jid:str):
        with store.db() as db:row=db.execute('SELECT owner,project,status FROM jobs WHERE id=? AND kind=?',(jid,JOB_KIND)).fetchone()
        if not row:raise HTTPException(403,'图谱任务凭据无效')
        state=read_json(service.job_path(row['owner'],row['project'],jid),{})
        if not secrets.compare_digest(request.headers.get('x-paper-map-capability',''),state.get('capability','')) or row['status']!='running':raise HTTPException(403,'图谱任务凭据无效或任务未执行')
        project=store.get(row['owner'],row['project'])
        return {'owner':row['owner'],'project_id':row['project'],'workspace_id':project['native_id'],'root':project['root'],'model_selection':state.get('model_selection')}

    return service