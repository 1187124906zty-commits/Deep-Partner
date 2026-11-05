"""Verify the compact shared UI with real authenticated project APIs.

Slide keyboard navigation additionally uses an explicitly named two-page UI
fixture in the browser only, since the acceptance project has no saved deck.
"""
from pathlib import Path
from urllib.parse import urlparse,unquote,quote
import argparse,json,mimetypes,subprocess,sys,re
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
ORIGIN='https://tutor.example.invalid'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');parser.add_argument('--preview-css',action='store_true');args=parser.parse_args()
    mode='preview' if args.preview_css else 'published' if args.published else 'candidate'
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    report={'mode':mode,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id'],'errors':[],'checks':{},'new_model_turn':False,'user_materials_changed':False,'screenshots':[]}
    checks=report['checks']
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':920})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        projects=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects']
        project=next(x for x in projects if x['id']=='c0b9c547b07c401aa7fc7454b0104345')
        prefix='/research/api/projects/'+project['id']
        parent=json.loads((ROOT/'reports/unified-stream-live.json').read_text())['session_id']
        session_url=ORIGIN+'/api/sessions/'+parent+'?dt_workspace='+project['native_id']
        before=ctx.request.get(session_url).json()['messages']
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/('index.html' if not name else name)
                    assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda error:report['errors'].append(str(error)))
        def shot(name):
            target=ROOT/f'reports/screenshots/compact-{mode}-{name}.png'
            page.screenshot(path=str(target));report['screenshots'].append(str(target))
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&session='+parent,wait_until='domcontentloaded')
        if args.preview_css:page.add_style_tag(path=str(DIST.parent/'src/workspace.css'))
        sidebar=page.locator('.dp-native-shell aside').first
        sidebar.get_by_role('navigation',name='科研工作区').wait_for(timeout=45000)
        for label,selector in [('文献','.literature-reading-layout'),('文件','.files-reading-layout'),('论文','.paper-workspace'),('图表','.files-reading-layout'),('PPT','.slides-reading-layout'),('程序','.files-reading-layout')]:
            sidebar.get_by_role('button',name=label,exact=True).click()
            page.locator('.dp-artifacts '+selector).wait_for(timeout=30000)
            assert sidebar.get_by_role('button',name=label,exact=True).get_attribute('aria-current')=='page'
            assert not page.locator('.dp-artifacts nav[aria-label="研究成果"]').is_visible()
            checks['direct_entry_'+label]=True
        checks['single_grouped_navigation']=sidebar.get_by_role('heading',name='资料',exact=True).count()==1 and sidebar.get_by_role('heading',name='创作',exact=True).count()==1
        checks['compact_header']=page.locator('.dp-workspace-header').bounding_box()['height']<=46
        # Find real existing code and image files, without creating project data.
        found={};queue=[''];visited=0
        while queue and visited<20 and len(found)<2:
            directory=queue.pop(0);visited+=1
            result=ctx.request.get(ORIGIN+prefix+'/files?path='+quote(directory)).json()
            for item in result['items']:
                if item['kind']=='folder':queue.append(item['path'])
                elif item['name'].lower().endswith(('.py','.m','.rs','.ts')):found.setdefault('code',item['path'])
                elif item['name'].lower().endswith(('.png','.jpg','.webp')):found.setdefault('image',item['path'])
        report['real_file_probes']=found
        if 'code' in found:
            sidebar.get_by_role('button',name='程序',exact=True).click()
            for part in found['code'].split('/'):
                page.locator('.file-table td:first-child>span').filter(has_text=re.compile('^'+re.escape(part)+'$')).click()
            page.get_by_label('程序源代码',exact=True).wait_for(timeout=30000)
            checks['real_code_opens']=True;shot('code')
        sidebar.get_by_role('button',name='图表',exact=True).click()
        if 'image' in found:
            for part in found['image'].split('/'):
                page.locator('.image-gallery strong').filter(has_text=re.compile('^'+re.escape(part)+'$')).click()
            page.locator('.figure-detail-pane').wait_for(timeout=30000)
            checks['real_image_opens']=True;shot('figure')
        sidebar.get_by_role('button',name='论文',exact=True).click();page.locator('.paper-workspace').wait_for()
        page.wait_for_timeout(800);shot('paper')
        page.get_by_role('button',name='展开助手',exact=True).click()
        page.locator('.dp-assistant-header').wait_for();page.wait_for_timeout(300)
        content=page.locator('.dp-artifacts').bounding_box();assistant=page.locator('.dp-chat-pane').bounding_box()
        checks['content_left_assistant_right']=content['x']<assistant['x'] and content['width']>assistant['width']
        separator=page.get_by_role('separator',name='调整助手宽度');separator.focus();separator.press('ArrowLeft')
        checks['assistant_keyboard_resize']=int(separator.get_attribute('aria-valuenow'))>=420
        page.locator('.dp-workspace-location').click();shot('paper-assistant')
        page.get_by_role('button',name='问 Dito',exact=True).click()
        panel=page.locator('.dt-viewer-panel[data-open="true"]');panel.wait_for();panel.get_by_placeholder('问 Dito…',exact=True).wait_for()
        checks['dito_preserves_open_document']=page.locator('.dp-artifacts .paper-workspace').is_visible()
        box=panel.bounding_box();chatbox=page.locator('.dp-chat-pane').bounding_box();checks['dito_stays_in_assistant_pane']=box['x']>=chatbox['x']-1 and box['width']<=chatbox['width']+1
        shot('context-question')
        panel.get_by_role('button',name='关闭查看器',exact=True).click()
        page.get_by_role('button',name='收起助手',exact=True).first.click()
        # Existing full settings and import remain connected to native components.
        sidebar.get_by_role('button',name='导入项目',exact=True).click()
        page.get_by_role('region',name='导入项目卡片').wait_for()
        checks['native_import_card']=page.locator('.dt-viewer-panel[data-open="true"]').is_visible()
        page.locator('.dt-viewer-panel[data-open="true"]').get_by_role('button',name='关闭查看器',exact=True).click()
        sidebar.get_by_role('button',name='设置',exact=True).click()
        page.locator('.dp-tutor-settings [data-settings-page="general"]').wait_for()
        page.get_by_role('button',name='返回应用',exact=True).click();checks['full_settings_return']=True
        page.set_viewport_size({'width':1280,'height':760});page.wait_for_timeout(350)
        checks['laptop_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        shot('laptop')
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(350)
        checks['mobile_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        shot('mobile')
        # Test playback against a fixture response, never written to the backend.
        page.set_viewport_size({'width':1440,'height':920})
        if page.get_by_role('button',name='收起助手',exact=True).count():page.get_by_role('button',name='收起助手',exact=True).first.click()
        ctx.route(ORIGIN+prefix+'/slides',lambda route:route.fulfill(json={'title':'界面播放测试（非研究成果）','sections':[{'id':'ui-1','title':'界面测试第 1 页','content':'仅验证幻灯片播放与键盘操作。'},{'id':'ui-2','title':'界面测试第 2 页','content':'本内容未保存到项目。'}]}))
        sidebar.get_by_role('button',name='PPT',exact=True).click()
        shot('before-playback')
        page.get_by_role('button',name='播放',exact=True).click()
        playback=page.get_by_role('dialog',name='PPT 播放');playback.wait_for();playback.press('ArrowRight')
        assert playback.locator('output').inner_text()=='2 / 2'
        playback.press('Home');assert playback.locator('output').inner_text()=='1 / 2'
        playback.press('Escape');assert not playback.count()
        checks['slide_playback_keyboard_fixture']=True
        if not args.preview_css:
            sidebar.get_by_role('button',name='论文',exact=True).click()
            page.get_by_role('button',name='阅读',exact=True).click()
            page.locator('.local-reader').wait_for()
            page.wait_for_function("Array.from(document.querySelectorAll('.local-pdf-container canvas')).some(canvas=>canvas.width>0)",timeout=60000)
            checks['paper_reading_renders_pdf']=True;shot('paper-reading')
            page.get_by_role('button',name='返回编辑',exact=True).click()
            page.locator('.quiet-paper-toolbar').wait_for();checks['paper_returns_to_editor']=True
            page.evaluate("localStorage.setItem('deeptutor-theme','dark')")
            page.reload(wait_until='domcontentloaded');page.locator('.quiet-paper-toolbar').wait_for(timeout=30000);page.wait_for_timeout(300)
            checks['dark_theme_no_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            shot('dark')
        report['playback_evidence']='Two-page UI fixture intercepted in browser only; no saved deck in acceptance project.'
        checks['main_session_unchanged']=ctx.request.get(session_url).json()['messages']==before
        checks['no_script_errors']=not report['errors']
        report['passed']=all(checks.values())
        browser.close()
    (ROOT/f'reports/compact-ui-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));assert report['passed']

if __name__=='__main__':main()
