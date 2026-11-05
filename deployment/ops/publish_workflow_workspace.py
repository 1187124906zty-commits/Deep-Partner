"""Publish the build exercised by layout, workflow and code-result UI checks."""
from pathlib import Path
import json,subprocess,tarfile
from publish_agentic_fixes import remote
ROOT=Path(__file__).resolve().parents[1]
WB=Path('D:/Development/research-workbench')


def main():
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    assert build['state']=='COMPLETED' and build['exit_code']=='0:0'
    checks=[]
    for name in ['ui-candidate.json','flow-controls-candidate.json','code-task-candidate.json']:
        qa=json.loads((ROOT/'reports/agentic-product'/name).read_text(encoding='utf8'))
        assert qa['passed'],name
        assert (qa.get('frontend_job_id') or qa['build']['slurm_job_id'])==build['job_id'],name
        checks.append(name)
    backend=ROOT/'.local/workflow-workspace-backend.tar.gz'
    files=['server/research_flow.py','server/workflow_control.py']
    with tarfile.open(backend,'w:gz') as bundle:
        for rel in files:bundle.add(WB/rel,arcname=rel)
    for path,name in [(Path(build['local_artifact']),'workflow-workspace-ui.tar.gz'),(backend,'workflow-workspace-backend.tar.gz')]:
        subprocess.run(['scp','-q',str(path),'papers-research:/srv/research-workbench/'+name],check=True,timeout=150)
    code='EXPECTED='+repr(build['job_id'])+'\nFILES='+repr(files)+'\n'+r'''from pathlib import Path
import json,tarfile,shutil,sqlite3,subprocess,time,urllib.request
root=Path('/srv/research-workbench');source=root/'source';staged=root/('workflow-ui-'+EXPECTED);staged.mkdir(exist_ok=True)
with tarfile.open(root/'workflow-workspace-ui.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert json.loads((staged/'build-info.json').read_text())['slurm_job_id']==EXPECTED
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
assert not db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone(),'Wait for current execution before backend reload'
with tarfile.open(root/'workflow-workspace-backend.tar.gz') as bundle:
 for item in bundle.getmembers():
  assert item.name in FILES
  data=bundle.extractfile(item).read();compile(data,item.name,'exec');(source/item.name).write_bytes(data)
for name in ['research-flow','research-flow-project','research-flow-recovery','research-workbench']:
 subprocess.run(['docker','restart',name],check=True,capture_output=True)
 cmd=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]['Config']['Cmd'];port=cmd[cmd.index('--port')+1]
 for _ in range(50):
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+port+'/health',timeout=2) as r:
    if r.status==200:break
  except OSError:pass
  time.sleep(.3)
 else:raise RuntimeError(name+' is not ready')
# Copy immutable assets first, then replace the entry document. Existing tabs
# can still load their previous hashed chunks while the new page is released.
static=source/'static'
for path in staged.rglob('*'):
 if path.is_file() and path.name!='index.html':
  dest=static/path.relative_to(staged);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
temporary=static/'index.next.html';shutil.copyfile(staged/'index.html',temporary);temporary.replace(static/'index.html')
print(json.dumps({'published':True,'frontend_job_id':EXPECTED,'backend_files':FILES,'existing_tab_assets_preserved':True,'url':'https://tutor.example.invalid/research/'}))
'''
    result=json.loads(remote(code,110));result['candidate_reports']=checks
    (ROOT/'reports/agentic-product/workflow-workspace-published.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
