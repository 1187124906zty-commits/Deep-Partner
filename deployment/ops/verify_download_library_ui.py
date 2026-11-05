"""Read the real download queue, bibliography attachments and PDF in the UI."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
ORIGIN='https://tutor.example.invalid'
PID='638495c5ba024a93a305ff69b4658811'
TITLES=['On the limited memory BFGS method for large scale optimization','Adam: A method for stochastic optimization']


def main():
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    report={'checks':{},'errors':[],'model_calls':0,'project_id':PID,'mode':'published_website_real_project'}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            ctx=browser.new_context(viewport={'width':1540,'height':1000})
            assert ctx.request.post(ORIGIN+'/api/auth/login',data=account,headers={'Origin':ORIGIN}).ok
            project=next(row for row in ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'] if row['id']==PID)
            worker=ctx.request.get(ORIGIN+'/research/api/download-worker/status').json()
            report['worker']=worker;report['checks']['worker_still_online_after_native_probe_exit']=worker['online']
            page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
            page.goto(ORIGIN+'/research/?project='+PID+'&dt_workspace='+project['native_id']+'&area=literature',wait_until='domcontentloaded')
            queue=page.locator('details.download-queue');queue.wait_for(timeout=30000)
            queue.locator(':scope > summary').click()
            report['checks']['device_connected_in_ui']='本机 ScanSci 已连接' in queue.inner_text()
            for title in TITLES:
                job=queue.locator('.download-job-list article').filter(has_text=title)
                job.wait_for()
                assert '已加入文献库' in job.inner_text(),job.inner_text()
            report['checks']['both_actual_jobs_show_library_delivery']=True
            page.locator('.bibliography-table tbody tr').filter(has_text=TITLES[0]).get_by_role('button',name='阅读全文',exact=True).wait_for(timeout=20000)
            screenshot=ROOT/'reports/screenshots/download-real-completed.png'
            page.screenshot(path=str(screenshot));report['screenshot']=str(screenshot)
            search=page.get_by_role('textbox',name='搜索文献')
            for i,title in enumerate(TITLES):
                search.fill(title)
                row=page.locator('.bibliography-table tbody tr').filter(has_text=title)
                row.get_by_role('button',name='阅读全文',exact=True).wait_for(timeout=20000)
                report['checks']['bfgs_reference_has_full_text' if i==0 else 'adam_reference_has_full_text']=True
            search.fill(TITLES[0])
            page.locator('.bibliography-table tbody tr').filter(has_text=TITLES[0]).get_by_role('button',name='阅读全文',exact=True).click()
            page.locator('.local-reader .reader-page-control input').wait_for(timeout=20000)
            page.wait_for_function("document.querySelector('.reader-page-control input')?.max==='26' && Array.from(document.querySelectorAll('.local-pdf-container canvas')).some(c=>c.width>100 && c.height>100)",timeout=45000)
            report['checks']['bfgs_26_page_pdf_paints_in_reader']=True
            reader_shot=ROOT/'reports/screenshots/download-bfgs-readable.png';page.screenshot(path=str(reader_shot));report['reader_screenshot']=str(reader_shot)
            report['checks']['no_ui_script_errors']=not report['errors'];report['passed']=all(report['checks'].values());assert report['passed'],report
            browser.close()
    except Exception as e:report['passed']=False;report['failure']=str(e);raise
    finally:
        (ROOT/'reports/download-library-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
