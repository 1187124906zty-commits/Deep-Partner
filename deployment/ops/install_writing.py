"""Install the writing extension through Tutor's public plugin interface."""
from pathlib import Path
import json
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
SSH=['ssh','-o','ProxyJump=research-cluster-xh5','papers-research']


def remote(code,timeout=60):
    r=subprocess.run([*SSH,'sudo -n python3 -'],input=code,capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return r.stdout


def main():
    sys.stdout.reconfigure(encoding='utf8')
    archive=ROOT/'.local/writing-install.tar.gz'
    files=['app.py','task_workflows.py','writing.py','writing_tools.py','writing_prompts.py']
    with tarfile.open(archive,'w:gz') as tar:
        for name in files:tar.add(SOURCE/'server'/name,arcname='server/'+name)
        for name in ['setup_writing.py']:tar.add(ROOT/'ops'/name,arcname='ops/'+name)
        for name in ['partner_writing.py','deeptutor_dify_delivery-0.1.0.dist-info/entry_points.txt']:
            tar.add(ROOT/'tutor-extension'/name,arcname='tutor-extension/'+name)
    subprocess.run(['scp','-q','-o','ProxyJump=research-cluster-xh5',str(archive),
                    'papers-research:/srv/dify-research/writing-install.tar.gz'],check=True,timeout=60)
    code=r'''from pathlib import Path
import datetime,json,shutil,subprocess,tarfile,urllib.request,time
base=Path('/srv/dify-research');wb=Path('/srv/research-workbench')
probe="from server.app import store\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
old=wb/'releases'/('before-writing-'+stamp);old.mkdir(parents=True)
with tarfile.open(base/'writing-install.tar.gz') as tar:
 for item in tar.getmembers():
  target=(wb/'source'/item.name) if item.name.startswith('server/') else base/item.name
  if target.exists():
   prior=old/item.name;prior.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,prior)
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(tar.extractfile(item).read());target.chmod(0o644)
  if target.suffix=='.py':compile(target.read_text(),str(target),'exec')
subprocess.run(['docker','restart','research-workbench'],check=True,capture_output=True)
for _ in range(50):
 try:
  with urllib.request.urlopen('http://127.0.0.1:47900/health',timeout=2) as r:
   if json.load(r).get('ok'):break
 except OSError:pass
 time.sleep(.3)
else:raise RuntimeError('Workbench health failed')
print(json.dumps({'backend_installed':True,'rollback':str(old),'native_core_modified':False}))
'''
    report=json.loads(remote(code))
    published=remote("import subprocess\nr=subprocess.run(['python3','/srv/dify-research/ops/setup_writing.py'],capture_output=True,text=True)\nprint(r.stdout)\nassert r.returncode==0,r.stderr",90)
    report['workflow']=json.loads(published.strip().splitlines()[-1])
    (ROOT/'reports/writing-install.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
