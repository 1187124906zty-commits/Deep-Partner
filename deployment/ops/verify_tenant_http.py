"""Actual two-account isolation and quota update acceptance; creates only named test accounts."""
import asyncio
import json
from pathlib import Path
import secrets
import time
from urllib.parse import quote
import uuid

import httpx

ORIGIN='https://tutor.example.invalid'


async def login(client,account):
    response=await client.post('http://127.0.0.1:8001/api/auth/login',json=account)
    response.raise_for_status();token=response.cookies.get('dt_token')
    assert token
    return {'Authorization':'Bearer '+token,'Origin':ORIGIN}


async def main():
    checks={};created=[];projects=[];marker=uuid.uuid4().hex[:10]
    async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
        admin=await login(client,json.loads(Path('/migration/admin-login.json').read_text()))
        async def request(method,path,headers=admin,expected=200,**kwargs):
            response=await client.request(method,ORIGIN+path,headers=headers,**kwargs)
            assert response.status_code==expected,(method,path,response.status_code,response.text[:300])
            return response.json() if 'json' in response.headers.get('content-type','') else response.text
        users=[]
        try:
            for suffix in ('a','b'):
                account={'username':'storage_probe_'+marker+'_'+suffix,'password':secrets.token_urlsafe(24)}
                value=await request('POST','/api/auth/users',json=account,expected=201);created.append(account['username'])
                headers=await login(client,account);users.append({'id':value['user_id'],'headers':headers})
                project=await request('POST','/research/api/projects',headers=headers,json={'name':'Storage isolation probe '+marker})
                projects.append(project)
            a,b=users;pa,pb=projects
            checks['project_listing_isolated']=all(p['id']!=pa['id'] for p in (await request('GET','/research/api/projects',headers=b['headers']))['projects'])
            await request('GET','/research/api/projects/'+pa['id']+'/files',headers=b['headers'],expected=404)
            checks['cross_owner_project_read_rejected']=True
            label='tenant-probe-'+marker
            ka=await request('POST','/api/knowledge-bases?resource_library=true',headers=a['headers'],data={'name':label,'rag_provider':'llamaindex'})
            kb=await request('POST','/api/knowledge-bases?resource_library=true',headers=b['headers'],data={'name':label,'rag_provider':'llamaindex'})
            checks['same_kb_name_in_separate_accounts']=ka['id']==kb['id'] and ka['name']==kb['name']
            # Qualified IDs refer to the current account; identical labels never imply shared paths.
            da=await request('GET','/api/knowledge-bases/'+quote(ka['id'],safe='')+'?resource_library=true',headers=a['headers'])
            db=await request('GET','/api/knowledge-bases/'+quote(kb['id'],safe='')+'?resource_library=true',headers=b['headers'])
            checks['native_kb_paths_distinct']=da.get('path')!=db.get('path') and bool(da.get('path')) and bool(db.get('path'))
            route='/research/api/admin/storage/'+a['id']
            current=(await request('GET',route))['policy'];revision=current['revision']
            body={'expected_revision':revision,'quota_bytes':32,'cache_limit_bytes':1024,'archive_quota_bytes':0,'reason':'Isolated acceptance: force budget denial without touching user data'}
            await request('PUT',route,headers=a['headers'],json=body,expected=403);checks['user_cannot_increase_quota']=True
            await request('PUT',route,json=body)
            await request('PUT',route,json=body,expected=409);checks['stale_admin_quota_update_rejected']=True
            file_route='/research/api/projects/'+pa['id']+'/file'
            await request('PUT',file_route,headers=a['headers'],json={'path':'docs/quota-check.txt','content':'x'*200,'reason':'Expected quota rejection'},expected=507)
            checks['live_write_enforces_latest_quota']=True
            body.update(expected_revision=revision+1,quota_bytes=4*1024**2,reason='Isolated acceptance: restore test budget and permit the original write')
            await request('PUT',route,json=body)
            await request('PUT',file_route,headers=a['headers'],json={'path':'docs/quota-check.txt','content':'quota-update-ok','reason':'Quota update actual write'})
            assert await request('GET',file_route+'?path=docs/quota-check.txt',headers=a['headers'])=='quota-update-ok'
            checks['live_quota_increase_immediate']=True
            usage=await request('GET','/research/api/storage',headers=a['headers']);checks['usage_revision_matches_policy']=usage['policy_revision']==revision+2
            before=await request('GET','/research/api/download-worker/status',headers=a['headers']);checks['operator_worker_not_inherited']=not before['paired']
            pair=await request('POST','/research/api/download-worker/pair',headers=a['headers'])
            devices=(await request('GET','/research/api/download-worker/devices',headers=a['headers']))['devices'];device=devices[-1]['id']
            assert (await request('GET','/research/api/download-worker/devices',headers=b['headers']))['devices']==[]
            await request('POST','/research/api/download-worker/devices/'+device+'/revoke',headers=b['headers'],expected=404)
            await request('POST','/research/api/download-worker/devices/'+device+'/revoke',headers=a['headers'])
            await request('GET','/research/api/download-worker/next',headers={'x-workbench-worker':pair['token']},expected=403)
            checks['device_owner_and_revocation_enforced']=True
        finally:
            # Exact accounts created by this verifier only; no existing account is removed.
            for name in created:
                response=await client.delete('http://127.0.0.1:8001/api/auth/users/'+quote(name,safe=''),headers=admin)
                checks['cleanup_'+name.rsplit('_',1)[-1]]=response.status_code==200
        report={'verified':all(checks.values()),'checks':checks,'test_marker':marker,
            'created_user_ids':[u['id'] for u in users],
            'scope':'Actual separate accounts, empty native KBs, project files, quota revisions, device pairing and revoke; no production account or source KB modified.'}
        Path('/migration/tenant-http-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False),flush=True)
        assert report['verified'],checks


if __name__=='__main__':asyncio.run(main())
