"""Reproduce sidebar width, real model selection and theme surface failures."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,io,json,mimetypes,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from PIL import Image
ORIGIN='https://tutor.example.invalid'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',action='store_true');parser.add_argument('--preview-css',action='store_true');args=parser.parse_args()
    mode='preview' if args.preview_css else 'candidate' if args.candidate else 'published'
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    report={'mode':mode,'checks':{},'surfaces':{},'errors':[],'new_model_turn':False,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1360,'height':900})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        projects=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'];project=next(x for x in projects if x['name']=='水分扩散')
        if args.candidate:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/('index.html' if not name else name)
                    assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        captured=[];socket_urls=[];socket_types=[]
        def intercept(socket):
            socket_urls.append(socket.url)
            upstream=socket.connect_to_server()
            def receive(message):
                try:event=json.loads(message)
                except (ValueError,TypeError):upstream.send(message);return
                socket_types.append(event.get('type'))
                if event.get('type')=='start_turn':captured.append(event)
                else:upstream.send(message)
            socket.on_message(receive)
        ctx.route_web_socket(re.compile(r'.*'),intercept)
        page=ctx.new_page();page.on('pageerror',lambda error:report['errors'].append(str(error)))
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=literature',wait_until='domcontentloaded')
        page.locator('.literature-reading-layout').wait_for(timeout=30000)
        if args.preview_css:page.add_style_tag(path=str(DIST.parent/'src/workspace.css'))
        initial_theme=page.evaluate("document.documentElement.classList.contains('theme-glass')?'glass':document.documentElement.classList.contains('dark')?'dark':document.documentElement.classList.contains('theme-snow')?'snow':'light'")
        sidebar=page.locator('.dp-native-shell aside').first
        sidebar.get_by_role('button',name='研究对话',exact=True).click()
        row=sidebar.get_by_role('button',name='研究对话',exact=True)
        width=row.bounding_box()['width'];parent=row.locator('..').bounding_box()['width']
        report['sidebar_row']={'width':width,'available':parent}
        report['checks']['chat_selected_background_full_row']=width>=parent-4
        composer=page.locator('.dp-composer-policy').first;composer.wait_for()
        selector=composer.get_by_role('button',name=re.compile('^(选择模型|Select model)$'))
        report['checks']['model_selector_is_interactive']=selector.count()==1
        if selector.count():
            selector.click();page.wait_for_timeout(150)
            report['checks']['model_menu_opens']=selector.get_attribute('aria-expanded')=='true'
            options=ctx.request.get(ORIGIN+'/api/settings/llm-options').json()['options']
            chosen=next((option for option in options if not option.get('is_active_default')),options[0])
            option_label=chosen['model_name']+' | '+chosen['profile_name']
            composer.get_by_role('button',name=option_label,exact=True).click()
            report['checks']['chosen_model_visible']=chosen['model'] in selector.inner_text()
            selector.click()
            report['checks']['chosen_model_marked']=composer.get_by_role('button',name=option_label,exact=True).locator('svg.lucide-check').count()==1
            composer.get_by_role('button',name=option_label,exact=True).click()
            report['chosen_model']={key:chosen[key] for key in ['profile_id','model_id','model']}
            page.screenshot(path=str(ROOT/f'reports/screenshots/theme-model-{mode}-selector.png'))
        sidebar.get_by_role('button',name='文献',exact=True).click()
        themes=[(0,'snow'),(3,'glass'),(2,'dark'),(1,'light'),(0,'snow')]
        if initial_theme!='snow':themes.append(({'light':1,'dark':2,'glass':3}[initial_theme],initial_theme))
        for index,theme in themes:
            sidebar.get_by_role('button',name='设置',exact=True).click()
            settings=page.locator('.dp-tutor-settings');settings.locator('a[href*="settings_section=appearance"]').first.click();page.wait_for_timeout(350)
            tiles=settings.locator('[data-tour="tour-appearance"] .grid>button')
            if tiles.nth(index).get_attribute('aria-pressed')!='true':
                tiles.nth(index).click()
                settings.get_by_role('button',name=re.compile('^(应用更改|Apply changes)$')).click()
            settings.get_by_role('button',name='返回应用',exact=True).click()
            page.locator('.literature-reading-layout').wait_for();page.wait_for_timeout(180)
            data=page.locator('.dp-artifacts').evaluate("e=>({className:document.documentElement.className,card:getComputedStyle(e).getPropertyValue('--card').trim(),layers:[e,...e.querySelectorAll('.embedded-workbench,.workspace,.main-content,.literature-reading-layout,.library-content')].map(n=>({name:n.className,background:getComputedStyle(n).backgroundColor}))})")
            shot=page.screenshot(path=str(ROOT/f'reports/screenshots/theme-model-{mode}-{theme}.png'))
            pixel=Image.open(io.BytesIO(shot)).convert('RGB').getpixel((1050,760));data['content_pixel']=pixel
            report['surfaces'][theme]=data
            if theme=='glass':report['checks']['glass_content_not_flat_grey']=max(pixel)<=45
            report['checks']['no_overflow_'+theme]=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        report['checks']['original_theme_restored']=page.evaluate("document.documentElement.classList.contains('theme-glass')?'glass':document.documentElement.classList.contains('dark')?'dark':document.documentElement.classList.contains('theme-snow')?'snow':'light'")==initial_theme
        if 'chosen_model' in report:
            sidebar.get_by_role('button',name='研究对话',exact=True).click()
            selector.click();composer.get_by_role('button',name=option_label,exact=True).click()
            composer.locator('textarea').first.fill('界面测试：只核对模型选择参数，此请求由浏览器测试拦截。')
            composer.get_by_role('button',name=re.compile('^(发送|Send|Send message)$')).click()
            for _ in range(40):
                if captured:break
                page.wait_for_timeout(100)
            report['checks']['selected_model_in_turn_payload']=bool(captured) and captured[0].get('llm_selection')=={key:chosen[key] for key in ['profile_id','model_id']}
            report['turn_intercepted_before_server']=bool(captured)
            report['sockets']={'urls':socket_urls,'types':socket_types,'selected':captured[0].get('llm_selection') if captured else None}
            page.screenshot(path=str(ROOT/f'reports/screenshots/theme-model-{mode}-send-check.png'))
        report['checks']['no_script_errors']=not report['errors']
        report['passed']=all(report['checks'].values())
        browser.close()
    (ROOT/f'reports/theme-model-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));assert report['passed']

if __name__=='__main__':main()
