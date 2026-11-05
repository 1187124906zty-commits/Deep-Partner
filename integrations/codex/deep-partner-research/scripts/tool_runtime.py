"""Project-bound bridge to real native tools; durable calls survive client exits."""
from pathlib import Path,PurePosixPath
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
import argparse,asyncio,base64,json,os,re,secrets,subprocess,sys,threading,time,urllib.request,uuid
from deepcode_native import workflow,mcp_call,PYTHON,agent_turn,read_agent_turn,rpc,code_prompt
from runtime_connection import ensure_tunnel,spawn

ROOT=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'deep-partner/tool-runtime'
PORT=47906
POOL=ThreadPoolExecutor(max_workers=3)
LOCK=threading.RLock()
ACTIVE=set()

def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.pending')
    with LOCK:temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(path)
def relative(value):
    p=PurePosixPath(str(value))
    if p.is_absolute() or '\\' in str(value) or ':' in str(value) or any(v in ('','..','.') or v.startswith('.') for v in str(value).split('/')):raise ValueError('Invalid project relative path')
    return p.as_posix()
def key(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(value)):raise ValueError('Invalid operation identity')
    return str(value)
def state_path(jid):return ROOT/'jobs'/(key(jid)+'.json')
def snapshot(jid):return json.loads(state_path(jid).read_text(encoding='utf8'))
def save(state):atomic(state_path(state['id']),state)
def add_event(state,tool,action,**result):
    state.setdefault('tool_calls',[]).append({'tool':tool,'action':action,'at':time.time(),**result});save(state)

async def durable_agent_call(state,binding):
    marker='[DeepPartner operation '+state['id']+']'
    prompt=code_prompt(state['payload']['instruction'])+'\n\n'+marker
    if not state.get('native_turn_id') and state.get('agent_admission')=='submitting':
        turn=await agent_turn(state['workspace'],marker)
        if turn:state.update(native_turn_id=turn['id'],mcp_session_id=turn['threadId']);save(state)
        else:raise ConnectionError('Native admission is being reconciled; original operation marker retained')
    if state.get('native_turn_id'):
        while True:
            result=await read_agent_turn(state['native_turn_id']);turn=result['turn']
            if turn['status']=='completed':return {'tool':'DeepCode native RPC','result':{'session_id':turn['threadId']},'summary':result['summary']}
            if turn['status'] in ('failed','cancelled','interrupted'):raise RuntimeError('Native turn '+turn['status']+': '+str(turn.get('errorMessage')))
            if result['approvals'] and any(a.get('status')=='pending' for a in result['approvals']):
                return {'tool':'deepcode-reply','result':{'session_id':turn['threadId']},'summary':'needs your approval: original native turn retained'}
            await asyncio.sleep(3)
    state['agent_admission']='submitting';save(state)
    session_id=state.get('mcp_session_id') or binding.get('mcp_session_id')
    name='deepcode-reply' if session_id else 'deepcode'
    args={'session_id':session_id,'prompt':prompt} if session_id else {'workspace':state['workspace'],'prompt':prompt}
    pending=asyncio.create_task(mcp_call(name,args));add_event(state,name,'start')
    while not pending.done():
        await asyncio.sleep(1)
        if not state.get('native_turn_id'):
            turn=await agent_turn(state['workspace'],marker)
            if turn:state.update(native_turn_id=turn['id'],mcp_session_id=turn['threadId']);save(state)
    result=await pending
    state['agent_admission']='completed';save(state)
    return result

async def run_native(state):
    workspace=Path(state['workspace']);payload=state['payload'];mode=payload.get('code_engine','paper2code')
    grant=payload.get('workspace_authorization') or {}
    if not state.get('workspace_permissions') and grant:
        if grant.get('project_id')!=state['project_id'] or grant.get('owner_key')!=state['owner_key'] or grant.get('file_edit') is not True or grant.get('python_tests') is not True:
            raise PermissionError('Workspace authorization does not match the current owned project')
        native=await rpc('project/add',{'path':str(workspace.resolve()),'displayName':'Deep Partner · '+state['project_id'],'trustState':'trusted'})
        native_id=native['project']['id']
        if native['project'].get('trustState')!='trusted':await rpc('project/update',{'projectId':native_id,'trustState':'trusted'})
        selected=await rpc('settings/update',{'scope':'project','projectId':native_id,'patch':{'security':{'permissions':{
            'write':'allow','edit':'allow','apply_patch':'allow','bash':{'*python*':'allow','*pytest*':'allow'},
            '*_execute_bash':{'*python*':'allow','*pytest*':'allow'}}}}})
        profile=selected['settings']['resolvedDefaultSecurityProfile']
        state['workspace_permissions']={'native_project_id':native_id,'filesystem_scope':profile['filesystemScope'],'command_sandbox':profile['commandSandbox']};save(state)
    binding_path=ROOT/'sessions'/state['owner_key']/state['project_id']/(uuid.uuid5(uuid.NAMESPACE_URL,payload.get('conversation_id',state['id'])).hex+'.json')
    binding=json.loads(binding_path.read_text(encoding='utf8')) if binding_path.is_file() else {}
    if mode=='agent':
        if not state.get('mcp_session_id'):state['mcp_session_id']=binding.get('mcp_session_id')
        result=await durable_agent_call(state,binding)
        state['mcp_session_id']=result['result'].get('session_id');state['summary']=result['summary']
        state['status']='waiting_input' if permission_blocked(result['summary']) else 'completed'
        binding['mcp_session_id']=state['mcp_session_id'];atomic(binding_path,binding)
        add_event(state,result['tool'],'completed',session_id=state['mcp_session_id']);return
    if not state.get('workflow_run_id'):
        source=workspace/('source-'+state['id']+'.md');source.write_text(code_prompt(payload['instruction']),encoding='utf8')
        result=await workflow('start',workspace=str(workspace),source=str(source),source_type='local',options=payload.get('workflow_options',{'planReview':True,'enableIndexing':False}),thread_id=binding.get('native_thread_id',''))
        state['workflow_run_id']=result['workflow']['id'];state['native_thread_id']=result['workflow']['threadId']
        binding['native_thread_id']=state['native_thread_id'];atomic(binding_path,binding)
        add_event(state,'deepcode_workflow','workflow/start',run_id=state['workflow_run_id'])
    while True:
        result=await workflow('read',run_id=state['workflow_run_id']);native=result['workflow'];state['native']=native;state['artifacts']=result.get('artifacts',[])
        state['stage']=native.get('currentStage');state['status']='waiting_input' if native['status']=='waiting' else native['status'];save(state)
        if native['status']=='waiting':return
        if native['status']=='failed' and native.get('errorCode')=='WORKFLOW_INCOMPLETE' and 'no_tests_discovered' in str(native.get('errorMessage')) and not state.get('verification_recheck'):
            state['verification_recheck']=True;save(state)
            add_event(state,'deepcode_workflow','diagnose',code='no_tests_discovered',action_detail='Inspect native codebase artifact and rerun its verification stage')
            verified=await workflow('verify',workspace=str(workspace),run_id=state['workflow_run_id'])
            state['recovered_verification']=verified;state['status']='completed'
            add_event(state,'deepcode_workflow','native verification stage',passed=True,checks=len(verified['checks']));return
        if native['status']=='failed' and native.get('errorCode')=='WORKFLOW_INTERRUPTED' and not state.get('native_retry'):
            add_event(state,'deepcode_workflow','diagnose',code=native['errorCode'],reason=native.get('errorMessage'))
            retried=await workflow('retry',run_id=state['workflow_run_id']);state['native_retry']=True;state['workflow_run_id']=retried['workflow']['id']
            add_event(state,'deepcode_workflow','workflow/retry',run_id=state['workflow_run_id']);continue
        if native['status'] in ('completed','failed','cancelled'):
            add_event(state,'deepcode_workflow','workflow/read',status=native['status']);return
        await asyncio.sleep(4)

def schedule(jid):
    with LOCK:
        if jid in ACTIVE:return
        ACTIVE.add(jid)
    POOL.submit(work,jid)

def work(jid):
    state=snapshot(jid)
    try:
        state['status']='running';save(state)
        if state['payload'].get('operation')=='parse_pdf':
            from cluster_pdf_runtime import parse
            payload={**state['payload'],'local_state':str(ROOT/'cluster-jobs'/state['id']),
                     'owner_key':state['owner_key'],'project_id':state['project_id']}
            state['result']=parse(payload,lambda values:(state.update(values),save(state)))
            state['status']='completed'
        elif state['payload'].get('operation')=='simulate':
            from cluster_simulation_runtime import run
            payload={**state['payload'],'local_state':str(ROOT/'simulation-jobs'/state['id']),
                     'owner_key':state['owner_key'],'project_id':state['project_id']}
            state['result']=run(payload,lambda values:(state.update(values),save(state)));state['status']='completed'
        else:asyncio.run(run_native(state))
    except (ConnectionError,TimeoutError,subprocess.TimeoutExpired) as error:
        attempts=state.get('recovery_attempts',0)+1
        state.update(status='recovering',recovery_attempts=attempts,retry_after=time.time()+min(120,2**min(attempts,7)),
                     error={'code':type(error).__name__,'message':str(error)[-1200:],'retryable':True})
    except Exception as error:
        state.update(status='failed',error={'code':type(error).__name__,'message':str(error)[-1800:]})
    finally:
        save(state)
        with LOCK:ACTIVE.discard(jid)

def permission_blocked(summary):
    """A tool denial is a waiting result, never a completed implementation."""
    text=str(summary).casefold()
    return any(value in text for value in ('permission denied','needs your approval','changing files needs','工具层权限拦截','工具权限拒绝'))

def publication_baseline(workspace):
    """The current turn owns changes, not every file left by earlier turns."""
    workspace=Path(workspace).resolve();files={}
    for path in workspace.rglob('*'):
        if not path.is_file() or not path.resolve().is_relative_to(workspace):continue
        rel=path.relative_to(workspace)
        if any(part.startswith('.') or part in ('__pycache__','node_modules','.venv','venv') for part in rel.parts):continue
        stat=path.stat();files[rel.as_posix()]={'modified':stat.st_mtime_ns,'bytes':stat.st_size}
    return files


def collect(state):
    workspace=Path(state['workspace']).resolve();payload=state['payload']
    if state['status']!='completed':raise ValueError('Native tool has not completed')
    roots=[]
    native=state.get('native') or {};result=native.get('result') or {}
    for value in [result.get('code_directory'),(result.get('implementation_result') or result.get('implementation') or {}).get('code_directory')]:
        if value:roots.append(Path(value))
    for item in state.get('artifacts',[]):
        p=workspace/str(item.get('storagePath') or item.get('path',''))
        if p.is_dir() and item.get('kind') in ('code','directory','codebase'):roots.append(p)
    if not roots:
        candidates=list((workspace/'.deepcode/workflows').glob('tasks/*/generate_code'))
        roots=candidates or [workspace]
    base=roots[0].resolve()
    if not base.is_relative_to(workspace):raise ValueError('Native artifact is outside the bound workspace')
    checks=(state.get('recovered_verification') or {}).get('checks') or []
    verified_roots={Path(c['working_directory']).resolve() for c in checks if c.get('passed') and c.get('working_directory')}
    if len(verified_roots)==1:
        verified_root=next(iter(verified_roots))
        if verified_root.is_relative_to(base):base=verified_root
    files=[];size=0
    for p in sorted(base.rglob('*')):
        if not p.is_file() or not p.resolve().is_relative_to(base):continue
        rel=p.relative_to(base)
        if any(v.startswith('.') or v in ('__pycache__','node_modules','.venv','venv') for v in rel.parts):continue
        if p.name.startswith('source-') or p.name.endswith(('.backup','.bak','.tmp','.lock')) or p.name in ('source.md','research-handoff.json','verification.json','deepcode_config.json'):continue
        baseline=state.get('publication_baseline')
        if payload.get('code_engine')=='agent' and baseline is not None:
            stat=p.stat();prior=baseline.get(p.relative_to(workspace).as_posix())
            if prior=={'modified':stat.st_mtime_ns,'bytes':stat.st_size}:continue
        if p.stat().st_size>4_000_000:continue
        data=p.read_bytes();size+=len(data)
        if len(files)>=80 or size>16_000_000:raise ValueError('Native artifacts exceed the bounded publication size')
        prefix=payload.get('publish_root','src');name=rel.as_posix()
        target=relative(name if name in state.get('input_paths',[]) or name.startswith(prefix+'/') else prefix+'/'+name)
        files.append({'path':target,'content_b64':base64.b64encode(data).decode(),'bytes':len(data)})
    scoped=payload.get('code_engine')=='agent' and 'publication_baseline' in state
    if not files and not scoped:raise ValueError('Native workflow completed without publishable files')
    return {'files':files,'summary':state.get('summary') or result.get('summary') or 'Native Paper2Code artifacts',
            'publication_scope':'current_turn_changes' if scoped else 'native_code_artifacts',
            'verification':state.get('recovered_verification') or result.get('verification') or result.get('implementation_result') or {},'tool_calls':state.get('tool_calls',[])}

def serve():
    config=json.loads((ROOT/'bridge.json').read_text(encoding='utf8'))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value):
            data=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.path=='/health':self.reply(200,{'ok':True,'version':1,'runtime_revision':'stage-code-1','pid':os.getpid(),'tools':['deepcode','deepcode-reply','deepcode_workflow','cluster_pdf_parse','cluster_simulation']});return
            self.reply(404,{'error':'unknown path'})
        def do_POST(self):
            if not secrets.compare_digest(self.headers.get('x-partner-tools',''),config['token']):self.reply(403,{'error':'unauthorized'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=150_000_000:raise ValueError('Request size is invalid')
                request=json.loads(self.rfile.read(length));action=request['action'];jid=key(request['id'])
                if action=='start':
                    with LOCK:
                        if state_path(jid).exists():state=snapshot(jid)
                        else:
                            pid=key(request['project_id']);owner=key(request['owner_key']);conversation=uuid.uuid5(uuid.NAMESPACE_URL,request['payload'].get('conversation_id',jid)).hex
                            workspace=ROOT/'workspaces'/owner/pid/conversation;workspace.mkdir(parents=True,exist_ok=True)
                            for item in request.get('inputs',[]):
                                p=workspace/relative(item['path']);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(item['content_b64'],validate=True))
                            state={'id':jid,'project_id':pid,'owner_key':owner,'workspace':str(workspace),'payload':request['payload'],'status':'queued','tool_calls':[]}
                            if request['payload'].get('code_engine')=='agent':
                                state['publication_baseline']=publication_baseline(workspace)
                                state['input_paths']=[relative(item['path']) for item in request.get('inputs',[])]
                            save(state);schedule(jid)
                else:
                    state=snapshot(jid)
                    if state['project_id']!=request['project_id'] or state['owner_key']!=request['owner_key']:raise ValueError('Tool operation belongs to another project')
                    if action=='collect':self.reply(200,collect(state));return
                    if action in ('respond','retry'):
                        if action=='respond':
                            asyncio.run(workflow('respond',run_id=state['workflow_run_id'],interaction_id=request['interaction_id'],response=request['response']))
                        else:
                            result=asyncio.run(workflow('retry',run_id=state['workflow_run_id']));state['workflow_run_id']=result['workflow']['id']
                        state['status']='queued';save(state);schedule(jid)
                public={k:v for k,v in state.items() if k not in ('payload','workspace','publication_baseline')};self.reply(200,public)
            except FileNotFoundError:self.reply(404,{'error':{'code':'external_task_not_found','message':'This operation ID has not been admitted'}})
            except Exception as error:self.reply(400,{'error':{'code':type(error).__name__,'message':str(error)[-1800:]}})
    # Claim the listener before recovering work so duplicate guardians cannot execute it twice.
    try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    except OSError:return
    # Native/cluster runs have durable identities. Read them after restart rather than submit twice.
    for p in (ROOT/'jobs').glob('*.json'):
        state=json.loads(p.read_text(encoding='utf8'))
        if state['status'] in ('queued','running','recovering'):schedule(state['id'])
    def maintain_connection():
        last_supervisor=0
        while True:
            time.sleep(5)
            if time.time()-last_supervisor>=20:
                try:
                    from runtime_supervisor import ensure as ensure_supervisor
                    ensure_supervisor();last_supervisor=time.time()
                except (OSError,ValueError,subprocess.SubprocessError):pass
            for path in (ROOT/'jobs').glob('*.json'):
                try:
                    state=json.loads(path.read_text(encoding='utf8'))
                    if state['status']=='recovering' and state.get('retry_after',0)<=time.time():schedule(state['id'])
                except (OSError,ValueError):pass
    threading.Thread(target=maintain_connection,name='project-tool-connection',daemon=True).start()
    server.serve_forever()

def ensure():
    ROOT.mkdir(parents=True,exist_ok=True);config=ROOT/'bridge.json'
    if not config.is_file():atomic(config,{'port':PORT,'token':secrets.token_urlsafe(40)})
    def health():
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f'http://127.0.0.1:{PORT}/health',timeout=2) as response:return json.load(response).get('version')==1
        except (OSError,ValueError):return False
    flags=0x08000000 if os.name=='nt' else 0
    if not health():
        process=spawn([str(PYTHON),'-X','utf8',__file__,'--serve'],ROOT,'bridge')
        atomic(ROOT/'bridge-process.json',{'pid':process.pid})
        for _ in range(30):
            if health():break
            time.sleep(.1)
    if not health():return {'ready':False,'diagnosis':'tool_bridge_start_failed'}
    return {**ensure_tunnel(ROOT,PORT),'tools':['deepcode','deepcode-reply','deepcode_workflow','cluster_pdf_parse','cluster_simulation']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');args=p.parse_args()
    if args.serve:serve()
    else:print(json.dumps(ensure(),ensure_ascii=False))
