"""Verify real research provenance, then exercise corrections on isolated copies."""
from pathlib import Path
from copy import deepcopy
import argparse,asyncio,json,subprocess,sys,time
import httpx
from verify_partner_workflow import client
from publish_agentic_fixes import remote,ROOT,OUT

CASES={
 'chloride':{'project':'1ea03384007d4bb9b88d43e3368099f3','name':'验收 · 氯硫真实研究路径','task':'bnn-identification',
  'paths':['research/STATE.md','coupled-research-collection/materials/chloride-sulfate-3d-bayes-phasefield/results/delivery/建模结果报告.md'],
  'records':[],
  'request':'请回查当前项目的研究状态与建模结果报告，纠正参数辨识任务的表述：浓度拟合或局部最后层后验近似不能自动说明参数已可辨识，也不能直接称为完整贝叶斯神经网络采样。请根据原始报告，更新bnn-identification任务的已有认识与下一步；保留实际数值、条件和不确定处，不改变主线或提交新计算。'},
 'hydration':{'project':'2f8ed851ef2744d9a248a4dca6e9133e','name':'验收 · 水化真实研究路径','task':'interpret-3d',
  'paths':['docs/native100-production-20261105/production-report.md','docs/native100-production-20261105/validation/review.md','results/simulations/a19e004dcc1c4a16998092ec9bf58f2c/result.json','code/native100-warm-20261105/run-pf100-existing.py','code/native100-independent-20261105/check_saved_pf.py'],
  'records':['finding:native100-pf-accepted-initiation','finding:native100-saved-state-independent','limitation:native100-initiation-only'],
  'request':'请回查当前项目的三维生产报告、独立核验和保存结果。已有起裂态与保存场核验不能自动称为完整峰后曲线或完成二维同相图比较。请把该边界补入finding:native100-pf-accepted-initiation的detail，并更新interpret-3d任务的已有认识与下一步。保留真实工况、实际范围和原始回执，不改变主线、不提交新Slurm任务。'}
}


def prepare():
    report={'cases':{},'checks':{}};spec=[]
    with client() as c:
        saved=OUT/'research-path-fixtures.json';fixtures=json.loads(saved.read_text(encoding='utf8')) if saved.exists() else {}
        for key,case in CASES.items():
            pid=case['project'];prefix='/research/api/projects/'+pid
            o=c.get(prefix+'/research-outline');o.raise_for_status();outline=o.json();document=outline['active'] or outline['draft']
            g=c.get(prefix+'/research-flow/graph?limit=2000');g.raise_for_status();data=g.json()
            files=[]
            for path in case['paths']:
                r=c.get(prefix+'/file',params={'path':path});r.raise_for_status()
                files.append({'path':path,'bytes':len(r.content),'read':True})
            linked=list(dict.fromkeys(j for group in document['outline'] for task in group['tasks'] for j in task['job_ids']))
            jobs=c.get(prefix+'/jobs').json();jobs=jobs.get('jobs',jobs) if isinstance(jobs,dict) else jobs
            by_id={j['id']:j for j in jobs};actual=[by_id[j] for j in linked if j in by_id]
            report['cases'][key]={'source_project':pid,'mainline':document['mainline'],'main_tasks':len(document['outline']),
                'detail_tasks':sum(len(g['tasks']) for g in document['outline']),'sources':files,'retrieval':document['retrieval'],
                'linked_jobs':[{'id':j['id'],'kind':j['kind'],'status':j['status'],'stage':j.get('stage'),'result_keys':list((j.get('result') or {}).keys())} for j in actual]}
            report['checks'][key+'_actual_sources_read']=all(f['read'] for f in files)
            report['checks'][key+'_owned_job_links']=len(actual)==len(linked)
            report['checks'][key+'_proposal_not_auto_adopted']=outline['active'] is None
            if key=='chloride':report['checks']['chloride_real_rag_and_conversation']=any(r.get('knowledge_base') and r.get('source_count',0)>0 for r in document['retrieval']) and bool(document['coverage']['conversations'])
            if key=='hydration':
                runs=[j for j in actual if j['kind']=='simulation']
                report['checks']['hydration_has_real_simulation_and_code']=bool(runs) and all((j['result'].get('simulation_request') or {}).get('input_paths') for j in runs)
                report['cases'][key]['simulation_receipts']=[{'id':j['id'],'status':j['status'],'result':j.get('result')} for j in runs]
                accounting=subprocess.check_output(['ssh','research-cluster-xh5','sacct -j 25414990,25417779 --format=JobIDRaw,State,ExitCode --parsable2 --noheader'],text=True,timeout=40)
                report['cases'][key]['slurm_accounting']=accounting.strip()
                report['checks']['original_slurm_jobs_completed']=all(j+'|COMPLETED|0:0' in accounting for j in ['25414990','25417779'])
            if key not in fixtures:
                r=c.post('/research/api/projects',json={'name':case['name']});r.raise_for_status();fixtures[key]=r.json();saved.write_text(json.dumps(fixtures,ensure_ascii=False,indent=2),encoding='utf8')
            spec.append({'key':key,'source':pid,'target':fixtures[key]['id'],'paths':case['paths'],'record_ids':case['records']})
        # Copy exact selected materials and the task hierarchy into separately named
        # acceptance projects. Original task IDs remain only in the provenance report.
        remote_code='SPEC='+repr(spec)+'\n'+r'''from pathlib import Path
import json,subprocess
inner="""import os,json,shutil
from pathlib import Path
from server.storage import Store,atomic_json
from server.research_flow import graph,graph_path
from server.research_outline import read_state,location
store=Store(Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench')))
for item in SPEC:
 with store.db() as db:owner=db.execute('SELECT owner FROM projects WHERE id=?',(item['source'],)).fetchone()[0]
 source=store.path(owner,item['source']);target=store.path(owner,item['target'])
 for rel in item['paths']:
  dest=target/'project'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/'project'/rel,dest)
 state=read_state(store,owner,item['source']);document=state.get('active') or state['draft']
 for g in document['outline']:
  for t in g['tasks']:t['job_ids']=[]
 document['status']='proposal';document['limitations'].append('软件验收副本；研究内容来自原项目，未替原项目采用主线或运行计算。')
 atomic_json(location(store,owner,item['target']),{'revision':1,'active':None,'draft':document,'generation_job_id':None})
 data=graph(store,owner,item['source'],limit=2000);ids=set(item['record_ids'])
 data['nodes']=[n for n in data['nodes'] if n['id'] in ids];data['edges']=[e for e in data['edges'] if e['source'] in ids and e['target'] in ids];data['revision']=1
 atomic_json(graph_path(store,owner,item['target']),data)
 (target/'project/docs').mkdir(parents=True,exist_ok=True)
 (target/'project/docs/验收来源.md').write_text('软件验收副本。来源项目：'+item['source']+'\\n这里只验证真实材料上的研究理解、纠正和写回，不替代科学复现。')
print(json.dumps({'copied':len(SPEC)}))
"""
r=subprocess.run(['docker','exec','-i','research-workbench','python','-'],input='SPEC='+repr(SPEC)+'\n'+inner,text=True,capture_output=True)
assert r.returncode==0,r.stderr
print(r.stdout)
'''
        report['copy']=json.loads(remote(remote_code,60));report['fixtures']={k:{'id':p['id'],'native_id':p['native_id']} for k,p in fixtures.items()}
    report['passed']=all(report['checks'].values());(OUT/'research-path-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'checks':report['checks'],'fixtures':report['fixtures']},ensure_ascii=False))


async def live(key):
    import websockets
    fixtures=json.loads((OUT/'research-path-fixtures.json').read_text(encoding='utf8'));p=fixtures[key];case=CASES[key]
    with client() as c:
        token=c.cookies.get('dt_token');options=c.get('/api/settings/llm-options').json()['options']
        selection=next({'profile_id':x['profile_id'],'model_id':x['model_id']} for x in options if x.get('profile_id') and x.get('model_id'))
        before=c.get('/research/api/projects/'+p['id']+'/research-outline').json()
    prompt=('这是使用真实项目材料副本的工作流验收，请实际执行，不只给计划。'+case['request']+
            ' 可回查路径：'+json.dumps(case['paths'],ensure_ascii=False)+
            ' 请使用research_workbench的research overview→inspect→update完成回查和保存，再overview回读验证。这是一项已授权的范围内纠正，无需等待整版大纲确认。'
            ' 最后说明原证据支持什么、修订了什么、还缺什么。保持原项目和本副本主线不变，不生成新论文，不调用计算工具。')
    payload={'type':'start_turn','protocol_version':'2.0','capability':'chat','language':'zh','workspace_id':p['native_id'],
             'content':prompt,'llm_selection':selection,'config':{'partner_mode':'research','partner_writing_phase':'auto'}}
    result={'case':key,'project_id':p['id'],'tools':[],'results':[],'events':[]};start=time.monotonic()
    try:
        async with asyncio.timeout(600):
            async with websockets.connect('wss://tutor.example.invalid/ws?dt_workspace='+p['native_id'],additional_headers={'Cookie':'dt_token='+token,'Origin':'https://tutor.example.invalid'},max_size=20000000) as ws:
                await ws.send(json.dumps(payload,ensure_ascii=False))
                async for raw in ws:
                    event=json.loads(raw);kind=event.get('type');meta=event.get('metadata',{})
                    if kind not in result['events']:result['events'].append(kind)
                    if event.get('session_id'):result['session_id']=event['session_id']
                    if event.get('turn_id'):result['turn_id']=event['turn_id']
                    if kind=='tool_call':result['tools'].append({'name':meta.get('tool_name'),'arguments':meta.get('arguments') or event.get('content')})
                    if kind=='tool_result' and meta.get('tool_name')=='research_workbench':
                        try:result['results'].append(json.loads(event.get('content') or '{}'))
                        except ValueError:result['results'].append({'error':str(event.get('content'))[:1500]})
                    if kind=='result':result['reply']=meta.get('response') or event.get('content')
                    if kind in ('error','protocol_error'):raise RuntimeError(str(event)[:2000])
                    if kind=='done':result['status']=meta.get('status');break
                    (OUT/('research-path-'+key+'-live.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    finally:
        result['elapsed_seconds']=round(time.monotonic()-start,1)
        with client() as c:
            after=c.get('/research/api/projects/'+p['id']+'/research-outline').json();updates=c.get('/research/api/projects/'+p['id']+'/research-updates').json()['updates']
            result['checks']={'native_turn_completed':result.get('status')=='completed','update_saved_and_read_back':bool(updates),
                'mainline_unchanged':(after.get('draft') or after.get('active'))['mainline']==(before.get('draft') or before.get('active'))['mainline'],
                'proposal_not_adopted':after.get('active') is None,'before_after_preserved':bool(updates) and all(x.get('before') is not None and x.get('after') for x in updates[0]['changes'])}
            result['updates']=updates;result['passed']=all(result['checks'].values())
        (OUT/('research-path-'+key+'-live.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ['case','project_id','session_id','checks','elapsed_seconds','passed']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','chloride','hydration']);args=parser.parse_args()
    prepare() if args.action=='prepare' else asyncio.run(live(args.action))
