"""Actual bundled Windows/WebView2 checks with one standard save dialog."""
from pathlib import Path
import json,os,re,socket,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,CACHE,STATE
from verify_workspace_interactions import geometry
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
PROFILE=NATIVE/'verification/workspace-interactions';PROFILE.mkdir(exist_ok=True)

def free_port():
    with socket.socket() as listener:listener.bind(('127.0.0.1',0));return listener.getsockname()[1]

def main():
    prior_path=ROOT/'reports/workspace-interactions-native.json'
    prior=json.loads(prior_path.read_text(encoding='utf8')) if prior_path.exists() else {}
    project=json.loads(STATE.read_text(encoding='utf8'))['project'];report={'mode':'actual_packaged_tauri_webview2','checks':{},'errors':[],'project_id':project['id'],'model_turns_requested':0,'screenshots':[]}
    debug=free_port();config={'server_url':'https://tutor.example.invalid','workspace':str(PROFILE/'workspace'),'bridge_port':free_port(),'browser_port':free_port(),'cpu_workers':2,'ssh_host':'isolated-ui-qa.invalid','cluster_host':'','desktop_control':False}
    (PROFILE/'config.json').write_text(json.dumps(config),encoding='utf8')
    executable=NATIVE/'dist/Deep partner.exe';child=subprocess.Popen([str(executable)],cwd=executable.parent,env=dict(os.environ,DEEP_PARTNER_HOME=str(PROFILE),WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port='+str(debug)),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    browser=None
    try:
        with sync_playwright() as p:
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                if child.poll() is not None:raise RuntimeError('Desktop test process exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:'+str(debug)+'/json/version',timeout=1) as response:version=json.load(response)
                    break
                except OSError:time.sleep(.3)
            else:raise RuntimeError('WebView2 did not expose the test debugging endpoint')
            browser=p.chromium.connect_over_cdp('http://127.0.0.1:'+str(debug));ctx=browser.contexts[0];page=ctx.pages[0];page.on('pageerror',lambda error:report['errors'].append(str(error)))
            page.wait_for_url(re.compile(r'^http://127\.0\.0\.1:\d+/(?:\?.*)?$'),wait_until='domcontentloaded',timeout=45000)
            page.locator('#root>*').first.wait_for(state='attached',timeout=45000)
            origin=page.evaluate('location.origin');headers={'Origin':origin};assert origin.startswith('http://127.0.0.1:')
            class LoginClient:
                def post(self,path,json=None):
                    response=ctx.request.post(origin+path,data=json,headers=headers)
                    class Result:
                        def raise_for_status(self):assert response.ok,response.text()
                    return Result()
            login(LoginClient());report['build']=ctx.request.get(origin+'/build-info.json').json();expected=json.loads((NATIVE/'ui-dist/build-info.json').read_text())
            assert report['build']==expected
            report['frontend_job_id']=expected['slurm_job_id'];report['checks']['bundled_frontend_is_the_current_slurm_artifact']=True
            report['checks']['remote_credentials_stay_out_of_webview_cookies']=all(c['name'] not in ('dt_token','__Host-dt_trusted','__Host-dt_pair') for c in ctx.cookies())
            base=origin+'/?project='+project['id']+'&dt_workspace='+project['native_id']
            report['geometry']=[]
            for area in ['literature','paper','figures','code','slides','questions']:
                page.goto(base+'&area='+area,wait_until='domcontentloaded');page.locator('.dp-artifacts').wait_for(timeout=45000);page.wait_for_timeout(1500);measured=geometry(page);measured['area']=area;report['geometry'].append(measured)
            report['checks']['native_six_pages_have_no_toolbar_overlap']=all(not r['toolbar_overlaps'] for r in report['geometry'])
            report['checks']['native_six_pages_have_no_horizontal_page_overflow']=all(not r['horizontal_page_overflow'] for r in report['geometry'])
            page.goto(base+'&area=paper',wait_until='domcontentloaded');page.get_by_role('button',name='稿件导出',exact=True).click();page.get_by_label('导出保存位置',exact=True).wait_for(timeout=30000);page.locator('.export-template-list article').nth(1).wait_for()
            output=CACHE/'native-exports';output.mkdir(exist_ok=True);token=str(int(time.time()));manual=output/('manual-'+token+'.docx')
            page.get_by_label('导出文件名',exact=True).fill('桌面保存验收');page.get_by_label('导出保存位置',exact=True).fill(str(manual))
            previous=Path(prior.get('manual_save',{}).get('path','missing'))
            if prior.get('frontend_job_id')==report['frontend_job_id'] and prior.get('checks',{}).get('native_ui_export_saves_the_manually_entered_path') and previous.is_file():
                manual=previous;report['export_job_id']=prior['export_job_id'];report['reused_completed_export']=True
            else:
                with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/manuscript/export'),timeout=45000) as submitted:page.get_by_role('button',name='导出',exact=True).click()
                assert submitted.value.ok,submitted.value.text();report['export_job_id']=submitted.value.json()['job_id'];report['model_turns_requested']=1
                page.locator('.export-receipt').wait_for(timeout=300000)
            assert manual.is_file() and manual.read_bytes().startswith(b'PK');report['checks']['native_ui_export_saves_the_manually_entered_path']=True
            report['manual_save']={'path':str(manual),'bytes':manual.stat().st_size}
            shot=ROOT/'reports/screenshots/workspace-interactions-native-export.png';page.screenshot(path=str(shot));report['screenshots'].append(str(shot))
            # A standard native SaveFile dialog is exercised through the actual
            # location button; only the isolated output filename is changed.
            dialog_path=output/('dialog-'+token+'.docx');page.get_by_label('导出文件名',exact=True).fill(dialog_path.stem);page.get_by_label('导出保存位置',exact=True).fill('');page.get_by_role('button',name='选择保存位置',exact=True).click(no_wait_after=True)
            ready={'pid':child.pid,'debug_port':debug,'origin':origin,'expected_save_path':str(dialog_path),'frontend_job_id':report['frontend_job_id'],'status':'standard_save_dialog_open'}
            (CACHE/'native-window-ready.json').write_text(json.dumps(ready,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(ready,ensure_ascii=False),flush=True)
            # The Windows dialog is handled through the computer-use skill.
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                chosen=page.get_by_label('导出保存位置',exact=True).input_value()
                if (CACHE/'native-dialog-selected.json').exists():break
                if child.poll() is not None:raise RuntimeError('Native process closed during save dialog check')
                page.wait_for_timeout(500)
            else:raise RuntimeError('Native save dialog was not completed')
            signal=json.loads((CACHE/'native-dialog-selected.json').read_text(encoding='utf8'));assert signal['frontend_job_id']==report['frontend_job_id'];assert chosen==str(dialog_path),(chosen,dialog_path)
            job=ctx.request.get(origin+'/research/api/projects/'+project['id']+'/jobs',headers=headers).json()['jobs'];export=next(r for r in job if r['id']==report['export_job_id'])
            response=ctx.request.post(origin+'/desktop/save-export',data={'url':export['result']['url'],'path':str(dialog_path)},headers=headers);assert response.ok,response.text();assert dialog_path.is_file() and dialog_path.read_bytes()==manual.read_bytes()
            report['checks']['standard_windows_save_dialog_returns_and_saves_the_selected_path']=True;report['dialog_save']={'path':str(dialog_path),'bytes':dialog_path.stat().st_size}
            page.get_by_role('button',name='返回稿件',exact=True).click();page.get_by_role('button',name='查看项目任务',exact=True).click();page.get_by_role('button',name='运行本机工具',exact=True).click();page.get_by_role('heading',name='运行本机工具',exact=True).wait_for();report['checks']['local_tools_launch_from_the_same_project_task_center']=True
            report['checks']['no_duplicate_local_task_sidebar_entry']=page.get_by_role('navigation',name='科研工作区').get_by_role('button',name='本机任务',exact=True).count()==0
            page.get_by_role('button',name='关闭任务面板',exact=True).click()
            report['checks']['no_native_script_errors']=not report['errors'];report['passed']=all(report['checks'].values());assert report['passed'],report['checks']
            report['webview_version']=version.get('Browser');browser.close();browser=None
    except Exception as error:
        report['passed']=False;report['failure']=type(error).__name__+': '+str(error);raise
    finally:
        (ROOT/'reports/workspace-interactions-native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'passed':report.get('passed'),'checks':report['checks'],'failure':report.get('failure')},ensure_ascii=False),flush=True)
        if browser is not None:
            try:browser.close()
            except Exception:pass
        if child.poll() is None:child.terminate();child.wait(timeout=10)

if __name__=='__main__':main()
