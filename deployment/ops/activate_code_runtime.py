"""Refresh only the tool bridge after verifying durable external task identities."""
from pathlib import Path
import json,sys,time

SCRIPTS=Path.home()/'.codex/skills/deep-partner-research/scripts'
sys.path.insert(0,str(SCRIPTS))
from runtime_connection import http_json,stop_owned
from tool_runtime import ROOT,ensure


def main():
    before={}
    for path in (ROOT/'jobs').glob('*.json'):
        state=json.loads(path.read_text(encoding='utf8'))
        if state['status'] not in ('queued','running','recovering','waiting_input'):continue
        operation=state['payload'].get('operation')
        if state['status']=='running':
            if operation=='simulate':
                assert (state.get('cluster') or {}).get('submission')=='submitted' and state['cluster'].get('job_id'), 'Keep bridge alive during cluster submission'
            elif operation=='parse_pdf':
                raise RuntimeError('Keep bridge alive until current parser operation finishes')
            else:
                assert state.get('workflow_run_id') or state.get('native_turn_id'),'Keep bridge alive during native admission'
        before[state['id']]={k:state.get(k) for k in ('workflow_run_id','native_turn_id')}
        if state.get('cluster'):before[state['id']]['job_id']=state['cluster'].get('job_id')
    health=http_json('http://127.0.0.1:47906/health')
    if health.get('runtime_revision')!='stage-code-1':
        assert stop_owned(health['pid'],'tool_runtime.py'),'Owned bridge process was not stopped'
        for _ in range(30):
            try:http_json('http://127.0.0.1:47906/health')
            except OSError:break
            time.sleep(.1)
        result=ensure();assert result.get('ready'),result
    health=http_json('http://127.0.0.1:47906/health');assert health['runtime_revision']=='stage-code-1'
    for jid,identities in before.items():
        current=json.loads((ROOT/'jobs'/(jid+'.json')).read_text(encoding='utf8'))
        for key,value in identities.items():
            actual=(current.get('cluster') or {}).get(key) if key=='job_id' else current.get(key)
            assert actual==value,'External execution identity changed: '+jid
    result={'activated':True,'revision':health['runtime_revision'],'preserved_operations':before,
            'restarted':['tool_runtime.py'],'native_or_cluster_processes_restarted':False}
    path=Path(__file__).resolve().parents[1]/'reports/code-runtime-release.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
