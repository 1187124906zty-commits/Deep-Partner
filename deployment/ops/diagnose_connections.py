"""Compare public and native HTTP/WS; probe new-session UI without model calls."""
from pathlib import Path
import json,os,socket,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));return listener.getsockname()[1]

def main():
    account=json.loads(subprocess.run(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    profile=NATIVE/'verification/connection-diagnosis';profile.mkdir(exist_ok=True)
    (profile/'config.json').write_text(json.dumps({'server_url':'https://tutor.example.invalid','workspace':str(profile/'workspace'),'bridge_port':free_port(),'browser_port':free_port()}))
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe'),'--headless-ui'],env=dict(os.environ,DEEP_PARTNER_HOME=str(profile)),stdout=subprocess.PIPE,text=True,encoding='utf8')
    try:
        bootstrap=json.loads(child.stdout.readline())['url']
        local='/'.join(bootstrap.split('/')[:3]);report={'surfaces':{},'model_calls':0}
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            for mode,origin in [('public','https://tutor.example.invalid'),('native',local)]:
                ctx=browser.new_context(viewport={'width':1440,'height':950},extra_http_headers={'Origin':origin})
                if mode=='native':ctx.request.get(bootstrap)
                login=ctx.request.post(origin+'/api/auth/login',data=account,headers={'Origin':origin});print(json.dumps({'surface':mode,'login_status':login.status,'login_ok':login.ok}),flush=True);assert login.ok
                project_response=ctx.request.get(origin+'/research/api/projects');print(json.dumps({'surface':mode,'projects_status':project_response.status,'error':project_response.text()[:400] if not project_response.ok else None}),flush=True);project_response.raise_for_status() if hasattr(project_response,'raise_for_status') else None
                projects=project_response.json()['projects'];project=next(x for x in projects if x['name']=='水分扩散')
                page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+('/research/' if mode=='public' else '/')+'?project='+project['id']+'&dt_workspace='+project['native_id'],wait_until='domcontentloaded')
                page.locator('.dp-composer-policy').wait_for(timeout=30000)
                probe=page.evaluate("""async workspace=>{
                  const url=new URL('/ws',location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:';url.searchParams.set('dt_workspace',workspace);
                  return await new Promise(resolve=>{const w=new WebSocket(url);let result={opened:false,closed:false,code:null,messages:[]};w.onopen=()=>{result.opened=true;setTimeout(()=>{result.state=w.readyState;w.close();resolve(result)},2000)};w.onmessage=e=>result.messages.push(e.data.slice(0,300));w.onclose=e=>{result.closed=true;result.code=e.code;if(!result.opened)resolve(result)};w.onerror=()=>{};setTimeout(()=>{result.state=w.readyState;w.close();resolve(result)},7000)})
                }""",project['native_id'])
                page.get_by_role('button',name='新会话',exact=True).first.click();page.wait_for_timeout(500)
                result={'websocket':probe,'new_session_composer_visible':page.locator('.dp-composer-policy textarea').is_visible(),'url_after_new':page.url,'errors':errors,
                        'connection_error_visible':page.get_by_text('无法连接到服务器，请检查网络后重试。',exact=False).count()>0}
                if mode=='native':result['desktop_status']=ctx.request.get(origin+'/desktop/status',headers={'Origin':origin}).json()
                page.screenshot(path=str(ROOT/f'reports/screenshots/connection-initial-{mode}.png'))
                report['surfaces'][mode]=result;print(json.dumps({'surface':mode,**result},ensure_ascii=False),flush=True);ctx.close()
            browser.close()
        (ROOT/'reports/connection-initial-repro.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
        assert all(v['websocket']['opened'] and v['websocket'].get('state')==1 for v in report['surfaces'].values()),'An authenticated websocket closes before it can accept a turn'
    finally:child.terminate();child.wait(timeout=10)

if __name__=='__main__':main()
