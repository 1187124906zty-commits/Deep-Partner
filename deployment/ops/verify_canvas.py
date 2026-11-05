"""Isolated browser QA; authenticate with the deployment account, never daily cookies."""
import base64
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://tutor.example.invalid'


def main():
    account=json.loads((ROOT/'.local/admin-login.json').read_text(encoding='utf-8'))
    output=ROOT/'reports/screenshots';output.mkdir(exist_ok=True)
    apps=[('联合检索','643e80d5-4c8e-4449-a692-816f8fea221d'),
        ('交付事件','587c5e8f-5df8-4b54-866d-598a582dccb4'),
        ('定时协调','185575c4-6eda-4f00-b01b-0b0f7093c018'),
        ('成果交付','5c9d68ae-3847-4774-8e94-ecbfa9543e25'),
        ('网页证据读取','2f0d0b10-0d03-4a92-89b5-f8f07a51769a')]
    report=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(viewport={'width':1800,'height':1100},device_scale_factor=1)
        response=context.request.post(ORIGIN+'/dify/console/api/login',data={'email':account['email'],
            'password':base64.b64encode(account['password'].encode()).decode(),'remember_me':True},
            headers={'Origin':ORIGIN})
        assert response.ok and response.json().get('result')=='success','Browser test account could not authenticate'
        page=context.new_page()
        failures=[];errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)[:500]))
        page.on('response',lambda r: failures.append({'path':urlsplit(r.url).path,'status':r.status}) if r.status>=400 else None)
        for name,app_id in apps:
            failures.clear();errors.clear()
            response=page.goto(ORIGIN+'/dify/app/'+app_id+'/workflow',wait_until='domcontentloaded',timeout=90000)
            page.locator('.react-flow__node').first.wait_for(timeout=60000)
            page.wait_for_timeout(1500)
            nodes=page.locator('.react-flow__node').all_inner_texts()
            assert len(nodes)>=4,(name,nodes)
            assert '/signin' not in page.url,page.url
            screenshot=output/(app_id+'.png');page.screenshot(path=str(screenshot),full_page=False)
            checklist=page.get_by_role('button',name=re.compile('检查清单')).inner_text()
            issue_count=int(re.search(r'\d+',checklist).group()) if re.search(r'\d+',checklist) else 0
            issue_details=''
            if issue_count:
                page.get_by_role('button',name=re.compile('检查清单')).click()
                issue_details=page.locator('body').inner_text().split('发布前请解决以下问题')[-1]
            report.append({'app':name,'app_id':app_id,'http_status':response.status,'nodes':nodes,
                'page_errors':list(errors),'failed_responses':list(failures),'screenshot':str(screenshot),
                'canvas_validation_issues':issue_count,'canvas_validation_details':issue_details})
        browser.close()
    (ROOT/'reports/canvas-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'app':r['app'],'nodes':len(r['nodes']),'page_errors':r['page_errors'],'failed_responses':r['failed_responses'],
        'canvas_validation_issues':r['canvas_validation_issues'],'canvas_validation_details':r['canvas_validation_details']} for r in report],ensure_ascii=False))
    assert not any(r['canvas_validation_issues'] or r['page_errors'] or r['failed_responses'] for r in report),'Canvas validation failed; see saved report'


if __name__=='__main__':main()
