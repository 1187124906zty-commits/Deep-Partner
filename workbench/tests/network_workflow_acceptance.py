"""API contract checks for selected downloads, profile data and sourced metrics."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio,hashlib,json,uuid
import fitz,httpx
from server.storage import Store,atomic_json
from server.native import actor
from server.download_bridge import install,CLUSTER_ROOT
from server.author_profile import prepare_preview,validate
from server.journal_metrics import clarivate
from server.workspace_files import usage

async def main():
    checks=[]
    with TemporaryDirectory() as folder:
        root=Path(folder);store=Store(root/'state');p=store.create('alice','API contract');pid=p['id'];other=store.create('bob','Other owner')
        def api_path(owner):return root/owner/'api.json'
        worker_token='fixture-worker';atomic_json(store.root/'download-workers.json',{hashlib.sha256(worker_token.encode()).hexdigest():{'owner':'alice'}})
        app=FastAPI();install(app,store,api_path)
        @app.exception_handler(ValueError)
        async def invalid(request,e):return JSONResponse({'detail':str(e)},400)
        @app.exception_handler(KeyError)
        async def missing(request,e):return JSONResponse({'detail':str(e)},404)
        app.dependency_overrides[actor]=lambda:{'id':'alice'}
        entry={'title':'Verified research PDF','doi':'10.1234/verified','year':2025}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            result=await client.post('/research/api/projects/'+pid+'/literature/download-batch',json={'entries':[entry,entry],'folder':'methods'});result.raise_for_status();result=result.json();assert result['queued']==1 and len(result['skipped'])==1;jid=result['items'][0]['id'];checks.append('selected entries and in-batch duplicate skip')
            duplicate=await client.post('/research/api/projects/'+pid+'/literature/download-batch',json={'entries':[entry]});assert duplicate.json()['queued']==0;checks.append('pending duplicate skipped')
            denied=await client.get('/research/api/projects/'+other['id']+'/literature/downloads');assert denied.status_code==404;checks.append('owner isolation')
            headers={'x-workbench-worker':worker_token};claimed=(await client.get('/research/api/download-worker/next',headers=headers)).json()['job'];assert claimed['id']==jid and claimed['folder']=='methods';checks.append('paired worker atomic claim')
            with fitz.open() as pdf:
                page=pdf.new_page();page.insert_text((50,50),entry['title'],fontsize=20);page.insert_text((50,90),entry['doi']);data=pdf.tobytes()
            prefix=CLUSTER_ROOT+'/owners/'+uuid.uuid5(uuid.NAMESPACE_URL,'alice').hex+'/'+pid+'/papers/'
            receipt={'connection':'research-cluster-xh5','cluster_path':prefix+hashlib.sha256(data).hexdigest()+'.pdf','cluster_verified':True,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            endpoint='/research/api/download-worker/'+jid+'/result'
            missing=await client.post(endpoint,headers=headers,files={'file':('paper.pdf',data)},data={'transfer':'{}'});assert missing.status_code==400
            bad=await client.post(endpoint,headers=headers,files={'file':('paper.pdf',data)},data={'transfer':json.dumps({**receipt,'sha256':'0'*64})});assert bad.status_code==400
            traversal=await client.post(endpoint,headers=headers,files={'file':('paper.pdf',data)},data={'transfer':json.dumps({**receipt,'cluster_path':prefix+'../other/'+hashlib.sha256(data).hexdigest()+'.pdf'})});assert traversal.status_code==400;checks.append('cluster receipt, transfer hash and path required')
            temporary=(await client.post('/research/api/download-worker/'+jid+'/delivery-ticket',headers=headers)).json()
            rejected=await client.post(endpoint,headers={'x-workbench-delivery':'wrong-ticket'},files={'file':('paper.pdf',data)},data={'transfer':json.dumps(receipt)});assert rejected.status_code==403
            scoped={'x-workbench-delivery':temporary['token']};denied_ticket=await client.post('/research/api/download-worker/'+jid+'/delivery-ticket',headers=scoped);assert denied_ticket.status_code==403;checks.append('temporary delivery credential cannot claim or mint tasks')
            saved=await client.post(endpoint,headers=scoped,files={'file':('paper.pdf',data)},data={'transfer':json.dumps(receipt)});saved.raise_for_status();assert saved.json()['saved'];assert (store.path('alice',pid)/'literature'/saved.json()['receipt']['name']).read_bytes()==data
            repeated=await client.post(endpoint,headers=headers,files={'file':('paper.pdf',data)},data={'transfer':json.dumps(receipt)});assert repeated.json()['already_completed'];checks.append('verified PDF delivery and idempotent completion')
            again=(await client.post('/research/api/projects/'+pid+'/literature/download-batch',json={'entries':[entry]})).json();assert again['queued']==0 and len(again['skipped'])==1;checks.append('existing full text skipped')
            second=(await client.post('/research/api/projects/'+pid+'/literature/download-batch',json={'entries':[{'title':'Other PDF','doi':'10.1234/other'}]})).json()['items'][0]['id'];await client.get('/research/api/download-worker/next',headers=headers)
            await client.post('/research/api/download-worker/'+second+'/result',headers=headers,data={'error':'Fixture network failure'})
            assert (await client.post('/research/api/projects/'+pid+'/literature/downloads/'+second+'/retry')).json()['queued'];checks.append('failed transfer retry')
        cache=store.path('alice',pid)/'.workbench/neoread/cache';cache.mkdir(parents=True);(cache/'page.bin').write_bytes(b'x'*100)
        totals=usage(store,'alice');assert totals['cache_used']==100 and not totals['over_quota'];checks.append('reproducible cache separated from user quota')
    doc={'title':'A study','content':{'type':'doc','content':[{'type':'heading','content':[{'type':'text','text':'Abstract'}]}]}}
    profile=validate({'name':'Author','affiliation':'University','email':'author@example.org'})
    prepared=prepare_preview(doc,profile,'en');assert len(doc['content']['content'])==1 and prepared['preview_metadata']['date_kind']=='preview';assert 'author@example.org' in json.dumps(prepared);checks.append('preview copy contains supplied author details and date')
    def source(request):
        assert request.headers['X-ApiKey']=='jcr-fixture'
        if request.url.path.endswith('/journals'):return httpx.Response(200,json={'hits':[{'id':'WRONG'},{'id':'MATCH'}]})
        if request.url.path.endswith('/WRONG'):return httpx.Response(200,json={'id':'WRONG','issn':'1111-1111'})
        if request.url.path.endswith('/MATCH'):return httpx.Response(200,json={'id':'MATCH','issn':'1234-5678','journalCitationReports':{'value':[{'2024':'source'},{'2025':'source'}]}})
        assert request.url.path.endswith('/reports/year/2025')
        return httpx.Response(200,json={'year':2025,'metrics':{'impactMetrics':{'jif':'4.2'}},'ranks':{'jif':[{'category':'Mechanics','quartile':'Q1','edition':'SCIE','rank':'12/170'},{'category':'Materials','quartile':'Q2','edition':'SCIE'}]}})
    original=httpx.AsyncClient
    def client(*args,**kwargs):return original(*args,**kwargs,transport=httpx.MockTransport(source))
    with patch('httpx.AsyncClient',client):
        value=await clarivate({'name':'Test Journal','issn':['1234-5678']},{'jcr_api_key':'jcr-fixture'});assert value['status']=='ready' and value['year']==2025 and len(value['categories'])==2;checks.append('JCR exact ISSN, report year and all category quartiles')
    assert (await clarivate({'name':'Test Journal'},{}))['status']=='not_configured';checks.append('missing JCR authorization stays explicit')
    print(json.dumps({'passed':True,'checks':checks,'count':len(checks),'external_calls':0},ensure_ascii=False))

asyncio.run(main())
