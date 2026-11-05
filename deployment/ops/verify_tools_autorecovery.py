"""Real failures of owned idle services; the guardian must repair them unaided."""
from pathlib import Path
import json,subprocess,sys,time
SCRIPTS=Path('C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
sys.path.insert(0,str(SCRIPTS))
from runtime_connection import http_json,remote_http_ready,stop_owned
ROOT=Path(__file__).resolve().parents[1]
HOME=Path('C:/Users/DEVELOPER/.codex')
REPORT=ROOT/'reports/partner-tool-autorecovery-live.json'


def wait(check,limit=70):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        try:
            result=check()
            if result:return result
        except (OSError,ValueError):pass
        time.sleep(1)
    raise TimeoutError('Independent guardian did not restore the owned service')


def listener(port):
    script='(Get-NetTCPConnection -LocalPort '+str(port)+' -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique'
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=8)
    values=result.stdout.strip().splitlines()
    return int(values[0]) if values else None


def main():
    report={'tests':[],'all_passed':False,'repair_invoked_by_test':False}
    def record(name,started,previous,current):
        report['tests'].append({'name':name,'passed':True,'seconds':round(time.monotonic()-started,2),'previous_pid':previous,'restored_pid':current})
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report['tests'][-1]),flush=True)

    tunnel_path=HOME/'workbench-search/tunnel-state.json'
    previous=json.loads(tunnel_path.read_text())['pid'];started=time.monotonic()
    assert stop_owned(previous,'127.0.0.1:47903:127.0.0.1:47903')
    def restored_tunnel():
        current=json.loads(tunnel_path.read_text())['pid']
        return current if current!=previous and remote_http_ready(47903) else None
    current=wait(restored_tunnel);record('scholar reverse tunnel restored',started,previous,current)

    previous=listener(47903);started=time.monotonic();assert stop_owned(previous,'local_search_bridge.py')
    def restored_scholar():
        value=http_json('http://127.0.0.1:47903/health');current=listener(47903)
        return current if value.get('ok') and current!=previous else None
    current=wait(restored_scholar);record('scholar bridge process restored',started,previous,current)

    status_path=HOME/'workbench-download/worker.status.json'
    status=json.loads(status_path.read_text());assert status['state']=='idle' and status.get('job_id') is None,'Do not interrupt an active download'
    previous=status['pid'];started=time.monotonic();assert stop_owned(previous,'download_worker.py')
    def restored_download():
        current=json.loads(status_path.read_text())
        return current['pid'] if current['pid']!=previous and current.get('runtime_revision')=='automatic-recovery-1' and time.time()-current['heartbeat']<30 else None
    current=wait(restored_download);record('paired ScanSci worker restored',started,previous,current)

    previous=http_json('http://127.0.0.1:47908/health')['pid'];started=time.monotonic();assert stop_owned(previous,'runtime_supervisor.py')
    current=wait(lambda:(lambda d:d['pid'] if d['pid']!=previous else None)(http_json('http://127.0.0.1:47908/health')))
    record('independent supervisor restored by tool bridge',started,previous,current)

    folder=HOME/'deep-partner/tool-runtime/jobs';identities={}
    for path in folder.glob('*.json'):
        state=json.loads(path.read_text())
        if state['status'] in ('running','queued','recovering'):
            identity=state.get('native_turn_id') or state.get('workflow_run_id') or state.get('cluster',{}).get('job_id')
            assert identity,'Every active operation must have a durable external identity before test'
            identities[state['id']]=identity
    previous=http_json('http://127.0.0.1:47906/health')['pid'];started=time.monotonic();assert stop_owned(previous,'tool_runtime.py')
    current=wait(lambda:(lambda d:d['pid'] if d['pid']!=previous and d.get('runtime_revision')=='automatic-recovery-1' else None)(http_json('http://127.0.0.1:47906/health')))
    for jid,identity in identities.items():
        state=json.loads((folder/(jid+'.json')).read_text())
        actual=state.get('native_turn_id') or state.get('workflow_run_id') or state.get('cluster',{}).get('job_id')
        assert actual==identity,'Recovery must not create another external execution'
    record('tool bridge restored with original external identities',started,previous,current)
    report['preserved_external_identities']=identities
    report['all_passed']=True
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
