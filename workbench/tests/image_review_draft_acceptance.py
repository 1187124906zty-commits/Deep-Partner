"""A prepared image review preserves its draft without initiating model work."""
import asyncio
import base64
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from starlette.requests import Request
from server import app as module


async def main():
    with tempfile.TemporaryDirectory(dir=module.DATA) as folder:
        record = {'id':'draft-fixture','source':{'modified':1.0},'processed_at':'2026-11-01T00:00:00Z'}
        request = Request({'type':'http','headers':[]})
        payload = module.ImageReview(path='fixture.png', image='data:image/png;base64,'+base64.b64encode(b'fixture').decode(), instruction='Keep draft', send=False)
        events = []
        class State:
            def get(self, owner, project):
                return {'native_id':'workspace-fixture'}
            def path(self, owner, project):
                return Path(folder)
        async def submit(*args):
            events.append('submit')
            return {'session_id':'session-fixture','url':'/chat/session-fixture'}
        with patch.object(module,'store',State()), patch('server.reviews.prepare_review',return_value=(record,'fixture prompt','image')), patch('server.annotations.save_annotation',return_value={'id':'question-fixture','locator':{}}), patch.object(module,'schedule_review_summary',side_effect=lambda *a:events.append('summary')), patch('server.reviews.submit_review',side_effect=submit):
            result = await module.image_review(request,'project',payload,{'id':'owner'})
            assert result['prepared'] is True and events == []
            payload.send = True
            result = await module.image_review(request,'project',payload,{'id':'owner'})
            assert result['sent'] is True and events == ['summary','submit']
    print(json.dumps({'passed':2,'checks':['prepared draft triggers no model summary or submission','explicit send retains summary and native submission']}))


asyncio.run(main())
