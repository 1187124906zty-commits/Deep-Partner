"""Live Dify delivery/readback and same-run identity; no model or solver task."""
from pathlib import Path
import json,sys,subprocess
from verify_partner_workflow import client

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/agentic-product'
PID='64c6b5e79b824bc4bf23637e8204446c'
WS='ws_62eb9eb8014c4484913c5904d0b903dd'
SID='unified_1793859485638_2608ac3e'


def main():
    report={'project_id':PID,'checks':{}}
    with client() as c:
        context=c.get('/research/dify/api/context',params={'project_id':PID,'task':'code','workspace_id':WS});context.raise_for_status();context=context.json()
        report['checks']['actual_lazy_skill_catalog']=bool(context['skills']) and all(s.get('url') and not s.get('content') for s in context['skills'])
        content='# Agentic workflow 软件验证\n\n本文件通过真实 Dify 工作流保存并回读，验证技能按需读取接口、逐阶段回执与重复交付。此记录不表示科学结论或论文质量通过验证。\n'
        body={'request_id':'agentic-fix-live-20261105','project_id':PID,'workspace_id':WS,'session_id':SID,'task':'code','standard_version':context['standard_version'],
              'artifact':{'type':'file','path':'docs/agentic-workflow-check.md','content':content,'summary':'Dify交付链路修复验证'},'validation':[],'limitations':['软件链路验证，不是科学结果']}
        r=c.post('/research/dify/api/deliver',json=body);r.raise_for_status();saved=r.json()
        report['delivery']=saved
        (OUT/'workflow-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        assert saved['status']=='saved',saved
        assert saved.get('workflow_status')=='succeeded' and saved.get('processing_history_verified') is True,saved
        read=c.get('/research/api/projects/'+PID+'/file',params={'path':'docs/agentic-workflow-check.md'});read.raise_for_status()
        report['checks']['real_file_readback']=read.text==content
        again=c.post('/research/dify/api/deliver',json=body);again.raise_for_status()
        report['checks']['duplicate_delivery_same_run']=again.json()['run_id']==saved['run_id']
        conflict={**body,'request_id':'agentic-stale-live-20261105','artifact':{**body['artifact'],'content':'must not overwrite','expected_modified':0}}
        r=c.post('/research/dify/api/deliver',json=conflict);r.raise_for_status();rejected=r.json()
        report['stale_version']={k:rejected.get(k) for k in ('run_id','status','error')}
        report['checks']['stale_version_preserves_content']=rejected['status']=='failed' and c.get('/research/api/projects/'+PID+'/file',params={'path':body['artifact']['path']}).text==content
        original=json.loads((ROOT/'.local/partner-workflow/recovery-search.json').read_text(encoding='utf8'))
        route='/research/api/projects/'+PID+'/research-flow/runs'
        repeated=c.post(route,json=original);repeated.raise_for_status()
        report['existing_research_run']=repeated.json()
        report['checks']['existing_research_run_not_resubmitted']=repeated.json().get('duplicate') is True and repeated.json().get('status')=='completed'
        changed=c.post(route,json={**original,'query':'different query must not use the old result'})
        report['checks']['changed_request_id_rejected']=changed.status_code==409
    # Negative Dify cases exercise the real published nodes without executing a model.
    code=r'''from pathlib import Path
import json,urllib.request,subprocess
key=Path('/srv/dify-research/private/writing-key').read_text().strip();rows=[]
for stage in ['not-a-stage','intent']:
 body={'inputs':{'run_id':'agentic-missing-run','ticket':'invalid-test-ticket','stage':stage},'response_mode':'blocking','user':'agentic-product-verification'}
 request=urllib.request.Request('http://127.0.0.1:8088/v1/workflows/run',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=45) as response:value=json.load(response)
 data=value['data'];rows.append({'stage':stage,'status':data['status'],'error':str(data.get('error') or '')[-800:],'workflow_run_id':value.get('workflow_run_id')})
print(json.dumps(rows,ensure_ascii=False))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=100)
    if result.returncode:raise RuntimeError(result.stderr[-1500:])
    report['writing_rejection_runs']=json.loads(result.stdout)
    report['checks']['unknown_stage_fails_explicitly']=report['writing_rejection_runs'][0]['status']=='failed' and '未知写作阶段' in report['writing_rejection_runs'][0]['error']
    report['checks']['rejected_callback_is_not_success']=report['writing_rejection_runs'][1]['status']=='failed' and 'HTTP ' in report['writing_rejection_runs'][1]['error']
    report['passed']=all(report['checks'].values())
    (OUT/'workflow-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'checks':report['checks'],'passed':report['passed'],'delivery_run':report['delivery']['run_id'],'workflow_run':report['delivery']['workflow_run_id'],'stale_version':report['stale_version'],'writing_rejection_runs':report['writing_rejection_runs']},ensure_ascii=False))
    assert report['passed']


if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
