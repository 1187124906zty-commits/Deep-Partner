"""Exercise routing, parsed-source identity and the resume boundary."""
import asyncio,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from server.storage import Store,atomic_json
from server.native import actor
from server.research_flow import RunInput,install
from server.research_tool_flow import parsed_excerpts,schedule_parse,ToolUnavailable,native_execution_allowed

class ToolFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name);self.owner='alice';self.project=self.store.create(self.owner,'test');self.pid=self.project['id'];self.root=self.store.path(self.owner,self.pid)
    def tearDown(self):self.temp.cleanup()
    def parsed(self):
        asset='reading/source.pdf';p=self.root/'literature'/asset;p.parent.mkdir(parents=True);p.write_bytes(b'original PDF fixture bytes')
        digest=hashlib.sha256(p.read_bytes()).hexdigest();prefix=self.root/'project/docs/literature/parsed'/digest
        atomic_json(self.root/'.workbench/literature-index.json',{asset:{'title':'Source fixture','doi':'10.1234/source'}})
        atomic_json(prefix/'pages.json',{'sha256':digest,'page_count':12,'pages':[{'page':i,'text':'Page '+str(i)} for i in range(1,13)],'cluster_job_id':'12345'})
        return asset,prefix
    def test_native_workflow_is_real_default_and_fallback_is_explicit(self):
        request=RunInput(kind='code',instruction='Implement the selected source')
        self.assertEqual(request.code_engine,'paper2code');self.assertFalse(request.allow_search_fallback)
        self.assertEqual(RunInput(kind='search',search_tool='get_author_papers',author='Author').search_tool,'get_author_papers')
    def test_native_execution_grant_is_project_scoped(self):
        config={'native_execution_enabled':False,'native_execution_projects':[self.pid]}
        self.assertTrue(native_execution_allowed(config,self.pid))
        self.assertFalse(native_execution_allowed(config,'another-project'))
        self.assertFalse(native_execution_allowed({},self.pid))
    def test_code_dispatch_keeps_project_inputs_and_stage_guidance(self):
        from server.research_tool_flow import native_code,bind_authorization
        source=self.root/'project/src/model.py';source.parent.mkdir(parents=True,exist_ok=True);source.write_text('value = 1\n')
        binding={'id':'operation','versions':{},'session_id':'session'}
        bind_authorization(binding,self.owner,self.pid,self.project['native_id'])
        state={'native_code':binding};sent=[]
        async def dispatch(owner,pid,jid,binding,state,persist,start):
            sent.append(start);return {'status':'waiting_input','native':{}}
        request=RunInput(kind='code',instruction='Implement selected experiment',code_engine='agent',input_paths=['src/model.py'])
        with patch('server.research_tool_flow.bridge_config',return_value={'native_execution_projects':[self.pid]}),patch('server.research_tool_flow.bound_call',dispatch):
            result=asyncio.run(native_code(self.store,self.owner,self.pid,'operation',request,{},state,lambda value:None))
        self.assertEqual(result['status'],'requires_input')
        payload=sent[0]['payload'];self.assertEqual(payload['code_engine'],'agent')
        self.assertIn('Implement selected experiment',payload['instruction']);self.assertIn(self.pid,payload['instruction'])
        self.assertIn('src/model.py',payload['instruction']);self.assertIn('按有意义的阶段实现并集中验证',payload['instruction'])
        self.assertIn('目标实验完成分别报告',payload['instruction'])
        self.assertEqual([r['path'] for r in sent[0]['inputs']],['src/model.py'])
    def test_code_result_is_archived_without_automatic_knowledge_node(self):
        from server.research_flow import graph,save_record
        app=FastAPI();app.dependency_overrides[actor]=lambda:{'id':self.owner}
        install(app,self.store,lambda owner:Path(self.temp.name)/'api.json',None)
        save_record(self.store,self.owner,self.pid,{'id':'prior','nodes':[{'id':'prior','kind':'idea','label':'Existing scientific idea','status':'proposed'}]})
        workers=[]
        class Pool:
            def submit(self,fn):workers.append(fn)
        async def code(*args):
            return {'status':'completed','session_id':'native-session','published_reply':'Implemented requested entry point; software tests passed.',
                    'files':[{'path':'src/main.py','saved':True}],'verification':{'passed':True}}
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/research/api/projects/'+self.pid+'/research-flow/runs',json={
                    'kind':'code','code_engine':'agent','instruction':'Implement the requested code','query':'Software acceptance'})
                self.assertEqual(response.status_code,200,response.text)
                return response.json()['id']
        with patch('server.research_flow.RUNNERS',Pool()),patch('server.research_tool_flow.native_code',code):
            jid=asyncio.run(check())
            workers[0]()
        row=next(r for r in self.store.jobs(self.owner,self.pid) if r['id']==jid)
        self.assertEqual(row['status'],'completed',row)
        self.assertEqual([n['id'] for n in graph(self.store,self.owner,self.pid)['nodes']],['prior'])
        receipt=row['result']['record_receipt'];self.assertEqual(receipt['nodes'],0)
        self.assertIn('software tests passed',(self.root/'project'/receipt['path']).read_text(encoding='utf8'))
        self.assertTrue((self.root/'project'/row['result']['path']).is_file())
    def test_reading_uses_requested_cluster_pages_and_source_identity(self):
        asset,folder=self.parsed();rows=parsed_excerpts(self.store,self.owner,self.pid,[asset],3,{asset:[7,8]})
        self.assertEqual([p['page'] for p in rows[0]['pages']],[7,8]);self.assertEqual(rows[0]['parser_job_id'],'12345')
        value=json.loads((folder/'pages.json').read_text());value['sha256']='wrong';atomic_json(folder/'pages.json',value)
        with self.assertRaises(ValueError):parsed_excerpts(self.store,self.owner,self.pid,[asset],3)
    def test_resume_reuses_job_identity_and_does_not_submit_external_work(self):
        app=FastAPI();app.dependency_overrides[actor]=lambda:{'id':self.owner}
        install(app,self.store,lambda owner:Path(self.temp.name)/'api.json',None)
        jid=self.store.job(self.owner,self.pid,'research-flow',{'subject':'retry'});self.store.set_job(jid,status='failed',stage='failed')
        root=self.root/'.workbench/research-flow/runs'/jid;atomic_json(root/'request.json',RunInput(kind='analyze',assets=['reading/source.pdf']).model_dump());atomic_json(root/'state.json',{'stage_receipts':{'parse':{'at':'previous'}}})
        calls=[]
        class Pool:
            def submit(self,fn):calls.append(fn)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                with patch('server.research_flow.RUNNERS',Pool()):r=await client.post('/research/api/projects/'+self.pid+'/research-flow/runs/'+jid+'/resume')
                self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['id'],jid);self.assertTrue(r.json()['resumed'])
        asyncio.run(check());self.assertEqual(len(calls),1);self.assertIn('parse',json.loads((root/'state.json').read_text())['stage_receipts'])
        # Drain the captured worker so its cross-process lease is released on Windows.
        with patch('server.research_tool_flow.parsed_excerpts',return_value=[]):calls[0]()
    def test_offline_parser_waits_then_reconnects_the_same_job(self):
        jid=self.store.job(self.owner,self.pid,'cluster-pdf-parse',{'asset':'reading/source.pdf'})
        class Pool:
            def submit(self,fn):fn()
        async def offline(*args):raise ToolUnavailable('tool bridge offline')
        async def restored(*args):return {'path':'docs/literature/parsed/source/','cluster_job_id':'12345','cached':True}
        with patch('server.research_flow.RUNNERS',Pool()),patch('server.research_tool_flow.parse_pdf',offline):schedule_parse(self.store,self.owner,self.pid,'reading/source.pdf',jid)
        row=next(r for r in self.store.jobs(self.owner,self.pid) if r['id']==jid);self.assertEqual(row['status'],'queued');self.assertNotEqual(row['status'],'completed')
        with patch('server.research_flow.RUNNERS',Pool()),patch('server.research_tool_flow.parse_pdf',restored):schedule_parse(self.store,self.owner,self.pid,'reading/source.pdf',jid)
        row=next(r for r in self.store.jobs(self.owner,self.pid) if r['id']==jid);self.assertEqual(row['status'],'completed');self.assertEqual(row['result']['cluster_job_id'],'12345')

if __name__=='__main__':unittest.main()
