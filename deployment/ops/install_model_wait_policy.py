"""Install the verified model-wait policy as persistent, read-only source mounts."""
from pathlib import Path
import json
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SSH = ['ssh', '-o', 'ProxyJump=research-cluster-xh5', 'papers-research']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log = (ROOT/'reports/model-wait-policy-candidate.log').read_text(encoding='utf-8')
    assert 'Ran 9 tests' in log and log.rstrip().endswith('OK'), 'Candidate verification is required'
    archive = ROOT/'.local/model-wait-policy.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        bundle.add(ROOT/'.local/model-timeout-candidate', arcname='candidate')
        bundle.add(ROOT/'ops/verify_model_wait_policy.py', arcname='test_model_wait_policy.py')
    subprocess.run(['scp', '-q', '-o', 'ProxyJump=research-cluster-xh5', str(archive),
                    'papers-research:/srv/deeptutor/migration/model-wait-policy.tar.gz'], check=True, timeout=60)
    stage = r"""from pathlib import Path
import tarfile,shutil,json,subprocess
incoming=Path('/srv/deeptutor/migration/model-wait-policy')
with tarfile.open(incoming.with_suffix('.tar.gz')) as bundle:
    bundle.extractall(incoming,filter='data')
target=Path('/srv/dify-research/model-wait-policy');target.mkdir(parents=True,exist_ok=True)
files=[]
for source in (incoming/'candidate').rglob('*.py'):
    relative=source.relative_to(incoming/'candidate')
    content=source.read_text();compile(content,str(relative),'exec')
    destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination);destination.chmod(0o644);files.append(str(relative))
override=Path('/srv/deeptutor/compose.override.yaml')
config=json.loads(override.read_text())
volumes=config['services']['deeptutor'].setdefault('volumes',[])
for relative in files:
    destination='/app/'+relative
    volumes[:]=[v for v in volumes if not (isinstance(v,str) and v.split(':')[1]==destination)]
    volumes.append(str(target/relative)+':'+destination+':ro')
override.write_text(json.dumps(config,indent=2)+'\n')
subprocess.run(['docker','compose','-f','/srv/deeptutor/compose.yaml','-f',str(override),'config','--quiet'],check=True)
print(json.dumps({'staged':files,'persistent_mounts':True}))
"""
    result = subprocess.run([*SSH, 'sudo -n python3 -'], input=stage,
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    if result.returncode:
        raise RuntimeError(result.stderr)
    report = json.loads(result.stdout)
    # Recheck the affected research session immediately before replacing the worker.
    check = """import json,httpx
from pathlib import Path
account=json.loads(Path('/migration/admin-login.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:8001',headers={'Origin':'https://tutor.example.invalid'},trust_env=False,timeout=20) as client:
    client.post('/api/auth/login',json=account).raise_for_status()
    client.headers['Cookie']='; '.join(k+'='+v for k,v in client.cookies.items())
    response=client.get('/api/sessions',params={'dt_workspace':'ws_0e6fc7aba58a4b258e25e1195702fde3'})
    response.raise_for_status();sessions=response.json()['sessions']
    active=[s['id'] for s in sessions if s.get('active_turn_id')]
    print(json.dumps({'active_turns':active}));assert not active,'Research session is active; wait before reloading'
"""
    status = subprocess.run([*SSH, 'docker exec -i deeptutor python -'], input=check,
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    if status.returncode:
        raise RuntimeError(status.stdout+status.stderr)
    report['before_reload'] = json.loads(status.stdout)
    result = subprocess.run([*SSH, 'sudo -n docker compose -f /srv/deeptutor/compose.yaml '
                            '-f /srv/deeptutor/compose.override.yaml up -d --no-deps --pull never deeptutor'],
                            capture_output=True, text=True, encoding='utf-8', timeout=90)
    report.update(reload_exit_code=result.returncode, reload_output=result.stdout+result.stderr)
    (ROOT/'reports/model-wait-policy-install.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if result.returncode:
        raise RuntimeError('Service reload failed; see installation report')


if __name__ == '__main__':
    main()
