"""The published project run must finish after an actual Scholar bridge outage."""
from pathlib import Path
import json,sys,time
from verify_partner_workflow import ROOT,client
from verify_tools_autorecovery import listener
sys.path.insert(0,'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
from runtime_connection import http_json,stop_owned


def main():
    pid='64c6b5e79b824bc4bf23637e8204446c'
    output=ROOT/'reports/partner-scholar-same-run-recovery.json'
    # Act immediately after a guardian cycle so the request reaches the outage.
    before=http_json('http://127.0.0.1:47908/health').get('updated')
    deadline=time.monotonic()+45
    while http_json('http://127.0.0.1:47908/health').get('updated')==before:
        if time.monotonic()>deadline:raise TimeoutError('Guardian cycle did not advance')
        time.sleep(.3)
    with client() as connection:
        previous=listener(47903);assert stop_owned(previous,'local_search_bridge.py')
        request={'kind':'search','query':'phase field reactive transport dissolution','limit':1,
                 'allow_search_fallback':False,'request_id':'scholar-outage-same-run-20261105'}
        response=connection.post('/research/api/projects/'+pid+'/research-flow/runs',json=request);response.raise_for_status();started=response.json()
        report={'run_id':started['id'],'request_id':request['request_id'],'manual_restore_called':False,'manual_resume_called':False,'samples':[]}
        end=time.monotonic()+180
        while True:
            response=connection.get('/research/api/projects/'+pid+'/research-flow/runs/'+started['id']);response.raise_for_status();row=response.json()
            report['samples'].append({'status':row['status'],'stage':row['stage'],'recovery':row['result'].get('recovery')})
            report['run']=row;output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            assert row['status'] not in ('failed','cancelled','waiting_input'),row.get('error')
            if row['status']=='completed':break
            if time.monotonic()>end:raise TimeoutError('Same project run did not resume automatically')
            time.sleep(3)
        assert any(sample['recovery'] for sample in report['samples']),'The request never observed the injected outage'
        assert any(f['code']=='bridge_transport_error' for f in row['result'].get('failures',[]))
        assert row['result']['sources'] and row['result']['searches'][-1]['provider']=='scholar_mcp'
        assert all(r['provider']=='scholar_mcp' for r in row['result']['searches'])
        report['same_run_auto_completed']=True
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'run_id':row['id'],'same_run_auto_completed':True,'manual_resume_called':False,'sources':len(row['result']['sources'])},ensure_ascii=False))


if __name__=='__main__':main()
