"""Real product UI acceptance against candidate assets or the published website."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,json,mimetypes,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
OUT=ROOT/'reports/agentic-product'
ORIGIN='https://tutor.example.invalid'
PROJECT='64c6b5e79b824bc4bf23637e8204446c'
WORKSPACE='ws_62eb9eb8014c4484913c5904d0b903dd'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    mode='published' if args.published else 'candidate'
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=35))
    report={'mode':mode,'checks':{},'layouts':[],'errors':[],'build':json.loads((DIST/'build-info.json').read_text())}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':960})
        assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/(name or 'index.html');assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.goto(ORIGIN+'/research/?project='+PROJECT+'&dt_workspace='+WORKSPACE+'&area=questions',wait_until='domcontentloaded')
        page.locator('.dp-native-shell').wait_for(timeout=60000)
        for area in ['研究对话','文献与知识库','项目画布','论文','图表','程序']:
            page.set_viewport_size({'width':1440,'height':960})
            page.locator('.dp-native-shell aside').first.get_by_role('button',name=area,exact=True).click()
            page.wait_for_timeout(800)
            if area=='项目画布':page.locator('.project-canvas-graph canvas').first.wait_for(timeout=30000)
            if area=='文献与知识库':page.locator('.bibliography-table').wait_for(timeout=30000)
            for width,height in [(1440,960),(768,1024),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(180)
                page.screenshot(path=str(OUT/f'{mode}-{area}-{width}.png'))
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                report['layouts'].append({'area':area,'width':width,'document_overflow':overflow})
                if area=='文献与知识库':
                    report['checks']['read_button_visible_'+str(width)]=page.locator('.bibliography-read').first.evaluate('(e)=>{let r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.width>=60}')
                if area=='研究对话':
                    report['checks']['compact_writing_toolbar_'+str(width)]=page.locator('.dp-writing-toolbar').evaluate('(e)=>{let r=e.getBoundingClientRect();return r.width<=740&&r.height<160&&r.left>=0&&r.right<=innerWidth}')
        page.set_viewport_size({'width':1440,'height':960})
        nav=page.locator('.dp-native-shell aside').first
        nav.get_by_role('button',name='研究对话',exact=True).click()
        selector=page.get_by_role('button',name='工作模式',exact=True)
        selector.click();page.get_by_role('listbox').wait_for()
        report['checks']['select_stays_in_viewport']=page.locator('.dp-select-popover').evaluate('(e)=>{let r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight}')
        page.keyboard.press('Escape');report['checks']['escape_closes_select']=selector.get_attribute('aria-expanded')=='false'
        nav.get_by_role('button',name='项目画布',exact=True).click()
        page.get_by_role('button',name='证据关系',exact=True).wait_for()
        page.locator('.project-canvas-graph canvas').first.wait_for(timeout=30000)
        report['checks']['connected_graph_default']=page.get_by_role('button',name='证据关系',exact=True).get_attribute('aria-pressed')=='true'
        page.get_by_role('textbox',name='查找研究记录').fill('软件')
        report['checks']['graph_record_search']=page.locator('.canvas-record-picker button').count()>0
        page.get_by_role('textbox',name='查找研究记录').fill('')
        page.get_by_role('button',name='适合画布',exact=True).click()
        page.screenshot(path=str(OUT/f'{mode}-graph.png'))
        for theme in ['light','dark','snow','glass']:
            page.evaluate('''theme=>{localStorage.setItem('deeptutor-theme',theme);location.reload()}''',theme)
            page.locator('.dp-native-shell').wait_for(timeout=60000)
            page.locator('.dp-native-shell aside').first.get_by_role('button',name='研究对话',exact=True).click()
            page.locator('.dp-writing-toolbar').wait_for();page.wait_for_timeout(200)
            report['checks']['theme_'+theme]=page.locator('.dp-writing-toolbar').evaluate('(e)=>getComputedStyle(e).color!==getComputedStyle(e).backgroundColor')
            page.screenshot(path=str(OUT/f'{mode}-theme-{theme}.png'))
        browser.close()
    report['passed']=all(report['checks'].values()) and not report['errors'] and not any(r['document_overflow'] for r in report['layouts'])
    (OUT/f'ui-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))
    assert report['passed'],'See saved UI checks and screenshots'


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
