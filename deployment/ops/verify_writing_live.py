"""Exercise real Dify callbacks, journal sources and the selected Tutor model."""
from pathlib import Path
import argparse,json,os,sys,time
import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'.local/writing-fixture.json'


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status']);args=parser.parse_args()
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=120,trust_env=False) as c:
        login(c)
        if args.action=='start':
            if STATE.exists():state=json.loads(STATE.read_text(encoding='utf8'))
            else:
                existing=c.get('/research/api/projects').json()['projects']
                response=c.post('/research/api/projects',json={'name':'写作工作流验收 · 20261103'});response.raise_for_status()
                state={'project':response.json(),'baseline_projects':[p['id'] for p in existing]}
                STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
            prefix='/research/api/projects/'+state['project']['id']
            journal=c.get('/research/api/journals/search',params={'q':'Cement and Concrete Research'});journal.raise_for_status()
            selected=next(x for x in journal.json()['items'] if x['name'].lower()=='cement and concrete research')
            c.put(prefix+'/writing/settings',json={'journal':selected,'phase':'auto','mode':'writing'}).raise_for_status()
            for path,content in [('docs/writing-fixture.md','# 写作工作流软件验收材料\n\n以下是人工定义的软件测试输入，不属于研究实验结果。\n请求仅润色英文段落，不撰写完整论文。\n原文：The benchmark solves a one-dimensional diffusion equation. The error decreases when the mesh is refined. The boundary values are prescribed at both ends.\n'),('data/writing-metrics.json',json.dumps({'metrics':[{'data_source_id':'project/data/error.csv','target_metric':'error'}]})),('data/error.csv','mesh,error\n8,0.04\n16,0.01\n32,0.0025\n')]:
                saved=c.put(prefix+'/file',json={'path':path,'content':content})
                if not saved.is_success:raise RuntimeError(str(saved.status_code)+' '+saved.text)
            request='请结合项目中 writing-fixture.md 的英文原段，润色成一个自然、连贯的英文段落，保留三个原有事实；本轮只交付这一段。目标期刊已选，不需要确认启动。该输入为软件功能测试。'
            response=c.post(prefix+'/writing/start',json={'request':request,'operation_id':'writing-live-v1','phase':'auto'});response.raise_for_status()
            state['run']=response.json();STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(state['run'],ensure_ascii=False));return
        state=json.loads(STATE.read_text(encoding='utf8'));prefix='/research/api/projects/'+state['project']['id']
        response=c.get(prefix+'/writing/runs/'+state['run']['id']);response.raise_for_status();run=response.json()
        report={'project':state['project'],'run':run,'checks':{}}
        if run['status']=='completed':
            content=c.get(prefix+'/file',params={'path':run['outputs']['path'].removeprefix('project/')});content.raise_for_status()
            report['checks']={'all_roles_completed':[s['stage'] for s in run['stage_history']]==['intent','exemplar','alignment','narrow','wide','review'],
                'seven_real_dify_routes':len(run['dify_runs'])==7,'output_readback_equals_model_output':content.text==run['outputs']['text'],
                'journal_profile_saved':run['journal']['journal']['name']=='Cement and Concrete Research',
                'metrics_computed_from_project_csv':run['tool_results']['comparative_metric_calculator'][0]['n']==3}
            report['passed']=all(report['checks'].values())
        (ROOT/'reports/writing-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'id':run['id'],'status':run['status'],'stage':run['stage'],'error':run['error'],
                          'checks':report['checks'],'dify_routes':len(run['dify_runs']),
                          'output':run.get('outputs'),'journal_pages':[{'url':p.get('url'),'status':p.get('status')} for p in (run.get('journal') or {}).get('pages',[])]},ensure_ascii=False))


if __name__=='__main__':main()
