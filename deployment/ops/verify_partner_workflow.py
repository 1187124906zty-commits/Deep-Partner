"""Real Windows CLI/project/API acceptance; scientific projects are left untouched."""
from pathlib import Path
import argparse,json,os,subprocess,time,sys
from contextlib import contextmanager
import httpx
ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'.local/partner-workflow';ORIGIN='https://tutor.example.invalid'
DP=STAGE/'dp.exe'

def account():return json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=40))
@contextmanager
def client():
    client=httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy=os.environ.get('WORKBENCH_HTTP_PROXY','http://127.0.0.1:12000'),trust_env=False,timeout=90)
    try:
        response=client.post('/api/auth/login',json=account());response.raise_for_status();yield client
    finally:client.close()
def cli(*args,timeout=180):
    r=subprocess.run([str(DP),*map(str,args)],capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr[-2000:]+r.stdout[-1500:])
    return r.stdout
def task(c,pid,rid,maximum=180):
    end=time.monotonic()+maximum
    while time.monotonic()<end:
        r=c.get(f'/research/api/projects/{pid}/research-flow/runs/{rid}');r.raise_for_status();row=r.json()
        if row['status'] in ('completed','failed','interrupted','cancelled'):return row
        time.sleep(3)
    return row
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['setup','chat','search','download','resume','archive']);a=p.parse_args()
    STAGE.mkdir(parents=True,exist_ok=True);report_path=ROOT/'reports/partner-workflow-live.json'
    report=json.loads(report_path.read_text(encoding='utf8')) if report_path.is_file() else {'checks':{},'evidence':{}}
    with client() as c:
        if a.action=='setup':
            response=c.post('/research/api/projects',json={'name':'自动研究工作流接入验收 · 20261105'});response.raise_for_status();project=response.json()
            (STAGE/'fixture.json').write_text(json.dumps(project,ensure_ascii=False,indent=2),encoding='utf8')
        project=json.loads((STAGE/'fixture.json').read_text(encoding='utf8'));pid=project['id'];prefix='/research/api/projects/'+pid
        report['fixture_project_id']=pid
        if a.action=='setup':
            routes=c.get(prefix+'/research-flow/routes',params={'kind':'survey'});routes.raise_for_status();report['checks']['route_loads_only_selected_workflow']=list(routes.json()['routes'])==['survey']
            record={'id':'fixture-relationships','title':'软件接入验收节点','content':'仅验证节点与关系保存，不是科学结论。',
                'nodes':[{'id':'fixture:q','kind':'question','label':'软件接入验收问题','status':'recorded'},{'id':'fixture:idea','kind':'idea','label':'软件接入验收想法','status':'proposed'}],
                'edges':[{'source':'fixture:q','target':'fixture:idea','relation':'motivates'}]}
            saved=c.post(prefix+'/research-flow/records',json=record);saved.raise_for_status();g=c.get(prefix+'/research-flow/graph').json()
            report['checks']['graph_records_real_edges']=any(e['relation']=='motivates' for e in g['edges'])
            path=saved.json()['path'];r=c.get(prefix+'/file',params={'path':path});report['checks']['record_material_is_readable_project_file']=r.is_success and '软件接入验收' in r.text
            r=c.post(prefix+'/research-flow/records',json={'nodes':[{'kind':'gap','label':'无人做过','status':'not_found_in_scope'}]});report['checks']['unscoped_negative_claim_rejected']=r.status_code==400
        elif a.action=='chat':
            first=cli('chat','send','--project',pid,'--message','这是一项软件连接验收，请记住本次口令 DP_FLOW_20261105，只回复“已记住”。不要调用工具，不修改文件。','--jsonl')
            (STAGE/'chat-first.jsonl').write_text(first,encoding='utf8');events=[json.loads(line) for line in first.splitlines() if line.strip().startswith('{')]
            sid=next(e['session_id'] for e in events if e.get('session_id'));report['session_id']=sid
            report['checks']['cli_receives_actual_stream_and_project_receipt']=any(e.get('type')=='done' for e in events) and any(e.get('type')=='project_receipt' for e in events)
            second=cli('chat','send','--project',pid,'--session',sid,'--message','本次软件验收口令是什么？仅返回口令。','--jsonl')
            (STAGE/'chat-second.jsonl').write_text(second,encoding='utf8');events=[json.loads(line) for line in second.splitlines() if line.strip().startswith('{')]
            reply=''.join(e.get('content','') for e in events if e.get('type')=='content');report['checks']['same_session_retains_conversation']= 'DP_FLOW_20261105' in reply
            data=json.loads(cli('chat','history','--project',pid,'--session',sid));report['checks']['history_has_two_user_messages']=sum(m.get('role')=='user' for m in data.get('messages',[]))==2
            report['evidence']['same_session_answer']=reply
            other='1ea03384007d4bb9b88d43e3368099f3';wrong=subprocess.run([str(DP),'chat','history','--project',other,'--session',sid],capture_output=True,text=True,encoding='utf8',timeout=60)
            report['checks']['cross_project_conversation_rejected']=wrong.returncode!=0
        elif a.action=='search':
            path=STAGE/'search.json';path.write_text(json.dumps({'kind':'search','query':'phase field reactive transport dissolution','limit':3,'request_id':'acceptance-search-1'}),encoding='utf8')
            started=json.loads(cli('workflow','run','--project',pid,'--file',path));again=json.loads(cli('workflow','run','--project',pid,'--file',path));report['checks']['duplicate_run_does_not_replay_search']=again['id']==started['id'] and again.get('duplicate') is True
            row=task(c,pid,started['id']);report['evidence']['search']={k:row[k] for k in ('id','status','result','error')};report['checks']['real_search_runs_and_archives']=row['status']=='completed' and bool(row['result'].get('sources'))
        elif a.action=='download':
            path=STAGE/'download.json';path.write_text(json.dumps({'kind':'download','entries':[{'doi':'10.1038/s41598-022-22684-1','title':'A phase-field model for reactive transport and fracture in porous media'}],'request_id':'acceptance-download-1'}),encoding='utf8')
            started=json.loads(cli('workflow','run','--project',pid,'--file',path));row=task(c,pid,started['id'],300)
            report['evidence']['download']={k:row[k] for k in ('id','status','result','error')}
            report['checks']['scansci_download_enters_same_project']=row['status']=='completed' and bool(row['result'].get('read_coverage'))
        elif a.action=='resume':
            sid=report['session_id'];marker='RESUME_MARKER_20261105'
            proc=subprocess.Popen([str(DP),'chat','send','--project',pid,'--session',sid,'--message',marker+'：这是一项断线恢复软件验收，请生成8条简短编号句，说明项目材料如何归档。不要调用工具，不修改文件。','--jsonl'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',bufsize=1)
            seen=[]
            try:
                while True:
                    line=proc.stdout.readline()
                    if not line:raise RuntimeError('Client ended before turn acceptance')
                    event=json.loads(line);seen.append(event)
                    if event.get('turn_id') and event.get('seq',0)>0:break
            finally:proc.kill();proc.wait(timeout=10)
            resumed=cli('chat','resume','--project',pid,'--session',sid,'--jsonl',timeout=180)
            (STAGE/'chat-resumed.jsonl').write_text(resumed,encoding='utf8');events=[json.loads(line) for line in resumed.splitlines() if line.strip().startswith('{')]
            data=json.loads(cli('chat','history','--project',pid,'--session',sid))
            report['checks']['client_restart_resumes_existing_turn']=any(e.get('type')=='done' for e in events)
            report['checks']['resume_does_not_duplicate_user_submission']=sum(marker in str(m.get('content','')) for m in data.get('messages',[]) if m.get('role')=='user')==1
        elif a.action=='archive':
            config=project['config'];config['archived']=True;response=c.patch(prefix,json={'name':project['name'],'config':config});response.raise_for_status();report['fixture_archived']=True
    current=json.loads(report_path.read_text(encoding='utf8')) if report_path.is_file() else {}
    current.setdefault('checks',{}).update(report['checks']);current.setdefault('evidence',{}).update(report['evidence'])
    current.update({k:v for k,v in report.items() if k not in ('checks','evidence')});report=current
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'action':a.action,'checks':report['checks'],'project_id':pid},ensure_ascii=False),flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
