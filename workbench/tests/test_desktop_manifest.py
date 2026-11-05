import asyncio
import json

import httpx
from fastapi import FastAPI,HTTPException,Request

from server import desktop_manifest,standards


def setup_manifest(tmp_path):
    application=FastAPI();state={'version':'capability-one','fail':False,'authenticated':True}
    async def actor(request:Request):
        if not state['authenticated']:raise HTTPException(401,'Login required')
        return {'id':'owner-a'}
    async def native(request,method,path):
        assert method=='GET' and path=='/api/capabilities/registered'
        if state['fail']:raise RuntimeError('secret-upstream-token')
        return {'capabilities':[{'id':state['version'],'available':True,'manifest':{'name':state['version']},'config_schema':{}}]}
    desktop_manifest.install(application,actor,native,tmp_path)
    def get(query='',headers=None):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application),base_url='http://test') as client:
                return await client.get('/research/api/desktop/manifest'+query,headers=headers)
        return asyncio.run(send())
    return get,state


def test_manifest_discovery_compatibility_and_etag(tmp_path,monkeypatch):
    get,state=setup_manifest(tmp_path)
    first=get('?frontend_version=0.4.0&protocol_version=2.0')
    assert first.status_code==200
    body=first.json()
    assert body['compatibility']['compatible'] is True
    assert body['frontend']['minimum']=='0.4.0' and body['frontend']['current']=='0.4.2'
    assert body['protocol']=={'minimum':'2.0','maximum':'2.0','current':'2.0'}
    assert body['capabilities']['items'][0]['id']=='capability-one'
    assert body['standards']['version']==standards.VERSION
    assert body['updates']['remote_code_execution'] is False
    assert all(row['declared'] and row['availability']=='unknown' and row['publication']['version'] is None for row in body['workflows'])
    etag=first.headers['etag']
    cached=get('?frontend_version=0.4.0&protocol_version=2.0',{'If-None-Match':etag})
    assert cached.status_code==304 and cached.content==b''
    assert 'private' in cached.headers['cache-control'] and 'Authorization' in cached.headers['vary']
    state['version']='capability-two'
    assert get('?frontend_version=0.4.0&protocol_version=2.0',{'If-None-Match':etag}).headers['etag']!=etag
    monkeypatch.setattr(standards,'VERSION','updated-standards')
    assert get().json()['standards']['version']=='updated-standards'
    incompatible=get('?frontend_version=0.3.9&protocol_version=3.0').json()['compatibility']
    assert incompatible['compatible'] is False and incompatible['upgrade_required'] is True
    assert set(incompatible['reasons'])=={'frontend_upgrade_required','protocol_unsupported'}
    assert get().json()['compatibility']['compatible'] is None


def test_manifest_requires_auth_even_for_conditional_request(tmp_path):
    get,state=setup_manifest(tmp_path);first=get();state['authenticated']=False
    assert get(headers={'If-None-Match':first.headers['etag']}).status_code==401


def test_manifest_publication_needs_matching_file_evidence(tmp_path):
    get,state=setup_manifest(tmp_path)
    row=desktop_manifest.WORKFLOWS[0]
    (tmp_path/'desktop-workflows.json').write_text(json.dumps({'workflows':[
        {'app_id':row['app_id'],'published_version':'dify-real-release-identity',
         'source':'deployment-receipt','observed_at':'2026-11-02T12:00:00Z','api_key':'never-return-this'},
        {'app_id':'wrong-app','published_version':'fake','source':'fake','observed_at':'now'}]}),encoding='utf8')
    response=get();body=response.json()
    assert body['workflows'][0]['publication']['version']=='dify-real-release-identity'
    assert body['workflows'][0]['publication']['status']=='published'
    assert body['workflows'][0]['availability']=='unknown'
    assert body['workflows'][1]['publication']['version'] is None
    assert 'never-return-this' not in response.text and 'api_key' not in response.text
    state['fail']=True
    degraded=get()
    assert degraded.status_code==200 and degraded.json()['capabilities']['status']=='unavailable'
    assert 'secret-upstream-token' not in degraded.text
