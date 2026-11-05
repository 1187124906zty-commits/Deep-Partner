"""Stage and publish the inspected workflow fixes; preserve durable job identities."""
from pathlib import Path
import argparse,json,subprocess,tarfile,sys

ROOT=Path(__file__).resolve().parents[1]
WB=Path('D:/Development/research-workbench')
OUT=ROOT/'reports/agentic-product'
FILES=['server/research_flow.py','server/task_workflows.py','server/writing.py','server/app.py','server/healthcheck.py']


def remote(code,timeout=60):
    r=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr[-3500:]+r.stdout[-2000:])
    return r.stdout


def stage():
    archive=ROOT/'.local/agentic-candidate.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for rel in FILES:bundle.add(WB/rel,arcname='workbench/'+rel)
        for rel in ['tests/test_flow_request_identity.py','tests/test_workflow_recovery.py','tests/test_research_tool_flow.py','tests/test_scholar_workflow_contract.py']:
            bundle.add(WB/rel,arcname='workbench/'+rel)
        for rel in ['bridge/delivery.py','ops/workflow_guards.py','ops/optimize_workflow.py','ops/setup_writing.py','ops/partner_workflow_dev.py','ops/deploy_partner_recovery.py']:
            bundle.add(ROOT/rel,arcname='deployment/'+rel)
        bundle.add(WB/'scripts/deploy.py',arcname='workbench/scripts/deploy.py')
        bundle.add(WB/'scripts/local_search_bridge.py',arcname='workbench/scripts/local_search_bridge.py')
        for rel in FILES:
            prior=ROOT/'.local/agentic-baseline'/rel
            if prior.is_file():bundle.add(prior,arcname='baseline/'+rel)
        bundle.add(ROOT/'.local/agentic-baseline/deployment/bridge/delivery.py',arcname='baseline/bridge/delivery.py')
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/agentic-candidate.tar.gz'],check=True,timeout=60)
    code=r'''from pathlib import Path
import tarfile,subprocess,json
root=Path('/srv/research-workbench');stage=root/'agentic-candidate';stage.mkdir(exist_ok=True)
with tarfile.open(root/'agentic-candidate.tar.gz') as bundle:bundle.extractall(stage,filter='data')
for prior in (stage/'baseline').rglob('*.py'):
 relative=prior.relative_to(stage/'baseline')
 current=Path('/srv/dify-research')/relative if relative.parts[0]=='bridge' else root/'source'/relative
 assert prior.read_text()==current.read_text(),'Source changed since inspection: '+str(relative)
(stage/'workbench/server/__init__.py').write_text("__path__.append('/workbench/server')\n")
subprocess.run(['docker','exec','research-workbench','mkdir','-p','/tmp/agentic-candidate'],check=True,capture_output=True)
subprocess.run(['docker','cp',str(stage/'workbench')+'/.','research-workbench:/tmp/agentic-candidate'],check=True,capture_output=True)
r=subprocess.run(['docker','exec','-e','WORKBENCH_FLOW_RECOVERY=0','-e','PYTHONPATH=/tmp/agentic-candidate:/opt/workbench-tools/python-libs','-w','/tmp/agentic-candidate','research-workbench','python','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr);assert r.returncode==0,'Server candidate tests failed'
print(json.dumps({'candidate_tests_passed':True}))
'''
    output=remote(code,90);(OUT/'backend-candidate.txt').write_text(output,encoding='utf8');print(output)


def backend():
    code='FILES='+repr(FILES)+'\n'+r'''from pathlib import Path
import subprocess,json,shutil,sqlite3,time,urllib.request,fcntl
root=Path('/srv/research-workbench');stage=root/'agentic-candidate'
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
active=[dict(r) for r in db.execute("SELECT id,owner,project,kind,status FROM jobs WHERE status IN ('running','queued','waiting_service','waiting_input')")]
assert not any(r['status']=='running' for r in active),'A running task must finish before restart'
assert not any(r['status']=='queued' and r['kind'] not in ('research-flow','simulation','cluster-pdf-parse','literature-download','paper-content-map') for r in active),'An in-process queued job must finish'
with sqlite3.connect('/srv/dify-research/state/deliveries.sqlite3') as delivery:
 assert not delivery.execute("SELECT 1 FROM deliveries WHERE state NOT IN ('completed','failed','interrupted','saved') LIMIT 1").fetchone(),'An active delivery must finish'
for rel in FILES:
 source=stage/'workbench'/rel;compile(source.read_text(),str(source),'exec');shutil.copyfile(source,root/'source'/rel)
shutil.copyfile(stage/'deployment/bridge/delivery.py',Path('/srv/dify-research/bridge/delivery.py'))
# Existing container checks invoke /app/healthcheck.py. Replace that small probe
# without recreating containers; future deploy scripts explicitly select it too.
services=['research-flow','research-flow-project','research-flow-recovery','research-workbench']
for name in services:
 subprocess.run(['docker','cp',str(root/'source/server/healthcheck.py'),name+':/app/healthcheck.py'],check=True,capture_output=True)
 subprocess.run(['docker','restart',name],check=True,capture_output=True)
 command=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]['Config']['Cmd']
 port=command[command.index('--port')+1]
 for _ in range(40):
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+port+'/health',timeout=2) as response:
    if json.load(response).get('ok'):break
  except OSError:pass
  time.sleep(.25)
 else:raise RuntimeError(name+' did not become ready')
 subprocess.run(['docker','exec',name,'python','/app/healthcheck.py'],check=True,capture_output=True)
subprocess.run(['docker','restart','dify-workbench-bridge'],check=True,capture_output=True)
after=[dict(r) for r in db.execute('SELECT id,status FROM jobs WHERE id IN ('+','.join('?' for _ in active)+')',[r['id'] for r in active])] if active else []
assert not any(r['status']=='interrupted' for r in after),'A durable job was incorrectly interrupted'
print(json.dumps({'published':FILES+['bridge/delivery.py'],'active_before':[{k:v for k,v in r.items() if k!='owner'} for r in active],'retained_jobs':after,'health_probes_passed':services},ensure_ascii=False))
'''
    value=remote(code,90);(OUT/'backend-published.json').write_text(value,encoding='utf8');print(value)


def dify():
    code=r'''from pathlib import Path
import shutil,subprocess,json
root=Path('/srv/dify-research');stage=Path('/srv/research-workbench/agentic-candidate/deployment')
for name in ['workflow_guards.py','optimize_workflow.py','setup_writing.py','partner_workflow_dev.py','deploy_partner_recovery.py']:
 shutil.copyfile(stage/'ops'/name,root/'ops'/name)
rows=[]
for name in ['optimize_workflow.py','setup_writing.py']:
 r=subprocess.run(['python3',str(root/'ops'/name)],capture_output=True,text=True)
 assert r.returncode==0,r.stderr[-2000:]+r.stdout[-1000:]
 rows.append(json.loads(r.stdout.splitlines()[-1]))
print(json.dumps(rows,ensure_ascii=False))
'''
    value=remote(code,90);(OUT/'dify-published.json').write_text(value,encoding='utf8');print(value)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','backend','dify']);a=p.parse_args();OUT.mkdir(exist_ok=True);globals()[a.action]()
