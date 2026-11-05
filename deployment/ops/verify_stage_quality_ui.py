"""Read-only browser checks with a fresh native API sign-in."""
from pathlib import Path
import argparse
import json
import re
import subprocess
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://tutor.example.invalid'
STAGES=['ingestion','idea','landscape','concept','evidence','code','figure','writing','translation','slides-plan','slides-export','review','delivery']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project-id');args=parser.parse_args()
    result=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True)
    account=json.loads(result.stdout)
    output=ROOT/'reports/screenshots';output.mkdir(exist_ok=True)
    report={'read_only':True,'fresh_api_login':True,'api':{},'screenshots':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(viewport={'width':1680,'height':1060},device_scale_factor=1)
        login=context.request.post(ORIGIN+'/api/auth/login',data={'username':account['username'],'password':account['password']},headers={'Origin':ORIGIN})
        assert login.ok, 'Native API sign-in failed'
        settings_response=context.request.get(ORIGIN+'/research/api/api-settings')
        assert settings_response.ok, 'Model settings endpoint failed'
        settings=settings_response.json()
        assert not any(settings.get(k) for k in ['api_key','reviewer_api_key']), 'Secret returned by settings read'
        report['api']['reviewer_mode']=settings.get('reviewer_mode','inherit')
        report['api']['rubrics']={}
        for stage in STAGES:
            response=context.request.get(ORIGIN+'/research/api/quality/rubric?stage='+stage+('&purpose=group' if stage.startswith('slides-') else ''))
            assert response.ok, 'Rubric endpoint failed: '+stage
            value=response.json()
            report['api']['rubrics'][stage]={'version':value['version'],'dimensions':len(value.get('dimensions',[]))}
        response=context.request.get(ORIGIN+'/research/api/projects')
        assert response.ok,'Project listing failed'
        projects=response.json()['projects'];assert projects,'No project available for read-only UI'
        project=next(x for x in projects if x['id']==args.project_id) if args.project_id else next((x for x in projects if 'qa' in x['name'].lower() or '验收' in x['name']),projects[0])
        pid=project['id'];report['project_id']=pid
        gate=context.request.get(ORIGIN+'/research/api/projects/'+pid+'/quality/gate?stage=slides-plan&purpose=group')
        assert gate.ok,'Current-version gate unavailable: '+gate.text()[:300]
        report['api']['gate']=gate.json()
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)[:500]))
        page.goto(ORIGIN+'/research/?project='+pid,wait_until='domcontentloaded',timeout=60000)
        page.get_by_role('button',name='工作台设置',exact=True).first.click(timeout=30000)
        dialog=page.get_by_role('dialog')
        dialog.get_by_role('button',name='模型与检索',exact=True).click()
        selector=dialog.get_by_label('评审模型来源',exact=True)
        assert selector.input_value()==settings.get('reviewer_mode','inherit')
        selector.select_option('custom')
        for label in ['评审 API 地址','评审模型名称','评审 API Key']:
            assert dialog.get_by_label(label,exact=True).is_visible(),label
        dialog.get_by_label('评审 API 地址',exact=True).scroll_into_view_if_needed()
        screenshot=output/'quality-reviewer-desktop.png';page.screenshot(path=str(screenshot));report['screenshots'].append(str(screenshot))
        selector.select_option(settings.get('reviewer_mode','inherit'))
        dialog.get_by_role('button',name='阶段评分',exact=True).click()
        (ROOT/'reports/quality-ui-debug.txt').write_text(dialog.inner_text(),encoding='utf8')
        page.screenshot(path=str(output/'quality-debug.png'))
        stage_select=dialog.get_by_role('combobox',name=re.compile('^当前阶段'))
        expect(stage_select.locator('option')).to_have_count(13)
        if args.project_id:
            stage_select.select_option('ingestion')
            expect(dialog.locator('.quality-result h4')).to_have_text('满足当前阶段要求')
            expect(dialog.locator('.quality-result > article')).to_have_count(4)
            assert dialog.locator('.quality-result > p').first.inner_text().startswith('75')
            screenshot=output/'quality-real-ingestion-desktop.png';page.screenshot(path=str(screenshot));report['screenshots'].append(str(screenshot))
            report['actual_ingestion_review_displayed']=True
        stage_select.select_option('slides-plan')
        purposes=dialog.get_by_role('combobox',name=re.compile('^汇报用途'))
        expect(purposes.locator('option')).to_have_count(6)
        assert dialog.get_by_role('button',name='评审当前产物',exact=True).is_visible()
        screenshot=output/'quality-stage-desktop.png';page.screenshot(path=str(screenshot));report['screenshots'].append(str(screenshot))
        page.set_viewport_size({'width':390,'height':844})
        screenshot=output/'quality-stage-mobile.png';page.screenshot(path=str(screenshot));report['screenshots'].append(str(screenshot))
        report['mobile_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not report['mobile_horizontal_overflow'],'Mobile viewport horizontally overflows'
        assert not errors,errors
        report['page_errors']=errors
        report['ui']={'stage_count':13,'purpose_count':6,'custom_reviewer_fields_visible':True,'settings_saved':False}
        browser.close()
    (ROOT/'reports/quality-production-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
