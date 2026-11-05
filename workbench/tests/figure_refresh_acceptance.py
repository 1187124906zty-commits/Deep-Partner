"""A saved linked figure refreshes exports with the current request and owner."""
import asyncio
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from starlette.requests import Request
from server import app as module


async def main():
    with tempfile.TemporaryDirectory(dir=module.DATA) as folder:
        root=Path(folder)
        for name in ['manuscript/exports/清稿.docx','manuscript/exports/清稿.pdf','slides/exports/研究汇报.pptx']:
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'fixture')
        user={'id':'figure-refresh-owner'}
        request=Request({'type':'http','headers':[]})
        events=[]
        class State:
            def path(self,owner,pid):
                assert owner==user['id'] and pid=='fixture'
                return root
            def get(self,owner,pid):
                assert owner==user['id'] and pid=='fixture'
                return {'config':{'slides_confirmation':{'id':'confirmed'}}}
        async def manuscript(given_request,pid,payload,given_user):
            assert given_request is request and given_user is user and pid=='fixture'
            events.append(payload.format);return {'job_id':'manuscript-'+payload.format}
        async def slides(pid,given_user):
            assert given_user is user and pid=='fixture'
            events.append('slides');return {'job_id':'slides'}
        payload=module.FigureEdit(path='figure.png',changes={},revision=1)
        with patch.object(module,'store',State()),patch('server.figures.save',return_value={'updated_references':['manuscript/main.json']}),patch.object(module,'manuscript_export',side_effect=manuscript),patch.object(module,'slides_export',side_effect=slides):
            result=await module.figure_save(request,'fixture',payload,user)
            assert events==['docx','pdf','slides'] and len(result['refreshing'])==3
            events.clear();payload.autosave=True
            result=await module.figure_save(request,'fixture',payload,user)
            assert not events and not result['refreshing']
    print(json.dumps({'passed':2,'checks':['linked exports preserve original request and account','autosave avoids repeated export jobs']}))


asyncio.run(main())
