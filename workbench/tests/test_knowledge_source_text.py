"""Keyword retrieval must reach actual converted text beyond native previews."""
import asyncio
import httpx
from fastapi import FastAPI
from server import knowledge_search
from server.native import actor
from server.storage import Store


def run_query(tmp_path,monkeypatch,asset,content,kb='private-kb'):
    store=Store(tmp_path/'store');project=store.create('owner','reference fixture')
    store.update('owner',project['id'],native_id='owned-workspace',config={'knowledge_bases':['private-kb']})
    calls=[]
    async def native_call(request,method,path,**kwargs):
        calls.append(path)
        return {'files':[{'name':asset,'type':'file'}]}
    async def native_text(request,path):
        calls.append(path)
        return content if '/files/' in path else content[:1000]
    monkeypatch.setattr(knowledge_search,'call',native_call)
    monkeypatch.setattr(knowledge_search,'text_call',native_text)
    app=FastAPI();app.dependency_overrides[actor]=lambda:{'id':'owner'}
    knowledge_search.install(app,store)
    async def execute():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
            return await client.post('/research/api/projects/'+project['id']+'/knowledge/search',
                json={'query':'word-of-mouth','mode':'fulltext-keyword','knowledge_base':kb})
    return asyncio.run(execute()),calls


def test_converted_book_keyword_beyond_preview_uses_owned_source(tmp_path,monkeypatch):
    content='words of introductory material, '*10000+'PDF page 172: word-of-mouth advertising about a product.'
    response,calls=run_query(tmp_path,monkeypatch,'book.md',content)
    assert response.status_code==200
    value=response.json()
    assert 'word-of-mouth' in value['items'][0]['excerpt']
    assert value['items'][0]['evidence']=='source-text'
    assert value['coverage'][0]['characters']==len(content)
    assert value['coverage'][0]['truncated'] is False
    assert calls[-1]=='/api/knowledge-bases/private-kb/files/book.md?dt_workspace=owned-workspace'


def test_other_formats_keep_native_extraction_and_disclose_preview(tmp_path,monkeypatch):
    response,calls=run_query(tmp_path,monkeypatch,'source.pdf','word-of-mouth in extracted text')
    assert response.status_code==200
    assert '/file-preview-text/source.pdf' in calls[-1]
    assert response.json()['coverage'][0]['basis']=='native text preview'


def test_unbound_library_is_rejected_before_any_source_read(tmp_path,monkeypatch):
    response,calls=run_query(tmp_path,monkeypatch,'book.md','word-of-mouth',kb='another-owners-kb')
    assert response.status_code==403 and calls==[]
