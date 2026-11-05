"""Read-only live product diagnosis, with isolated deployment-account login."""
from pathlib import Path
import argparse, json, subprocess, sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/browser-qa'))
PROJECT = '64c6b5e79b824bc4bf23637e8204446c'
WORKSPACE = 'ws_62eb9eb8014c4484913c5904d0b903dd'
ORIGIN = 'https://tutor.example.invalid'
OUT = ROOT / 'reports/agentic-product'


def server():
    code = r'''
import json, subprocess, urllib.request
names=['research-workbench','research-flow','research-flow-project','research-flow-recovery','dify-workbench-bridge']
rows=[]
for name in names:
    v=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
    health=v['State'].get('Health',{})
    rows.append({'name':name,'command':v['Config']['Cmd'],'healthcheck':v['Config'].get('Healthcheck'),
        'health':health.get('Status'),'last_health_output':health.get('Log',[{}])[-1].get('Output','')[-900:]})
for port in [47901,47905,47907,47909]:
    try:
        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/health',timeout=8) as response:
            rows.append({'port':port,'http':response.status,'body':json.load(response)})
    except Exception as e: rows.append({'port':port,'error':str(e)})
print(json.dumps(rows,ensure_ascii=False))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=55)
    if result.returncode: raise RuntimeError(result.stderr[-1500:])
    value=json.loads(result.stdout);(OUT/'server-before.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value,ensure_ascii=False))


def browser():
    from playwright.sync_api import sync_playwright
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=30))
    report={'pages':[], 'errors':[], 'failed_requests':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':960})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        page=ctx.new_page()
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.on('response',lambda r:report['failed_requests'].append({'path':urlsplit(r.url).path,'status':r.status}) if r.status>=400 else None)
        page.goto(ORIGIN+'/research/?project='+PROJECT+'&dt_workspace='+WORKSPACE+'&area=questions',wait_until='domcontentloaded')
        page.locator('.dp-native-shell').wait_for(timeout=60000)
        page.wait_for_timeout(1800)
        for area in ['研究对话','项目画布','程序与数据','稿件','图表','文献与知识库']:
            nav=page.locator('.dp-native-shell aside').first
            button=nav.get_by_role('button',name=area,exact=True)
            if button.count():
                button.click();page.wait_for_timeout(1200)
            else:
                report['pages'].append({'area':area,'missing_navigation':True});continue
            for width,height in [(1440,960),(768,1024),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(200)
                screen=OUT/f'before-{area}-{width}.png';page.screenshot(path=str(screen))
                metrics=page.evaluate('''()=>({overflow:document.documentElement.scrollWidth>innerWidth,
                    body:document.body.innerText.slice(0,16000),
                    clipped:[...document.querySelectorAll('button,input,textarea,select')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=0&&r.top<innerHeight&&(r.right>innerWidth+1||r.left< -1)}).slice(0,15).map(e=>({text:e.innerText||e.getAttribute('aria-label'),rect:JSON.stringify(e.getBoundingClientRect())}))})''')
                report['pages'].append({'area':area,'width':width,'screenshot':str(screen),**metrics})
            page.set_viewport_size({'width':1440,'height':960})
        report['navigation']=page.locator('.dp-native-shell aside').first.inner_text()
        browser.close()
    (OUT/'browser-before.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'pages':[{k:v for k,v in r.items() if k not in ('body','screenshot')} for r in report['pages']], 'errors':report['errors'],'failed_requests':report['failed_requests'],'navigation':report['navigation']},ensure_ascii=False))


def api():
    from verify_partner_workflow import client
    with client() as c:
        report={}
        for name,path in [('build','/research/build-info.json'),('jobs',f'/research/api/projects/{PROJECT}/jobs'),('writing',f'/research/api/projects/{PROJECT}/writing')]:
            r=c.get(path);r.raise_for_status();report[name]=r.json() if 'application/json' in r.headers.get('content-type','') else {'content_type':r.headers.get('content-type'),'status':r.status_code}
    (OUT/'api-before.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    jobs=report['jobs'].get('jobs',report['jobs'].get('items',[]))
    print(json.dumps({'build':report['build'],'jobs':[{k:v for k,v in j.items() if k in ('id','kind','status','stage','error','created','updated')} for j in jobs],'writing_settings':report['writing'].get('settings')},ensure_ascii=False))


def dify():
    code = r'''
from pathlib import Path
import sys,json,base64
sys.path.insert(0,'/srv/dify-research/ops')
import setup_app as api
api.BASE='https://tutor.example.invalid/dify/console/api'
credentials=json.loads(Path('/srv/dify-research/private/admin-login.json').read_text())
assert api.call('POST','/login',{'email':credentials['email'],'password':base64.b64encode(credentials['password'].encode()).decode(),'remember_me':True})['result']=='success'
apps=api.call('GET','/apps?page=1&limit=100')['data']
out=[]
for app in apps:
    row={'id':app['id'],'name':app['name'],'mode':app['mode']}
    if app['mode'] not in ('workflow','advanced-chat'):continue
    draft=api.call('GET','/apps/'+app['id']+'/workflows/draft')
    row['nodes']=[{'id':n['id'],'type':n.get('data',{}).get('type'),'title':n.get('data',{}).get('title'),'error_strategy':n.get('data',{}).get('error_strategy'),'retry':n.get('data',{}).get('retry_config')} for n in draft.get('graph',{}).get('nodes',[])]
    try:
        published=api.call('GET','/apps/'+app['id']+'/workflows/publish')
        row['draft_differs_from_published']=draft.get('graph')!=published.get('graph')
    except Exception as e:row['published_error']=str(e)[:300]
    try:
        logs=api.call('GET','/apps/'+app['id']+'/workflow-runs?page=1&limit=12')
        row['runs']=[{k:v for k,v in r.items() if k in ('id','status','error','elapsed_time','total_steps','created_at','finished_at')} for r in logs.get('data',[])]
    except Exception as e:row['logs_error']=str(e)[:300]
    out.append(row)
print(json.dumps(out,ensure_ascii=False))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError(result.stderr[-1600:])
    value=json.loads(result.stdout);(OUT/'dify-before.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['server','browser','api','dify']);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    globals()[args.mode]()
