"""Exercise real model streaming code with deterministic, accelerated silence.

Run inside the deployed Tutor runtime. Set TUTOR_TIMEOUT_SOURCE to test a
candidate source tree before installing it. Finite production deadlines are
accelerated to 20 ms, while the model takes 60 ms to produce its first delta.
"""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, '/app')


def load_candidate(name):
    root = os.environ.get('TUTOR_TIMEOUT_SOURCE')
    if not root:
        return __import__(name, fromlist=['*'])
    path = Path(root) / (name.replace('.', '/') + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


http_helper = load_candidate('deeptutor.services.llm.openai_http_client')
compat = load_candidate('deeptutor.services.llm.provider_core.openai_compat_provider')
anthropic = load_candidate('deeptutor.services.llm.provider_core.anthropic_provider')
azure = load_candidate('deeptutor.services.llm.provider_core.azure_openai_provider')
agent = load_candidate('deeptutor.agents.loop.agent_loop')

real_wait_for = asyncio.wait_for


async def accelerated_wait(awaitable, timeout=None):
    return await real_wait_for(awaitable, None if timeout is None else 0.02)


async def delayed_events(*events):
    await asyncio.sleep(0.06)
    for event in events:
        yield event


def provider(wire_api='responses'):
    return compat.OpenAICompatProvider(
        api_key='test-key', api_base='http://127.0.0.1:1/v1',
        default_model='test-model', wire_api=wire_api, configure_env=False,
    )


class ModelWaitPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_agent_accepts_output_after_long_silence(self):
        with patch('asyncio.wait_for', side_effect=accelerated_wait):
            output = [x async for x in agent._bounded_stream_chunks(delayed_events('answer'))]
        self.assertEqual(output, ['answer'])

    async def test_agent_wait_can_be_cancelled(self):
        waiting = asyncio.Event()
        async def silence():
            await waiting.wait()
            yield 'never'
        task = asyncio.create_task(anext(agent._bounded_stream_chunks(silence())))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_responses_accepts_output_after_long_silence(self):
        p = provider()
        p._create_responses_with_status_retry = AsyncMock(return_value=delayed_events(
            SimpleNamespace(type='response.output_text.delta', delta='delayed answer'),
            SimpleNamespace(type='response.completed', response={'status': 'completed'}),
        ))
        try:
            with patch('asyncio.wait_for', side_effect=accelerated_wait):
                response = await p.chat_stream(messages=[{'role': 'user', 'content': 'test'}])
            self.assertEqual(response.finish_reason, 'stop')
            self.assertEqual(response.content, 'delayed answer')
        finally:
            await p._client.close()

    async def test_chat_completions_accepts_output_after_long_silence(self):
        from openai.types.chat import ChatCompletionChunk
        p = provider('chat_completions')
        chunks = [ChatCompletionChunk(id='test', created=0, model='test-model', object='chat.completion.chunk',
                   choices=[{'index': 0, 'delta': {'content': 'delayed answer'}, 'finish_reason': None}]),
                  ChatCompletionChunk(id='test', created=0, model='test-model', object='chat.completion.chunk',
                   choices=[{'index': 0, 'delta': {}, 'finish_reason': 'stop'}])]
        p._create_with_key_rotation = AsyncMock(return_value=delayed_events(*chunks))
        try:
            with patch('asyncio.wait_for', side_effect=accelerated_wait):
                response = await p.chat_stream(messages=[{'role': 'user', 'content': 'test'}])
            self.assertEqual(response.finish_reason, 'stop')
            self.assertEqual(response.content, 'delayed answer')
        finally:
            await p._client.close()

    async def test_provider_busy_remains_an_error(self):
        p = provider()
        p._create_responses_with_status_retry = AsyncMock(return_value=delayed_events(
            SimpleNamespace(type='response.failed', response={
                'error': {'code': 'server_busy', 'message': 'Our servers are currently busy.'}}),
        ))
        try:
            response = await p.chat_stream(messages=[{'role': 'user', 'content': 'test'}])
            self.assertEqual(response.finish_reason, 'error')
            self.assertIn('server_busy', response.content)
        finally:
            await p._client.close()

    async def test_provider_wait_can_be_cancelled(self):
        p = provider()
        started = asyncio.Event()
        async def silence():
            started.set()
            await asyncio.Event().wait()
            yield None
        p._create_responses_with_status_retry = AsyncMock(return_value=silence())
        task = asyncio.create_task(p.chat_stream(messages=[{'role': 'user', 'content': 'test'}]))
        try:
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            await p._client.close()

    async def test_openai_sdk_has_no_deadline(self):
        p = provider()
        try:
            self.assertIsNone(p._client.timeout)
            self.assertTrue(all(v is None for v in p._client._client.timeout.as_dict().values()))
        finally:
            await p._client.close()

    async def test_anthropic_sdk_has_no_deadline(self):
        p = anthropic.AnthropicProvider(api_key='test-key')
        try:
            self.assertIsNone(p._client.timeout)
            self.assertTrue(all(v is None for v in p._client._client.timeout.as_dict().values()))
        finally:
            await p._client.close()

    async def test_azure_sdk_has_no_deadline(self):
        p = azure.AzureOpenAIProvider(api_key='test-key', api_base='https://test.openai.azure.com')
        try:
            self.assertIsNone(p._client.timeout)
            self.assertTrue(all(v is None for v in p._client._client.timeout.as_dict().values()))
        finally:
            await p._client.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
