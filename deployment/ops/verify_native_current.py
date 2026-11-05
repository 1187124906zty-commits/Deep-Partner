"""Check the actual packaged Tauri/WebView2 app through its debugging transport."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--keep-open',action='store_true');args=parser.parse_args()
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    env=dict(os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9241')
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe')],env=env,cwd=NATIVE/'dist')
    report={'app':'packaged Tauri/WebView2','errors':[],'checks':{},'frontend_job_id':build['job_id'],'new_model_turn':False,'import_applied':False}
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen('http://127.0.0.1:9241/json/version',timeout=1) as response:json.load(response)
                break
            except OSError:time.sleep(.3)
        else:raise RuntimeError('WebView2 debugging transport unavailable')
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp('http://127.0.0.1:9241')
            ctx=browser.contexts[0];page=ctx.pages[0]
            page.wait_for_url('http://127.0.0.1:*/**',timeout=30000)
            origin=page.url.split('/desktop/bootstrap')[0] if '/desktop/bootstrap' in page.url else '/'.join(page.url.split('/')[:3])
            assert ctx.request.post(origin+'/api/auth/login',data=account,headers={'Origin':origin}).ok
            local_build=ctx.request.get(origin+'/build-info.json',headers={'Origin':origin}).json()
            assert local_build['slurm_job_id']==build['job_id'],local_build
            status=ctx.request.get(origin+'/desktop/status',headers={'Origin':origin}).json();assert status['version']=='0.4.2'
            projects=ctx.request.get(origin+'/research/api/projects',headers={'Origin':origin}).json()['projects']
            project=next(x for x in projects if x['id']=='c0b9c547b07c401aa7fc7454b0104345')
            parent=json.loads((ROOT/'reports/unified-stream-live.json').read_text())['session_id']
            route=origin+'/?project='+project['id']+'&dt_workspace='+project['native_id']+'&session='+parent
            page.on('pageerror',lambda e:report['errors'].append(str(e)))
            page.goto(route,wait_until='domcontentloaded')
            page.locator('.dp-chat-pane').get_by_text('DEEP_PARTNER_STREAM_OK',exact=False).first.wait_for(timeout=30000)
            page.get_by_role('button',name='导入项目',exact=True).click()
            panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for()
            card=panel.get_by_role('region',name='导入项目卡片');card.wait_for()
            card.get_by_label('导入来源位置',exact=True).fill('D:\\博士工作\\博士项目\\水分扩散\\2026-11-2\\网站项目')
            assert page.evaluate('new URL(location.href).searchParams.get("session")')==parent
            page.wait_for_timeout(300)
            page.screenshot(path=str(ROOT/'reports/screenshots/native-current-dito-import.png'))
            report['checks']['native_dito_import_keeps_main_session']=True
            panel.get_by_role('button',name='关闭查看器',exact=True).click()
            page.get_by_role('button',name='设置',exact=True).click()
            settings=page.locator('.dp-tutor-settings');settings.locator('[data-settings-page="general"]').wait_for()
            settings.locator('a[href*="settings_section=appearance"]').first.click()
            settings.locator('[data-settings-page="appearance"]').wait_for()
            page.screenshot(path=str(ROOT/'reports/screenshots/native-current-settings.png'))
            settings.get_by_role('button',name='返回应用',exact=True).click()
            report['checks']['native_original_settings_and_return']=page.evaluate('new URL(location.href).searchParams.get("session")')==parent
            module=ctx.request.get(origin+'/research/reader/'+project['id']+'/assets/pdf-B0s6D7Gr.js',headers={'Origin':origin})
            report['reader_module']={'status':module.status,'mime':module.headers.get('content-type',''),'bytes':len(module.body())}
            report['checks']['reader_module_javascript']=module.status==200 and 'javascript' in module.headers.get('content-type','')
            prefs=ctx.request.get(origin+'/desktop/preferences',headers={'Origin':origin}).json()
            report['preferences']=prefs
            report['checks']['native_version_and_embedded_build']=True
            report['passed']=not report['errors'] and all(report['checks'].values())
            (ROOT/'reports/native-current-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(report,ensure_ascii=False));assert report['passed']
            if args.keep_open:
                current=next((x for x in projects if x['name']=='水分扩散'),project)
                page.goto(origin+'/?project='+current['id']+'&dt_workspace='+current['native_id'],wait_until='domcontentloaded')
                page.get_by_role('button',name='导入项目',exact=True).click()
                card=page.get_by_role('region',name='导入项目卡片');card.wait_for()
                card.get_by_label('导入来源位置',exact=True).fill('D:\\博士工作\\博士项目\\水分扩散\\2026-11-2\\网站项目')
                bridge=ctx.request.post(origin+'/desktop/bridge/connect',data={},headers={'Origin':origin})
                assert bridge.ok and bridge.json()['connected']
                page.screenshot(path=str(ROOT/'reports/screenshots/bridge-fixed-ready.png'))
    finally:
        if not args.keep_open:
            child.terminate();child.wait(timeout=10)
if __name__=='__main__':main()
