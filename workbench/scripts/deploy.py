"""Install a separate same-domain workbench without restarting DeepTutor."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
SSH='C:/Windows/System32/OpenSSH/ssh.exe'
SCP='C:/Windows/System32/OpenSSH/scp.exe'
HOST='papers-research'


def remote(code,timeout=45,root=False):
    jump=['-o','ProxyJump='+os.environ['WORKBENCH_PROXY_JUMP']] if os.environ.get('WORKBENCH_PROXY_JUMP') else []
    result=subprocess.run([SSH,'-o','BatchMode=yes','-o','ConnectTimeout=12',*jump,HOST,('sudo -n ' if root else '')+'python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr[-2500:] or result.stdout[-1500:])
    return result.stdout


def upload_backend(folders=None):
    archive=ROOT/'build/backend-current.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in (folders or ['server','templates','vendor','licenses','examples']):
            for p in (ROOT/name).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.part'):tar.add(p,arcname=p.relative_to(ROOT))
    subprocess.run([SCP,'-q',str(archive),HOST+':/srv/research-workbench/backend-current.tar.gz'],check=True,timeout=180)
    print(remote("from pathlib import Path\nimport tarfile\nr=Path('/srv/research-workbench')\nwith tarfile.open(r/'backend-current.tar.gz') as t:t.extractall(r/'source',filter='data')\nprint('Current server sources received')\n").strip(),flush=True)


def start():
    code=r'''from pathlib import Path
import subprocess,json,time,urllib.request,os
root=Path('/srv/research-workbench');source=root/'source'
data=Path('/srv/deeptutor/data/research-workbench');data.mkdir(exist_ok=True);os.chown(data,1000,1000)
existing=subprocess.run(['docker','ps','-a','--filter','name=^research-workbench$','--format','{{.Names}}'],capture_output=True,text=True).stdout.strip()
if existing:
 probe="from server.app import store;import json\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work; keep it running'\nprint('idle; queued local downloads are retained')"
 state=json.loads(subprocess.check_output(['docker','inspect','research-workbench'],text=True))[0]['State']
 if state['Running']:subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
 subprocess.run(['docker','rm','-f','research-workbench'],check=True,capture_output=True)
image=json.loads(subprocess.check_output(['docker','inspect','deeptutor'],text=True))[0]['Image']
custom=subprocess.run(['docker','image','inspect','research-workbench-runtime:current','--format','{{.Id}}'],capture_output=True,text=True)
if custom.returncode==0:image=custom.stdout.strip()
subprocess.run(['docker','run','-d','--name','research-workbench','--restart','unless-stopped','--network','host','--user','1000:1000',
 '--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','2','--memory','3g','--workdir','/workbench','--health-cmd','python /workbench/server/healthcheck.py',
 '-e','WORKBENCH_DATA=/app/data/research-workbench','-e','WORKBENCH_NATIVE_URL=http://127.0.0.1:8008',
 '-e','WORKBENCH_ORIGIN=https://tutor.example.invalid','-e','WORKBENCH_PANDOC=/opt/workbench-tools/pandoc/bin/pandoc',
 '-e','HOME=/app/data/research-workbench/runtime-home','-e','PYTHONPATH=/opt/workbench-tools/python-libs',
 '-v',str(source)+':/workbench:ro','-v',str(root/'tools')+':/opt/workbench-tools:ro',
 '-v',str(root/'fonts')+':/usr/share/fonts/truetype/research-workbench:ro',
 '-v','/srv/deeptutor/data:/app/data','-v','/srv/deeptutor/workspaces:/workspace',
 '--entrypoint','python',image,'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','47900'],check=True,capture_output=True)
for i in range(40):
 try:
  with urllib.request.urlopen('http://127.0.0.1:47900/health',timeout=2) as r:status=json.load(r)
  if status.get('ok'):break
 except OSError:pass
 time.sleep(.5)
else:raise RuntimeError('Workbench health failed')
print(json.dumps({'service_ready':True,'listen':'127.0.0.1:47900','native_tutor_restarted':False,'image':image}))
'''
    print(remote(code,root=True).strip(),flush=True)
    import time
    (ROOT/'build/preview-revision.json').write_text(json.dumps({'deployed':time.time_ns()}),encoding='utf8')


def publish():
    code=r'''from pathlib import Path
import subprocess,json
path=Path('/etc/caddy/deeptutor.caddy');text=path.read_text()
block='''+repr('    handle /research {\n        reverse_proxy 127.0.0.1:47900\n    }\n    handle /research/* {\n        reverse_proxy 127.0.0.1:47900\n    }\n')+r'''
if 'handle /research/* {' not in text:
 marker='    handle /novix {'
 assert marker in text,'Site routing changed; inspect first'
 old=text;text=text.replace(marker,block+marker,1)
 trial=path.with_name('research-workbench.caddy.check');trial.write_text(text)
 try:
  subprocess.run(['caddy','validate','--config',str(trial),'--adapter','caddyfile'],check=True,capture_output=True)
  path.write_text(text)
  subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
 except Exception:
  path.write_text(old);raise
 finally:trial.unlink(missing_ok=True)
print(json.dumps({'published':True,'url':'https://tutor.example.invalid/research/','original_routes_preserved':True,'native_tutor_restarted':False}))
'''
    report=json.loads(remote(code,root=True).strip().splitlines()[-1])
    (ROOT/'verification/deployment.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--skip-backend-upload',action='store_true');p.add_argument('--server-only',action='store_true');args=p.parse_args()
    if not args.skip_backend_upload:upload_backend(['server','vendor/workbench-skills'] if args.server_only else None)
    start()
    if args.publish:publish()
