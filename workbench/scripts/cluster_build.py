"""Bounded Slurm build using the already verified Node/container runtime."""
from pathlib import Path
import json
import subprocess
import tarfile
import textwrap

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench'
SSH='C:/Windows/System32/OpenSSH/ssh.exe'
SCP='C:/Windows/System32/OpenSSH/scp.exe'


def remote(command,input=None,timeout=40):
    result=subprocess.run([SSH,'-o','BatchMode=yes','-o','ConnectTimeout=12','research-cluster-xh5',command],input=input,text=True,encoding='utf8',capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr[-2500:] or result.stdout[-1500:])
    return result.stdout


def main():
    (ROOT/'build').mkdir(exist_ok=True)
    archive=ROOT/'build/source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for folder in ['web','server','templates','vendor','licenses','tests','research']:
            for path in (ROOT/folder).rglob('*'):
                if path.is_file() and not any(part in ('node_modules','__pycache__','.git') for part in path.parts):tar.add(path,arcname=path.relative_to(ROOT))
    setup=f'''from pathlib import Path
root=Path({REMOTE!r})
for name in ['src','logs','tools','artifacts','research','tmp']:(root/name).mkdir(parents=True,exist_ok=True)
print(root)
'''
    print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',setup).strip(),flush=True)
    subprocess.run([SCP,'-q',str(archive),'research-cluster-xh5:'+REMOTE+'/source.tar.gz'],check=True,timeout=90)
    unpack=f'''from pathlib import Path
import tarfile
root=Path({REMOTE!r})
with tarfile.open(root/'source.tar.gz') as tar:
 for member in tar.getmembers():
  assert member.isfile() and (root/'src'/member.name).resolve().is_relative_to(root/'src')
 tar.extractall(root/'src')
for name in ['BRIEF.md','STATE.md']:
 source=root/'src/research'/name
 target=root/'research'/name
 if not target.exists():target.write_bytes(source.read_bytes())
print('Source received')
'''
    print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',unpack).strip(),flush=True)
    inner=textwrap.dedent(f'''\
        #!/bin/bash
        set -euo pipefail
        root={REMOTE}
        export PATH=/work/home/cluster_user/.pi-desktop/pi-host/current/bin:$PATH
        export TMPDIR="$root/tmp"
        export NODE_OPTIONS=--max-old-space-size=3072
        export npm_config_cache=/work/home/cluster_user/research-projects/deeptutor-integration/frontend/npm-cache
        cd "$root/src/web"
        node /work/home/cluster_user/research-projects/deeptutor-integration/frontend/tools/npm/bin/npm-cli.js install --no-fund --no-audit
        node node_modules/typescript/bin/tsc --noEmit
        node node_modules/vitest/vitest.mjs run
        node node_modules/vite/bin/vite.js build
        cd "$root/src"
        python3 -m compileall -q server
        tar -czf "$root/artifacts/research-workbench-runtime.tar.gz" static
        cp web/package-lock.json "$root/artifacts/package-lock.json"
        echo RESEARCH_WORKBENCH_BUILD_PASSED
        ''')
    batch=textwrap.dedent(f'''\
        #!/bin/bash
        #SBATCH --job-name=research-workbench
        #SBATCH --partition=xhacnormalb
        #SBATCH --account=cluster_user
        #SBATCH --qos=user_cluster_user
        #SBATCH --nodes=1
        #SBATCH --ntasks=1
        #SBATCH --cpus-per-task=2
        #SBATCH --mem=5G
        #SBATCH --time=00:15:00
        #SBATCH --output={REMOTE}/logs/build-%j.log
        set -euo pipefail
        module purge
        module load apps/apptainer/1.3.4
        apptainer exec --writable --cleanenv --bind /work --home /work/home/cluster_user:/work/home/cluster_user /work/home/cluster_user/opensource/openpaso/containers/python-runtime /bin/bash {REMOTE}/run-build.sh
        ''')
    for name,value in [('run-build.sh',inner),('build.sbatch',batch)]:
        path=ROOT/'build'/name;path.write_text(value,encoding='utf8',newline='\n')
        subprocess.run([SCP,'-q',str(path),'research-cluster-xh5:'+REMOTE+'/'+name],check=True,timeout=40)
    job=remote('sbatch --parsable '+REMOTE+'/build.sbatch').strip().split(';')[0]
    report={'job_id':job,'connection':'research-cluster-xh5','source_root':REMOTE+'/src','runtime':REMOTE+'/artifacts/research-workbench-runtime.tar.gz','log':REMOTE+'/logs/build-'+job+'.log','state':'submitted'}
    (ROOT/'verification/build.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
