from pathlib import Path
import sys,json
import pytest
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
sys.path.insert(0,'D:/Development/research-workbench')
from server.storage import Store,atomic_json,Conflict
from server.native import actor
from server.literature_folders import install,read


@pytest.fixture
def setup(tmp_path):
    store=Store(tmp_path);project=store.create('alice','研究');pid=project['id'];root=store.path('alice',pid)
    (root/'literature/reading').mkdir(parents=True);(root/'literature/reading/source.pdf').write_bytes(b'original source')
    atomic_json(root/'.workbench/literature-index.json',{'reading/source.pdf':{'title':'Source'}})
    app=FastAPI();install(app,store);app.dependency_overrides[actor]=lambda:{'id':'alice'}
    @app.exception_handler(ValueError)
    async def invalid(request:Request,error):return JSONResponse({'detail':str(error)},409 if isinstance(error,Conflict) else 400)
    @app.exception_handler(KeyError)
    async def missing(request:Request,error):return JSONResponse({'detail':str(error)},404)
    return store,pid,root,TestClient(app)


def test_topic_folders_persist_and_are_independent_of_purpose_and_pdf_paths(setup):
    store,pid,root,client=setup;route='/research/api/projects/'+pid+'/literature/folders'
    legacy=client.put(route,json={'asset':'workspace/reading/source.pdf','category':'methods'});assert legacy.status_code==200
    value=client.patch(route,json={'expected_revision':legacy.json()['revision'],'folders':[{'id':'reaction','name':'反应传输'},{'id':'inverse','name':'贝叶斯反演'}],'memberships':{'workspace/reading/source.pdf':['reaction','inverse']}})
    assert value.status_code==200,value.text;assert value.json()['status']=='saved' and value.json()['verified']
    saved=client.get(route).json();assert saved['assignments']['workspace/reading/source.pdf']=='methods'
    assert saved['memberships']['workspace/reading/source.pdf']==['reaction','inverse']
    assert (root/'literature/reading/source.pdf').read_bytes()==b'original source'
    assert len(list((root/'literature').rglob('*.pdf')))==1


def test_invalid_batch_or_stale_revision_does_not_partially_change_library(setup):
    store,pid,root,client=setup;route='/research/api/projects/'+pid+'/literature/folders';before=client.get(route).json()
    result=client.patch(route,json={'expected_revision':0,'folders':[{'id':'good','name':'主题'}],'memberships':{'workspace/reading/missing.pdf':['good']}})
    assert result.status_code==400 and client.get(route).json()==before
    result=client.patch(route,json={'expected_revision':1,'folders':[{'id':'good','name':'主题'}]})
    assert result.status_code==409 and client.get(route).json()==before


def test_foreign_owner_cannot_read_or_assign_project_folders(setup):
    store,pid,root,client=setup;client.app.dependency_overrides[actor]=lambda:{'id':'bob'}
    assert client.get('/research/api/projects/'+pid+'/literature/folders').status_code==404
    assert client.patch('/research/api/projects/'+pid+'/literature/folders',json={'expected_revision':0,'folders':[{'id':'good','name':'主题'}]}).status_code==404
