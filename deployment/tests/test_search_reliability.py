"""Regressions for observed read disconnects and misleading search failures."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
import tempfile
import threading
import time
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
from workbench_mcp.client import WorkbenchClient

package = ModuleType('search_fixture')
package.__path__ = [str(ROOT / 'workbench-search/server')]
sys.modules['search_fixture'] = package
from search_fixture import search_mcp
from search_fixture import network_sources
from search_fixture.search_errors import SearchProviderError


class SearchReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_fast_public_engine_failure_retries_once_and_preserves_source(self):
        ddgs=ModuleType('ddgs');calls=[]
        class DDGS:
            def __init__(self,**kwargs):pass
            def text(self,*args,**kwargs):
                calls.append(1)
                if len(calls)==1:raise RuntimeError('upstream temporarily unavailable')
                return [{'title':'Source','href':'https://example.test/recovered','body':'Original snippet'}]
        ddgs.DDGS=DDGS
        with patch.dict(sys.modules,{'ddgs':ddgs}),patch.object(network_sources,'_PUBLIC_WEB_GATE',asyncio.Semaphore(1)):
            result=await network_sources.web_search('fast failure recovery fixture',{})
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['attempts'],2)
        self.assertEqual(result['source'],network_sources.PUBLIC_WEB_SOURCE)

    async def test_public_rate_limit_does_not_loop_or_cache_failure(self):
        ddgs=ModuleType('ddgs');calls=[]
        class RatelimitException(Exception):pass
        class DDGS:
            def __init__(self,**kwargs):pass
            def text(self,*args,**kwargs):
                calls.append(1)
                if len(calls)==1:raise RatelimitException('sensitive provider diagnostic')
                return [{'title':'Source','href':'https://example.test/after-limit','body':'Original snippet'}]
        ddgs.DDGS=DDGS
        with patch.dict(sys.modules,{'ddgs':ddgs}),patch.object(network_sources,'_PUBLIC_WEB_GATE',asyncio.Semaphore(1)):
            failed=await network_sources.web_search('rate limit fixture',{})
            self.assertEqual(len(calls),1)
            recovered=await network_sources.web_search('rate limit fixture',{})
        self.assertEqual(failed['error']['code'],'rate_limited')
        self.assertNotIn('sensitive',str(failed))
        self.assertEqual(recovered['status'],'ready')
        self.assertEqual(len(calls),2)

    async def test_concurrent_public_queries_are_serialized_at_unkeyed_provider(self):
        ddgs=ModuleType('ddgs');lock=threading.Lock();state={'active':0,'peak':0}
        class DDGS:
            def __init__(self,**kwargs):pass
            def text(self,*args,**kwargs):
                with lock:
                    state['active']+=1;state['peak']=max(state['peak'],state['active'])
                time.sleep(.04)
                with lock:state['active']-=1
                return [{'title':'Source','href':'https://example.test/'+args[0],'body':'Original snippet'}]
        ddgs.DDGS=DDGS
        with patch.dict(sys.modules,{'ddgs':ddgs}),patch.object(network_sources,'_PUBLIC_WEB_GATE',asyncio.Semaphore(1)):
            results=await asyncio.gather(*(network_sources.web_search('parallel fixture '+str(i),{}) for i in range(4)))
        self.assertTrue(all(r['status']=='ready' for r in results))
        self.assertEqual(state['peak'],1)

    async def test_recent_public_result_is_reused_without_another_provider_request(self):
        ddgs=ModuleType('ddgs');calls=[]
        class DDGS:
            def __init__(self,**kwargs):pass
            def text(self,*args,**kwargs):
                calls.append(1)
                if len(calls)>1:raise RuntimeError('intermittent public provider failure')
                return [{'title':'Actual page','href':'https://example.test/page','body':'Source excerpt'}]
        ddgs.DDGS=DDGS
        with patch.dict(sys.modules,{'ddgs':ddgs}):
            first=await network_sources.web_search('unique reliability fixture',{})
            second=await network_sources.web_search('unique reliability fixture',{})
        self.assertEqual(first['items'],second['items'])
        self.assertTrue(second.get('cached'))
        self.assertEqual(len(calls),1)

    async def test_transient_read_disconnect_retries_once(self):
        calls = []
        async def upstream(request):
            calls.append(request.method)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError('Server disconnected without sending a response', request=request)
            return httpx.Response(200, json={'items':[{'title':'Actual result'}]})
        client = WorkbenchClient('https://workbench.test')
        client._session = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        self.addAsyncCleanup(client.close)
        result = await client.request('GET', '/research/api/search/web')
        self.assertEqual(result['items'][0]['title'], 'Actual result')
        self.assertEqual(calls, ['GET', 'GET'])

    async def test_write_disconnect_does_not_repeat_side_effect(self):
        calls = []
        async def upstream(request):
            calls.append(request.method)
            raise httpx.ReadError('Reply lost after write', request=request)
        client = WorkbenchClient('https://workbench.test')
        client._session = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        self.addAsyncCleanup(client.close)
        with self.assertRaises(httpx.ReadError):
            await client.request('POST', '/research/api/projects/example/agent-receipt', json={})
        self.assertEqual(calls, ['POST'])

    async def test_scholar_transport_failure_is_not_manual_verification(self):
        class BridgeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, *args, **kwargs):
                raise httpx.ConnectError('private transport detail')
        with patch.object(search_mcp, 'ready', return_value=True), \
             patch.object(search_mcp, 'bridge_config', return_value={'url':'https://bridge.test','token':'private'}), \
             patch('httpx.AsyncClient', return_value=BridgeClient()):
            with self.assertRaises(ValueError) as caught:
                await search_mcp.discover('Fourier neural operator', limit=2)
        self.assertEqual(getattr(caught.exception, 'code', None), 'bridge_unavailable')
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn('private', str(caught.exception))

    async def test_scholar_challenge_has_nonretryable_recovery(self):
        class BridgeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, *args, **kwargs):
                return httpx.Response(200, request=httpx.Request('POST','https://bridge.test/scholar'),
                    json={'ok':False,'error':{'code':'verification_required'}})
        with patch.object(search_mcp, 'ready', return_value=True), \
             patch.object(search_mcp, 'bridge_config', return_value={'url':'https://bridge.test','token':'private'}), \
             patch('httpx.AsyncClient', return_value=BridgeClient()):
            with self.assertRaises(ValueError) as caught:
                await search_mcp.discover('Fourier neural operator', limit=2)
        self.assertEqual(getattr(caught.exception, 'code', None), 'verification_required')
        self.assertFalse(caught.exception.retryable)
        self.assertIn('人工', caught.exception.next_action)

    async def test_slow_metadata_preserves_original_discovery(self):
        references=ModuleType('search_fixture.references')
        async def slow(*args, **kwargs):
            await asyncio.sleep(1)
            return []
        references.search=slow
        rows=search_mcp.PaperRows([{'title':'Actual paper','url':'https://example.test/paper'}],next_cursor='10')
        with patch.dict(sys.modules,{'search_fixture.references':references}), \
             patch.object(search_mcp,'METADATA_TIMEOUT_SECONDS',0.01), \
             patch.object(search_mcp,'RECONCILE_TIMEOUT_SECONDS',0.03):
            result=await search_mcp.reconcile(rows)
        self.assertEqual(result[0]['title'],'Actual paper')
        self.assertEqual(result[0]['metadata_status'],'unverified')
        self.assertEqual(result.next_cursor,'10')

    async def test_explicit_failure_and_auto_fallback_keep_actual_source(self):
        references=ModuleType('search_fixture.references')
        native=ModuleType('search_fixture.native');native.actor=lambda:None
        storage=ModuleType('search_fixture.storage');storage.now=lambda:'2026-11-01T00:00:00Z'
        calls=[]
        async def search(*args,source=None,**kwargs):
            calls.append(source)
            if source=='scholar_mcp':
                raise SearchProviderError('verification_required','需要人工验证',provider='Google Scholar · MCP',next_action='人工验证')
            return [{'title':'Actual metadata','doi':'10.1000/example'}]
        references.search=search
        with patch.dict(sys.modules,{'search_fixture.references':references,'search_fixture.native':native,'search_fixture.storage':storage}):
            spec=importlib.util.spec_from_file_location('search_fixture.literature_network',ROOT/'workbench-search/server/literature_network.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        from fastapi import FastAPI
        app=FastAPI()
        with tempfile.TemporaryDirectory() as directory:
            class Store:
                def get(self,*args):return {}
            module.install(app,Store(),lambda owner:Path(directory)/'missing.json')
            endpoint=next(route.endpoint for route in app.routes if route.path.endswith('/literature/search'))
            with patch.object(search_mcp,'ready',return_value=True):
                failed=await endpoint('a'*32,'actual topic',source='scholar_mcp',user={'id':'owner'})
                self.assertEqual(failed['error']['code'],'verification_required')
                self.assertEqual(calls,['scholar_mcp'])
                calls.clear()
                recovered=await endpoint('a'*32,'actual topic',source='auto',user={'id':'owner'})
            self.assertEqual(calls,['scholar_mcp','crossref'])
            self.assertEqual(recovered['provider'],'crossref')
            self.assertEqual(recovered['status'],'degraded')
            self.assertEqual(recovered['warnings'][0]['code'],'verification_required')


if __name__ == '__main__':
    unittest.main()
