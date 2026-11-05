"""Fault injection for same-run recovery, without external services or secrets."""
import asyncio
import base64
import json
import os
import uuid
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import FastAPI,Request,Depends
from server.storage import Store, atomic_json
from server import research_flow as flow
from server import research_tool_flow as tools
from server import research_simulation_flow as simulation
from server import search_mcp as scholar


class Queue:
    def __init__(self): self.work = []
    def submit(self, fn): self.work.append(fn)
    def run(self): self.work.pop(0)()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.owner = 'alice'
        self.pid = self.store.create(self.owner, 'recovery')['id']
        self.root = self.store.path(self.owner, self.pid)
        self.pool = Queue()
        self.patchers = [patch.object(flow, 'RUNNERS', self.pool), patch.object(tools, 'start_recovery')]
        for p in self.patchers: p.start()
        self.runtime = self.install()

    def tearDown(self):
        for p in reversed(self.patchers): p.stop()
        self.temp.cleanup()

    def install(self):
        self.app=FastAPI()
        self.app.dependency_overrides[flow.actor]=lambda:{'id':self.owner}
        return flow.install(self.app, self.store, lambda owner: Path(self.temp.name)/'api.json', None)

    def make_run(self, payload, state=None, status=None):
        jid = self.store.job(self.owner, self.pid, 'simulation' if payload.kind == 'simulate' else 'research-flow', {})
        folder = self.root/'.workbench/research-flow/runs'/jid
        atomic_json(folder/'request.json', payload.model_dump())
        if state is not None: atomic_json(folder/'state.json', state)
        if status: self.store.set_job(jid, status=status)
        return jid, folder

    def row(self, jid): return flow.job_row(self.store, self.owner, self.pid, jid)

    def test_code_transport_failure_persisted_then_same_run_recovers(self):
        payload = flow.RunInput(kind='code', instruction='implement')
        jid, folder = self.make_run(payload)
        async def offline(store, owner, pid, rid, payload, auth, state, persist):
            state['native_code'] = {'id': rid, 'workflow_run_id': 'external-1'}
            state['stage_receipts'] = {'earlier': {'at': 'saved'}}
            persist(state)
            raise tools.ToolUnavailable('offline')
        with patch.object(tools, 'native_code', side_effect=offline):
            self.runtime['schedule'](self.owner, self.pid, jid, payload, {'Cookie': 'do-not-persist'})
            self.pool.run()
        row = self.row(jid)
        self.assertEqual(row['status'], 'queued')
        recovery = row['result']['recovery']
        self.assertEqual(recovery['attempts'], 1)
        self.assertGreater(recovery['retry_after'], 0)
        self.assertEqual(row['result']['native_code']['workflow_run_id'], 'external-1')
        self.assertNotIn('do-not-persist', (folder/'state.json').read_text())
        self.runtime['recover'](now_ts=recovery['retry_after']-1)
        self.assertEqual(len(self.pool.work), 0)
        # A new installer models a process restart: no in-memory auth is available.
        restarted = self.install()
        result = {'status': 'completed', 'session_id': 'native-session', 'published_reply': 'saved', 'files': []}
        with patch.object(tools, 'native_code', new_callable=AsyncMock, return_value=result) as resumed, patch.object(flow, 'save_record', return_value={}):
            restarted['recover'](now_ts=recovery['retry_after']+1)
            self.pool.run()
            self.assertEqual(resumed.call_args.args[3], jid)
            self.assertEqual(resumed.call_args.args[6]['native_code']['workflow_run_id'], 'external-1')
        self.assertEqual(self.row(jid)['status'], 'completed')
        self.assertIn('earlier', self.row(jid)['result']['stage_receipts'])

    def test_simulation_unavailable_not_scientific_failure(self):
        payload = flow.RunInput(kind='simulate', simulation={'entrypoint': 'src/a.py'}, input_paths=['src/a.py'])
        jid, _ = self.make_run(payload)
        with patch.object(simulation, 'run', new_callable=AsyncMock, side_effect=tools.ToolUnavailable('offline')):
            self.runtime['schedule'](self.owner, self.pid, jid, payload, {})
            self.pool.run()
        self.assertEqual(self.row(jid)['status'], 'queued')
        other, _ = self.make_run(payload)
        with patch.object(simulation, 'run', new_callable=AsyncMock, return_value={'status': 'failed', 'project_path': 'results/'}):
            self.runtime['schedule'](self.owner, self.pid, other, payload, {})
            self.pool.run()
        self.assertEqual(self.row(other)['status'], 'failed')
        self.assertNotIn('recovery', self.row(other)['result'])

    def test_multi_install_only_one_worker_then_cheap_health_after_eight_failures(self):
        payload = flow.RunInput(kind='code', instruction='implement')
        jid, folder = self.make_run(payload)
        another = self.install()
        self.runtime['schedule'](self.owner, self.pid, jid, payload, {})
        another['schedule'](self.owner, self.pid, jid, payload, {})
        self.assertEqual(len(self.pool.work), 1)
        with patch.object(tools, 'native_code', new_callable=AsyncMock, side_effect=tools.ToolUnavailable('offline')):
            self.pool.run()
            for _ in range(8):
                row = self.row(jid)
                if row['status'] != 'queued': break
                self.runtime['recover'](now_ts=row['result']['recovery']['retry_after']+1)
                self.pool.run()
        row = self.row(jid)
        self.assertEqual(row['status'], 'waiting_service')
        self.assertEqual(row['result']['recovery']['status'], 'waiting_service')
        self.assertLessEqual(row['result']['recovery']['attempts'], 8)
        with patch.object(flow,'service_health',new_callable=AsyncMock,return_value=False) as health:
            for i in range(12):
                self.runtime['recover'](now_ts=10**12+i*301)
                self.assertEqual(len(self.pool.work),0)
            self.assertEqual(health.await_count,12)
        self.assertEqual(self.row(jid)['result']['recovery']['attempts'],8)
        with patch.object(flow,'service_health',new_callable=AsyncMock,return_value=True):
            self.runtime['recover'](now_ts=10**12+13*301)
        self.assertEqual(len(self.pool.work),1)
        result={'status':'completed','session_id':'native','files':[],'published_reply':'done'}
        with patch.object(tools,'native_code',new_callable=AsyncMock,return_value=result) as code, patch.object(flow,'save_record',return_value={}):
            self.pool.run()
            self.assertEqual(code.call_args.args[3],jid)
        self.assertEqual(self.row(jid)['status'],'completed')

    def test_concurrent_instances_have_one_os_lease(self):
        payload=flow.RunInput(kind='code',instruction='implement')
        jid,_=self.make_run(payload)
        runtimes=[self.runtime,self.install()]
        with ThreadPoolExecutor(max_workers=8) as threads:
            futures=[threads.submit(runtimes[i%2]['schedule'],self.owner,self.pid,jid,payload,{}) for i in range(16)]
            self.assertEqual(sum(f.result() for f in futures),1)
        self.assertEqual(len(self.pool.work),1)
        with patch.object(tools,'native_code',new_callable=AsyncMock,side_effect=tools.ToolUnavailable('offline')):
            self.pool.run()

    def test_normal_pending_does_not_consume_retry_budget_or_expire_after_hours(self):
        state={}
        for i in range(20):flow.defer_run(state,tools.ToolPending('running'),clock=100+i*100000)
        self.assertEqual(state['recovery']['attempts'],0)
        self.assertEqual(state['recovery']['status'],'waiting')

    def test_recovery_project_filter_leaves_legacy_running_project_untouched(self):
        payload=flow.RunInput(kind='code',instruction='implement')
        allowed,_=self.make_run(payload,status='interrupted')
        other=self.store.create(self.owner,'legacy')['id']
        old=self.store.job(self.owner,other,'research-flow',{})
        oldroot=self.store.path(self.owner,other)/'.workbench/research-flow/runs'/old
        atomic_json(oldroot/'request.json',payload.model_dump())
        atomic_json(oldroot/'state.json',{'native_code':{'workflow_run_id':'old-worker'}})
        self.store.set_job(old,status='running',result={'legacy':True})
        before=(oldroot/'state.json').read_bytes()
        with patch.dict(os.environ,{'WORKBENCH_FLOW_RECOVERY_PROJECTS':json.dumps([self.pid])}):
            self.runtime['recover'](now_ts=10**12)
            self.assertEqual(len(self.pool.work),1)
            self.assertTrue(tools.recovery_project_allowed(self.pid))
            self.assertFalse(tools.recovery_project_allowed(other))
            self.assertFalse((oldroot/'.execution.lock').exists())
        self.assertEqual(flow.job_row(self.store,self.owner,other,old)['status'],'running')
        self.assertEqual((oldroot/'state.json').read_bytes(),before)
        with patch.object(tools,'native_code',new_callable=AsyncMock,side_effect=tools.ToolUnavailable('offline')):
            self.pool.run()

    def test_new_generation_recovers_outside_legacy_project_allowlist(self):
        payload=flow.RunInput(kind='code',instruction='implement')
        jid,folder=self.make_run(payload,{'runtime_generation':flow.RUNTIME_GENERATION},status='interrupted')
        with patch.dict(os.environ,{'WORKBENCH_FLOW_RECOVERY_PROJECTS':json.dumps(['different-project'])}):
            self.runtime['recover'](now_ts=10**12)
        self.assertEqual(len(self.pool.work),1)
        with patch.object(tools,'native_code',new_callable=AsyncMock,side_effect=PermissionError('project not authorized')):
            self.pool.run()
        self.assertEqual(self.row(jid)['status'],'waiting_input')
        self.assertEqual(self.row(jid)['result']['runtime_generation'],flow.RUNTIME_GENERATION)

    def test_pdf_recovery_keeps_project_scope_even_for_new_generation(self):
        other=self.store.create(self.owner,'legacy pdf')['id']
        jobs=[]
        for pid in (self.pid,other):
            jid=self.store.job(self.owner,pid,'cluster-pdf-parse',{})
            self.store.set_job(jid,status='running',result={'asset':'source.pdf','runtime_generation':flow.RUNTIME_GENERATION})
            jobs.append(jid)
        with patch.dict(os.environ,{'WORKBENCH_FLOW_RECOVERY_PROJECTS':json.dumps([self.pid])}),patch.object(tools,'schedule_parse') as schedule:
            tools.recover_parses(self.store,now_ts=10**12)
            schedule.assert_called_once_with(self.store,self.owner,self.pid,'source.pdf',jobs[0])
        self.assertEqual(flow.job_row(self.store,self.owner,other,jobs[1])['status'],'running')

    def test_pdf_exhausted_budget_probes_only_until_healthy(self):
        jid=self.store.job(self.owner,self.pid,'cluster-pdf-parse',{})
        state={'asset':'source.pdf','recovery':{'status':'waiting_service','attempts':8,'retry_after':0,'service':'tools'}}
        self.store.set_job(jid,status='waiting_service',result=state)
        with patch.object(flow,'service_health',new_callable=AsyncMock,return_value=False),patch.object(tools,'schedule_parse') as schedule:
            tools.recover_parses(self.store,now_ts=1000)
            schedule.assert_not_called()
        with patch.object(flow,'service_health',new_callable=AsyncMock,return_value=True),patch.object(tools,'schedule_parse') as schedule:
            tools.recover_parses(self.store,now_ts=1400)
            schedule.assert_called_once_with(self.store,self.owner,self.pid,'source.pdf',jid)
        self.assertEqual(self.row(jid)['result']['recovery']['attempts'],0)

    def test_start_run_writes_generation_before_scheduling(self):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test') as client:
                response=await client.post('/research/api/projects/'+self.pid+'/research-flow/runs',json={'kind':'code','instruction':'implement'})
                self.assertEqual(response.status_code,200,response.text)
                return response.json()['id']
        jid=asyncio.run(request())
        folder=self.root/'.workbench/research-flow/runs'/jid
        self.assertEqual(json.loads((folder/'state.json').read_text())['runtime_generation'],flow.RUNTIME_GENERATION)
        with patch.object(tools,'native_code',new_callable=AsyncMock,side_effect=PermissionError('project not authorized')):
            self.pool.run()

    def test_slides_reuses_dispatch_child_without_plan_or_worker_wait(self):
        child = self.store.job(self.owner, self.pid, 'slides-plan', {})
        self.store.set_job(child, status='completed', result={'quality': {'can_proceed': True}})
        payload = flow.RunInput(kind='slides', confirmation_id='confirmed')
        jid, _ = self.make_run(payload, {'dispatch': {'job_id': child}, 'steps': [], 'searches': []})
        async def fail_if_called(*args, **kwargs): raise AssertionError('duplicate slides plan')
        with patch.object(flow.httpx.AsyncClient, 'post', side_effect=fail_if_called):
            self.runtime['schedule'](self.owner, self.pid, jid, payload, {})
            self.pool.run()
        self.assertEqual(self.row(jid)['status'], 'completed')
        self.assertEqual(self.row(jid)['result']['dispatch']['job_id'], child)

    def test_slides_lost_response_reconciles_deterministic_child_after_restart(self):
        calls=[]
        app=self.app
        @app.post('/research/api/projects/{pid}/slides/plan')
        async def plan(pid:str,body:dict,user=Depends(flow.actor)):
            child=self.store.job(user['id'],pid,'slides-plan',{'subject':'slides'})
            calls.append(child)
            self.store.set_job(child,status='completed',result={'quality':{'can_proceed':True}})
            raise httpx.ReadError('response lost after child persisted')
        payload=flow.RunInput(kind='slides',confirmation_id='confirmed')
        jid,folder=self.make_run(payload)
        self.runtime['schedule'](self.owner,self.pid,jid,payload,{'Cookie':'private'})
        self.pool.run()
        self.assertEqual(self.row(jid)['status'],'queued')
        self.assertEqual(len(calls),1)
        recovery=self.row(jid)['result']['recovery']
        restarted=self.install()
        restarted['recover'](now_ts=recovery['retry_after']+1)
        self.pool.run()
        self.assertEqual(len(calls),1)
        self.assertEqual(self.row(jid)['status'],'completed')
        self.assertEqual(self.row(jid)['result']['dispatch']['job_id'],calls[0])

    def test_scholar_bridge_waits_for_guardian_same_tool_no_fallback(self):
        payload = flow.RunInput(kind='search', query='Ada', search_tool='get_author_papers', cursor='opaque', allow_search_fallback=True)
        jid, _ = self.make_run(payload)
        error = scholar.ScholarMCPError({'code': 'bridge_transport_error', 'retryable': True, 'message': 'offline'})
        with patch.object(scholar, 'discover', new_callable=AsyncMock, side_effect=error), patch('server.references.search', new_callable=AsyncMock) as fallback:
            self.runtime['schedule'](self.owner, self.pid, jid, payload, {})
            self.pool.run()
            fallback.assert_not_called()
        self.assertEqual(self.row(jid)['status'], 'queued')
        with patch.object(scholar, 'discover', new_callable=AsyncMock, return_value=scholar.PaperRows([], 'next')) as discover, patch.object(scholar, 'reconcile', new_callable=AsyncMock, return_value=scholar.PaperRows([], 'next')), patch.object(flow, 'save_record', return_value={}):
            self.runtime['recover'](now_ts=self.row(jid)['result']['recovery']['retry_after']+1)
            self.pool.run()
            self.assertEqual(discover.call_args.kwargs['tool'], 'get_author_papers')
            self.assertEqual(discover.call_args.kwargs['cursor'], 'opaque')
        self.assertEqual(self.row(jid)['status'], 'completed')

    def test_rate_limit_cooldown_then_same_run_tool_and_cursor(self):
        request=httpx.Request('POST','http://scholar/search')
        cases=[
            (scholar.ScholarMCPError({'code':'rate_limited','retryable':False,'details':{'Retry-After':'420'}}),420),
            (scholar.ScholarMCPError({'code':'rate_limited','details':{}}),300),
            (httpx.HTTPStatusError('throttled',request=request,
                response=httpx.Response(429,headers={'Retry-After':'600'},request=request)),600),
        ]
        for error,delay in cases:
            with self.subTest(error=type(error).__name__,delay=delay):
                payload=flow.RunInput(kind='search',query='Ada',author='Ada Lovelace',
                    search_tool='get_author_papers',cursor='opaque',allow_search_fallback=True)
                jid,folder=self.make_run(payload)
                with patch.object(flow.time,'time',return_value=1000),patch.object(scholar,'discover',new_callable=AsyncMock,side_effect=error) as discover,patch('server.references.search',new_callable=AsyncMock) as fallback:
                    self.runtime['schedule'](self.owner,self.pid,jid,payload,{})
                    self.pool.run()
                    discover.assert_awaited_once()
                    fallback.assert_not_called()
                self.assertEqual(self.row(jid)['status'],'queued')
                recovery=json.loads((folder/'state.json').read_text())['recovery']
                self.assertEqual(recovery['retry_after'],1000+delay)
                self.assertEqual(recovery['service'],'scholar')
                self.runtime['recover'](now_ts=1000+delay-1)
                self.assertFalse(self.pool.work)
                with patch.object(scholar,'discover',new_callable=AsyncMock,return_value=scholar.PaperRows([],'next')) as resumed,patch.object(scholar,'reconcile',new_callable=AsyncMock,return_value=scholar.PaperRows([],'next')),patch.object(flow,'save_record',return_value={}):
                    self.install()['recover'](now_ts=1000+delay)
                    self.assertEqual(len(self.pool.work),1)
                    self.pool.run()
                    resumed.assert_awaited_once()
                    self.assertEqual(resumed.call_args.kwargs['tool'],payload.search_tool)
                    self.assertEqual(resumed.call_args.kwargs['cursor'],'opaque')
                    self.assertEqual(resumed.call_args.kwargs['author'],'Ada Lovelace')
                self.assertEqual(self.row(jid)['status'],'completed')
                self.assertEqual(self.row(jid)['result']['id'],jid)

    def test_rate_limit_budget_keeps_cooldown_before_health_probes(self):
        error=scholar.ScholarMCPError({'code':'rate_limited','details':{'retry_after':900}})
        state={'recovery':{'attempts':7}}
        flow.defer_run(state,error,clock=1000)
        self.assertEqual(state['recovery']['status'],'waiting_service')
        self.assertEqual(state['recovery']['attempts'],8)
        self.assertEqual(state['recovery']['retry_after'],1900)
        for invalid in ('invalid',-1,float('inf'),float('nan')):
            error=scholar.ScholarMCPError({'code':'rate_limited','details':{'Retry-After':invalid}})
            state={}
            flow.defer_run(state,error,clock=1000)
            self.assertEqual(state['recovery']['retry_after'],1300)

    def test_challenge_and_permission_never_auto_resume(self):
        for error in (scholar.ScholarMCPError({'code': 'verification_required', 'retryable': True, 'message': 'verify'}), PermissionError('not granted')):
            payload = flow.RunInput(kind='code', instruction='implement')
            jid, _ = self.make_run(payload)
            with patch.object(tools, 'native_code', new_callable=AsyncMock, side_effect=error):
                self.runtime['schedule'](self.owner, self.pid, jid, payload, {})
                self.pool.run()
            self.assertEqual(self.row(jid)['status'], 'waiting_input')
            self.assertNotIn('recovery', self.row(jid)['result'])
        self.runtime['recover'](now_ts=10**12)
        self.assertFalse(self.pool.work)


class AdapterRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.owner = 'alice'
        self.pid = self.store.create(self.owner, 'adapters')['id']
        self.root = self.store.path(self.owner, self.pid)

    async def asyncTearDown(self): self.temp.cleanup()

    def authorized_http(self):
        client = AsyncMock()
        response = Mock()
        response.json.return_value = {'role': 'admin', 'workspace_id': ''}
        client.get.return_value = response
        factory = patch('httpx.AsyncClient')
        mocked = factory.start()
        mocked.return_value.__aenter__.return_value = client
        self.addCleanup(factory.stop)
        return client

    async def test_code_partial_save_continues_without_start_or_overwrite(self):
        self.authorized_http()
        payload = flow.RunInput(kind='code', instruction='implement', session_id='sid')
        state = {}
        snapshots = []
        def persist(value): snapshots.append(json.loads(json.dumps(value)))
        completed = {'status': 'completed', 'workflow_run_id': 'native-1'}
        collected = {'files': [{'path': 'src/a.py', 'content_b64': base64.b64encode(b'a=1').decode()},
                               {'path': 'src/b.py', 'content_b64': base64.b64encode(b'b=2').decode()}],
                     'summary': 'done', 'verification': {}, 'tool_calls': []}
        actions = []
        async def call(owner, pid, jid, action, **kwargs):
            actions.append(action)
            return collected if action == 'collect' else completed
        real_replace = self.store.replace
        def flaky_replace(owner, pid, path, data, reason):
            if path.name == 'b.py': raise tools.ToolUnavailable('storage connection lost')
            return real_replace(owner, pid, path, data, reason)
        with patch.object(tools, 'bridge_config', return_value={'native_execution_projects': [self.pid]}), patch.object(tools, 'tool_call', side_effect=call), patch.object(self.store, 'replace', side_effect=flaky_replace):
            with self.assertRaises(tools.ToolUnavailable):
                await tools.native_code(self.store, self.owner, self.pid, 'run', payload, {'Cookie': 'private'}, state, persist)
        first_mtime = (self.root/'project/src/a.py').stat().st_mtime_ns
        with patch.object(tools, 'bridge_config', return_value={'native_execution_projects': [self.pid]}), patch.object(tools, 'tool_call', side_effect=call):
            result = await tools.native_code(self.store, self.owner, self.pid, 'run', payload, {}, state, persist)
        self.assertEqual(actions.count('start'), 1)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual((self.root/'project/src/a.py').stat().st_mtime_ns, first_mtime)
        self.assertNotIn('private', json.dumps(snapshots))

    async def test_workspace_authorization_is_constructed_from_granted_project(self):
        self.authorized_http()
        # Extra user fields are not part of RunInput and cannot become a grant.
        payload=flow.RunInput(kind='code',instruction='implement',session_id='sid',
            workspace_authorization={'project_id':'other','owner_key':'forged','file_edit':False})
        state={}
        with patch.object(tools,'bridge_config',return_value={'native_execution_projects':[self.pid]}), patch.object(tools,'tool_call',new_callable=AsyncMock,return_value={'status':'running'}) as call:
            with self.assertRaises(tools.ToolPending):
                await tools.native_code(self.store,self.owner,self.pid,'run',payload,{},state,lambda s:None)
            self.assertEqual(call.call_args.kwargs['payload']['workspace_authorization'],{
                'project_id':self.pid,'owner_key':uuid.uuid5(uuid.NAMESPACE_URL,self.owner).hex,
                'file_edit':True,'python_tests':True})
        with patch.object(tools,'bridge_config',return_value={'native_execution_projects':['other-project']}), patch.object(tools,'tool_call',new_callable=AsyncMock) as call:
            with self.assertRaises(PermissionError):
                await tools.native_code(self.store,self.owner,self.pid,'run',payload,{},state,lambda s:None)
            call.assert_not_called()

    async def test_wrong_account_cannot_construct_workspace_grant(self):
        http=self.authorized_http()
        http.get.return_value.json.return_value={'id':'another-owner','role':'admin'}
        payload=flow.RunInput(kind='code',instruction='implement',session_id='sid')
        with patch.object(tools,'bridge_config',return_value={'native_execution_projects':[self.pid]}),patch.object(tools,'tool_call',new_callable=AsyncMock) as call:
            with self.assertRaises(PermissionError):
                await tools.native_code(self.store,self.owner,self.pid,'run',payload,{}, {}, lambda s:None)
            call.assert_not_called()

    async def test_readiness_probe_never_calls_a_tool_or_scholar_request(self):
        from scripts import local_search_bridge as bridge
        probe=Mock(stdout=json.dumps({'modules_ready':True,'network_ready':False,'proxy_configured':True}))
        with patch.object(bridge.subprocess,'run',return_value=probe) as run,patch.object(bridge,'invoke') as invoke:
            result=bridge.health({'python':'configured-runtime'})
            self.assertTrue(result['ok'])
            self.assertFalse(result['ready'])
            self.assertEqual(run.call_args.args[0][:3],['configured-runtime','-X','utf8'])
            self.assertIn('socket.create_connection',run.call_args.args[0][-1])
            self.assertNotIn('urlopen(',run.call_args.args[0][-1])
            invoke.assert_not_called()

    async def test_infrastructure_response_is_recoverable_science_failure_is_not(self):
        for error,retry in [({'code':'ssh_unavailable','retryable':True},True),
                            ({'code':'scientific_validation_failed','retryable':True},False),
                            ({'code':'verification_required','retryable':True},False)]:
            response=Mock(status_code=200,is_success=True)
            response.json.return_value={'status':'failed','error':error}
            fake=AsyncMock();fake.post.return_value=response
            with patch.object(tools,'bridge_config',return_value={'url':'http://bridge','token':'not-saved'}),patch.object(tools.httpx,'AsyncClient') as factory:
                factory.return_value.__aenter__.return_value=fake
                if retry:
                    with self.assertRaises(tools.ToolUnavailable):await tools.tool_call(self.owner,self.pid,'same-run','status')
                else:
                    row=await tools.tool_call(self.owner,self.pid,'same-run','status')
                    self.assertEqual(row['error'],error)

    async def test_ambiguous_start_then_status404_replays_identical_id_and_request(self):
        state={};binding={};requests=[]
        start={'payload':{'instruction':'original'},'inputs':[{'path':'a','content_b64':'YQ=='}]}
        async def offline(owner,pid,jid,action,**kwargs):
            requests.append((jid,action,kwargs))
            raise tools.ToolUnavailable('response lost')
        with patch.object(tools,'tool_call',side_effect=offline):
            with self.assertRaises(tools.ToolUnavailable):
                await tools.bound_call('alice',self.pid,'same-id',binding,state,lambda s:None,start)
        async def reconciled(owner,pid,jid,action,**kwargs):
            requests.append((jid,action,kwargs))
            if action=='status':raise tools.ToolNotFound('confirmed 404')
            return {'status':'running'}
        with patch.object(tools,'tool_call',side_effect=reconciled):
            await tools.bound_call('alice',self.pid,'same-id',binding,state,lambda s:None,{'payload':{'instruction':'changed'}})
        self.assertEqual([v[1] for v in requests],['start','status','start'])
        self.assertTrue(all(v[0]=='same-id' for v in requests))
        self.assertEqual(requests[0][2],requests[2][2])

    async def test_disconnected_scholar_only_diagnoses_then_waits_for_guardian(self):
        error={'ok':False,'error':{'code':'bridge_transport_error','retryable':True,'message':'offline'}}
        with patch.object(scholar,'bridge_config',return_value={'url':'http://offline','token':'hidden'}), patch.object(scholar,'_bridge_post',new_callable=AsyncMock,return_value=error) as post, patch.object(scholar,'_repair',new_callable=AsyncMock) as repair:
            with self.assertRaises(scholar.ScholarMCPError) as caught:
                await scholar.discover('Ada',tool='get_author_papers',cursor='opaque')
            self.assertEqual([c.args[1] for c in post.call_args_list],['/scholar','/diagnostics'])
            repair.assert_not_called()
            self.assertEqual(caught.exception.diagnostics[-1]['stage'],'wait_for_guardian')

    async def test_simulation_reconnect_polls_same_operation_only(self):
        self.authorized_http()
        (self.root/'project/src/a.py').write_text('print(1)')
        payload = flow.RunInput(kind='simulate', simulation={'entrypoint': 'src/a.py'}, input_paths=['src/a.py'])
        state = {}
        actions = []
        async def first(owner, pid, jid, action, **kwargs):
            actions.append((jid, action))
            if action == 'start': return {'id': jid, 'status': 'running', 'cluster': {'job_id': 'slurm-1'}}
            raise tools.ToolUnavailable('offline')
        with patch.object(simulation, 'tool_call', side_effect=first), patch.object(simulation.asyncio, 'sleep', new_callable=AsyncMock):
            with self.assertRaises(tools.ToolUnavailable):
                await simulation.run(self.store, self.owner, self.pid, 'run', payload, {'Cookie': 'private'}, state, lambda value: None)
        result = {'result': {'status': 'completed'}, 'remote_root': '/cluster/run', 'job_id': 'slurm-1', 'slurm_state': 'COMPLETED'}
        async def restored(owner, pid, jid, action, **kwargs):
            actions.append((jid, action))
            return {'id': jid, 'status': 'completed', 'result': result}
        with patch.object(simulation, 'tool_call', side_effect=restored):
            saved = await simulation.run(self.store, self.owner, self.pid, 'run', payload, {}, state, lambda value: None)
        self.assertEqual(sum(action == 'start' for _, action in actions), 1)
        self.assertTrue(all(jid == 'simulate-run' for jid, _ in actions))
        self.assertEqual(saved['status'], 'completed')


if __name__ == '__main__': unittest.main()
