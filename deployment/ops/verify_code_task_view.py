"""Verify real code output visibility and the route back to its conversation."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,json,mimetypes,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
OUT=ROOT/'reports/agentic-product';ORIGIN='https://tutor.example.invalid'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    fixture=json.loads((OUT/'publication-scope-live.json').read_text(encoding='utf8'))
    mode='published' if args.published else 'candidate';pid=fixture['project_id'];rid=fixture['run_id']
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,timeout=35))
    report={'checks':{},'errors':[],'mode':mode,'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id']}
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
        page.goto(ORIGIN+'/research/?project='+pid+'&dt_workspace=ws_62eb9eb8014c4484913c5904d0b903dd&view=workflow',wait_until='domcontentloaded')
        page.locator('[data-workflow-id="'+rid+'"]').wait_for(timeout=60000);page.locator('[data-workflow-id="'+rid+'"]').click()
        evidence=page.get_by_role('region',name='代码成果与验证依据')
        evidence.wait_for();report['checks']['one_current_turn_file']=evidence.locator('ul>li').count()==1
        report['checks']['missing_verification_is_explicit']='执行器未回传结构化验证记录' in evidence.inner_text()
        report['checks']['original_session_link']=bool(evidence.get_by_role('link',name='回到原会话继续处理').get_attribute('href').split('session=')[-1])
        page.screenshot(path=str(OUT/f'code-task-{mode}.png'))
        evidence.get_by_role('button',name='docs/publication-scope-check/scope_check_20261105.md').click()
        page.wait_for_timeout(1200)
        report['checks']['file_preview_is_visible']=page.locator('.dp-chat-pane').is_visible()
        page.screenshot(path=str(OUT/f'code-task-{mode}-preview.png'))
        report['passed']=all(report['checks'].values()) and not report['errors']
        (OUT/f'code-task-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False));browser.close();assert report['passed'],report


if __name__=='__main__':main()
