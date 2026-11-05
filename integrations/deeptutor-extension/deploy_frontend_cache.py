"""Install the checked frontend bundle while preserving existing backend mounts.

Run on papers-research after the Slurm production build has succeeded.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import yaml

ROOT=Path('/srv/deeptutor')
BUILD=ROOT/'frontend-cache'
BUILD.mkdir(exist_ok=True)
RUNTIME=BUILD/'runtime'
STAGE=BUILD/'runtime.incoming'
ARCHIVE=ROOT/'migration/frontend-runtime.tar.gz'
IMAGE='deeptutor:1.7.0-memory-cache'


def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def main():
    if STAGE.exists():
        assert STAGE.resolve().is_relative_to(BUILD.resolve())
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    with tarfile.open(ARCHIVE) as tar:
        for member in tar.getmembers():
            target=(STAGE/member.name).resolve()
            if not target.is_relative_to(STAGE.resolve()):raise ValueError('Invalid bundle path')
            if member.issym() and not (target.parent/member.linkname).resolve().is_relative_to(STAGE.resolve()):
                raise ValueError('Bundle symlink escapes runtime')
        tar.extractall(STAGE)
    assert (STAGE/'server.js').is_file()
    assert (STAGE/'.next/BUILD_ID').is_file()
    assert (STAGE/'.next/static').is_dir()
    if RUNTIME.exists():
        assert RUNTIME.resolve().is_relative_to(BUILD.resolve())
        shutil.rmtree(RUNTIME)
    STAGE.rename(RUNTIME)
    shutil.copyfile(ROOT/'workbench-src/Dockerfile.frontend-cache',BUILD/'Dockerfile')
    run(['docker','build','-t',IMAGE,str(BUILD)])
    name='deeptutor-frontend-preflight'
    run(['docker','run','--rm','-d','--name',name,'--network','deeptutor_default',
         '-p','127.0.0.1:18008:3782','--memory','256m','--cpus','0.5',
         '-e','PORT=3782','-e','HOSTNAME=0.0.0.0',
         '-e','DEEPTUTOR_API_BASE_URL=http://deeptutor:8001',
         '-e','DEEPTUTOR_AUTH_ENABLED=true','--entrypoint','node',IMAGE,'/app/web/server.js'])
    try:
        for attempt in range(40):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18008/login',timeout=3) as response:
                    assert response.status==200
                    assert 'DeepTutor' in response.read().decode()
                break
            except Exception:
                if attempt==39:raise
                time.sleep(.5)
    finally:
        run(['docker','stop',name],stdout=subprocess.DEVNULL)
    # Don't interrupt an active turn, including one from another browser.
    run(['docker','exec','--user','1000:1000','-e','PYTHONPATH=/app','deeptutor',
         'python','/migration/check_idle.py'])
    compose_path=ROOT/'compose.yaml'
    compose=yaml.safe_load(compose_path.read_text())
    compose['services']['deeptutor']['image']=IMAGE
    compose_path.write_text(yaml.safe_dump(compose,sort_keys=False,allow_unicode=True))
    run(['docker','compose','-f',str(compose_path),'config','--quiet'])
    run(['docker','compose','-f',str(compose_path),'up','-d','deeptutor'])
    receipt={'image':IMAGE,'base':'ghcr.io/hkuds/deeptutor:1.7.0',
        'build_id':(RUNTIME/'.next/BUILD_ID').read_text().strip(),
        'preflight_login_http':200,'backend':'native image and existing mounted extensions',
        'rollback_image':'ghcr.io/hkuds/deeptutor:1.7.0'}
    (ROOT/'migration/frontend-cache-deployment.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
