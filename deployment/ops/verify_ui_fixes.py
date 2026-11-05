"""Exercise themed selectors, native feedback composer and the unopened import action."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,json,mimetypes,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
ORIGIN='https://tutor.example.invalid'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');parser.add_argument('--stream',action='store_true');parser.add_argument('--resume-side',action='store_true');args=parser.parse_args()
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    mode='published' if args.published else 'candidate'
    report={'mode':mode,'errors':[],'import_requests':0,'checks':{},'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    prior_path=ROOT/'reports/ui-fixes-candidate.json'
    prior=json.loads(prior_path.read_text(encoding='utf8')) if args.resume_side else {}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1540,'height':1000})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        projects=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects']
        project=next((x for x in projects if 'Dify 部署' in x['name']),projects[0])
        if not args.published:
            def route(r):
                name=unquote(urlparse(r.request.url).path).removeprefix('/research/').strip('/')
                target=DIST/('index.html' if not name else name)
                if not name or name.startswith(('assets/','fonts/')):
                    assert target.resolve().is_relative_to(DIST.resolve())
                    r.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:r.continue_()
            ctx.route(ORIGIN+'/research/**',route)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        def requested(req):
            if req.method=='POST' and urlparse(req.url).path.endswith('/import'):report['import_requests']+=1
        page.on('request',requested)
        parent=json.loads((ROOT/'reports/unified-stream-live.json').read_text(encoding='utf8'))['session_id']
        parent_path=ORIGIN+'/api/sessions/'+parent+'?dt_workspace='+project['native_id']
        before=ctx.request.get(parent_path).json()['messages']
        report['parent_session_id']=parent
        frames=[];sent=[]
        def opened(socket):
            def receive(raw):
                try:frames.append(json.loads(raw))
                except (ValueError,TypeError):pass
            socket.on('framereceived',receive)
            def transmit(raw):
                try:sent.append(json.loads(raw))
                except (ValueError,TypeError):pass
            socket.on('framesent',transmit)
        page.on('websocket',opened)
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&session='+parent,wait_until='domcontentloaded')
        page.locator('.dp-chat-pane').get_by_text('DEEP_PARTNER_STREAM_OK',exact=False).first.wait_for(timeout=30000)
        selector=page.get_by_role('button',name='切换研究项目',exact=True);selector.wait_for()
        selector.click();page.get_by_role('listbox').wait_for();page.wait_for_timeout(220)
        report['checks']['selector_opaque_surface']=page.locator('.dp-select-popover').evaluate("e=>getComputedStyle(e).backgroundColor!=='rgba(0, 0, 0, 0)'")
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-select.png'))
        page.keyboard.press('Escape');assert selector.get_attribute('aria-expanded')=='false'
        selector.focus();page.keyboard.press('ArrowDown');page.get_by_role('listbox').wait_for();page.keyboard.press('Escape')
        report['checks']['project_selector_themed_and_keyboard']=True
        view=page.get_by_role('navigation',name='工作视图')
        view.get_by_role('button',name='问 Dito',exact=True).click()
        panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for()
        editor=panel.get_by_placeholder('问 Dito…',exact=True);editor.wait_for()
        assert page.evaluate('new URL(location.href).searchParams.get("session")')==parent
        if args.stream:
            editor.fill('本次只验证 Dito 独立侧边会话。不要调用工具或读取文件，只回复 DP_DITO_SIDE_OK。')
            editor.press('Enter')
            page.wait_for_timeout(4000)
            page.screenshot(path=str(ROOT/'reports/screenshots/dito-stream-current.png'))
            (ROOT/'reports/dito-stream-current.json').write_text(json.dumps({'received':frames,'sent':sent,'errors':report['errors'],'body':panel.inner_text()},ensure_ascii=False,indent=2),encoding='utf8')
            import time
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                if any(e.get('type') in ('done','protocol_error','error') for e in frames):break
                page.wait_for_timeout(800)
            else:raise RuntimeError('Dito independent side turn did not complete')
            side_ids={e.get('session_id') for e in frames if e.get('session_id') and e.get('session_id')!=parent}
            assert side_ids,frames[-5:]
            side_id=next(iter(side_ids))
            side=ctx.request.get(ORIGIN+'/api/sessions/'+side_id+'?dt_workspace='+project['native_id']).json()
            assert any('DP_DITO_SIDE_OK' in str(m.get('content','')) for m in side['messages'] if m['role']=='assistant')
            assert side['preferences']['session_kind']=='selection_tutor'
            report['side_stream']={'session_id':side_id,'separate_from_main':True,'persisted_marker':True,'session_kind':side['preferences']['session_kind']}
        if args.resume_side:
            side_id=prior['side_stream']['session_id']
            side=ctx.request.get(ORIGIN+'/api/sessions/'+side_id+'?dt_workspace='+project['native_id']).json()
            assert side['preferences']['session_kind']=='selection_tutor'
            assert page.locator('.dp-native-shell aside').first.get_by_text(side['title'],exact=True).count()==0
            report['checks']['main_sidebar_excludes_dito_threads']=True
            panel.get_by_role('button',name='新标签页',exact=True).click()
            panel.get_by_text(side['title'],exact=True).first.click()
            panel.get_by_text('DP_DITO_SIDE_OK',exact=False).first.wait_for(timeout=30000)
            report['side_stream']={**prior['side_stream'],'source':'persisted_native_side_turn_from_previous_actual_ui_send','reload_recovered':True}
        after=ctx.request.get(parent_path).json()['messages'];assert after==before
        report['checks']['dito_uses_native_viewer_and_preserves_main']=True
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-dito.png'))
        panel.get_by_role('button',name='关闭查看器',exact=True).click()
        view.get_by_role('button',name='成果',exact=True).click()
        page.get_by_role('navigation',name='研究成果').get_by_role('button',name='论文',exact=True).click()
        page.get_by_role('button',name='问 Agent',exact=True).click()
        panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for()
        panel.get_by_placeholder('问 Dito…',exact=True).wait_for()
        assert page.locator('.dp-feedback-composer').count()==0
        report['checks']['artifact_question_opens_native_dito']=True
        page.wait_for_timeout(300)
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-feedback.png'))
        panel.get_by_role('button',name='关闭标签页',exact=True).last.click()
        panel.get_by_role('button',name='关闭查看器',exact=True).click()
        page.get_by_role('button',name='导入项目',exact=True).click()
        card=page.get_by_role('region',name='导入项目卡片');card.wait_for()
        assert card.locator('xpath=ancestor::*[contains(@class,"dt-viewer-panel")]').count()==1
        card.get_by_label('导入来源位置',exact=True).fill(r'D:\博士工作\博士项目\水分扩散\2026-11-2\网站项目')
        card.get_by_role('button',name='导入来源类型').click()
        page.get_by_role('option',name='ChatGPT 导出文件夹',exact=True).click()
        assert card.get_by_role('button',name='导入来源类型').inner_text()=='ChatGPT 导出文件夹'
        page.wait_for_timeout(250)
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-import.png'))
        assert report['import_requests']==0 and ctx.request.get(parent_path).json()['messages']==before
        assert page.evaluate('new URL(location.href).searchParams.get("session")')==parent
        report['checks']['import_card_in_dito_main_unchanged']=True
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
        report['checks']['mobile_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-mobile.png'))
        panel.get_by_role('button',name='关闭查看器',exact=True).click()
        page.set_viewport_size({'width':1540,'height':1000})
        page.get_by_role('button',name='设置',exact=True).click()
        settings=page.locator('.dp-tutor-settings');settings.locator('[data-settings-page="general"]').wait_for()
        assert page.evaluate('new URL(location.href).searchParams.get("session")')==parent
        for section in ['appearance','connections','llm','knowledge']:
            settings.locator('a[href*="settings_section='+section+'"]').first.click()
            settings.locator('[data-settings-page="'+section+'"]').wait_for()
            page.wait_for_timeout(300)
        report['checks']['original_settings_sections_restored']=True
        settings.locator('a[href*="settings_section=appearance"]').first.click()
        settings.locator('[data-settings-page="appearance"]').wait_for()
        page.screenshot(path=str(ROOT/f'reports/screenshots/ui-fixes-{mode}-settings.png'))
        settings.get_by_role('button',name='返回应用',exact=True).click()
        assert page.evaluate('new URL(location.href).searchParams.get("session")')==parent
        report['checks']['settings_return_preserves_main']=True
        report['passed']=not report['errors'] and all(report['checks'].values()) and report['import_requests']==0
        browser.close()
    (ROOT/f'reports/ui-fixes-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));assert report['passed']
if __name__=='__main__':main()
