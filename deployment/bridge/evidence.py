"""Project-scoped parallel evidence retrieval with explicit source coverage."""
import asyncio
import json
from pathlib import Path
import secrets
import time
from typing import Literal
import uuid

from fastapi import HTTPException
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str = ''
    workspace_id: str = ''
    query: str = Field(min_length=3,max_length=600)
    sources: list[Literal['knowledge','web','papers']] = Field(default_factory=lambda:['knowledge','web','papers'],min_length=1,max_length=3)
    knowledge_base: str = ''
    paper_source: Literal['auto','scholar_mcp','crossref','semantic','academic_web'] = 'auto'
    limit: int = Field(default=5,ge=1,le=10)

    @field_validator('sources')
    @classmethod
    def unique_sources(cls,value):
        if len(set(value))!=len(value):raise ValueError('检索来源不能重复')
        return value


def unwrap(results):
    if not isinstance(results,list) or len(results)!=1:raise ValueError('检索分支缺少唯一结果')
    value=results[0]
    for _ in range(4):
        if isinstance(value,dict) and 'branch' in value:return value
        value=value.get('data') if isinstance(value,dict) else None
    raise ValueError('检索分支未返回状态包络')


def merge(branches,query):
    """No model synthesis: preserve all source identities and failed branches."""
    seen,items={},[]
    for branch in branches:
        for original in branch.get('items',[]):
            item=dict(original)
            identity=str(item.get('doi') or item.get('url') or item.get('document_id') or item.get('title') or '')
            if not identity:continue
            # Preserve different passages from the same RAG document.
            key=(identity.casefold().rstrip('/'),str(item.get('locator') or ''),item.get('excerpt',''))
            provenance={'branch':item.get('branch',branch['branch']),'source':item.get('source',branch.get('source'))}
            if key in seen:
                prior=items[seen[key]]
                if provenance not in prior['provenance']:prior['provenance'].append(provenance)
                continue
            item['provenance']=[provenance]
            seen[key]=len(items);items.append(item)
    requested=[b for b in branches if b['status']!='not_requested']
    failed=[b['branch'] for b in requested if b['status'] in {'failed','timed_out','not_configured','partial'}]
    status='partial' if failed and items else 'unavailable' if failed else 'ready' if items else 'empty'
    return {'status':status,'query':query,'items':items,
        'coverage':[ {k:b.get(k) for k in ('branch','status','source','count','elapsed_seconds','error','warnings')} for b in branches],
        'missing_sources':failed,'retrieved_at':time.time(),
        'scope':'并行检索所得题录、网页摘要与知识库片段；未自动阅读全部原文，未据此生成研究结论。',
        'next_action':'按缺失来源或冲突定向补查，并回读支持具体主张的原文。' if failed else '根据具体主张读取原文，检查反证与适用条件。'}


class EvidenceService:
    def __init__(self,service):
        self.service=service
        self.tickets={}
        self.gates={name:asyncio.Semaphore(2) for name in ('knowledge','web','papers')}
        self.run_gate=asyncio.Semaphore(3)
        self.deadlines={'knowledge':55,'web':25,'papers':30}
        with service.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS evidence_runs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,
                project_id TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,result TEXT,workflow_run_id TEXT,
                error TEXT,created REAL NOT NULL,updated REAL NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS evidence_branches(run_id TEXT NOT NULL,branch TEXT NOT NULL,
                result TEXT NOT NULL,PRIMARY KEY(run_id,branch))''')
            db.execute("UPDATE evidence_runs SET state='interrupted',error='检索服务已重启，请重新按需检索' WHERE state='running'")

    def ticket(self,run_id):
        value=self.tickets.get(run_id)
        if not value or value['expires']<time.time():raise HTTPException(404,'检索任务已过期，请从当前会话重新检索')
        return value

    def record(self,run_id,value):
        with self.service.db() as db:
            db.execute('INSERT OR REPLACE INTO evidence_branches VALUES(?,?,?)',
                (run_id,value['branch'],json.dumps(value,ensure_ascii=False)))
        return value

    async def branch(self,run_id,name,workflow_run_id=''):
        if name not in self.gates:raise HTTPException(400,'未知检索分支')
        ticket=self.ticket(run_id)
        if workflow_run_id:
            try:uuid.UUID(workflow_run_id)
            except ValueError:raise HTTPException(400,'Dify 检索运行编号无效') from None
            if ticket.get('workflow_run_id') not in (None,workflow_run_id):raise HTTPException(409,'同一次检索的 Dify 运行编号发生变化')
            ticket['workflow_run_id']=workflow_run_id
            with self.service.db() as db:
                db.execute('UPDATE evidence_runs SET workflow_run_id=?,updated=? WHERE id=?',(workflow_run_id,time.time(),run_id))
        request=ticket['request']
        start=time.monotonic()
        value={'branch':name,'status':'not_requested','source':name,'count':0,'items':[],'warnings':[]}
        if name not in request.sources:return self.record(run_id,value)
        try:
            # One deadline covers waiting for provider capacity and actual I/O.
            async with asyncio.timeout(self.deadlines[name]):
                async with self.gates[name]:
                    if name=='knowledge':
                        bound=ticket['project'].get('config',{}).get('knowledge_bases',[])
                        libraries=[request.knowledge_base] if request.knowledge_base else bound[:2]
                        if not libraries:
                            value.update(status='not_configured',error={'code':'knowledge_base_unbound',
                                'message':'当前项目没有绑定知识库；账号中存在知识库不代表当前项目已启用。'})
                        else:
                            if set(libraries)-set(bound):raise HTTPException(403,'知识库未绑定到当前项目')
                            results=await asyncio.gather(*(self.fetch_knowledge(ticket,library) for library in libraries),return_exceptions=True)
                            hits=[];errors=[]
                            for library,result in zip(libraries,results):
                                if isinstance(result,BaseException):
                                    error={'knowledge_base':library,'code':type(result).__name__,'retryable':False}
                                    if isinstance(result,HTTPException):
                                        error.update(code='http_'+str(result.status_code),message=str(result.detail)[:500],
                                            retryable=result.status_code in {429,500,502,503,504})
                                    elif isinstance(result,httpx.HTTPError):
                                        error.update(retryable=True,message='知识库连接未完成')
                                        if isinstance(result,httpx.TimeoutException):error['code']='timeout'
                                    errors.append(error)
                                else:
                                    try:hits.extend(self.knowledge_items(result,library,request.query))
                                    except (ValueError,KeyError,TypeError):
                                        errors.append({'knowledge_base':library,'code':'invalid_upstream_result',
                                            'message':'知识库未返回符合契约的来源片段','retryable':False})
                            value.update(items=hits,status='partial' if errors and hits else 'failed' if errors else 'ok' if hits else 'empty',
                                source='DeepTutor 原生 RAG',warnings=errors)
                            if errors and not hits and all(e['code']=='timeout' for e in errors):value['status']='timed_out'
                            if errors:value['error']=errors[0]
                            if len(bound)>2 and not request.knowledge_base:value['warnings'].append({'code':'library_limit','message':'本轮读取前两个绑定库，可指定其他库补查'})
                    else:
                        path='/research/api/search/web' if name=='web' else '/research/api/projects/'+ticket['project']['id']+'/literature/search'
                        params={'q':request.query}
                        if name=='papers':params.update(source=request.paper_source,page=1,limit=request.limit)
                        raw=(await self.service.request(self.service.workbench_url,'GET',path,ticket['auth'],params=params)).json()
                        if not isinstance(raw,dict) or not isinstance(raw.get('items',[]),list) or any(not isinstance(item,dict) for item in raw.get('items',[])):
                            raise ValueError('检索来源未返回对象列表')
                        items=raw.get('items',[])[:request.limit]
                        value.update(source=raw.get('source') or name,warnings=raw.get('warnings') or [],
                            status='failed' if raw.get('status') in {'unavailable','failed'} or raw.get('error') else 'ok' if items else 'empty',
                            error=raw.get('error'),items=[self.search_item(item,name,request.query,raw.get('source') or name) for item in items])
        except (TimeoutError,httpx.TimeoutException):
            value.update(status='timed_out',error={'code':'timeout','message':'该来源超过本轮等待上限','retryable':True})
        except HTTPException as exc:
            value.update(status='failed',error={'code':'http_'+str(exc.status_code),'message':str(exc.detail)[:500],
                'retryable':exc.status_code in {429,500,502,503,504}})
        except httpx.HTTPError as exc:
            value.update(status='failed',error={'code':type(exc).__name__,'message':'检索连接未完成','retryable':True})
        except (ValueError,KeyError,TypeError):
            value.update(status='failed',error={'code':'invalid_upstream_result','message':'来源结果不符合检索契约','retryable':False})
        value.update(count=len(value['items']),elapsed_seconds=round(time.monotonic()-start,3))
        return self.record(run_id,value)

    async def fetch_knowledge(self,ticket,library):
        request=ticket['request']
        value=(await self.service.request(self.service.workbench_url,'POST','/research/api/projects/'+ticket['project']['id']+'/knowledge/search',
            ticket['auth'],json={'query':request.query,'mode':'semantic','knowledge_base':library,'limit':request.limit})).json()
        result=value.get('result',value) if isinstance(value,dict) else None
        if isinstance(result,dict) and (result.get('error_type') or result.get('needs_reindex') or result.get('error')
                or result.get('status') in {'failed','unavailable'}):
            raise HTTPException(409,'知识库检索未完成：'+str(result.get('error_type') or result.get('error') or '索引或检索配置需要检查')[:400])
        return value

    @staticmethod
    def search_item(item,branch,query,source):
        return {'branch':branch,'query':query,'source':source,'title':str(item.get('title') or ''),
            'url':item.get('url') or item.get('link') or '', 'doi':item.get('doi') or '',
            'excerpt':str(item.get('snippet') or item.get('abstract') or item.get('description') or item.get('body') or '')[:2000],
            'locator':'','evidence_kind':'metadata-and-search-snippet','raw':item}

    @staticmethod
    def knowledge_items(raw,library,query):
        if not isinstance(raw,dict):raise ValueError('RAG结果应为对象')
        result=raw.get('result',raw)
        if isinstance(result,list):nodes=result
        elif isinstance(result,dict):nodes=result.get('sources') or result.get('source_nodes') or result.get('chunks') or result.get('results') or result.get('nodes') or []
        else:raise ValueError('RAG结果应为对象或片段列表')
        if not isinstance(nodes,list):raise ValueError('RAG来源应为列表')
        items=[]
        for item in nodes:
            if not isinstance(item,dict):raise ValueError('RAG来源应为对象')
            node=item.get('node',item)
            if not isinstance(node,dict):raise ValueError('RAG来源节点应为对象')
            metadata=node.get('metadata') or item.get('metadata') or {}
            if not isinstance(metadata,dict):raise ValueError('RAG来源元数据应为对象')
            text=node.get('evidence_text') or node.get('text') or node.get('content') or item.get('evidence_text') or item.get('text') or item.get('content') or ''
            if not text:continue
            title=metadata.get('file_name') or metadata.get('filename') or item.get('title') or metadata.get('title') or library
            document=item.get('document_key') or item.get('source') or metadata.get('file_path') or metadata.get('document_id') or node.get('id_') or node.get('node_id') or title
            locator=str(item.get('page_label') or metadata.get('page_label') or metadata.get('page_number') or metadata.get('page') or item.get('page') or item.get('chunk_id') or '')
            items.append({'branch':'knowledge','query':query,'source':raw.get('source','DeepTutor 原生 RAG'),
                'title':str(title),'document_id':str(document),'knowledge_base':library,
                'url':metadata.get('url') or item.get('url') or '', 'locator':locator,'excerpt':str(text)[:3000],
                'score':item.get('score'),'evidence_kind':'indexed-source-excerpt','raw':item})
        return items

    async def search(self,auth,request):
        owner=(await self.service.profile(auth))['id']
        project=await self.service.project(auth,request.project_id,request.workspace_id)
        if request.knowledge_base and request.knowledge_base not in project.get('config',{}).get('knowledge_bases',[]):
            raise HTTPException(403,'知识库未绑定到当前项目')
        # Fail fast under whole-workflow saturation; provider queues are bounded by deadlines.
        try:
            await asyncio.wait_for(self.run_gate.acquire(),timeout=3)
        except TimeoutError:raise HTTPException(429,'联合检索并发已满，请等待当前检索完成后重试') from None
        run_id=uuid.uuid4().hex;now=time.time()
        try:
            with self.service.db() as db:
                db.execute('INSERT INTO evidence_runs(id,owner,project_id,payload,state,created,updated) VALUES(?,?,?,?,?,?,?)',
                    (run_id,owner,project['id'],request.model_dump_json(),'running',now,now))
            self.tickets[run_id]={'request':request,'project':project,'auth':auth,'expires':now+180}
            key=self.service.dify_key.parent/'evidence-key'
            if not key.is_file():raise HTTPException(503,'Dify 联合检索流程尚未发布')
            raw=(await self.service.request(self.service.dify_url,'POST','/v1/workflows/run',
                {'Authorization':'Bearer '+key.read_text().strip()},json={'inputs':{'run_id':run_id,'query':request.query},
                    'response_mode':'blocking','user':'deeptutor-'+owner})).json()
            if not isinstance(raw,dict) or not isinstance(raw.get('data'),dict):
                raise ValueError('Dify 未返回结构化运行终态')
            data=raw.get('data',{})
            outputs=data.get('outputs')
            if not isinstance(outputs,dict):raise ValueError('Dify 未返回结构化输出')
            result=outputs.get('evidence') or outputs.get('partial_evidence')
            if isinstance(result,str):result=json.loads(result)
            if data.get('status')!='succeeded' or not isinstance(result,dict):
                raise ValueError('Dify 联合检索未取得完整分支回执')
            # The authoritative coverage is the actual recorded branches, not generated text.
            with self.service.db() as db:
                branches=[json.loads(r[0]) for r in db.execute('SELECT result FROM evidence_branches WHERE run_id=? ORDER BY branch',(run_id,))]
            if {b['branch'] for b in branches}!={'knowledge','web','papers'}:raise ValueError('联合检索缺少分支状态')
            result=merge(branches,request.query)
            result.update(run_id=run_id,project_id=project['id'],workflow_run_id=raw.get('workflow_run_id'),elapsed_seconds=round(time.time()-now,3))
            with self.service.db() as db:
                db.execute('UPDATE evidence_runs SET state=?,result=?,workflow_run_id=?,updated=? WHERE id=?',
                    (result['status'],json.dumps(result,ensure_ascii=False),result['workflow_run_id'],time.time(),run_id))
            return result
        except (HTTPException,httpx.HTTPError,ValueError,OSError,TimeoutError) as exc:
            error=str(exc.detail) if isinstance(exc,HTTPException) else type(exc).__name__
            with self.service.db() as db:
                branches=[json.loads(r[0]) for r in db.execute('SELECT result FROM evidence_branches WHERE run_id=?',(run_id,))]
            missing={'knowledge','web','papers'}-{b['branch'] for b in branches}
            branches += [{'branch':name,'status':'not_requested' if name not in request.sources else 'failed',
                'source':name,'items':[],'count':0,'error':{'code':'workflow_incomplete','message':error}} for name in sorted(missing)]
            result=merge(branches,request.query)
            with self.service.db() as db:
                workflow_id=db.execute('SELECT workflow_run_id FROM evidence_runs WHERE id=?',(run_id,)).fetchone()[0]
            result.update(run_id=run_id,project_id=project['id'],workflow_run_id=workflow_id,workflow_error=error,elapsed_seconds=round(time.time()-now,3))
            with self.service.db() as db:
                db.execute('UPDATE evidence_runs SET state=?,result=?,error=?,updated=? WHERE id=?',
                    (result['status'],json.dumps(result,ensure_ascii=False),error,time.time(),run_id))
            return result
        finally:
            self.tickets.pop(run_id,None)
            self.run_gate.release()

    async def status(self,auth,run_id):
        owner=(await self.service.profile(auth))['id']
        with self.service.db() as db:
            row=db.execute('SELECT * FROM evidence_runs WHERE id=? AND owner=?',(run_id,owner)).fetchone()
        if not row:raise HTTPException(404,'检索任务不存在')
        return json.loads(row['result']) if row['result'] else {'run_id':run_id,'status':row['state'],'error':row['error']}
