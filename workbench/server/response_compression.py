"""Compress complete text responses; forward streams immediately and unchanged."""
import gzip
from starlette.datastructures import Headers,MutableHeaders


class BufferedResponseCompression:
    def __init__(self,app,minimum_size=1000):
        self.app=app;self.minimum_size=minimum_size

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or 'gzip' not in Headers(scope=scope).get('accept-encoding',''):
            await self.app(scope,receive,send);return
        start=None;started=False
        async def compressed(message):
            nonlocal start,started
            if message['type']=='http.response.start':start=message;return
            if message['type']!='http.response.body' or started:
                if start is not None and not started:await send(start);started=True
                await send(message);return
            headers=MutableHeaders(raw=start['headers'])
            content_type=headers.get('content-type','').split(';')[0]
            body=message.get('body',b'')
            if not message.get('more_body',False) and start['status']==200 and len(body)>=self.minimum_size and 'content-encoding' not in headers and (content_type.startswith('text/') or content_type=='application/json') and content_type!='text/event-stream':
                packed=gzip.compress(body,compresslevel=3)
                if len(packed)<len(body):
                    message={**message,'body':packed};headers['content-encoding']='gzip';headers['content-length']=str(len(packed));headers.add_vary_header('Accept-Encoding')
            await send(start);started=True;await send(message)
        await self.app(scope,receive,compressed)
