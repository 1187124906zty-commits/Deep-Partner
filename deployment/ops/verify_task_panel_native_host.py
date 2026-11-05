"""Check the bundled Windows HTTP host without controlling the locked desktop."""
from pathlib import Path
import json,os,socket,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from verify_task_panel import exercise
from task_panel_fixture import update,attach_output,FIXTURE

def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def main():
    fixture=json.loads(FIXTURE.read_text(encoding='utf8'));attach_output();update('reset')
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    profile=NATIVE/'verification/task-panel-host';profile.mkdir(exist_ok=True)
    (profile/'config.json').write_text(json.dumps({'server_url':'https://tutor.example.invalid','workspace':str(profile/'workspace'),'bridge_port':free_port(),'browser_port':free_port(),'ssh_host':'task-panel-qa.invalid','cluster_host':'','desktop_control':False}),encoding='utf8')
    child=subprocess.Popen([str(NATIVE/'dist/task-cards/Deep partner.exe'),'--headless-ui'],cwd=NATIVE/'dist',env=dict(os.environ,DEEP_PARTNER_HOME=str(profile)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',creationflags=0x08000000)
    report={'checks':{},'errors':[],'mode':'native-bundled-host','desktop_window_verified':False,'desktop_window_limitation':'Windows is locked; native window input and screenshot checks are pending unlock.','model_calls':0,'evidence_scope':fixture['evidence_scope']}
    try:
        line=child.stdout.readline()
        if not line:raise RuntimeError('Native test host did not start: '+child.stderr.read()[:500])
        bootstrap=json.loads(line)['url'];origin='/'.join(bootstrap.split('/')[:3]);headers={'Origin':origin}
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            ctx=browser.new_context(viewport={'width':1440,'height':980},extra_http_headers=headers)
            assert ctx.request.get(bootstrap).ok;assert ctx.request.post(origin+'/api/auth/login',data=account,headers=headers).ok
            report['build']=ctx.request.get(origin+'/build-info.json').json();report['frontend_job_id']=report['build']['slurm_job_id']
            page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
            try:exercise(ctx,page,origin,fixture,report,'native-host')
            except Exception:
                report['body']=page.locator('body').inner_text();page.screenshot(path=str(ROOT/'reports/screenshots/task-panel-native-host-failure.png'));raise
            report['checks']['no_script_errors']=not report['errors'];report['passed']=all(report['checks'].values());browser.close()
    except Exception as e:report['passed']=False;report['failure']=str(e);raise
    finally:
        child.terminate();child.wait(timeout=10);update('close')
        (ROOT/'reports/task-panel-native-host.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
    assert report['passed']

if __name__=='__main__':main()
