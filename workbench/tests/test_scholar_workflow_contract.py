"""Dispatch, HTTP authorization, and bounded Scholar recovery contracts."""
import asyncio
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from server import scholar_mcp_client as client
from server import search_mcp as search
from scripts import local_search_bridge as bridge


def success(cursor='next'):
    return {'ok': True, 'data': {'results': [{'title': '[PDF] A paper', 'url': ''}], 'next_cursor': cursor}}


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_module_classified_before_mcp_launch(self):
        with patch('importlib.util.find_spec', side_effect=lambda name: None if name == 'scholar_mcp' else object()):
            result = await client.run({'operation': 'diagnostics'})
        self.assertEqual(result['error']['code'], 'python_module_missing')
        self.assertEqual(result['error']['details']['modules'], ['scholar_mcp'])
        self.assertFalse(result['error']['retryable'])

    async def test_text_response_and_author_schema_alias(self):
        session = SimpleNamespace(initialize=AsyncMock(), list_tools=AsyncMock(return_value=SimpleNamespace(
            tools=[SimpleNamespace(name='get_author_papers', inputSchema={'properties': {'author_name': {}, 'cursor': {}}})])),
            call_tool=AsyncMock(return_value=SimpleNamespace(structuredContent=None, isError=False,
                content=[SimpleNamespace(type='text', text=json.dumps(success('opaque-next')))])))
        result = await client.dispatch(session, {'tool': 'get_author_papers', 'arguments': {'author': 'Ada', 'cursor': 'opaque'}})
        session.call_tool.assert_awaited_once_with('get_author_papers', {'author_name': 'Ada', 'cursor': 'opaque'})
        self.assertEqual(result['data']['next_cursor'], 'opaque-next')

    async def test_official_session_sequence_and_tools(self):
        for tool, identity in [('search_papers_by_topic', {'query': 'quantum'}),
                               ('get_author_papers', {'author': 'Ada Lovelace'})]:
            events = []
            async def initialize(): events.append('initialize')
            async def listing():
                events.append('list_tools')
                return SimpleNamespace(tools=[SimpleNamespace(name=tool, inputSchema={})])
            async def call(name, arguments):
                events.append('call_tool')
                self.assertEqual(name, tool)
                self.assertEqual(arguments, {**identity, 'cursor': 'opaque', 'year_min': 2020, 'year_max': 2024})
                return SimpleNamespace(structuredContent=success(), isError=False)
            session = SimpleNamespace(initialize=initialize, list_tools=listing, call_tool=call)
            result = await client.dispatch(session, {'tool': tool, 'arguments': {**identity,
                'cursor': 'opaque', 'year_min': 2020, 'year_max': 2024}})
            self.assertEqual(events, ['initialize', 'list_tools', 'call_tool'])
            self.assertEqual(result['tool'], tool)
            self.assertEqual(result['data']['next_cursor'], 'next')

    async def test_structured_error_preserved(self):
        error = {'code': 'verification_required', 'retryable': False, 'details': {'manual': True}}
        session = SimpleNamespace(initialize=AsyncMock(), list_tools=AsyncMock(return_value=SimpleNamespace(
            tools=[SimpleNamespace(name='search_papers_by_topic', inputSchema={})])),
            call_tool=AsyncMock(return_value=SimpleNamespace(structuredContent={'ok': False, 'error': error}, isError=True)))
        result = await client.dispatch(session, {'query': 'quantum'})
        self.assertEqual(result['error'], error)

    async def test_missing_tool_never_called(self):
        session = SimpleNamespace(initialize=AsyncMock(), list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])), call_tool=AsyncMock())
        result = await client.dispatch(session, {'query': 'quantum'})
        self.assertEqual(result['error']['code'], 'mcp_tool_missing')
        session.call_tool.assert_not_called()


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_http_transport_and_protocol_errors(self):
        import httpx
        config = {'url': 'http://bridge', 'token': 'test-only'}
        for response, code, retryable in [
            (httpx.Response(502, text='gateway unavailable', request=httpx.Request('POST', 'http://bridge/scholar')), 'bridge_transport_error', True),
            (httpx.Response(403, text='forbidden', request=httpx.Request('POST', 'http://bridge/scholar')), 'bridge_http_error', False),
            (httpx.Response(200, text='not json', request=httpx.Request('POST', 'http://bridge/scholar')), 'mcp_protocol_error', False),
        ]:
            fake = AsyncMock()
            fake.post.return_value = response
            with patch('httpx.AsyncClient') as factory:
                factory.return_value.__aenter__.return_value = fake
                result = await search._bridge_post(config, '/scholar', {})
            self.assertEqual(result['error']['code'], code)
            self.assertEqual(result['error']['retryable'], retryable)

    async def test_arguments_pagination_and_old_call(self):
        with patch.object(search, 'bridge_config', return_value=None), patch.object(search, '_local_call', new_callable=AsyncMock, return_value=success()) as call:
            rows = await search.discover('topic', 5, 2019, 20)
            self.assertEqual(call.call_args.args[0]['arguments']['cursor'], '20')
            self.assertEqual(rows.next_cursor, 'next')
            self.assertEqual(rows[0]['title'], 'A paper')
            await search.discover('', tool='get_author_papers', author='Ada', cursor='opaque', year_max=2023, min_year=2020)
            self.assertEqual(call.call_args.args[0], {'tool': 'get_author_papers', 'arguments': {
                'author': 'Ada', 'page_size': 10, 'cursor': 'opaque', 'year_min': 2020, 'year_max': 2023}})

    async def test_diagnose_repair_retry_same_tool_once(self):
        events = []
        failure = client.failure('mcp_transport_error', 'transport', True)
        async def call(payload):
            events.append(('call', payload))
            return failure if len([x for x in events if x[0] == 'call']) == 1 else success()
        async def diagnose(config): events.append(('diagnose', None)); return {'reason': 'proxy_error'}
        async def repair(config, error, diagnosis): events.append(('repair', None)); return {'ok': True}
        with patch.object(search, 'bridge_config', return_value=None), patch.object(search, '_local_call', side_effect=call), patch.object(search, '_diagnose', side_effect=diagnose), patch.object(search, '_repair', side_effect=repair):
            rows = await search.discover('Ada', tool='get_author_papers')
        self.assertEqual([e[0] for e in events], ['call', 'diagnose', 'repair', 'call'])
        self.assertEqual(events[0][1], events[-1][1])
        self.assertEqual(len(rows.diagnostics), 3)

    async def test_no_implicit_fallback_or_unbounded_retry(self):
        for code in ('verification_required', 'blocked', 'rate_limited', 'mcp_transport_error'):
            error = {'code': code, 'retryable': True, 'details': {'hint': 'preserved'}, 'message': 'failed'}
            with patch.object(search, 'bridge_config', return_value=None), patch.object(search, '_local_call', new_callable=AsyncMock, return_value={'ok': False, 'error': error}) as call, patch.object(search, '_diagnose', new_callable=AsyncMock, return_value={}), patch.object(search, '_repair', new_callable=AsyncMock) as repair:
                with self.assertRaises(search.ScholarMCPError) as caught:
                    await search.discover('topic')
                self.assertEqual(caught.exception.details, {'hint': 'preserved'})
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(call.await_count, 2 if code == 'mcp_transport_error' else 1)
                self.assertEqual(repair.await_count, 1 if code == 'mcp_transport_error' else 0)

    async def test_diagnosed_block_stops_retry(self):
        with patch.object(search, 'bridge_config', return_value=None), patch.object(search, '_local_call', new_callable=AsyncMock, return_value=client.failure('mcp_transport_error', 'failed', True)) as call, patch.object(search, '_diagnose', new_callable=AsyncMock, return_value={'reason': 'rate_limited'}), patch.object(search, '_repair', new_callable=AsyncMock) as repair:
            with self.assertRaises(search.ScholarMCPError): await search.discover('topic')
            call.assert_awaited_once()
            repair.assert_not_awaited()


class BridgeTests(unittest.TestCase):
    def test_diagnostics_probe_configured_python_and_handshake(self):
        probe = Mock(stdout=json.dumps({'modules': {'mcp': True, 'scholar_mcp': False},
                                      'proxy_configured': True, 'network_status': 200}))
        with patch.object(bridge.subprocess, 'run', return_value=probe) as run, patch.object(bridge, 'invoke', return_value=client.failure('mcp_transport_error', 'failed')) as invoke, patch.object(bridge.Path, 'is_file', return_value=True):
            result = bridge.diagnostics({'python': 'configured-python'})
            self.assertEqual(run.call_args.args[0][:3], ['configured-python', '-X', 'utf8'])
            invoke.assert_called_once_with({'python': 'configured-python'}, {'operation': 'diagnostics'})
            self.assertEqual(result['reason'], 'python_module_missing')
            self.assertEqual(result['missing_modules'], ['scholar_mcp'])

    def test_missing_interpreter_error(self):
        with patch.object(bridge.subprocess, 'run', side_effect=FileNotFoundError):
            result = bridge.invoke({'python': 'missing-python'}, {'query': 'topic'})
        self.assertEqual(result['error']['code'], 'interpreter_missing')
        self.assertFalse(result['error']['retryable'])

    def test_http_dispatch_and_protected_endpoints(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.handler_for({'token': 'test-only'}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        def post(path, value, authorized=True):
            request = Request(base+path, json.dumps(value).encode(), headers={'x-workbench-search': 'test-only' if authorized else ''})
            with urlopen(request, timeout=3) as response: return json.load(response)
        try:
            with urlopen(base+'/capabilities') as response:
                self.assertIn('get_author_papers', json.load(response)['tools'])
            for path in ('/scholar', '/diagnostics', '/repair'):
                with self.assertRaises(HTTPError) as caught: post(path, {}, False)
                self.assertEqual(caught.exception.code, 403)
            with patch.object(bridge, 'invoke', return_value=success()) as invoke:
                post('/scholar', {'query': 'legacy'})
                self.assertEqual(invoke.call_args.args[1]['tool'], 'search_papers_by_topic')
                post('/scholar', {'tool': 'get_author_papers', 'arguments': {'author': 'Ada', 'cursor': 'opaque'}})
                self.assertEqual(invoke.call_args.args[1]['arguments']['cursor'], 'opaque')
            with patch.object(bridge, 'diagnostics', return_value={'ok': True}) as diagnose:
                self.assertTrue(post('/diagnostics', {})['ok'])
                diagnose.assert_called_once()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_repair_only_configured_and_never_challenge(self):
        config = {'repair_commands': {'proxy': ['configured-proxy', 'restore']}}
        with patch.object(bridge.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            for code in ('verification_required', 'blocked', 'rate_limited', 'interpreter_missing'):
                self.assertFalse(bridge.repair(config, {'code': code})['attempted'])
            run.assert_not_called()
            self.assertTrue(bridge.repair(config, {'code': 'proxy_error'})['ok'])
            self.assertEqual(run.call_args.args[0], ['configured-proxy', 'restore'])


if __name__ == '__main__':
    unittest.main()
