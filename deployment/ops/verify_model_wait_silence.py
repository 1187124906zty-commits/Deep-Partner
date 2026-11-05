"""Verify deployed SDK, provider adapter and agent against a silent SSE server."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/app')

from deeptutor.agents.loop.agent_loop import _bounded_stream_chunks
from deeptutor.runtime.agentic.client import _ProviderOpenAIStream
from deeptutor.services.llm.provider_core.openai_compat_provider import OpenAICompatProvider


async def main(silence_seconds):
    requests = []
    async def serve(reader, writer):
        header = await reader.readuntil(b'\r\n\r\n')
        headers = header.decode().split('\r\n')
        size = next((int(line.split(':', 1)[1]) for line in headers if line.lower().startswith('content-length:')), 0)
        if size:
            await reader.readexactly(size)
        requests.append(headers[0])
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n')
        writer.write(b'event: response.created\ndata: {"type":"response.created","response":{"id":"wait-test","status":"in_progress"}}\n\n')
        await writer.drain()
        await asyncio.sleep(silence_seconds)
        events = [
            {'type': 'response.output_text.delta', 'delta': 'WAIT_POLICY_OK', 'output_index': 0, 'content_index': 0},
            {'type': 'response.completed', 'response': {'id': 'wait-test', 'status': 'completed', 'output': [],
                'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}},
        ]
        for event in events:
            writer.write(('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(serve, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    provider = OpenAICompatProvider(api_key='test-key', api_base=f'http://127.0.0.1:{port}/v1',
        default_model='test-model', wire_api='responses', configure_env=False)
    stream = _ProviderOpenAIStream(provider=provider, messages=[{'role': 'user', 'content': 'wait test'}],
        tools=None, model='test-model', max_tokens=128, temperature=0.7,
        reasoning_effort=None, tool_choice=None, extra_kwargs={})
    start = time.monotonic()
    print(json.dumps({'test': 'deployed_real_sse_silence', 'silent_seconds': silence_seconds,
                      'external_model_calls': 0, 'sdk_timeout': provider._client.timeout}), flush=True)
    content = []
    try:
        async with server:
            async for chunk in _bounded_stream_chunks(stream):
                for choice in chunk.choices or []:
                    if choice.delta.content:
                        content.append(choice.delta.content)
        report = {'passed': ''.join(content) == 'WAIT_POLICY_OK' and len(requests) == 1,
                  'silence_seconds': silence_seconds, 'elapsed_seconds': round(time.monotonic()-start, 3),
                  'content': ''.join(content), 'http_requests': len(requests),
                  'external_model_calls': 0, 'sdk_timeout': provider._client.timeout}
        Path('/migration/model-wait-policy/real-silence.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
        assert report['passed'], report
    finally:
        await stream.close()
        await provider._client.close()
        server.close()
        await server.wait_closed()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--silence-seconds', type=float, default=100)
    asyncio.run(main(parser.parse_args().silence_seconds))
