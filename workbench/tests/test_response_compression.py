import asyncio,gzip
from server.response_compression import BufferedResponseCompression


def test_json_compressed_but_stream_first_chunk_is_forwarded_immediately():
    async def exercise(stream):
        output=[]
        async def send(message):output.append(message)
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/event-stream' if stream else b'application/json')]})
            body=b'event: jobs\ndata: '+b'x'*2000+b'\n\n' if stream else b'{"value":"'+b'x'*2000+b'"}'
            await send({'type':'http.response.body','body':body,'more_body':stream})
            if stream:assert output[1]['body']==body
            return body
        app_wrapped=BufferedResponseCompression(app)
        await app_wrapped({'type':'http','headers':[(b'accept-encoding',b'gzip')]},None,send)
        headers=dict(output[0]['headers'])
        if stream:assert b'content-encoding' not in headers
        else:assert headers[b'content-encoding']==b'gzip' and b'x'*2000 in gzip.decompress(output[1]['body'])
    asyncio.run(exercise(False));asyncio.run(exercise(True))
