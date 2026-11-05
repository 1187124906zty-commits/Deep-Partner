"""Actual HTTP boundary: a retry must never silently replace a different task."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from server import research_flow as flow
from server.storage import Store


class RequestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.owner = 'alice'
        self.pid = self.store.create(self.owner, 'request identity')['id']
        self.app = FastAPI()
        self.app.dependency_overrides[flow.actor] = lambda: {'id': self.owner}
        self.work = []
        self.patchers = [patch('server.research_tool_flow.start_recovery'),
                         patch.object(flow.RUNNERS, 'submit', side_effect=lambda fn: self.work.append(fn))]
        for p in self.patchers: p.start()
        flow.install(self.app, self.store, lambda _: Path(self.temp.name)/'api.json', None)

    def tearDown(self):
        # Queued fake workers own OS locks until invoked; finish without tools.
        with patch('server.research_tool_flow.native_code', side_effect=PermissionError('test complete')):
            for work in self.work: work()
        for p in reversed(self.patchers): p.stop()
        self.temp.cleanup()

    def send(self, **changes):
        body = {'kind': 'code', 'instruction': 'create a.py', 'request_id': 'same-request'}
        body.update(changes)
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test') as client:
                return await client.post(f'/research/api/projects/{self.pid}/research-flow/runs', json=body)
        return asyncio.run(request())

    def test_same_request_reuses_run_and_returns_current_status(self):
        first = self.send(); second = self.send()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual(second.json().get('status'), 'queued')
        self.assertTrue(second.json()['duplicate'])
        self.assertEqual(len(self.work), 1)

    def test_changed_input_under_same_id_is_a_conflict(self):
        first = self.send()
        changed = self.send(instruction='create a different b.py')
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(len(self.store.jobs(self.owner, self.pid)), 1)
        folder = self.store.path(self.owner, self.pid)/'.workbench/research-flow/runs'/first.json()['id']
        self.assertEqual(json.loads((folder/'request.json').read_text(encoding='utf8'))['instruction'], 'create a.py')

    def test_persisted_identity_survives_app_restart(self):
        first = self.send()
        second_app = FastAPI()
        second_app.dependency_overrides[flow.actor] = lambda: {'id': self.owner}
        flow.install(second_app, self.store, lambda _: Path(self.temp.name)/'api.json', None)
        self.app = second_app
        second = self.send()
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual(self.send(query='changed context').status_code, 409)
        self.assertEqual(len(self.work), 1)

    def test_plan_review_requires_an_explicit_current_decision(self):
        rid=self.send().json()['id']
        self.store.set_job(rid,status='waiting_input',result={'code_result':{
            'native_tool':True,'interaction':{'id':'current-review','request':{'interaction_type':'plan_review'}}}})
        async def reply(body):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test') as client:
                return await client.post(f'/research/api/projects/{self.pid}/research-flow/runs/{rid}/reply',json=body)
        with patch('server.research_tool_flow.tool_call') as tool:
            for response in [{},{'action':'modify','feedback':''},{'unrelated':'text'}]:
                with self.assertRaises(ValueError):asyncio.run(reply({'interaction_id':'current-review','response':response}))
            stale=asyncio.run(reply({'interaction_id':'old-review','response':{'action':'approve'}}))
            self.assertEqual(stale.status_code,409)
            tool.assert_not_called()
