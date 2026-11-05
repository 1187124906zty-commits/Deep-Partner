"""Check saved topic folders against the real library and its original PDFs."""
from pathlib import Path
import argparse,json,os,sys,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,ORIGIN
from verify_workspace_interactions import static_candidate,geometry
from verify_restored_ui import CONTRAST
PID='1ea03384007d4bb9b88d43e3368099f3'
WORKSPACE='ws_0e6fc7aba58a4b258e25e1195702fde3'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    mode='published' if args.published else 'candidate'
    report={'mode':mode,'checks':{},'errors':[],'folders':[],'themes':{},'layout':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1540,'height':1000},proxy={'server':os.environ.get('WORKBENCH_HTTP_PROXY','http://127.0.0.1:12000')})
        class Client:
            def post(self,path,json=None):
                response=ctx.request.post(ORIGIN+path,data=json,headers={'Origin':ORIGIN})
                class Result:
                    def raise_for_status(self):assert response.ok,response.text()[:200]
                return Result()
        login(Client())
        folder_response=ctx.request.get(ORIGIN+'/research/api/projects/'+PID+'/literature/folders');assert folder_response.ok
        organization=folder_response.json();assert len(organization['folders'])==8
        if not args.published:ctx.route(ORIGIN+'/research/**',static_candidate)
        page=ctx.new_page();page.on('pageerror',lambda error:report['errors'].append(str(error)))
        page.goto(ORIGIN+'/research/?project='+PID+'&dt_workspace='+WORKSPACE+'&area=literature',wait_until='domcontentloaded')
        page.get_by_role('button',name='主题文件夹',exact=True).wait_for(timeout=60000)
        page.locator('.bibliography-table tbody tr').first.wait_for(timeout=60000)
        for folder in organization['folders']:
            expected=sum(folder['id'] in ids for ids in organization['memberships'].values())
            page.get_by_role('button',name='主题文件夹',exact=True).click()
            page.get_by_role('option').filter(has_text=folder['name']).click()
            page.wait_for_timeout(80)
            actual=page.locator('.bibliography-table tbody tr').count()
            assert actual==expected,(folder['name'],actual,expected)
            report['folders'].append({'id':folder['id'],'name':folder['name'],'visible_records':actual})
        report['checks']['all_seven_topics_and_pending_filter_real_documents']=True
        for width,height in [(1540,1000),(1100,850),(900,800),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(100)
            page.get_by_role('button',name='主题文件夹',exact=True).click();page.wait_for_timeout(150)
            value=geometry(page);value['topic_controls']=page.locator('.library-topic-folders').evaluate("""el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth}}""");report['layout'].append(value)
            page.keyboard.press('Escape')
        report['checks']['topic_controls_and_menus_fit_four_widths']=all(not x['horizontal_page_overflow'] and all(p['inside'] for p in x['popups']) and x['topic_controls']['scrollWidth']<=x['topic_controls']['clientWidth']+1 for x in report['layout'])
        page.set_viewport_size({'width':1540,'height':1000})
        for theme in ['snow','light','dark','glass']:
            page.evaluate("""theme=>{localStorage.setItem('deeptutor-theme',theme);const root=document.documentElement;root.classList.remove('dark','theme-snow','theme-glass');if(theme==='dark'||theme==='glass')root.classList.add('dark');if(theme==='glass')root.classList.add('theme-glass');if(theme==='snow')root.classList.add('theme-snow');root.dataset.tutorTheme=theme;window.dispatchEvent(new StorageEvent('storage',{key:'deeptutor-theme',newValue:theme}));}""",theme)
            page.wait_for_timeout(180);report['themes'][theme]=page.evaluate(CONTRAST)
        report['checks']['four_themes_keep_text_contrast']=all(not x['low_contrast'] for x in report['themes'].values())
        page.get_by_role('button',name='主题文件夹',exact=True).click()
        page.get_by_role('option').filter(has_text='01_氯硫耦合机理与反应传输').click()
        page.get_by_role('button',name='主题文件夹',exact=True).click();page.wait_for_timeout(200)
        shot=ROOT/'reports/screenshots'/('library-folders-'+mode+'.png');page.screenshot(path=str(shot));report['screenshot']=str(shot)
        report['checks']['no_script_errors']=not report['errors']
        dist=Path('D:/Development/research-workbench/unified-ui/dist')
        expected=re.findall(r'<script[^>]+src="([^"]+)"',(dist/'index.html').read_text(encoding='utf8'))
        actual=page.locator('script[src]').evaluate_all('nodes=>nodes.map(node=>node.getAttribute("src"))')
        assert expected and all(any(value.split('/')[-1]==url.split('/')[-1] for url in actual) for value in expected),(expected,actual)
        report['build']=json.loads((dist/'build-info.json').read_text(encoding='utf8'));report['loaded_script_paths_match_build']=True
        report['passed']=all(report['checks'].values())
        (ROOT/'reports'/('library-folders-ui-'+mode+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'passed':report['passed'],'checks':report['checks'],'folders':report['folders'],'contrast_failures':{k:v['low_contrast'] for k,v in report['themes'].items()}},ensure_ascii=False));browser.close()
    assert report['passed']


if __name__=='__main__':main()
