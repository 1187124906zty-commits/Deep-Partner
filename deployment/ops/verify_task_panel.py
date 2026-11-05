"""Exercise task cards against durable API data and actual import results."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,json,mimetypes,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from task_panel_fixture import update,attach_output,FIXTURE
ORIGIN='https://tutor.example.invalid'

def exercise(ctx,page,origin,fixture,report,mode):
    initial_viewport=page.viewport_size or page.evaluate('({width:innerWidth,height:innerHeight})')
    project=fixture['project'];entry='/research/' if origin==ORIGIN else '/'
    href=origin+entry+'?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=files'
    page.goto(href,wait_until='domcontentloaded');trigger=page.get_by_role('button',name='查看项目任务',exact=True);trigger.wait_for(timeout=30000);trigger.click()
    panel=page.get_by_role('dialog',name='项目任务');panel.wait_for()
    report['checks']['compact_nonmodal_panel']=panel.get_attribute('aria-modal')=='false' and page.locator('.modal-backdrop:visible').count()==0
    running=panel.locator('[data-task-id="'+fixture['running']+'"]')
    assert running.count()==1
    report['checks']['specific_title_and_language']='水分扩散讨论稿' in running.inner_text() and '英文' in running.inner_text()
    report['checks']['titles_wrap_instead_of_clipping']=running.locator('.task-card-identity>strong').evaluate("element=>getComputedStyle(element).whiteSpace==='normal'")
    report['checks']['real_counter_shown']=running.locator('progress').get_attribute('value')=='12' and running.locator('progress').get_attribute('max')=='30'
    report['checks']['current_step_shown']=running.locator('[aria-current="step"]').inner_text().endswith('翻译段落')
    panel.get_by_role('button',name='全部',exact=False).click()
    for jid in fixture['imports']:
        card=panel.locator('[data-task-id="'+jid+'"]');assert card.count()==1
        card.get_by_role('button',expanded=False).first.click()
        assert card.locator('[data-state="done"]').count()==4
    report['checks']['same_type_runs_have_independent_named_cards']=all(name in panel.inner_text() for name in ['源程序与数据.zip','仿真图表.zip']) and panel.locator('[data-task-id]').count()==4
    failed=panel.locator('[data-task-id="'+fixture['failed']+'"]')
    report['checks']['failure_keeps_future_steps_pending']=failed.locator('[aria-current="step"]').get_attribute('data-state')=='failed' and failed.locator('[data-state="pending"]').count()==3 and failed.get_by_role('alert').count()==1
    for theme in ['snow','light','dark','glass']:
        page.evaluate("theme=>{document.documentElement.classList.remove('dark','theme-snow','theme-glass');if(theme==='dark')document.documentElement.classList.add('dark');else if(theme!=='light')document.documentElement.classList.add('theme-'+theme);document.documentElement.dataset.tutorTheme=theme}",theme)
        page.wait_for_timeout(100)
        page.screenshot(path=str(ROOT/f'reports/screenshots/task-panel-{mode}-{theme}.png'))
    bounds=panel.bounding_box();report['panel_bounds']=bounds
    report['checks']['panel_uses_content_height']=bounds['width']<=545 and bounds['height']<initial_viewport['height']-50 and bounds['x']>initial_viewport['width']/2
    update('advance')
    page.wait_for_function("id=>document.querySelector('[data-task-id=\"'+id+'\"] [aria-current=step]')?.textContent.includes('核对版本')",arg=fixture['running'],timeout=20000)
    report['checks']['polling_moves_current_step']=running.locator('[data-state="done"]').count()==1 and running.locator('progress').count()==0
    page.reload(wait_until='domcontentloaded');page.get_by_role('button',name='查看项目任务',exact=True).click();panel=page.get_by_role('dialog',name='项目任务')
    running=panel.locator('[data-task-id="'+fixture['running']+'"]')
    report['checks']['reload_preserves_current_step']='核对版本' in running.locator('[aria-current="step"]').inner_text()
    update('finish')
    page.wait_for_timeout(3200);panel.get_by_role('button',name='已完成',exact=False).click()
    running=panel.locator('[data-task-id="'+fixture['running']+'"]');running.wait_for()
    report['checks']['completion_keeps_distinct_card']=running.locator('.task-state').inner_text()=='已完成'
    panel.get_by_role('button',name='全部',exact=False).click()
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
    bounds=panel.bounding_box();report['mobile_bounds']=bounds
    report['checks']['mobile_fits']=bounds['x']>=0 and bounds['x']+bounds['width']<=391 and not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    page.screenshot(path=str(ROOT/f'reports/screenshots/task-panel-{mode}-mobile.png'))
    page.keyboard.press('Escape');report['checks']['escape_closes_panel']=panel.count()==0
    page.set_viewport_size(initial_viewport);page.get_by_role('button',name='查看项目任务',exact=True).click()
    panel=page.get_by_role('dialog',name='项目任务');panel.get_by_role('button',name='全部',exact=False).click()
    imported=panel.locator('[data-task-id="'+fixture['imports'][0]+'"]')
    imported.get_by_role('button',expanded=False).first.click();imported.get_by_role('button',name='输入说明.md',exact=True).click()
    page.locator('.dt-viewer-panel[data-open="true"]').get_by_text('实际导入验收',exact=True).wait_for(timeout=20000)
    report['checks']['task_artifact_opens_native_viewer']=panel.count()==0
    page.screenshot(path=str(ROOT/f'reports/screenshots/task-panel-{mode}-artifact.png'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args();mode='published' if args.published else 'candidate'
    fixture=json.loads(FIXTURE.read_text(encoding='utf8'));attach_output();update('reset')
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    report={'checks':{},'errors':[],'frontend_job_id':json.loads((DIST/'build-info.json').read_text())['slurm_job_id'],'mode':mode,'evidence_scope':fixture['evidence_scope'],'model_calls':0}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            ctx=browser.new_context(viewport={'width':1440,'height':980});assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
            if not args.published:
                def static(route):
                    name=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
                    if not name or name.startswith(('assets/','fonts/')):
                        file=DIST/('index.html' if not name else name);assert file.resolve().is_relative_to(DIST.resolve())
                        route.fulfill(status=200 if file.is_file() else 404,body=file.read_bytes() if file.is_file() else b'',content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                    else:route.continue_()
                ctx.route(ORIGIN+'/research/**',static)
            page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
            try:exercise(ctx,page,ORIGIN,fixture,report,mode)
            except Exception:
                report['body']=page.locator('body').inner_text();page.screenshot(path=str(ROOT/f'reports/screenshots/task-panel-{mode}-failure.png'));raise
            report['checks']['no_script_errors']=not report['errors'];report['passed']=all(report['checks'].values())
            browser.close()
    except Exception as e:report['passed']=False;report['failure']=str(e);raise
    finally:
        (ROOT/f'reports/task-panel-{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));update('close')
    assert report['passed']

if __name__=='__main__':main()
