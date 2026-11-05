"""Partner's built-in writing mode; Dify routes stages, native Tutor runs models."""
from __future__ import annotations
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import secrets
import uuid
from urllib.parse import quote
import httpx
from fastapi import Depends, HTTPException, Request
from .native import actor, headers, BASE
from .storage import atomic_json, child, now
from . import writing_prompts as prompts
from . import writing_tools as tools
from . import writing_scores as scoring
from . import writing_synthesis as synthesis

ACTIVE = {}
TASKS = {}
TERMINAL = {'completed','failed','cancelled','interrupted'}
KEY = Path('/opt/workbench-tools/writing/dify-key')
META = Path('/opt/workbench-tools/writing/app.json')


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else deepcopy(default)


def decode_json(text):
    import json_repair
    value=json_repair.loads(text)
    if not isinstance(value,dict):raise ValueError('写作Agent没有返回JSON对象')
    return value


def stage_acceptance(value, run_id, stage):
    """A Dify end node is not proof that the callback accepted this stage."""
    result=value.get('data') or {}
    if result.get('status')!='succeeded':
        raise ValueError('Dify阶段路由失败：'+str(result.get('error') or result.get('status') or '缺少终态'))
    receipt=(result.get('outputs') or {}).get('receipt_'+stage)
    if isinstance(receipt,str):
        try:receipt=json.loads(receipt)
        except ValueError:receipt=None
    if not isinstance(receipt,dict) or receipt.get('accepted') is not True:
        detail=receipt.get('detail') if isinstance(receipt,dict) else None
        raise ValueError('写作阶段未被接受：'+str(detail or '缺少有效的阶段受理回执'))
    if receipt.get('run_id',run_id)!=run_id:
        raise ValueError('写作阶段回执不属于当前任务')
    if receipt.get('stage',stage)!=stage and receipt.get('status')!='already_advanced':
        raise ValueError('写作阶段回执与请求不一致')
    return receipt


def settings(root):
    return {'mode':'research','phase':'auto','journal':None,'theme':'','exemplar_paths':[],
            **read_json(root/'.workbench/writing/settings.json',{})}


def save_settings(root, values):
    current=settings(root)
    for k in ['mode','phase','journal','theme','exemplar_paths']:
        if k in values:current[k]=values[k]
    if current['mode'] not in ('writing','research'):raise ValueError('工作模式无效')
    if current['phase'] not in ('auto',*prompts.PHASES):raise ValueError('写作阶段无效')
    if not isinstance(current['exemplar_paths'],list):raise ValueError('标杆资料需要路径列表')
    for p in current['exemplar_paths']:child(root,p)
    atomic_json(root/'.workbench/writing/settings.json',current)
    return current


def inventory(root, query='', limit=18):
    words=set(re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,5}',query.lower()))
    paths=[]
    for base in [root/'project',root/'literature',root/'manuscript']:
        if not base.is_dir():continue
        for p in base.rglob('*'):
            if not p.is_file() or any(v in p.parts for v in ['node_modules','.git','__pycache__','.venv','.workbench']):continue
            if p.suffix.lower() not in ['.md','.txt','.csv','.tsv','.json','.py','.pdf','.docx']:continue
            rel=p.relative_to(root).as_posix()
            score=sum(w in rel.lower() for w in words)*10
            if any(w in rel.lower() for w in ['brief','readme','research','handoff','main.json','convergence','metrics']):score+=3
            paths.append((score,rel,p))
            if len(paths)>=3000:break
    paths.sort(key=lambda item:(-item[0],len(item[1])))
    assets=[]
    for _,rel,p in paths:
        if len(assets)>=limit:break
        if p.suffix.lower() in ('.pdf','.docx'):continue
        if p.stat().st_size>3_000_000:continue
        content=p.read_text(encoding='utf-8',errors='replace')
        assets.append({'path':rel,'modified':p.stat().st_mtime,'text':content[:16000],'total_chars':len(content)})
    return {'files':[{'path':rel,'size':p.stat().st_size} for _,rel,p in paths],
            'selected_assets':assets,'indexed_files':len(paths)}


def document_markdown(doc):
    from .manuscripts import plain_document
    return '# '+doc.get('title','')+'\n\n'+plain_document(doc.get('content',{}))


def markdown_document(text, prior):
    """Keep equations/citations as editable Tiptap nodes via the existing Pandoc."""
    from markdown_it import MarkdownIt
    md=MarkdownIt();tokens=md.parse(text);nodes=[];heading=0;buffer=[]
    def flush():
        nonlocal buffer
        if buffer:
            value='\n'.join(buffer).strip();buffer=[]
            if value:nodes.append({'type':'paragraph','content':[{'type':'text','text':value}]})
    for token in tokens:
        if token.type=='heading_open':flush();heading=int(token.tag[1:])
        elif token.type=='inline':
            if heading:
                flush();nodes.append({'type':'heading','attrs':{'level':min(3,heading)},'content':[{'type':'text','text':token.content}]});heading=0
            else:buffer.append(token.content)
        elif token.type=='paragraph_close':flush()
        elif token.type in ('fence','code_block'):
            flush();nodes.append({'type':'codeBlock','attrs':{'language':token.info or ''},'content':[{'type':'text','text':token.content}]})
    flush()
    return {**prior,'content':{'type':'doc','content':nodes or [{'type':'paragraph'}]},'reason':'Partner写作工作流生成'}


class WritingService:
    def __init__(self,store):self.store=store

    def root(self,owner,pid):self.store.get(owner,pid);return self.store.path(owner,pid)
    def run_path(self,owner,pid,rid):return self.root(owner,pid)/'.workbench/writing/runs'/rid/'state.json'

    def load(self,owner,pid,rid):
        if not re.fullmatch(r'[a-f0-9]{32}',rid):raise ValueError('写作任务编号无效')
        value=read_json(self.run_path(owner,pid,rid))
        if not value:raise KeyError('写作任务不存在')
        return value

    def save(self,run):
        run['updated']=now();atomic_json(self.run_path(run['owner'],run['project_id'],run['id']),run)

    def public(self,run,detail=False):
        keys=['id','project_id','session_id','turn_id','status','stage','phase','created','updated','job_id',
              'request','intent','outputs','error','dify_runs','stage_history','stage_plan','journal','model_selection','workflow_url','tool_results','engine','agentic_calls','editorial_scope','reference_policy']
        result={k:run.get(k) for k in keys}
        if not detail and isinstance(result.get('tool_results'),dict):result['tool_results']={k:{'available':bool(v)} for k,v in result['tool_results'].items()}
        if not detail:
            result['outputs']={k:v for k,v in (result.get('outputs') or {}).items() if k!='text'}
            if result.get('journal'):result['journal']={'journal':run['journal'].get('journal',{}),'retrieved_at':run['journal'].get('retrieved_at')}
        return result

    async def generate(self,run,prompt,payload,structured=True):
        if self.load(run['owner'],run['project_id'],run['id'])['status']=='cancelled':raise asyncio.CancelledError()
        context=ACTIVE[run['id']]
        if run.get('engine')=='agentic':
            endpoint=Path('/opt/workbench-tools/writing/agent-url').read_text().strip()
            async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
                response=await client.post(endpoint+'/generate',headers=context['auth'],json={
                    'run_id':run['id'],'project_id':run['project_id'],
                    'stage':run.get('agent_stage') or run['stage'],'prompt':prompt,'payload':payload,
                    'model_selection':run.get('model_selection')})
                if not response.is_success:
                    raise ValueError('Agent阶段未完成：'+str(response.json().get('detail') or response.text[:1200]))
                value=response.json()
            run.setdefault('agentic_calls',[]).append({k:value.get(k) for k in ['trace','iterations','model']})
            return decode_json(value['text']) if structured else value['text']
        instruction=prompt+('\n严格只返回上述JSON对象。' if structured else '\n直接返回所要求的正文。')
        async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
            response=await client.post(BASE+'/api/documents/actions/edit?dt_workspace='+quote(context['native_id']),
                headers=context['auth'],json={'text':json.dumps(payload,ensure_ascii=False),'instruction':instruction,
                    'action':'rewrite','llm_selection':run.get('model_selection')})
            if not response.is_success:
                try:message=response.json().get('detail') or response.text[:700]
                except Exception:message=response.text[:700]
                raise ValueError('写作模型：'+str(message))
            result=response.json()['edited_text']
        return decode_json(result) if structured else result

    async def dispatch(self,run,stage):
        if not KEY.is_file():raise ValueError('Dify写作流程尚未发布')
        payload={'inputs':{'run_id':run['id'],'ticket':run['ticket'],'stage':stage},'response_mode':'blocking','user':run['owner']}
        async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
            r=await client.post('http://127.0.0.1:8088/v1/workflows/run',headers={'Authorization':'Bearer '+KEY.read_text().strip()},json=payload)
            r.raise_for_status();value=r.json()
        stage_acceptance(value,run['id'],stage)
        # A callback can advance the same task while the routing request completes.
        with self.store.lock('writing:'+run['id']):
            current=self.load(run['owner'],run['project_id'],run['id'])
            current.setdefault('dify_runs',[]).append({'stage':stage,'workflow_run_id':value.get('workflow_run_id') or value.get('data',{}).get('id'),'status':'succeeded'})
            self.save(current)

    async def start(self,owner,pid,body,auth):
        root=self.root(owner,pid);project=self.store.get(owner,pid);current=settings(root)
        # Calling start/resume is an explicit writing action. Automatic chat
        # dispatch resolves the project mode at its own endpoint below.
        if body.get('mode','writing')=='research':return {'status':'disabled','mode':'research'}
        operation=str(body.get('operation_id') or body.get('turn_id') or uuid.uuid4().hex)
        folder=root/'.workbench/writing/runs';folder.mkdir(parents=True,exist_ok=True)
        for p in folder.glob('*/state.json'):
            old=read_json(p,{})
            if old.get('operation_id')==operation:
                if old['status'] in ('interrupted','failed') and body.get('resume'):
                    ACTIVE[old['id']]={'auth':auth,'native_id':project['native_id']}
                    old.update(status='running',error='');self.save(old)
                    await self.dispatch(old,old['stage'])
                return self.public(old)
        rid=uuid.uuid4().hex;jid=self.store.job(owner,pid,'writing',{'subject':str(body.get('request',''))[:200]})
        selection=body.get('model_selection')
        run={'id':rid,'owner':owner,'project_id':pid,'operation_id':operation,'job_id':jid,
             'session_id':body.get('session_id',''),'turn_id':body.get('turn_id',''),'request':str(body.get('request','')),
             'history':body.get('history',[]),'model_selection':selection or None,'phase':body.get('phase') or current['phase'],
             'settings':current,'status':'running','stage':'intent','ticket':secrets.token_urlsafe(32),
             'created':now(),'updated':now(),'stage_history':[],'dify_runs':[],'outputs':{},'error':'',
             'workflow_url':read_json(META,{}).get('workflow_url',''),'tool_results':{},'cancel_requested':False}
        run.update(stage_plan=[x[0] for x in prompts.STAGES],
            l3=read_json(root/'.workbench/writing/L3_Journal_Genome.json',{}),
            l2=read_json(root/'.workbench/writing/L2_Manuscript_Alignment_State.json',{}),narrow={},wide={},review={})
        run.update(engine=body.get('engine','editor'),proposal=bool(body.get('proposal',False)),
            revision_mode=body.get('revision_mode',''),baseline_text=body.get('baseline_text',''),
            source_document=self.store.manuscript(owner,pid))
        if body.get('baseline_document_path'):
            baseline=read_json(child(root,body['baseline_document_path']))
            if not isinstance(baseline,dict) or not isinstance(baseline.get('content',{}).get('content'),list):
                raise ValueError('指定的候选底稿不是原生稿件文档')
            run['source_document']=baseline
            run['baseline_document_path']=body['baseline_document_path']
        run['scope_explicit']=bool(body.get('editorial_scope'))
        run['context_paths']=body.get('context_paths',[])
        if not isinstance(run['context_paths'],list):raise ValueError('当前写作资料需要项目路径列表')
        for path in run['context_paths']:child(root,path)
        run['editorial_scope']=synthesis.editorial_scope(body.get('editorial_scope'),
            fallback='local_edit' if run['revision_mode']=='incremental' else 'full_draft')
        run['reference_policy']=synthesis.reference_policy(body.get('reference_policy'))
        from .literature import read_index
        library={key:{**value,'source_path':'literature/'+key} for key,value in read_index(root).items()}
        supplied=body.get('source_manifest')
        if body.get('source_manifest_path'):
            supplied=read_json(child(root,body['source_manifest_path']))
            if not isinstance(supplied,list):raise ValueError('指定的来源清单需要是参考文献列表')
            run['source_manifest_path']=body['source_manifest_path']
        run['source_manifest']=synthesis.reference_manifest(run['source_document'],{} if supplied is not None else library,supplied)
        run['author_round']=bool(body.get('author_round',False))
        run['candidate_document']=deepcopy(run['source_document'])
        if run['author_round'] and run['baseline_text']:
            paragraphs=[p.strip() for p in re.split(r'\n\s*\n',run['baseline_text']) if p.strip()]
            nodes=run['candidate_document']['content']['content']
            split=next((i for i,n in enumerate(nodes) if n['type']=='heading'),len(nodes))
            if split==len(paragraphs):
                for i,p in enumerate(paragraphs):nodes[i]={'type':'paragraph','content':[{'type':'text','text':p}]}
                run['source_document']=deepcopy(run['candidate_document'])
        if body.get('reuse_run_id'):
            prior=self.load(owner,pid,body['reuse_run_id'])
            if prior.get('intent'):
                run['previous_intent']=deepcopy(prior['intent'])
                run['source_run_id']=prior['id']
        ACTIVE[rid]={'auth':auth,'native_id':project['native_id']};self.save(run)
        self.store.set_job(jid,status='running',stage='理解用户任务',step='intent')
        try:await self.dispatch(run,run['stage'])
        except Exception as exc:
            run=self.load(owner,pid,rid);run.update(status='failed',error=str(exc));self.save(run)
            self.store.set_job(jid,status='failed',stage='工作流启动失败',error=str(exc));raise
        return self.public(self.load(owner,pid,rid))

    async def restructure_native_sections(self,run,stage):
        """An explicit section rewrite uses native paragraphs and stable citations."""
        from .writing_revision import difference,revision_sections
        root=self.root(run['owner'],run['project_id']);folder=self.run_path(run['owner'],run['project_id'],run['id']).parent
        before=deepcopy(run['candidate_document'])
        role=prompts.WIDE if stage=='wide' else prompts.NARROW
        result=await self.generate(run,role+'\n'+synthesis.RESTRUCTURE_NOTE,{
            'user_request':run['request'],'phase':run['phase'],'intent':run['intent'],
            'editorial_scope':run['editorial_scope'],'reference_policy':run['reference_policy'],
            'source_manifest':synthesis.manifest_for_model(run['source_manifest']),'current_manuscript':revision_sections(before),
            'L2_State':run['l2'],'L3_Genome':run['l3'],
            'Literature_RAG_Slices':run.get('retrieved_evidence',[]),
            'project_assets':run['asset_index']['selected_assets']})
        candidate,receipt=synthesis.apply_section_restructure(before,result.get('sections',[]),
            run['editorial_scope']['sections'],run['source_manifest'],run['reference_policy'])
        run['candidate_document']=candidate
        result['actual_restructure']=receipt
        atomic_json(folder/(stage+'-candidate.json'),candidate)
        atomic_json(folder/(stage+'-restructure.json'),receipt)
        (folder/(stage+'-diff.html')).write_text(difference(before,candidate,'目标章节文献综合与论证重组'),encoding='utf8')
        return result

    async def revise_native_sections(self,run,stage,selection):
        from .writing_revision import revision_sections,apply_edits,edit_issue_ids,INCREMENTAL,difference
        from .writing_expression import selected_issue_ids,key_sentence_windows
        root=self.root(run['owner'],run['project_id']);folder=self.run_path(run['owner'],run['project_id'],run['id']).parent
        before=deepcopy(run['candidate_document']);sections=revision_sections(before)
        chosen=[s for s in sections if selection(s['title'])]
        batches=[];batch=[];size=0
        for section in chosen:
            length=len(json.dumps(section,ensure_ascii=False))
            if batch and size+length>24000:batches.append(batch);batch=[];size=0
            batch.append(section);size+=length
        if batch:batches.append(batch)
        reports=[];notes=[]
        for i,group in enumerate(batches):
            run['agent_stage']=stage+'_batch_'+str(i+1)
            selected_ids=selected_issue_ids(run.get('l2',{}).get('editorial_assessment'),run['request'])
            result=await self.generate(run,INCREMENTAL,{'user_request':run['request'],'round':run.get('author_round_number',1),
                'stage_role':dict(prompts.STAGES)[stage],'L2_State':run['l2'],'L3_Expression_Learning':run['l3'],
                'manuscript_title':before['title'],'manuscript_outline':[s['title'] for s in sections],
                'sections':group,'editorial_assessment':run.get('l2',{}).get('editorial_assessment'),
                'selected_issue_ids':sorted(selected_ids),'key_sentence_context':key_sentence_windows(group),
                'round_instructions':scoring.EDIT_NOTE if run.get('author_round') else ''})
            edits=result.get('edits',[]);not_selected=[]
            if run.get('author_round'):
                for edit in edits:edit['issue_ids']=edit_issue_ids(edit)
                selected=lambda e:bool(e['issue_ids']) and all(i in selected_ids for i in e['issue_ids'])
                not_selected=[{**e,'error':'该建议不属于本轮选中问题，保留供作者判断'} for e in edits if not selected(e)]
                edits=[e for e in edits if selected(e)]
            revised,report=apply_edits(run['candidate_document'],edits)
            report['rejected'].extend(not_selected)
            run['candidate_document']=revised;reports.append(report);notes.extend(result.get('author_notes',[]))
        run.pop('agent_stage',None)
        atomic_json(folder/(stage+'-candidate.json'),run['candidate_document'])
        atomic_json(folder/(stage+'-edits.json'),{'reports':reports,'author_notes':notes})
        (folder/(stage+'-diff.html')).write_text(difference(before,run['candidate_document'],'水分扩散稿件 · '+dict(prompts.STAGES)[stage]),encoding='utf8')
        return {'round':2 if stage=='review' else 1,'edited_fragments':sum(r['edited_fragments'] for r in reports),
                'rejected_edits':[e for r in reports for e in r['rejected']],'author_notes':notes,
                'candidate':stage+'-candidate.json','all_assertions_passed':False,'awaiting_author_review':True}

    def ticket_run(self,rid,ticket):
        if not re.fullmatch(r'[a-f0-9]{32}',rid):raise HTTPException(404,'任务不存在')
        with self.store.db() as db:
            rows=db.execute("SELECT owner,project FROM jobs WHERE kind='writing'").fetchall()
        for row in rows:
            p=self.run_path(row['owner'],row['project'],rid)
            if p.is_file():
                run=read_json(p)
                if not secrets.compare_digest(run['ticket'],ticket):raise HTTPException(403,'写作任务凭证无效')
                return run
        raise HTTPException(404,'写作任务不存在')

    async def accept_stage(self,rid,ticket,stage,workflow_run_id=''):
        run=self.ticket_run(rid,ticket)
        with self.store.lock('writing:'+rid):
            if run['status'] in TERMINAL:return {'accepted':True,'run_id':rid,'stage':stage,'status':run['status']}
            if stage!=run['stage']:return {'accepted':True,'run_id':rid,'status':'already_advanced','stage':run['stage']}
            if rid in TASKS and not TASKS[rid].done():return {'accepted':True,'run_id':rid,'stage':stage,'status':'running'}
            if rid not in ACTIVE:raise HTTPException(409,'请在原会话继续该写作任务')
            TASKS[rid]=asyncio.create_task(self.perform_stage(rid,run['owner'],run['project_id'],stage))
        return {'accepted':True,'run_id':rid,'stage':stage,'workflow_run_id':workflow_run_id}

    async def prepare_journal(self,run):
        root=self.root(run['owner'],run['project_id']);selected=run['settings'].get('journal')
        if isinstance(selected,str):
            from .journals import lookup
            selected=await lookup(selected)
        query=run.get('intent',{}).get('target_journal_query','')
        if not selected and query:
            async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
                r=await client.get('https://api.crossref.org/journals',params={'query':query,'rows':5});r.raise_for_status()
            rows=r.json()['message'].get('items',[])
            if rows:
                from .journals import crossref_journal
                selected=crossref_journal(rows[0])
        selected=selected or {'id':'general','name':'通用科技论文','homepage':'','issn':[]}
        cache=root/'.workbench/writing/journals'/re.sub(r'[^a-zA-Z0-9_-]','_',selected['id'])/'profile.json'
        prior=read_json(cache)
        if prior:return prior
        profile={'journal':selected,'retrieved_at':now(),'pages':[],'exemplar_candidates':[]}
        homepage=selected.get('homepage','')
        urls=[homepage]
        if 'sciencedirect.com/journal/' in homepage:
            urls=[homepage+'/about/aims-and-scope',homepage+'/publish/guide-for-authors']
        async with httpx.AsyncClient(timeout=45,trust_env=False,follow_redirects=True) as client:
            for url in [u for u in urls if u][:2]:
                try:
                    r=await client.get('https://tutor.example.invalid/research/dify/api/web-evidence',
                        headers=ACTIVE[run['id']]['auth'],params={'url':url})
                    r.raise_for_status();value=r.json()
                    profile['pages'].append({'url':url,**value})
                except (httpx.HTTPError,ValueError) as exc:profile['pages'].append({'url':url,'status':'unavailable','error':str(exc)[:300]})
            issn=next(iter(selected.get('issn',[])),'')
            if issn:
                try:
                    r=await client.get('https://api.crossref.org/journals/'+issn+'/works',params={
                        'query':run.get('intent',{}).get('target_theme','')[:180],'rows':8,'sort':'relevance'})
                    r.raise_for_status()
                    items=r.json()['message'].get('items',[])
                    if not items:
                        r=await client.get('https://api.crossref.org/journals/'+issn+'/works',params={'rows':8,'sort':'published','order':'desc'})
                        r.raise_for_status();items=r.json()['message'].get('items',[])
                    profile['exemplar_candidates']=[{'title':next(iter(x.get('title',[])),''),'doi':x.get('DOI',''),
                        'url':x.get('URL',''),'publisher':x.get('publisher',''),'links':x.get('link',[])} for x in items]
                except httpx.HTTPError as exc:profile['candidate_error']=str(exc)[:300]
        atomic_json(cache,profile)
        return profile

    async def retrieve_evidence(self,run):
        queries=run.get('intent',{}).get('research_queries',[])[:2]
        if not queries:return []
        auth=ACTIVE[run['id']]['auth'];project=self.store.get(run['owner'],run['project_id'])
        results=[]
        async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
            for query in queries:
                try:
                    r=await client.post('https://tutor.example.invalid/research/dify/api/evidence',headers=auth,
                        json={'project_id':run['project_id'],'workspace_id':project['native_id'],'query':str(query)[:600],
                              'sources':['knowledge','papers','web'],'limit':5})
                    r.raise_for_status();results.append(r.json())
                except (httpx.HTTPError,ValueError) as exc:results.append({'query':query,'status':'unavailable','error':str(exc)[:400]})
        return results

    async def perform_stage(self,rid,owner,pid,stage):
        try:
            run=self.load(owner,pid,rid);root=self.root(owner,pid);folder=self.run_path(owner,pid,rid).parent
            self.store.set_job(run['job_id'],status='running',stage=dict(prompts.STAGES)[stage],step=stage)
            payload={'user_request':run['request'],'phase':run['phase'],'current_manuscript':run.get('baseline_text') or document_markdown(run.get('source_document') or self.store.manuscript(owner,pid)),
                     'history':run['history'],'previous_state':read_json(root/'.workbench/writing/L2_Manuscript_Alignment_State.json',{}),
                     'editorial_scope':run.get('editorial_scope'), 'reference_policy':run.get('reference_policy',{}),
                     'source_manifest':synthesis.manifest_for_model(run.get('source_manifest',[]))}
            if stage=='intent':
                index=await asyncio.to_thread(inventory,root,run['request'])
                explicit=[]
                for relative in run.get('context_paths',[]):
                    path=child(root,relative)
                    if not path.is_file():raise ValueError('指定的当前写作资料不存在：'+relative)
                    explicit.append({'path':relative,'modified':path.stat().st_mtime,
                        'text':path.read_text(encoding='utf8')[:16000],'total_chars':path.stat().st_size})
                selected={a['path'] for a in explicit}
                index['selected_assets']=explicit+[a for a in index['selected_assets'] if a['path'] not in selected]
                result=await self.generate(run,prompts.INTENT,{**payload,'phase_selection':run['phase'],
                    'project':self.store.get(owner,pid)['name'],'settings':run['settings'],
                    'previous_intent':run.get('previous_intent'),
                    'assets':index['files'][:250],'selected_assets':index['selected_assets'][:5]})
                selected_phase=run['phase'] if run['phase'] in prompts.PHASES else result.get('phase','draft')
                if selected_phase not in prompts.PHASES:selected_phase='draft'
                run.update(intent=result,phase=selected_phase,asset_index=index)
                if not run.get('scope_explicit') and result.get('editorial_scope'):
                    run['editorial_scope']=synthesis.editorial_scope(result['editorial_scope'])
                if not run['reference_policy']:
                    run['reference_policy']=synthesis.reference_policy(result.get('reference_policy'))
                mode=run['editorial_scope']['mode']
                run['revision_mode']={'local_edit':'incremental','section_restructure':'section_restructure'}.get(mode,'')
                run['intent']['editorial_scope']=deepcopy(run['editorial_scope'])
                run['intent']['reference_policy']=deepcopy(run['reference_policy'])
                requested=result.get('execution_stages')
                if isinstance(requested,list) and requested:
                    run['stage_plan']=['intent']+[key for key,_ in prompts.STAGES if key!='intent' and (key in requested or key in ('review','deliver'))]
                if mode=='section_restructure':
                    titles=' '.join(run['editorial_scope']['sections'])
                    writing_stage='wide' if re.search(r'摘要|引言|结论|abstract|introduction|conclusion',titles,re.I) else 'narrow'
                    run['stage_plan']=['intent','exemplar','alignment',writing_stage,'review','deliver']
            elif stage=='exemplar':
                run['journal']=await self.prepare_journal(run)
                selected=run['settings'].get('exemplar_paths') or []
                if not selected:
                    matches=[a['path'] for a in run['asset_index']['selected_assets'] if a['path'].lower().endswith('.md')
                             and any(v in a['path'].lower() for v in ['reference','feng','bae','paper'])]
                    selected=matches[:3]
                    if not selected:selected=[a['path'] for a in run['asset_index']['files'] if a['path'].lower().endswith('.pdf')][:2]
                parsed=await asyncio.to_thread(tools.exemplar_structural_deconstructor,root,selected,
                    json.dumps(run['journal'].get('pages',[]),ensure_ascii=False))
                # Paragraph windows retain their source and section context; the full parse is saved separately.
                atomic_json(folder/'exemplar-structure.json',parsed)
                texts=[{**d,'paragraphs':d['paragraphs'][:100]} for d in parsed['documents']]
                result=await self.generate(run,prompts.EXEMPLAR,{'journal':run['journal'],'documents':texts,'intent':run['intent'],
                    'macro_slots':prompts.SLOTS,'micro_rhetorical_lens':prompts.LENSES})
                run['l3']=result;run['tool_results']['exemplar_structural_deconstructor']={'path':str((folder/'exemplar-structure.json').relative_to(root)),'documents':len(texts)}
                atomic_json(root/'.workbench/writing/L3_Journal_Genome.json',result)
            elif stage=='alignment':
                from .writing_expression import key_sentence_windows
                from .writing_revision import revision_sections
                assets=run['asset_index']['selected_assets'];decl=read_json(root/'project/data/quantities.json',{})
                run['retrieved_evidence']=await self.retrieve_evidence(run)
                atomic_json(folder/'retrieved-evidence.json',run['retrieved_evidence'])
                audit=await asyncio.to_thread(tools.intrinsic_scientific_rigor_auditor,assets,decl)
                metrics=[]
                for spec in read_json(root/'project/data/writing-metrics.json',{}).get('metrics',[]):
                    metrics.append(await asyncio.to_thread(tools.comparative_metric_calculator,root,**spec))
                assessment_note=synthesis.STRUCTURE_ASSESSMENT_NOTE if run.get('revision_mode')=='section_restructure' else scoring.ALIGNMENT_NOTE
                result=await self.generate(run,prompts.ALIGNMENT+('\n'+assessment_note if run.get('author_round') else ''),{**payload,'intent':run['intent'],'L3_Genome':run['l3'],
                    'Scattered_Assets':assets,'Literature_RAG_Slices':run['retrieved_evidence'],
                    'rubric':scoring.RUBRIC,'key_sentence_context':key_sentence_windows(revision_sections(run['source_document'])),
                    'MCP_Reports':{'rigor_audit':audit,'comparative_metrics':metrics}})
                if run.get('author_round'):
                    result['editorial_assessment']=scoring.normalize_score(result['editorial_assessment'],use_baseline=True)
                    result['editorial_assessment'].setdefault('author_expression_targets',result.get('author_expression_targets',[]))
                run['l2']=result;run['tool_results'].update(intrinsic_scientific_rigor_auditor=audit,comparative_metric_calculator=metrics)
                atomic_json(root/'.workbench/writing/L2_Manuscript_Alignment_State.json',result)
            elif stage=='narrow':
                if run.get('revision_mode')=='section_restructure':
                    result=await self.restructure_native_sections(run,stage)
                elif run.get('revision_mode')=='incremental':
                    result=await self.revise_native_sections(run,stage,lambda title:bool(re.search(r'^(?:2|3)(?:\.|\s)|方法|结果|分析|method|result|analysis',title,re.I)))
                else:result=await self.generate(run,prompts.NARROW+('\n'+scoring.EDIT_NOTE if run.get('author_round') else ''),{**payload,'intent':run['intent'],'L2_State':run['l2'],
                    'L3_Native_Bank':run['l3'].get('native_expression_bank',{}),'L1_Buffer':read_json(root/'.workbench/writing/L1_Paragraph_Flow_Buffer.json',{}),
                    'Current_Section_Assets':run['asset_index']['selected_assets']})
                run['narrow']=result
                atomic_json(root/'.workbench/writing/L1_Paragraph_Flow_Buffer.json',result.get('l1_buffer',{}))
            elif stage=='wide':
                if run.get('revision_mode')=='section_restructure':
                    result=await self.restructure_native_sections(run,stage)
                elif run.get('revision_mode')=='incremental':
                    result=await self.revise_native_sections(run,stage,lambda title:bool(re.search(r'摘要|引言|结论|abstract|introduction|conclusion',title,re.I)))
                else:result=await self.generate(run,prompts.WIDE+('\n'+scoring.EDIT_NOTE if run.get('author_round') else ''),{**payload,'intent':run['intent'],'L2_State':run['l2'],
                    'L3_Genome':run['l3'],'Locked_Narrow_Waist':run['narrow'],
                    'Literature_RAG_Slices':run.get('retrieved_evidence',[]),'project_assets':run['asset_index']['selected_assets']})
                run['wide']=result
            elif stage=='review':
                if run.get('revision_mode')=='incremental' and not run.get('author_round'):
                    result=await self.revise_native_sections(run,stage,lambda title:True)
                    run['review']=result
                else:
                    result=await self.review_text(run,payload,folder)
                run['review']=result
            elif stage=='deliver':
                await self.deliver_run(run,root,folder)
                return
            else:raise ValueError('未知写作阶段')
            atomic_json(folder/(stage+'.json'),result)
            run['stage_history'].append({'stage':stage,'completed':now(),'output':stage+'.json','prompt_version':prompts.VERSION})
            current=self.load(owner,pid,rid)
            if current['status']=='cancelled':return
            run['dify_runs']=current.get('dify_runs',[])
            plan=run.get('stage_plan') or [x[0] for x in prompts.STAGES]
            next_stage=plan[plan.index(stage)+1]
            run['stage']=next_stage;self.save(run)
            TASKS.pop(rid,None)
            await self.dispatch(run,next_stage)
        except asyncio.CancelledError:
            run=self.load(owner,pid,rid)
            if run['status']!='cancelled':run.update(status='cancelled');self.save(run)
            self.store.set_job(run['job_id'],status='cancelled',stage='写作已停止')
        except Exception as exc:
            run=self.load(owner,pid,rid);run.update(status='failed',error=str(exc));self.save(run)
            self.store.set_job(run['job_id'],status='failed',stage=dict(prompts.STAGES).get(stage,stage)+'未完成',error=str(exc))

    async def review_text(self,run,payload,folder):
        from .writing_expression import key_sentence_windows,expression_feedback_coverage
        from .writing_revision import revision_sections
        native_candidate=run.get('revision_mode') in ('incremental','section_restructure')
        if native_candidate:draft=document_markdown(run['candidate_document'])
        else:
            parts=[]
            for section in run.get('wide',{}).get('sections',[]):
                parts.append('## '+(section.get('title') or section.get('id','')))
                parts.extend(p if isinstance(p,str) else p.get('text','') for p in section.get('paragraphs',[]))
            parts.extend(p.get('text','') for p in run.get('narrow',{}).get('paragraphs',[]))
            draft='\n\n'.join(p for p in parts if p)
        diagnostics=tools.rhetorical_alignment_inspector(draft,run['l3'])
        result={}
        coverage=[]
        if run.get('revision_mode')=='incremental':
            targets=run.get('l2',{}).get('editorial_assessment',{}).get('author_expression_targets',[])
            coverage=expression_feedback_coverage(run.get('source_document',run['candidate_document']),run['candidate_document'],targets,run.get('request',''))
        for attempt in range(1 if run.get('author_round') else 3):
            result=await self.generate(run,prompts.REVIEW+('\n'+scoring.REVIEW_NOTE if run.get('author_round') else ''),{'Manuscript_Draft':draft,'L3_Genome':run['l3'],
                'L2_State':run['l2'],'Inspector_Diagnostics':diagnostics,'intent':run['intent'],'phase':run['phase'],
                'rubric':scoring.RUBRIC,'before_assessment':run.get('l2',{}).get('editorial_assessment'),
                'key_sentence_context':key_sentence_windows(revision_sections(run['candidate_document'])) if native_candidate else [],
                'reference_policy':run.get('reference_policy',{}),'source_manifest':synthesis.manifest_for_model(run.get('source_manifest',[])),
                'editorial_scope':run.get('editorial_scope'),
                'actual_author_feedback_coverage':coverage,
                'current_input':{**payload,'source_assets':run['asset_index']['selected_assets']}})
            if run.get('author_round'):
                result['after_assessment']=scoring.normalize_score(result['after_assessment'],baseline_assessment=run.get('l2',{}).get('editorial_assessment'))
                result['final_text']=draft
                result['all_assertions_passed']=False
                result['author_approval']='pending'
                result['model_author_feedback_coverage']=result.get('author_feedback_coverage',[])
                result['author_feedback_coverage']=coverage
            draft=result.get('final_text') or draft
            atomic_json(folder/f'review-{attempt+1}.json',result)
            if result.get('all_assertions_passed'):break
            diagnostics=tools.rhetorical_alignment_inspector(draft,run['l3'])
        run['tool_results']['rhetorical_alignment_inspector']=diagnostics
        return result

    async def deliver_run(self,run,root,folder):
        owner,pid,rid=run['owner'],run['project_id'],run['id']
        native_candidate=run.get('revision_mode') in ('incremental','section_restructure')
        text=document_markdown(run['candidate_document']) if native_candidate else run['review'].get('final_text') or ''
        target=root/'project/docs/writing'/run['phase']
        if run.get('proposal'):target=target/run['id']
        path=target/('manuscript.md' if run['intent'].get('task_kind')=='full_paper' or native_candidate else 'current-task.md')
        path.parent.mkdir(parents=True,exist_ok=True)
        self.store.replace(owner,pid,path,text.encode('utf-8'),'Partner '+prompts.PHASES[run['phase']]+'写作工作流')
        relative=path.relative_to(root).as_posix()
        run['outputs']={'path':relative,'url':'/research/api/projects/'+pid+'/file?path='+quote(relative.removeprefix('project/')),
            'text':text,'passed_red_team':bool(run['review'].get('all_assertions_passed'))}
        if run.get('proposal'):
            run['outputs']['author_approval']='pending'
            if native_candidate:
                from .writing_revision import difference
                atomic_json(target/'manuscript-candidate.json',run['candidate_document'])
                (target/'changes.html').write_text(difference(run['source_document'],run['candidate_document']),encoding='utf8')
                from .manuscripts import export_manuscript
                export_document=deepcopy(run['candidate_document'])
                blocks=export_document['content']['content']
                scope=run.get('editorial_scope',{})
                if scope.get('mode')=='section_restructure' and len(scope.get('sections',[]))==1 and blocks and blocks[0].get('type')=='paragraph':
                    # A stand-alone section has no author/affiliation front matter.
                    blocks.insert(0,{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':scope['sections'][0]}]})
                data,_,_=await asyncio.to_thread(export_manuscript,root,export_document,'docx')
                (target/'manuscript.docx').write_bytes(data)
                run['outputs'].update(docx_path=(target/'manuscript.docx').relative_to(root).as_posix(),
                    diff_path=(target/'changes.html').relative_to(root).as_posix())
        elif run['intent'].get('task_kind') in ('full_paper','section','polish'):
            doc=self.store.manuscript(owner,pid)
            # Apply explicit section edits to the source document as one native revision.
            if run['intent'].get('task_kind')=='full_paper' or not doc['revision']:
                saved=self.store.save_manuscript(owner,pid,markdown_document(text,doc));run['outputs']['manuscript_revision']=saved['revision']
        run.update(status='completed',error='');self.save(run)
        self.store.set_job(run['job_id'],status='completed',stage='写作成果已保存',step='deliver',
            result={'url':run['outputs']['url'],'name':path.name,'writing_run_id':rid,'phase':run['phase']})
        ACTIVE.pop(rid,None);return

def install(app,store):
    service=WritingService(store)

    @app.get('/research/api/projects/{pid}/writing')
    async def state(pid:str,user=Depends(actor)):
        root=service.root(user['id'],pid)
        rows=[read_json(p,{}) for p in (root/'.workbench/writing/runs').glob('*/state.json')]
        rows.sort(key=lambda r:r.get('created',''),reverse=True)
        return {'settings':settings(root),'runs':[service.public(r) for r in rows[:30]],'stages':prompts.STAGES,
                'tool_sources':tools.TOOL_SOURCES,'workflow':read_json(META,{})}

    @app.put('/research/api/projects/{pid}/writing/settings')
    async def configure(pid:str,payload:dict,user=Depends(actor)):
        return save_settings(service.root(user['id'],pid),payload)

    @app.post('/research/api/projects/{pid}/writing/start')
    async def start(request:Request,pid:str,payload:dict,user=Depends(actor)):
        return await service.start(user['id'],pid,payload,headers(request))

    @app.post('/research/api/writing/dispatch')
    async def dispatch(request:Request,payload:dict,user=Depends(actor)):
        workspace=payload.get('workspace_id','')
        project=next((p for p in store.list(user['id']) if p['native_id']==workspace),None)
        if not project:raise HTTPException(404,'当前会话未关联研究项目')
        mode=payload.get('mode',settings(service.root(user['id'],project['id']))['mode'])
        return await service.start(user['id'],project['id'],{**payload,'mode':mode},headers(request))

    @app.get('/research/api/projects/{pid}/writing/runs/{rid}')
    async def detail(pid:str,rid:str,user=Depends(actor)):
        return service.public(service.load(user['id'],pid,rid),True)

    @app.post('/research/api/projects/{pid}/writing/runs/{rid}/cancel')
    async def cancel(pid:str,rid:str,user=Depends(actor)):
        run=service.load(user['id'],pid,rid)
        if run['status'] not in TERMINAL:
            run.update(status='cancelled');service.save(run)
            if rid in TASKS:TASKS[rid].cancel()
            store.set_job(run['job_id'],status='cancelled',stage='写作已停止')
        return service.public(run)

    @app.post('/research/api/projects/{pid}/writing/runs/{rid}/resume')
    async def resume(request:Request,pid:str,rid:str,user=Depends(actor)):
        run=service.load(user['id'],pid,rid)
        return await service.start(user['id'],pid,{'operation_id':run['operation_id'],'resume':True},headers(request))

    @app.post('/research/api/writing/internal/runs/{rid}/dispatch')
    async def stage(request:Request,rid:str,payload:dict):
        return await service.accept_stage(rid,request.headers.get('x-writing-ticket',''),payload.get('stage',''),
                                          request.headers.get('x-dify-workflow-run-id',''))

    @app.post('/research/api/writing/internal/runs/{rid}/tools/{name}')
    async def tool(request:Request,rid:str,name:str,payload:dict):
        run=service.ticket_run(rid,request.headers.get('x-writing-ticket',''));root=service.root(run['owner'],run['project_id'])
        if name=='exemplar_structural_deconstructor':return await asyncio.to_thread(tools.exemplar_structural_deconstructor,root,**payload)
        if name=='intrinsic_scientific_rigor_auditor':return await asyncio.to_thread(tools.intrinsic_scientific_rigor_auditor,run.get('asset_index',{}).get('selected_assets',[]),payload.get('declarations'))
        if name=='comparative_metric_calculator':return await asyncio.to_thread(tools.comparative_metric_calculator,root,**payload)
        if name=='rhetorical_alignment_inspector':return tools.rhetorical_alignment_inspector(payload['draft_segment'],run.get('l3',{}),payload.get('macro_slot','FULL_PAPER'))
        raise HTTPException(404,'写作工具不存在')

    return service
