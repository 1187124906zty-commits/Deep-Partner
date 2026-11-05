"""User controls cross the same HTTP seam as the workspace, without model calls."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
import httpx
from fastapi import FastAPI
from server import research_flow as flow
from server import research_tool_flow as tools
from server.storage import Store,atomic_json


class Queue:
    def __init__(self):self.work=[]
    def submit(self,fn):self.work.append(fn)
    def run(self):self.work.pop(0)()


class WorkflowControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name)
        self.owner='alice';self.pid=self.store.create(self.owner,'control test')['id']
        self.pool=Queue();self.patches=[patch.object(flow,'RUNNERS',self.pool),patch.object(tools,'start_recovery')]
        for p in self.patches:p.start()
        self.app=FastAPI();self.app.dependency_overrides[flow.actor]=lambda:{'id':self.owner}
        self.runtime=flow.install(self.app,self.store,lambda _:Path(self.temp.name)/'api.json',None)
        self.payload=flow.RunInput(kind='code',instruction='Only create requested file',request_id='control-case')
        self.rid=self.store.job(self.owner,self.pid,'research-flow',{})
        self.folder=self.store.path(self.owner,self.pid)/'.workbench/research-flow/runs'/self.rid
        atomic_json(self.folder/'request.json',self.payload.model_dump())
        atomic_json(self.folder/'state.json',{'id':self.rid,'kind':'code','stage_receipts':{},'steps':[]})

    def tearDown(self):
        with patch.object(tools,'native_code',new_callable=AsyncMock,side_effect=PermissionError('test cleanup')):
            while self.pool.work:self.pool.run()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def request(self,method,suffix,body=None,pid=None):
        return asyncio.run(self.async_request(method,suffix,body,pid))

    async def async_request(self,method,suffix,body=None,pid=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test') as client:
            return await client.request(method,f'/research/api/projects/{pid or self.pid}/research-flow/runs/{self.rid}'+suffix,json=body)

    def test_inspector_shows_only_actual_route_and_original_request(self):
        response=self.request('GET','/progress');self.assertEqual(response.status_code,200,response.text)
        value=response.json()
        self.assertEqual([s['id'] for s in value['stages']],['dispatch','archive'])
        self.assertEqual(value['request']['instruction'],'Only create requested file')
        self.assertNotIn('authorization',json.dumps(value))

    def test_pause_before_stage_survives_restart_and_resume_never_reexecutes(self):
        response=self.request('POST','/control',{'action':'checkpoints','pause_before':['archive'],'expected_revision':0})
        self.assertEqual(response.status_code,200,response.text)
        completed={'status':'completed','native_tool':True,'session_id':'native','published_reply':'done','files':[]}
        with patch.object(tools,'native_code',new_callable=AsyncMock,return_value=completed) as execute,patch.object(flow,'save_record',return_value={}):
            self.runtime['schedule'](self.owner,self.pid,self.rid,self.payload,{})
            self.pool.run()
            self.assertEqual(flow.job_row(self.store,self.owner,self.pid,self.rid)['status'],'paused')
            self.assertIn('dispatch',json.loads((self.folder/'state.json').read_text(encoding='utf8'))['stage_receipts'])
            # New app has no memory of the original control request.
            app=FastAPI();app.dependency_overrides[flow.actor]=lambda:{'id':self.owner};self.app=app
            self.runtime=flow.install(app,self.store,lambda _:Path(self.temp.name)/'api.json',None)
            self.runtime['recover']();self.assertFalse(self.pool.work)
            resumed=self.request('POST','/resume',{})
            self.assertEqual(resumed.status_code,200,resumed.text);self.pool.run()
            self.assertEqual(execute.await_count,1)
            self.assertEqual(flow.job_row(self.store,self.owner,self.pid,self.rid)['status'],'completed')

    def test_pause_during_inflight_call_waits_for_safe_boundary(self):
        self.store.set_job(self.rid,status='running')
        async def inflight(*args):
            r=await self.async_request('POST','/control',{'action':'pause','expected_revision':0})
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['status'],'pause_requested')
            args[6]['native_code']={'id':self.rid,'submitted':True};args[7](args[6])
            raise tools.ToolPending('the same external task is still running')
        with patch.object(tools,'native_code',side_effect=inflight):
            self.runtime['schedule'](self.owner,self.pid,self.rid,self.payload,{})
            self.pool.run()
        row=flow.job_row(self.store,self.owner,self.pid,self.rid)
        self.assertEqual(row['status'],'paused')
        self.assertTrue(row['result']['native_code']['submitted'])
        self.runtime['recover'](now_ts=10**12);self.assertFalse(self.pool.work)

    def test_invalid_step_and_stale_control_do_not_silently_change_plan(self):
        bad=self.request('POST','/control',{'action':'checkpoints','pause_before':['invented'],'expected_revision':0})
        self.assertEqual(bad.status_code,400)
        good=self.request('POST','/control',{'action':'checkpoints','pause_before':['dispatch'],'expected_revision':0})
        self.assertEqual(good.status_code,200)
        stale=self.request('POST','/control',{'action':'checkpoints','pause_before':[],'expected_revision':0})
        self.assertEqual(stale.status_code,409)

    def test_other_project_cannot_read_or_control_run(self):
        other=self.store.create(self.owner,'other')['id']
        with self.assertRaises(KeyError):self.request('GET','/progress',pid=other)

    def test_simulation_internal_steps_are_observable_not_local_checkpoints(self):
        payload=flow.RunInput(kind='simulate',instruction='prepared case')
        atomic_json(self.folder/'request.json',payload.model_dump())
        value=self.request('GET','/progress').json()
        self.assertEqual([s['id'] for s in value['stages'] if s['can_pause']],['prepare','archive'])
        bad=self.request('POST','/control',{'action':'checkpoints','pause_before':['validate'],'expected_revision':0})
        self.assertEqual(bad.status_code,400)
