"""Check the actual packaged WebView2 application after the workspace rebuild."""
from pathlib import Path
import json,os,subprocess,sys,time,urllib.request,re
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

def main():
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    env=dict(os.environ,WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9249')
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe')],env=env,cwd=NATIVE/'dist')
    report={'app':'packaged Tauri/WebView2','errors':[],'checks':{},'frontend_job_id':build['job_id'],'new_model_turn':False,'user_materials_changed':False}
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen('http://127.0.0.1:9249/json/version',timeout=1) as response:json.load(response)
                break
            except OSError:time.sleep(.3)
        else:raise RuntimeError('WebView2 debugging transport unavailable')
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp('http://127.0.0.1:9249')
            ctx=browser.contexts[0];page=ctx.pages[0]
            page.wait_for_url('http://127.0.0.1:*/**',timeout=30000)
            origin='/'.join(page.url.split('/')[:3]);headers={'Origin':origin}
            assert ctx.request.post(origin+'/api/auth/login',data=account,headers=headers).ok
            assert ctx.request.get(origin+'/build-info.json',headers=headers).json()['slurm_job_id']==build['job_id']
            projects=ctx.request.get(origin+'/research/api/projects',headers=headers).json()['projects']
            project=next(x for x in projects if x['id']=='c0b9c547b07c401aa7fc7454b0104345')
            parent=json.loads((ROOT/'reports/unified-stream-live.json').read_text())['session_id']
            session=origin+'/api/sessions/'+parent+'?dt_workspace='+project['native_id']
            before=ctx.request.get(session,headers=headers).json()['messages']
            page.on('pageerror',lambda error:report['errors'].append(str(error)))
            page.goto(origin+'/?project='+project['id']+'&dt_workspace='+project['native_id']+'&session='+parent,wait_until='domcontentloaded')
            sidebar=page.locator('.dp-native-shell aside').first;sidebar.get_by_role('navigation',name='科研工作区').wait_for(timeout=30000)
            initial_theme=page.evaluate("document.documentElement.classList.contains('theme-glass')?'glass':document.documentElement.classList.contains('dark')?'dark':document.documentElement.classList.contains('theme-snow')?'snow':'light'")
            sidebar.get_by_role('button',name='研究对话',exact=True).click()
            row=sidebar.get_by_role('button',name='研究对话',exact=True)
            report['checks']['native_chat_row_full_width']=row.bounding_box()['width']>=row.locator('..').bounding_box()['width']-4
            model=page.locator('.dp-model-selector button[aria-expanded]').first;model.wait_for()
            model.click();assert model.get_attribute('aria-expanded')=='true';model.click()
            report['checks']['native_model_selector_works']=True
            for label in ['文献','文件','图表','PPT','程序','论文']:
                sidebar.get_by_role('button',name=label,exact=True).click()
                assert sidebar.get_by_role('button',name=label,exact=True).get_attribute('aria-current')=='page'
            page.get_by_role('button',name='阅读',exact=True).wait_for()
            report['checks']['native_grouped_entries']=True
            page.get_by_role('button',name='展开助手',exact=True).click()
            page.get_by_role('button',name='问 Dito',exact=True).click()
            panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for()
            panel.get_by_placeholder('问 Dito…',exact=True).wait_for()
            box=panel.bounding_box();chatbox=page.locator('.dp-chat-pane').bounding_box()
            assert box['x']>=chatbox['x']-1 and box['width']<=chatbox['width']+1
            report['checks']['native_dito_bounded_to_assistant']=True
            page.screenshot(path=str(ROOT/'reports/screenshots/compact-native-workspace.png'))
            panel.get_by_role('button',name='关闭查看器',exact=True).click()
            sidebar.get_by_role('button',name='设置',exact=True).click()
            page.locator('.dp-tutor-settings [data-settings-page="general"]').wait_for()
            settings=page.locator('.dp-tutor-settings')
            settings.locator('a[href*="settings_section=appearance"]').first.click()
            def choose_theme(index):
                tiles=settings.locator('[data-tour="tour-appearance"] .grid>button')
                if tiles.nth(index).get_attribute('aria-pressed')!='true':
                    tiles.nth(index).click();settings.get_by_role('button',name=re.compile('^(应用更改|Apply changes)$')).click()
                settings.get_by_role('button',name='返回应用',exact=True).click()
            choose_theme(3)
            report['checks']['native_glass_surface_resolved_once']='color-mix' in page.locator('.dp-artifacts').evaluate("e=>getComputedStyle(e).getPropertyValue('--card')")
            page.screenshot(path=str(ROOT/'reports/screenshots/compact-native-glass.png'))
            sidebar.get_by_role('button',name='设置',exact=True).click();settings.locator('a[href*="settings_section=appearance"]').first.click()
            choose_theme({'snow':0,'light':1,'dark':2,'glass':3}.get(initial_theme,0))
            report['checks']['native_original_theme_restored']=page.evaluate("document.documentElement.classList.contains('theme-glass')?'glass':document.documentElement.classList.contains('dark')?'dark':document.documentElement.classList.contains('theme-snow')?'snow':'light'")==initial_theme
            report['checks']['native_settings_return']=True
            report['checks']['native_embedded_build']=True
            module=ctx.request.get(origin+'/research/reader/'+project['id']+'/assets/pdf-B0s6D7Gr.js',headers=headers)
            report['checks']['native_pdf_module_available']=module.ok and 'javascript' in module.headers.get('content-type','')
            report['checks']['native_session_unchanged']=ctx.request.get(session,headers=headers).json()['messages']==before
            report['checks']['native_no_horizontal_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            report['passed']=not report['errors'] and all(report['checks'].values())
            (ROOT/'reports/compact-ui-native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(report,ensure_ascii=False));assert report['passed']
    finally:
        child.terminate();child.wait(timeout=10)

if __name__=='__main__':main()
