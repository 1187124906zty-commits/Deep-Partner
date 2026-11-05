"""Inspect the real graph using the candidate/published UI and actual project data."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,json,mimetypes,subprocess,sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];DIST=Path('D:/Development/research-workbench/unified-ui/dist');ORIGIN='https://tutor.example.invalid'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    project=json.loads((ROOT/'.local/partner-workflow/fixture.json').read_text(encoding='utf8'))
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8'))
    report={'checks':{},'page_errors':[],'published':args.published}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1500,'height':1000});r=ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN});assert r.ok
        if not args.published:
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/(name or 'index.html');assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id'],wait_until='domcontentloaded')
        page.get_by_role('button',name='项目画布',exact=True).click(timeout=45000)
        page.get_by_role('button',name='研究知识图谱',exact=True).wait_for(timeout=30000)
        page.locator('.project-canvas-graph canvas').first.wait_for(timeout=30000)
        report['checks']['research_graph_is_default']=page.get_by_role('button',name='研究知识图谱',exact=True).get_attribute('aria-pressed')=='true'
        graph=ctx.request.get(ORIGIN+'/research/api/projects/'+project['id']+'/research-flow/graph').json()
        report['checks']['real_graph_has_papers_and_relations']=any(n['kind']=='paper' for n in graph['nodes']) and bool(graph['edges'])
        page.get_by_role('button',name='适合画布',exact=True).click();page.screenshot(path=str(ROOT/'reports/partner-research-graph.png'),full_page=True)
        page.get_by_role('button',name='项目活动',exact=True).click();page.get_by_role('button',name='项目会话',exact=False).wait_for(timeout=30000)
        report['checks']['activity_view_retained']=page.locator('.canvas-outline').get_by_role('button',name='项目会话',exact=False).count()>0
        page.get_by_role('button',name='研究知识图谱',exact=True).click()
        report['checks']['no_page_errors']=not report['page_errors']
        browser.close()
    (ROOT/'reports/partner-canvas-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));assert all(report['checks'].values()),report

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
