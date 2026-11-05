"""Measure storage-to-browser task progress in an isolated, archived fixture."""
from pathlib import Path
import json,os,sys,threading,time
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,ORIGIN
from verify_workspace_interactions import static_candidate


def main():
    report={'mode':'isolated_progress_event_rehearsal','model_calls':0,'checks':{},'build':json.loads((DIST/'build-info.json').read_text())}
    project=None;owner=None;jid=None
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':950},**({'proxy':{'server':os.environ['WORKBENCH_HTTP_PROXY']}} if os.environ.get('WORKBENCH_HTTP_PROXY') else {}))
        class Client:
            def post(self,path,json=None):
                r=ctx.request.post(ORIGIN+path,data=json,headers={'Origin':ORIGIN})
                class Result:
                    def raise_for_status(self):assert r.ok
                return Result()
        login(Client());owner=ctx.request.get(ORIGIN+'/research/api/me').json()['id'];baseline=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects']
        project=ctx.request.post(ORIGIN+'/research/api/projects',data={'name':'响应速度验收 · 20261102'},headers={'Origin':ORIGIN}).json()
        try:
            inner="from server.app import store\nimport json\np=store.get(OWNER,PID)\nassert p['name']=='响应速度验收 · 20261102'\njid=store.job(OWNER,PID,'literature-metadata',{'subject':'软件进度验收'})\nprint(json.dumps({'id':jid}))".replace('OWNER',repr(owner)).replace('PID',repr(project['id']))
            outer="import subprocess\nr=subprocess.run(['docker','exec','research-workbench','python','-c',CODE],capture_output=True,text=True,check=True)\nprint(r.stdout)".replace('CODE',repr(inner))
            jid=json.loads(remote(outer,root=True))['id'];report['project_id']=project['id'];report['job_id']=jid
            ctx.route(ORIGIN+'/research/**',static_candidate);page=ctx.new_page();requests=[];page.on('request',lambda r:requests.append(r.url))
            page.goto(ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=literature',wait_until='domcontentloaded')
            page.get_by_role('button',name='查看项目任务',exact=True).wait_for(timeout=45000);page.get_by_role('button',name='查看项目任务',exact=True).click();card=page.locator('[data-task-id="'+jid+'"]');card.wait_for(timeout=15000)
            stamp='PROGRESS_STREAM_'+str(time.time_ns());result={}
            inner="from server.app import store\nimport json,time\nstore.set_job(JID,status='running',stage=STAMP)\nprint(json.dumps({'updated_at_ms':time.time()*1000}))".replace('JID',repr(jid)).replace('STAMP',repr(stamp))
            outer="import subprocess\nr=subprocess.run(['docker','exec','research-workbench','python','-c',CODE],capture_output=True,text=True,check=True)\nprint(r.stdout)".replace('CODE',repr(inner))
            def change():result.update(json.loads(remote(outer,root=True)))
            thread=threading.Thread(target=change);thread.start();card.get_by_text(stamp,exact=False).wait_for(timeout=20000);visible_ms=page.evaluate('Date.now()');thread.join(timeout=20)
            report['update_to_visible_ms']=round(visible_ms-result['updated_at_ms'],1);report['checks']['live_status_visible_without_periodic_jobs_request']=report['update_to_visible_ms']<2000 and not any(u.endswith('/jobs') for u in requests);report['jobs_stream_requests']=sum('/jobs/events' in u for u in requests)
            page.screenshot(path=str(ROOT/'reports/screenshots/live-progress-restored.png'));report['checks']['one_progress_stream']=report['jobs_stream_requests']==1
        finally:
            if jid:
                inner="from server.app import store\nstore.set_job(JID,status='completed',stage='软件进度验收完成',result={'software_verification':True})".replace('JID',repr(jid))
                outer="import subprocess\nsubprocess.run(['docker','exec','research-workbench','python','-c',CODE],check=True,capture_output=True)".replace('CODE',repr(inner));remote(outer,root=True)
            if project:
                response=ctx.request.patch(ORIGIN+'/api/settings/workspace/registrations/'+project['native_id'],data={'archived':True},headers={'Origin':ORIGIN});assert response.ok
                inner="from server.app import store\nimport json\np=store.get(OWNER,PID);assert p['name']=='响应速度验收 · 20261102'\nconfig=p['config'];config['archived']=True\nwith store.db() as db:db.execute('UPDATE projects SET config=? WHERE id=? AND owner=?',(json.dumps(config),PID,OWNER))".replace('OWNER',repr(owner)).replace('PID',repr(project['id']))
                outer="import subprocess\nsubprocess.run(['docker','exec','research-workbench','python','-c',CODE],check=True,capture_output=True)".replace('CODE',repr(inner));remote(outer,root=True)
                current=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'];assert {p['id'] for p in current}=={p['id'] for p in baseline};report['checks']['fixture_archived_and_original_projects_preserved']=True
            browser.close();report['passed']=all(report['checks'].values());(ROOT/'reports/live-progress-restored.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
