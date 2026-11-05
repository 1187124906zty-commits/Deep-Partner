"""Bounded real-service load, ownership, event and source-contract acceptance."""
import concurrent.futures
import http.cookiejar
import json
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path('/srv/dify-research')
ORIGIN='https://tutor.example.invalid'
jar=http.cookiejar.CookieJar()
login=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar))
cookie=''


def call(method,path,body=None,expected=200,as_text=False):
    request=urllib.request.Request(ORIGIN+path,method=method,
        headers={'Content-Type':'application/json','Cookie':cookie,'Origin':ORIGIN},
        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None)
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:response=client.open(request,timeout=150)
    except urllib.error.HTTPError as response:
        if response.code!=expected:raise RuntimeError(f'{method} {path}: HTTP {response.code}: '+response.read().decode()[:300]) from None
        return {'http_status':response.code}
    if response.status!=expected:raise AssertionError(f'Expected {expected}, got {response.status}')
    raw=response.read()
    return json.loads(raw) if not as_text and 'json' in response.headers.get('content-type','') else raw.decode()


def main():
    global cookie
    for attempt in range(30):
        try:
            if urllib.request.urlopen('http://127.0.0.1:47910/health',timeout=2).status==200:break
        except OSError:
            if attempt==29:raise
            time.sleep(1)
    account=json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    request=urllib.request.Request('http://127.0.0.1:8008/api/auth/login',method='POST',
        headers={'Content-Type':'application/json'},data=json.dumps(account).encode())
    login.open(request,timeout=20).close()
    cookie='; '.join(c.name+'='+c.value for c in jar)
    project=next(p for p in call('GET','/research/api/projects')['projects'] if p['name']=='Dify 部署与交付验证')
    pid,ws=project['id'],project['native_id']
    base={'project_id':pid,'workspace_id':ws,'limit':3,'query':'chloride diffusion sulfate'}
    checks={}
    for name,body,status in [
        ('unknown_project',{**base,'project_id':'0'*32},409),
        ('wrong_workspace',{**base,'workspace_id':'unrelated'},409),
        ('unbound_knowledge',{**base,'knowledge_base':'account:kb:not-visible'},403),
        ('invalid_source',{**base,'sources':['invented']},422),
        ('duplicate_source',{**base,'sources':['web','web']},422),
    ]:
        checks[name]=call('POST','/research/dify/api/evidence',body,expected=status)['http_status']==status
    checks['invalid_kb_binding']=call('PATCH','/research/api/projects/'+pid,
        {'knowledge_bases':['account:kb:not-visible']},expected=403)['http_status']==403
    cases=[]
    for query in ['chloride diffusion sulfate','Fourier neural operator parametric PDE','cement sulfate chloride transport',
            'reactive ionic transport concrete','physics informed neural operator','operator learning porous media',
            'multifidelity neural operator','competitive antagonism chloride sulfate']:
        cases.append({'query':query,'sources':['knowledge','web','papers']})
    for query in ['氯离子 扩散 结合','sulfate attack concrete','Friedel salt sulfate','Nernst Planck chloride',
            '水泥 硫酸盐 氯盐','coupled transport damage']:
        cases.append({'query':query,'sources':['knowledge']})
    for query in ['Anthropic building effective agents','Dify trigger schedule webhook','LangChain open deep research']:
        cases.append({'query':query,'sources':['web']})
    for query,source in [('Fourier neural operator','crossref'),('physics informed neural operator','scholar_mcp'),
            ('chloride sulfate concrete','auto')]:
        cases.append({'query':query,'sources':['papers'],'paper_source':source})

    def search(case):
        started=time.monotonic()
        result=call('POST','/research/dify/api/evidence',{**base,**case})
        assert result.get('run_id') and result['status'] in {'ready','partial','empty','unavailable'},result
        assert {b['branch'] for b in result['coverage']}=={'knowledge','web','papers'}
        for branch in result['coverage']:
            assert branch['status'] in {'ok','empty','failed','timed_out','not_configured','not_requested','partial'},branch
            assert branch['count']>=0
            if branch['status'] in {'failed','timed_out','partial','not_configured'}:
                assert branch['branch'] in result['missing_sources']
        for item in result['items']:
            assert item['query']==case['query'] and item['source'] and item['evidence_kind']
            assert item.get('url') or item.get('document_id') or item.get('title')
            assert item.get('provenance')
        restored=call('GET','/research/dify/api/evidence/'+result['run_id'])
        assert restored==result
        report={**case,'status':result['status'],'run_id':result['run_id'],
            'workflow_run_id':result.get('workflow_run_id'),'items':len(result['items']),
            'coverage':result['coverage'],'elapsed_seconds':round(time.monotonic()-started,3)}
        print(json.dumps({'case_finished':case['query'],'status':report['status'],'seconds':report['elapsed_seconds']},ensure_ascii=False),flush=True)
        return report

    started=time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(search,cases))
    elapsed=[r['elapsed_seconds'] for r in results]
    report={'checked_at':time.time(),'project_id':pid,'workspace_id':ws,'concurrency':3,
        'cases':results,'checks':checks,'total_seconds':round(time.time()-started,3),
        'latency':{'median':round(statistics.median(elapsed),3),'p95':round(sorted(elapsed)[int(len(elapsed)*.95)-1],3),'max':max(elapsed)},
        'status_counts':{s:sum(r['status']==s for r in results) for s in ('ready','partial','empty','unavailable')},
        'scope':'真实发布流程的连接、状态、证据来源和负载验收；不将查询非空当作语义相关性或科学结论正确率。'}
    (ROOT/'reports/intensive-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
