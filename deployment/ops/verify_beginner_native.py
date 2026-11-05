from pathlib import Path
import json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1];NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

def main():
    account=json.loads(subprocess.run(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    project=json.loads((ROOT/'.local/onboarding-test-project.json').read_text())
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe')],cwd=NATIVE/'dist',env=dict(os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9253'))
    report={'checks':{},'errors':[],'new_model_turn':False}
    try:
        for _ in range(70):
            try:urllib.request.urlopen('http://127.0.0.1:9253/json/version',timeout=1).close();break
            except OSError:time.sleep(.3)
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp('http://127.0.0.1:9253');ctx=browser.contexts[0];page=ctx.pages[0]
            page.wait_for_url('http://127.0.0.1:*/**');origin='/'.join(page.url.split('/')[:3]);h={'Origin':origin}
            assert ctx.request.post(origin+'/api/auth/login',data=account,headers=h).ok
            report['build']=ctx.request.get(origin+'/build-info.json',headers=h).json()
            page.on('pageerror',lambda error:report['errors'].append(str(error)))
            page.goto(origin+'/?project='+project['id']+'&dt_workspace='+project['native_id'],wait_until='domcontentloaded')
            page.locator('.dp-attachment-hint').wait_for(timeout=30000)
            assert page.locator('.dp-sidebar-footer').get_by_role('button',name='文献与知识库',exact=True).count()==1
            report['checks']['native_simple_navigation']=True
            transfer=page.evaluate_handle("()=>{const d=new DataTransfer();d.items.add(new File(['Native drop marker NATIVE_DROP_20261102'],'native-drop-check.md',{type:'text/markdown'}));return d}")
            with page.expect_response(lambda r:'/attachments' in r.url and r.request.method=='POST',timeout=120000) as response:page.locator('.dp-chat-pane').dispatch_event('drop',{'dataTransfer':transfer})
            assert response.value.ok;report['checks']['native_chat_drop_saves']=True
            page.get_by_role('button',name='查看网页',exact=True).click();page.get_by_label('网页地址',exact=True).fill('https://example.com');page.locator('.dp-web-address').get_by_role('button',name='打开',exact=True).click()
            page.get_by_role('region',name='网页预览').wait_for();report['checks']['native_web_preview']=True
            page.screenshot(path=str(ROOT/'reports/screenshots/beginner-native-workflow.png'))
            page.locator('.dt-viewer-panel[data-open="true"]').get_by_role('button',name='关闭查看器',exact=True).click()
            from verify_figure_dito import exercise
            fixture=next(p for p in ctx.request.get(origin+'/research/api/projects',headers=h).json()['projects'] if p['id']==project['id'])
            try:exercise(ctx,page,origin,fixture,report,'native')
            except Exception as error:
                report['passed']=False;report['failure']=str(error)
                (ROOT/'reports/beginner-workflow-native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
                page.screenshot(path=str(ROOT/'reports/screenshots/figure-dito-native-failure.png'))
                raise
            report['build']=ctx.request.get(origin+'/build-info.json',headers=h).json()
            report['checks']['native_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            report['passed']=not report['errors'] and all(report['checks'].values())
            (ROOT/'reports/beginner-workflow-native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));assert report['passed']
    finally:child.terminate();child.wait(timeout=10)

if __name__=='__main__':main()
