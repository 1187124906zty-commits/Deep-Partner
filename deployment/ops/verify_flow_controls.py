"""Exercise real workflow checkpoints via the deployed HTTP service and UI."""
from pathlib import Path
from urllib.parse import urlparse,unquote
import argparse,json,mimetypes,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
OUT=ROOT/'reports/agentic-product';FIXTURE=OUT/'flow-control-fixture.json'
ORIGIN='https://tutor.example.invalid'


def checked(response):
    assert response.ok,str(response.status)+' '+response.text()[:1000]
    return response.json()


def wait_status(ctx,base,status,before=None):
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        value=checked(ctx.get(ORIGIN+base+'/progress'))
        if value['status']==status and (before is None or value['control'].get('paused_before')==before):return value
        assert value['status'] not in ('failed','waiting_input'),value
        time.sleep(.5)
    raise AssertionError(value)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','candidate','published']);args=parser.parse_args()
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=35))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':960})
        checked(ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}))
        if args.action=='prepare':
            assert not FIXTURE.exists(),'Continue the saved test project instead of duplicating it'
            project=checked(ctx.request.post(ORIGIN+'/research/api/projects',data={'name':'工作流控制验收 2026-11-05'},headers={'Origin':ORIGIN}))
            body={'kind':'search','query':'Fourier neural operator parametric partial differential equations','limit':1,'request_id':'flow-controls-live-20261105','pause_before':['search','archive']}
            value={'project':project,'request':body};FIXTURE.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
            run=checked(ctx.request.post(ORIGIN+'/research/api/projects/'+project['id']+'/research-flow/runs',data=body,headers={'Origin':ORIGIN}))
            value['run']=run;FIXTURE.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
            base='/research/api/projects/'+project['id']+'/research-flow/runs/'+run['id']
            paused=wait_status(ctx.request,base,'paused')
            assert paused['control']['paused_before']=='search'
            print(json.dumps({'project_id':project['id'],'run_id':run['id'],'paused_before':'search'},ensure_ascii=False));return
        fixture=json.loads(FIXTURE.read_text(encoding='utf8'));project=fixture['project'];rid=fixture['run']['id']
        base='/research/api/projects/'+project['id']+'/research-flow/runs/'+rid
        report={'checks':{},'errors':[],'project_id':project['id'],'run_id':rid,'build':json.loads((DIST/'build-info.json').read_text()),'mode':args.action}
        if args.action=='candidate':
            def static(route):
                name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                if not name or name.startswith(('assets/','fonts/')):
                    target=DIST/(name or 'index.html');assert target.resolve().is_relative_to(DIST.resolve())
                    route.fulfill(status=200 if target.is_file() else 404,body=target.read_bytes() if target.is_file() else b'',content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                else:route.continue_()
            ctx.route(ORIGIN+'/research/**',static)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id'],wait_until='domcontentloaded')
        page.locator('.dp-native-shell').wait_for(timeout=60000)
        page.locator('.dp-writing-toolbar').wait_for(timeout=30000)
        report['checks']['default_is_research']=page.get_by_role('button',name='工作模式',exact=True).inner_text()=='研究对话'
        page.locator('.dp-native-shell aside').first.get_by_role('button',name='工作流',exact=True).click()
        page.get_by_role('main',name='项目工作流').wait_for()
        page.locator('[data-workflow-id="'+rid+'"]').click()
        card=page.locator('.workflow-run-detail [data-task-id="'+rid+'"]');card.wait_for()
        report['checks']['first_class_workflow_view']=True
        if card.locator('.workflow-progress').count()==0:card.locator('.task-card-toggle').click()
        control=card.locator('.workflow-progress');control.locator('summary').filter(has_text='流程与控制').click()
        control.get_by_text(fixture['request']['query'],exact=True).wait_for()
        report['checks']['original_request_visible']=True
        report['checks']['only_actual_stages']=control.locator('ol[aria-label="实际工作流阶段"]>li').count()==2
        control.locator('summary').filter(has_text='当前适用规范').click()
        control.get_by_text('规范版本：2026-11-05-stage-purpose1',exact=True).wait_for()
        report['checks']['rules_and_scope_visible']='项目记忆和历史记录不能扩大任务' in control.inner_text()
        for width,height in [(1440,960),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
            report['checks']['fits_'+str(width)]=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(OUT/f'flow-controls-{args.action}-{width}.png'))
        page.set_viewport_size({'width':1440,'height':960})
        initial=checked(ctx.request.get(ORIGIN+base+'/progress'))
        if initial['status']=='paused':
            if initial['control'].get('paused_before')=='search':
                control.get_by_role('button',name='继续原任务',exact=True).click()
                state=wait_status(ctx.request,base,'paused',before='archive')
            else:state=initial
            assert state['control']['paused_before']=='archive'
            report['checks']['real_search_completed_before_archive']=state['stages'][0]['status']=='done'
            raw=checked(ctx.request.get(ORIGIN+base))
            report['sources_returned']=len(raw['result']['sources'])
            report['search_receipt']=state['stages'][0]['receipt']
            page.reload(wait_until='domcontentloaded');page.get_by_role('main',name='项目工作流').wait_for()
            card=page.locator('.workflow-run-detail [data-task-id="'+rid+'"]');card.locator('.workflow-progress>summary').click()
            control=card.locator('.workflow-progress');control.get_by_role('button',name='继续原任务',exact=True).wait_for()
            report['checks']['reload_keeps_checkpoint']=True
            control.get_by_role('button',name='继续原任务',exact=True).click()
            final=wait_status(ctx.request,base,'completed')
            report['checks']['resume_keeps_run_and_search_receipt']=final['id']==rid and final['stages'][0]['receipt']==report['search_receipt']
        else:
            assert initial['status']=='completed',initial
            report['checks']['completed_run_preserved']=True
            live=json.loads((OUT/'flow-controls-search-live.json').read_text(encoding='utf8'))
            assert live['run_id']==rid and live['search_receipt']==initial['stages'][0]['receipt']
            report['live_resume_evidence']='flow-controls-search-live.json'
            report['checks']['prior_verified_resume_receipt_unchanged']=True
        page.locator('.workflow-tabs').get_by_role('button',name='流程说明',exact=True).click()
        page.get_by_role('heading',name='数值仿真',exact=True).wait_for()
        report['checks']['route_guide_visible']=True
        page.locator('.workflow-tabs').get_by_role('button',name='执行规范',exact=True).click()
        report['checks']['rules_view_visible']=page.get_by_role('heading',name='检查与评审',exact=True).is_visible()
        page.locator('.workflow-tabs').get_by_role('button',name='任务',exact=True).click()
        page.screenshot(path=str(OUT/f'flow-controls-{args.action}-complete.png'))
        report['passed']=all(report['checks'].values()) and not report['errors']
        (OUT/f'flow-controls-{args.action}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False));assert report['passed'],report
        browser.close()


if __name__=='__main__':main()
