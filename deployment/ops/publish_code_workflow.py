"""Publish only the code handoff and archival policy; preserve native/Slurm IDs."""
from pathlib import Path
import json,subprocess,tarfile
from partner_workflow_dev import ROOT,STAGE,WORKBENCH,remote


def main():
    STAGE.mkdir(parents=True,exist_ok=True)
    archive=STAGE/'code-workflow.tar.gz'
    names=['server/research_flow.py','server/research_tool_flow.py','tests/test_research_tool_flow.py']
    with tarfile.open(archive,'w:gz') as bundle:
        for name in names:bundle.add(WORKBENCH/name,arcname=name)
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/code-workflow.tar.gz'],check=True,timeout=60)
    code=r'''from pathlib import Path
import json,subprocess,tarfile,shutil,time,urllib.request
root=Path('/srv/research-workbench');candidate=root/'code-workflow-candidate';candidate.mkdir(exist_ok=True)
with tarfile.open(root/'code-workflow.tar.gz') as bundle:bundle.extractall(candidate,filter='data')
(candidate/'server/__init__.py').write_text("__path__.append('/workbench/server')\n")
subprocess.run(['docker','exec','research-flow-recovery','mkdir','-p','/tmp/code-workflow-candidate'],check=True,capture_output=True)
subprocess.run(['docker','cp',str(candidate)+'/.','research-flow-recovery:/tmp/code-workflow-candidate'],check=True,capture_output=True)
command=['docker','exec','-e','WORKBENCH_FLOW_RECOVERY=0','-e','PYTHONPATH=/tmp/code-workflow-candidate:/opt/workbench-tools/python-libs','-w','/tmp/code-workflow-candidate','research-flow-recovery','python','-m','unittest','discover','-s','tests','-p','test_research_tool_flow.py','-v']
tests=subprocess.run(command,capture_output=True,text=True)
print(tests.stdout+tests.stderr);assert tests.returncode==0,'Code handoff tests failed'
# Read persisted execution IDs before touching the API worker. Running solvers
# and native DeepCode are independent processes and are never restarted here.
probe="from server.storage import Store;from pathlib import Path;import os,json;s=Store(os.environ['WORKBENCH_DATA']);result=[]\nwith s.db() as db:rows=db.execute(\"SELECT id,owner,project,result FROM jobs WHERE kind IN ('research-flow','simulation') AND status IN ('queued','running','waiting_service')\").fetchall()\nfor r in rows:\n p=s.path(r['owner'],r['project'])/'.workbench/research-flow/runs'/r['id']/'state.json'\n if p.is_file():\n  state=json.loads(p.read_text());result.append({'id':r['id'],'state':state})\nprint(json.dumps(result))"
snapshot=subprocess.run(['docker','exec','-e','WORKBENCH_FLOW_RECOVERY=0','research-flow-recovery','python','-c',probe],capture_output=True,text=True,check=True)
before=json.loads(snapshot.stdout)
for row in before:
 state=row['state']
 if state.get('native_code',{}).get('submitted'):
  assert state['native_code'].get('workflow_run_id') or state['native_code'].get('id'),'Native submission identity missing'
for name in ['research_flow.py','research_tool_flow.py']:
 source=candidate/'server'/name;compile(source.read_text(),str(source),'exec');shutil.copyfile(source,root/'source/server'/name)
subprocess.run(['docker','restart','research-flow-recovery'],check=True,capture_output=True)
for _ in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:47909/health',timeout=2) as response:
   if json.load(response).get('ok'):break
 except OSError:pass
 time.sleep(.5)
else:raise RuntimeError('Code policy worker did not become ready')
loaded=subprocess.run(['docker','exec','-e','WORKBENCH_FLOW_RECOVERY=0','research-flow-recovery','python','-c',"import inspect,json;from server.research_tool_flow import native_code;from server.research_flow import install;print(json.dumps({'stage_policy': '按有意义的阶段实现并集中验证' in inspect.getsource(native_code), 'no_automatic_node': \"'nodes':[]\" in inspect.getsource(install)}))"],capture_output=True,text=True,check=True)
effective=json.loads(loaded.stdout);assert all(effective.values())
print(json.dumps({'deployed':True,'effective':effective,'preserved_run_ids':[r['id'] for r in before],
                  'restarted':['research-flow-recovery'],'native_or_cluster_processes_restarted':False}))
'''
    output=remote('papers-research',code);print(output)
    result=json.loads(output.splitlines()[-1])
    (ROOT/'reports/code-workflow-release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
