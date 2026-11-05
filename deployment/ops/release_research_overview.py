"""Publish the research view and the UI exercised against actual project records."""
from pathlib import Path
import argparse,json,subprocess,tarfile
from publish_agentic_fixes import remote,WB,ROOT,OUT


def backend():
    files=['server/research_overview.py','server/research_outline.py','server/research_updates.py','server/models.py','server/task_workflows.py','server/app.py','server/standards.py','vendor/workbench-skills/OUTPUT_STANDARD.md']
    archive=ROOT/'.local/research-overview-backend.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for rel in files:
            if rel.endswith('.py'):compile((WB/rel).read_text(encoding='utf8'),rel,'exec')
            bundle.add(WB/rel,arcname=rel)
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/research-overview-backend.tar.gz'],check=True,timeout=60)
    code='FILES='+repr(files)+'\n'+r'''from pathlib import Path
import json,sqlite3,tarfile,subprocess,time,urllib.request
root=Path('/srv/research-workbench');source=root/'source'
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3')
assert not db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone(),'Active execution must finish before reload'
assert not db.execute("SELECT 1 FROM jobs WHERE status='queued' AND kind NOT IN ('research-flow','simulation','cluster-pdf-parse','literature-download','paper-content-map') LIMIT 1").fetchone(),'Queued in-process work must finish'
with tarfile.open(root/'research-overview-backend.tar.gz') as bundle:
 for item in bundle.getmembers():
  assert item.name in FILES
  data=bundle.extractfile(item).read()
  if item.name.endswith('.py'):compile(data,item.name,'exec')
  (source/item.name).write_bytes(data)
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
print(json.dumps({'published':True,'backend_files':FILES,'healthy_services':4}))
'''
    result=json.loads(remote(code,110));(OUT/'research-overview-backend.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


def frontend():
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    qa=json.loads((OUT/'research-overview-candidate.json').read_text(encoding='utf8'))
    assert build['state']=='COMPLETED' and build['exit_code']=='0:0'
    assert qa['passed'] and qa['frontend_job_id']==build['job_id']
    assert qa['checks'].get('mainline_matches_actual_synthesis') and qa['checks'].get('actual_rag_retrieval_used')
    interaction=json.loads((OUT/'research-interaction-ui-candidate.json').read_text(encoding='utf8'))
    assert interaction['passed'] and interaction['build']==build['job_id']
    assert all(interaction['checks'].get(key) for key in ['real_author_question','refresh_resubscribes_same_turn','answer_resumes_original_turn','real_cancel_confirmed_by_execution'])
    subprocess.run(['scp','-q',build['local_artifact'],'papers-research:/srv/research-workbench/research-overview-ui.tar.gz'],check=True,timeout=150)
    code='EXPECTED='+repr(build['job_id'])+'\n'+r'''from pathlib import Path
import json,tarfile,shutil
root=Path('/srv/research-workbench');staged=root/('research-overview-ui-'+EXPECTED);staged.mkdir(exist_ok=True)
with tarfile.open(root/'research-overview-ui.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert json.loads((staged/'build-info.json').read_text())['slurm_job_id']==EXPECTED
static=root/'source/static'
for path in staged.rglob('*'):
 if path.is_file() and path.name!='index.html':
  dest=static/path.relative_to(staged);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
temporary=static/'index.next.html';shutil.copyfile(staged/'index.html',temporary);temporary.replace(static/'index.html')
print(json.dumps({'published':True,'frontend_job_id':EXPECTED,'url':'https://tutor.example.invalid/research/'}))
'''
    result=json.loads(remote(code,60));(OUT/'research-overview-published.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('part',choices=['backend','frontend']);args=parser.parse_args()
    backend() if args.part=='backend' else frontend()
