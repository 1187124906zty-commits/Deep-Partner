"""Typed project adapters for native DeepCode tools and cluster PDF parsing."""
from pathlib import Path
import asyncio,base64,hashlib,json,os,uuid,threading,time
import httpx
from .storage import atomic_json,child

class ToolUnavailable(ValueError):
    code='tool_bridge_unavailable'
    retryable=True
    def __init__(self,message,code=None):
        super().__init__(message)
        if code:self.code=code

class ToolPending(ToolUnavailable):
    """An existing external task is running; release the runner until next poll."""
    code='external_task_pending'

class SubmissionUncertain(ValueError):
    code='submission_uncertain'

class ToolNotFound(ValueError):
    code='external_task_not_found'

async def bound_call(owner,pid,jid,binding,state,persist,start):
    """Reconcile an uncertain submission before idempotently replaying its ID."""
    if binding.get('submitted'):
        try:return await tool_call(owner,pid,jid,'status')
        except ToolNotFound:
            # The bridge authoritatively confirmed absence, and start deduplicates
            # by this same ID. Keep the original request, including input bytes.
            if not binding.get('request'):raise SubmissionUncertain('原始提交请求缺失，不能重建任务')
    else:
        binding['request']=start
        binding['submitted']=True;persist(state)
    return await tool_call(owner,pid,jid,'start',**binding['request'])

def authorized_binding(binding,owner,pid,workspace):
    return binding.get('authorization')=={'owner':owner,'project_id':pid,'workspace_id':workspace}

def bind_authorization(binding,owner,pid,workspace):
    # An authorization receipt, never a cookie, token, or reusable account credential.
    binding['authorization']={'owner':owner,'project_id':pid,'workspace_id':workspace}

def claim_run(path):
    """OS-held nonblocking lock shared by threads, app instances and processes."""
    path.parent.mkdir(parents=True,exist_ok=True)
    handle=path.open('a+b')
    try:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        handle.close();return None
    return handle

def release_run(handle):
    if os.name=='nt':
        import msvcrt
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
    handle.close()
_parsing_active=set()
_parsing_lock=threading.Lock()
_recovery_started=False
_recovery_services={}

def recovery_project_allowed(pid):
    raw=os.environ.get('WORKBENCH_FLOW_RECOVERY_PROJECTS')
    if raw is None:return True
    try:
        projects=json.loads(raw)
        return isinstance(projects,list) and all(isinstance(p,str) for p in projects) and pid in projects
    except (ValueError,TypeError):return False

def bridge_config():
    path=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/tool-bridge/bridge.json'
    if not path.is_file():raise ValueError('本机原生工具桥尚未配置；先运行 dp workflow 以恢复已绑定工具')
    return json.loads(path.read_text(encoding='utf8'))

def native_execution_allowed(config,pid):
    return config.get('native_execution_enabled') is True or pid in config.get('native_execution_projects',[])

async def tool_call(owner,pid,jid,action,**extra):
    config=bridge_config();payload={'action':action,'id':jid,'project_id':pid,'owner_key':uuid.uuid5(uuid.NAMESPACE_URL,owner).hex,**extra}
    async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
        try:response=await client.post(config['url']+'/call',headers={'x-partner-tools':config['token']},json=payload)
        except httpx.HTTPError as error:raise ToolUnavailable('工具桥连接失败：'+type(error).__name__+'；保留执行 ID，恢复工具桥后接续') from None
        if response.status_code in (502,503,504):raise ToolUnavailable('工具桥基础设施暂不可用；保留原执行 ID')
        if response.status_code==404 and action in ('status','collect'):
            raise ToolNotFound('工具桥已确认该执行 ID 不存在')
        if not response.is_success:raise ValueError('Native tool request failed (HTTP '+str(response.status_code)+')')
        value=response.json()
        error=value.get('error')
        if isinstance(error,dict) and error.get('code') in (
                'tool_unavailable','bridge_transport_error','mcp_transport_error','network_error',
                'ssh_unavailable','cluster_unavailable','connection_error','service_unavailable','proxy_error'):
            if error.get('retryable') is not False:
                raise ToolUnavailable('工具基础设施暂不可用；保留原执行 ID',error['code'])
        return value

async def native_code(store,owner,pid,jid,payload,auth,state,persist):
    from .native import BASE
    if not native_execution_allowed(bridge_config(),pid):raise PermissionError('当前项目尚未启用 DeepCode 原生执行权限；原生工具路由已准备，未改用外层LLM执行')
    project=store.get(owner,pid);root=store.path(owner,pid);inputs=[]
    binding=state.setdefault('native_code',{'id':jid,'versions':{}})
    sid=binding.get('session_id') or payload.session_id
    if not authorized_binding(binding,owner,pid,project['native_id']):
        async with httpx.AsyncClient(headers=auth,timeout=30,trust_env=False) as client:
            response=await client.get(BASE+'/api/auth/profile');response.raise_for_status();profile=response.json()
            if profile.get('id') and profile['id']!=owner:raise PermissionError('原生账户不属于当前任务')
            if profile.get('role')!='admin' and not profile.get('is_admin'):raise PermissionError('原生代码执行沿用现有管理员权限')
            if not sid:
                response=await client.get(BASE+'/api/sessions',params={'dt_workspace':project['native_id'],'workspace_id':project['native_id'],'limit':1});response.raise_for_status()
                sessions=response.json().get('sessions',[])
                if sessions:sid=sessions[0].get('id') or sessions[0].get('session_id')
            if not sid:raise ValueError('请先连接当前项目研究会话，或提供 session_id')
            response=await client.get(BASE+'/api/sessions/'+sid,params={'dt_workspace':project['native_id']});response.raise_for_status()
            conversation=response.json();workspace=conversation.get('workspace_id') or conversation.get('preferences',{}).get('workspace_id')
            if workspace and workspace!=project['native_id']:raise ValueError('代码会话不属于当前项目')
        bind_authorization(binding,owner,pid,project['native_id'])
        binding['session_id']=sid;persist(state)
    submitted=binding.get('submitted') or binding.get('workflow_run_id')
    if not submitted:
        for path in payload.input_paths:
            target=child(root/'project',path)
            if not target.is_file() or target.stat().st_size>256000:raise ValueError('代码输入应为不超过256KB的明确项目文件')
            binding['versions'][path]=target.stat().st_mtime_ns;inputs.append({'path':path,'content_b64':base64.b64encode(target.read_bytes()).decode()})
        instruction=payload.instruction or payload.query
        instruction+='\n\n当前项目：'+pid+'；项目代码保存根：'+payload.publish_root+'；交接文件：'+(', '.join(payload.input_paths) or '无显式输入文件')+'。先从这些材料和现有项目确定问题、方法、代码入口与预期输出，沿用已有说明，不额外创建合同或台账。'
        instruction+='\n按有意义的阶段实现并集中验证，复用仍有效的结果，通过且无新改动、失败或疑点即交付；不逐文件微测或做主线无关的重复审查；最终或关键阶段产物的有依据独立评审仍按项目标准进行。复用现有求解器与环境，只为实际算法和调用需要增加抽象。数值工作选择影响结论的方程、量纲、初边值条件、稳定性及必要收敛检查，用解析解、成熟求解器或可信数据作独立参照，不让测试重复同一错误公式自证。论文复现保持目标数据与实验，小运行不冒充复现完成。失败先具体诊断与有限修正，同一路径无新证据时停止并报告真实缺口及影响；无关基准不无限阻断主线，替代方案注明范围变化。代码生成、软件验证、小基准与目标实验完成分别报告。'
        instruction+='\n\n输入文件已在当前执行目录。按已授权需求完成规划、实现与测试；大型计算通过现有SSH和Slurm运行。代码执行和正式项目保存分别返回真实状态。'
        start={'payload':{'code_engine':payload.code_engine,'instruction':instruction,
                    'workflow_options':payload.workflow_options,'publish_root':payload.publish_root,'conversation_id':sid,
                    'workspace_authorization':{'project_id':pid,'owner_key':uuid.uuid5(uuid.NAMESPACE_URL,owner).hex,
                                               'file_edit':True,'python_tests':True}},'inputs':inputs}
    else:
        start=binding.get('request')
        binding['submitted']=True
    result=await bound_call(owner,pid,jid,binding,state,persist,start)
    binding.update({k:result[k] for k in ('workflow_run_id','native_thread_id','mcp_session_id','stage','status','tool_calls') if k in result});persist(state)
    if result['status']=='waiting_input':return {'status':'requires_input','native_tool':True,'task_id':jid,'session_id':sid,
             'workflow_run_id':result.get('workflow_run_id'),'interaction':(result.get('native') or {}).get('checkpoint',{}).get('interaction'),'native':result.get('native')}
    if result['status'] not in ('failed','cancelled','completed'):raise ToolPending('DeepCode 原任务仍在执行，稍后查询同一 ID')
    if result['status']!='completed':raise ValueError('DeepCode 原生工作流未完成：'+json.dumps(result.get('error') or {k:(result.get('native') or {}).get(k) for k in ('errorCode','errorMessage')},ensure_ascii=False))
    collected=await tool_call(owner,pid,jid,'collect');saved=[]
    for item in collected['files']:
        target=child(root/'project',item['path']);expected=binding['versions'].get(item['path'])
        data=base64.b64decode(item['content_b64'],validate=True);digest=hashlib.sha256(data).hexdigest()
        artifacts=binding.setdefault('artifacts',{});receipt=artifacts.get(item['path'])
        if receipt and receipt['sha256']!=digest:raise ValueError('原生回交产物版本已变化')
        identical=target.is_file() and target.read_bytes()==data
        if not (receipt and identical):
            if target.exists() and (expected is None or target.stat().st_mtime_ns!=expected):raise ValueError('代码目标版本已变化，请先回读：'+item['path'])
            artifacts[item['path']]={'sha256':digest,'status':'saving'};persist(state)
            store.replace(owner,pid,target,data,'原生 DeepCode 工作流回交')
        if target.read_bytes()!=data:raise ValueError('代码保存回读失败')
        artifacts[item['path']]={'sha256':digest,'status':'saved'};persist(state)
        saved.append({'path':item['path'],'bytes':len(data),'saved':True,'read_back':True})
    return {'status':'completed','native_tool':True,'task_id':jid,'session_id':sid,'files':saved,
            'published_reply':collected['summary'],'verification':collected['verification'],'tool_calls':collected['tool_calls']}

async def parse_pdf(store,owner,pid,asset,state,persist):
    from .literature import read_index
    root=store.path(owner,pid);index=read_index(root)
    if asset not in index:raise ValueError('解析文献不属于当前项目')
    source=child(root/'literature',asset);data=source.read_bytes();digest=hashlib.sha256(data).hexdigest()
    prefix='docs/literature/parsed/'+digest+'/';cache=child(root/'project',prefix+'receipt.json')
    if cache.is_file():
        receipt=json.loads(cache.read_text(encoding='utf8'))
        if receipt.get('sha256')==digest and child(root/'project',prefix+'pages.json').is_file():return {'asset':asset,'cached':True,'path':prefix,**receipt}
    jid='parse-'+uuid.uuid5(uuid.NAMESPACE_URL,owner+':'+pid+':'+digest).hex
    payload={'operation':'parse_pdf','sha256':digest,'pdf_b64':base64.b64encode(data).decode()}
    binding=state.setdefault('parse_bindings',{}).setdefault(asset,{'id':jid})
    if state.get('parsing',{}).get(asset):binding['submitted']=True
    row=await bound_call(owner,pid,jid,binding,state,persist,{'payload':payload})
    state.setdefault('parsing',{})[asset]={k:row.get(k) for k in ('id','status','cluster')};persist(state)
    if row['status'] not in ('completed','failed','cancelled'):raise ToolPending('原PDF解析任务仍在运行，稍后查询同一 ID')
    if row['status']!='completed':raise ValueError('集群PDF解析未完成：'+str(row.get('error')))
    result=row['result'];receipt={**result['receipt'],'cluster_path':result['cluster_path'],'asset':asset}
    for name,content in [('paper.md',result['markdown']),('pages.json',json.dumps(result['packet'],ensure_ascii=False)),('receipt.json',json.dumps(receipt,ensure_ascii=False,indent=2))]:
        target=child(root/'project',prefix+name);store.replace(owner,pid,target,content.encode(),'集群PDF解析产物')
        if target.read_text(encoding='utf8')!=content:raise ValueError('解析产物回读不一致')
    return {'path':prefix,'cached':result['cached'],**receipt}

def parsed_excerpts(store,owner,pid,assets,max_sources,read_pages=None):
    from .literature import read_index
    from .research_flow import stable,identifier
    root=store.path(owner,pid);index=read_index(root);documents=[]
    for asset in assets[:max_sources]:
        source=child(root/'literature',asset);digest=hashlib.sha256(source.read_bytes()).hexdigest()
        packet=json.loads(child(root/'project','docs/literature/parsed/'+digest+'/pages.json').read_text(encoding='utf8'))
        if packet['sha256']!=digest:raise ValueError('解析材料与原PDF版本不符')
        wanted=(read_pages or {}).get(asset)
        candidates=wanted or list(dict.fromkeys(list(range(1,min(6,packet['page_count'])+1))+list(range(max(7,packet['page_count']-1),packet['page_count']+1))))
        if any(not isinstance(p,int) or p<1 or p>packet['page_count'] for p in candidates):raise ValueError('指定读取页码超出PDF范围')
        pages=[];budget=14000;by_page={p['page']:p for p in packet['pages']}
        for number in candidates:
            if budget<=0:break
            text=by_page[number]['text'][:min(4500,budget)];budget-=len(text)
            if text:pages.append({'page':number,'text':text})
        metadata=index[asset];documents.append({'asset':asset,'title':metadata.get('title',asset),'doi':metadata.get('doi',''),'pages':pages,
            'total_pages':packet['page_count'],'coverage':'bounded excerpts from verified cluster parsing; not a full-paper review',
            'id':stable('paper',identifier(metadata) or asset),'parser_job_id':packet.get('cluster_job_id')})
    return documents

def enqueue_parse(store,owner,pid,asset):
    """PDF ingestion always schedules parsing, without blocking the upload response."""
    from .research_flow import RUNNERS
    with store.lock('cluster-parse:'+pid):
        with store.db() as db:
            rows=db.execute("SELECT id,result FROM jobs WHERE owner=? AND project=? AND kind='cluster-pdf-parse' AND status IN ('queued','running')",(owner,pid)).fetchall()
        existing=next((r['id'] for r in rows if json.loads(r['result']).get('asset')==asset),None)
        if existing:return {'job_id':existing,'status':'queued','duplicate':True}
        jid=store.job(owner,pid,'cluster-pdf-parse',{'subject':asset,'asset':asset})
    schedule_parse(store,owner,pid,asset,jid)
    return {'job_id':jid,'status':'queued'}

def schedule_parse(store,owner,pid,asset,jid):
    from .research_flow import RUNNERS,defer_run
    handle=claim_run(store.path(owner,pid)/'.workbench/research-flow/parse-locks'/jid)
    if handle is None:return
    with _parsing_lock:
        if jid in _parsing_active:release_run(handle);return
        _parsing_active.add(jid)
    def work():
        with store.db() as db:row=db.execute('SELECT result FROM jobs WHERE id=?',(jid,)).fetchone()
        state=json.loads(row['result']) if row else {};state['asset']=asset
        def persist(value):store.set_job(jid,status='running',step='parse',stage='集群PDF解析中',result=value)
        try:
            result=asyncio.run(parse_pdf(store,owner,pid,asset,state,persist));store.set_job(jid,status='completed',step='save',stage='集群解析产物已保存并回读',result={'asset':asset,**result})
        except ToolUnavailable as error:
            retry=defer_run(state,error)
            state['recovery']['service']='tools'
            store.set_job(jid,status='waiting_service' if state['recovery']['status']=='waiting_service' else 'queued',stage='等待本机工具连接，随后自动接续解析',result=state,error=error.code)
        except Exception as error:store.set_job(jid,status='failed',stage='解析未完成，原PDF及执行ID保留',result=state,error=str(error)[-1400:])
        finally:
            release_run(handle)
            with _parsing_lock:_parsing_active.discard(jid)
    try:RUNNERS.submit(work)
    except Exception:
        release_run(handle)
        with _parsing_lock:_parsing_active.discard(jid)
        raise

def recover_parses(store,now_ts=None):
    from .research_flow import service_health
    clock=time.time() if now_ts is None else now_ts
    with store.db() as db:
        rows=db.execute("SELECT id,owner,project,result FROM jobs WHERE kind='cluster-pdf-parse' AND status IN ('queued','running','interrupted','waiting_service')").fetchall()
    for row in rows:
        if not recovery_project_allowed(row['project']):continue
        result=json.loads(row['result']);recovery=result.get('recovery') or {}
        if recovery.get('status') in ('stopped','resolved') or (recovery.get('retry_after') or 0)>clock:continue
        if recovery.get('status')=='waiting_service':
            handle=claim_run(store.path(row['owner'],row['project'])/'.workbench/research-flow/parse-locks'/row['id'])
            if handle is None:continue
            try:
                healthy=asyncio.run(service_health('tools'))
                recovery['health_probes']=recovery.get('health_probes',0)+1
                recovery['retry_after']=clock if healthy else clock+300
                if healthy:recovery.update(status='waiting',attempts=0)
                result['recovery']=recovery
                store.set_job(row['id'],result=result)
            finally:release_run(handle)
            if not healthy:continue
        asset=result.get('asset')
        if asset:schedule_parse(store,row['owner'],row['project'],asset,row['id'])

def start_recovery(store,recover_workflows=None):
    """A lightweight timer schedules due work; backoff never occupies RUNNERS."""
    if os.environ.get('WORKBENCH_FLOW_RECOVERY')=='0':return
    key=str(store.root)
    with _parsing_lock:
        if key in _recovery_services:
            if recover_workflows:_recovery_services[key]['callback']=recover_workflows
            return
        service={'callback':recover_workflows};_recovery_services[key]=service
    def loop():
        while True:
            time.sleep(15)
            try:
                if service['callback']:service['callback']()
                if os.environ.get('WORKBENCH_FLOW_RECOVERY')=='1':
                    recover_parses(store)
            except Exception:pass
    threading.Thread(target=loop,name='project-tool-recovery',daemon=True).start()
