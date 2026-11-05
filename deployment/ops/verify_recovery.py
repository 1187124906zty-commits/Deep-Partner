"""Real worker outage and adapter restart in the isolated verification project."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

sys.path.insert(0,str(Path(__file__).parent))
import verify_intensive as v

ROOT=Path('/srv/dify-research')


def wait_bridge():
    for attempt in range(30):
        try:
            if urllib.request.urlopen('http://127.0.0.1:47910/health',timeout=2).status==200:return
        except OSError:pass
        time.sleep(1)
    raise RuntimeError('Adapter did not become ready after restart')


def main():
    wait_bridge()
    account=json.loads(Path('/srv/deeptutor/migration/admin-login.json').read_text())
    request=urllib.request.Request('http://127.0.0.1:8008/api/auth/login',method='POST',headers={'Content-Type':'application/json'},data=json.dumps(account).encode())
    v.login.open(request,timeout=20).close();v.cookie='; '.join(c.name+'='+c.value for c in v.jar)
    project=next(p for p in v.call('GET','/research/api/projects')['projects'] if p['name']=='Dify 部署与交付验证')
    pid=project['id'];prefix='/research/api/projects/'+pid
    context=v.call('GET','/research/dify/api/context?project_id='+pid+'&task=review')
    content='# 重启与回调恢复验证\n\n这份文件用于软件集成测试，不是科学结论。\n'
    body={'request_id':'recovery-'+uuid.uuid4().hex,'project_id':pid,'workspace_id':project['native_id'],
        'session_id':'recovery-verification','task':'review','standard_version':context['standard_version'],
        'artifact':{'type':'file','path':'docs/recovery-proof.md','content':content,'summary':'验证工作队列停顿、适配器重启及交付不重复'}}
    with sqlite3.connect(ROOT/'state/deliveries.sqlite3') as db:
        evidence_run=db.execute("SELECT id FROM evidence_runs WHERE state='ready' ORDER BY created DESC LIMIT 1").fetchone()[0]
    evidence_before=v.call('GET','/research/dify/api/evidence/'+evidence_run)
    paused=False
    try:
        subprocess.run(['docker','pause','dify-research-worker-1'],check=True,stdout=subprocess.DEVNULL);paused=True
        saved=v.call('POST','/research/dify/api/deliver',body)
        assert saved['status']=='saved' and saved['workflow_status']=='succeeded',saved
        assert json.loads(subprocess.check_output(['docker','inspect','dify-research-worker-1']))[0]['State']['Paused'],'Worker unexpectedly resumed before the save check'
        run_id=saved['run_id']
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            status=v.call('GET','/research/dify/api/runs/'+run_id)
            if status['automation']['state']=='dispatched':break
            time.sleep(.5)
        assert status['automation']['state']=='dispatched',status['automation']
        assert v.call('GET',prefix+'/file?path=docs/recovery-proof.md')==content
        subprocess.run(['docker','restart','dify-workbench-bridge'],check=True,stdout=subprocess.DEVNULL)
        wait_bridge()
        after_restart=v.call('GET','/research/dify/api/runs/'+run_id)
        assert after_restart['status']=='saved' and after_restart['artifact']==saved['artifact']
        assert after_restart['automation']['state'] in {'queued','dispatched'}
        assert v.call('GET','/research/dify/api/evidence/'+evidence_run)==evidence_before
        repeated=v.call('POST','/research/dify/api/deliver',body)
        assert repeated['run_id']==run_id and repeated['artifact']==saved['artifact']
    finally:
        if paused and json.loads(subprocess.check_output(['docker','inspect','dify-research-worker-1']))[0]['State']['Paused']:
            subprocess.run(['docker','unpause','dify-research-worker-1'],check=True,stdout=subprocess.DEVNULL)
    deadline=time.monotonic()+50
    while time.monotonic()<deadline:
        status=v.call('GET','/research/dify/api/runs/'+run_id)
        if status['automation']['state']=='completed':break
        time.sleep(1)
    assert status['automation']['state']=='completed' and status['automation']['result']['outcome']=='delivered',status
    history=v.call('GET',prefix+'/review-history')
    matches=[e for e in history.get('events',[]) if e.get('kind')=='agent.receipt'
        and all(e.get('payload',{}).get(k)==saved['receipt'].get(k) for k in ('created','artifacts','validation'))]
    assert len(matches)==1,len(matches)
    with sqlite3.connect(ROOT/'state/deliveries.sqlite3') as db:
        events=db.execute('SELECT count(*) FROM automation_events WHERE run_id=?',(run_id,)).fetchone()[0]
    assert events==1,events
    report={'verified':True,'run_id':run_id,'evidence_run_id':evidence_run,'project_id':pid,
        'checks':{'saved_while_trigger_worker_paused':True,'webhook_acceptance_not_completion':True,
            'queue_survived_adapter_restart':True,'evidence_survived_restart':True,'same_request_reused_after_restart':True,
            'callback_completed_after_worker_resumed':True,'single_native_receipt':True,'single_durable_event':True},
        'automation':status['automation'],'scope':'真实暂停仅限 Dify 触发工作进程；始终在finally恢复。未停止Code或正式研究任务。'}
    (ROOT/'reports/recovery-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
