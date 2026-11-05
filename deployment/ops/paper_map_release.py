"""Test and publish the source-bound content-map feature in the existing product."""
from pathlib import Path
import argparse,json,subprocess,sys,tarfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
HOST=['ssh','-o','BatchMode=yes','-o','ProxyJump=research-cluster-xh5','papers-research']
FILES=['app.py','literature.py','chat_materials.py','task_workflows.py','paper_maps.py','paper_map_core.py']

def remote(code,timeout=90):
    result=subprocess.run([*HOST,'sudo -n python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stdout[-2000:]+result.stderr[-4000:])
    return result.stdout

def upload(path,name):
    subprocess.run(['scp','-q','-o','ProxyJump=research-cluster-xh5',str(path),'papers-research:/srv/research-workbench/'+name],check=True,timeout=180)

def test():
    archive=ROOT/'.local/paper-map-tests.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for path in (SOURCE/'server').glob('*.py'):bundle.add(path,arcname='server/'+path.name)
        bundle.add(SOURCE/'docs/paper-map-rules.json',arcname='docs/paper-map-rules.json')
        for name in ['test_paper_map_core.py','test_paper_maps.py','test_task_workflows.py']:
            bundle.add(SOURCE/'tests'/name,arcname='tests/'+name)
        for name in ['agent_service.py','paper_map_worker.py']:
            bundle.add(ROOT/'tutor-extension/writing_agent'/name,arcname='writing_agent/'+name)
    upload(archive,archive.name)
    output=remote(r'''from pathlib import Path
import subprocess,tarfile
root=Path('/srv/research-workbench/tools/paper-map-candidate');root.mkdir(exist_ok=True)
with tarfile.open('/srv/research-workbench/paper-map-tests.tar.gz') as bundle:bundle.extractall(root,filter='data')
for path in (root/'writing_agent').glob('*.py'):compile(path.read_text(),str(path),'exec')
result=subprocess.run(['docker','exec','-e','PYTHONPATH=/opt/workbench-tools/writing-libs:/opt/workbench-tools/python-libs','-w','/opt/workbench-tools/paper-map-candidate','research-workbench','python','-m','pytest','tests/test_paper_map_core.py','tests/test_paper_maps.py','tests/test_task_workflows.py','-q','-p','no:cacheprovider'],capture_output=True,text=True)
print(result.stdout);print(result.stderr);assert result.returncode==0
''')
    (ROOT/'reports/paper-map-server-tests.log').write_text(output,encoding='utf8');print(output)

def status():
    print(remote(r'''from pathlib import Path
import subprocess,json
code="from server.app import store; import json\nwith store.db() as db:rows=[dict(r) for r in db.execute(\"SELECT id,owner,project,kind,status FROM jobs WHERE status IN ('running','queued')\").fetchall()]\nprint(json.dumps(rows))"
result=subprocess.run(['docker','exec','research-workbench','python','-c',code],capture_output=True,text=True);print(result.stdout);assert result.returncode==0,result.stderr
'''))

def install():
    assert 'passed' in (ROOT/'reports/paper-map-server-tests.log').read_text(encoding='utf8')
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'));assert build['state']=='COMPLETED'
    upload(Path(build['local_artifact']),'paper-map-static.tar.gz')
    output=remote(r'''from pathlib import Path
import subprocess,shutil,json,time,urllib.request,tarfile,os,signal
wb=Path('/srv/research-workbench');candidate=wb/'tools/paper-map-candidate'
probe="from server.app import store\nwith store.db() as db:rows=db.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'"
r=subprocess.run(['docker','exec','research-workbench','python','-c',probe],capture_output=True,text=True);assert r.returncode==0,r.stderr
for name in '''+repr(FILES)+r''':
    source=candidate/'server'/name;compile(source.read_text(),str(source),'exec');shutil.copyfile(source,wb/'source/server'/name)
(wb/'source/docs').mkdir(exist_ok=True)
shutil.copyfile(candidate/'docs/paper-map-rules.json',wb/'source/docs/paper-map-rules.json')
target=Path('/srv/dify-research/tutor-extension/writing_agent')
for path in (candidate/'writing_agent').glob('*.py'):shutil.copyfile(path,target/path.name)
static=(wb/'source/static').resolve();assert static==Path('/srv/research-workbench/source/static')
staged=wb/'paper-map-static-staging';staged.mkdir(exist_ok=True)
with tarfile.open(wb/'paper-map-static.tar.gz') as bundle:bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file()
shutil.rmtree(static);staged.rename(static)
stop="""from pathlib import Path
import os,signal
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(bytes([0]))
 except OSError:continue
 if b'writing_agent.agent_service:app' in args:os.kill(int(p.name),signal.SIGTERM)
"""
subprocess.run(['docker','exec','-i','deeptutor','python','-'],input=stop,text=True,check=True,capture_output=True)
time.sleep(.5)
subprocess.run(['docker','exec','-d','-w','/app','-e','PYTHONPATH=/opt/dify-delivery:/app','deeptutor','python','-m','uvicorn','writing_agent.agent_service:app','--host','0.0.0.0','--port','47931','--log-level','warning'],check=True,capture_output=True)
for _ in range(40):
 try:
  with urllib.request.urlopen('http://172.19.0.3:47931/health',timeout=2) as response:worker=json.load(response)
  if worker.get('ok'):break
 except OSError:pass
 time.sleep(.3)
else:raise RuntimeError('Model worker health failed')
subprocess.run(['docker','restart','research-workbench'],check=True,capture_output=True)
for _ in range(40):
 try:
  with urllib.request.urlopen('http://127.0.0.1:47900/health',timeout=2) as response:workbench=json.load(response)
  if workbench.get('ok'):break
 except OSError:pass
 time.sleep(.3)
else:raise RuntimeError('Workbench health failed')
print(json.dumps({'installed':True,'worker':worker,'workbench':workbench,'build':json.loads((static/'build-info.json').read_text()),'url':'https://tutor.example.invalid/research/'}))
''')
    (ROOT/'reports/paper-map-release.json').write_text(output,encoding='utf8');print(output)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['test','status','install']);args=parser.parse_args()
    {'test':test,'status':status,'install':install}[args.action]()
