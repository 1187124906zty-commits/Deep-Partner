"""Bounded Slurm build of the author trial; no product publication."""
from pathlib import Path
import argparse,json,sys,subprocess
from shlex import quote
from build_unified_ui import ROOT,REMOTE,ssh,scp

REPORT=ROOT/'reports/paper-map-preview-build.json'
def submit():
    folder=ROOT/'.local/paper-map-preview'
    script=f'''#!/bin/bash
#SBATCH --job-name=paper-map-trial
#SBATCH --partition=xhacnormalb
#SBATCH --account=cluster_user
#SBATCH --qos=user_cluster_user
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output={REMOTE}/logs/paper-map-trial-%j.log
set -euo pipefail
module purge
module load apps/apptainer/1.3.4
apptainer exec --writable --cleanenv --bind /work --home /work/home/cluster_user:/work/home/cluster_user /work/home/cluster_user/opensource/openpaso/containers/python-runtime /bin/bash -c '
set -euo pipefail
export PATH=/work/home/cluster_user/.pi-desktop/pi-host/current/bin:$PATH
root={REMOTE}
exec 9>"$root/paper-map-trial.lock"
flock 9
mkdir -p "$root/tmp/paper-map-preview"
tar -xzf "$root/paper-map-review-source.tar.gz" -C "$root/tmp/paper-map-preview"
cd "$root/tmp/paper-map-preview"
ln -sfn "$root/src/web/node_modules" node_modules
node "$root/src/web/node_modules/vitest/vitest.mjs" run components/paper-content-map-data.test.ts components/paper-content-map.test.tsx --maxWorkers=1 --minWorkers=1 --pool=forks
node build.mjs
'
'''
    path=folder/'trial.sbatch';path.write_text(script,encoding='utf8',newline='\n');scp(path,REMOTE+'/paper-map-trial.sbatch')
    job=ssh('sbatch --parsable '+REMOTE+'/paper-map-trial.sbatch').split(';')[0]
    report={'job_id':job,'state':'submitted','log':REMOTE+'/logs/paper-map-trial-'+job+'.log','artifact':REMOTE+'/artifacts/paper-map-review.html'}
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
def status():
    report=json.loads(REPORT.read_text());print(ssh('sacct -j '+report['job_id']+' --format=JobID,State,ExitCode,Elapsed -X --noheader'))
    log=quote(report['log'])
    print(ssh('if [ -f '+log+' ]; then tail -25 '+log+'; fi'))
def fetch(target=None):
    report=json.loads(REPORT.read_text());assert 'COMPLETED|0:0' in ssh('sacct -j '+report['job_id']+' --format=State,ExitCode -X --noheader --parsable2')
    target=target or ROOT/'reports/氯硫框架具体化/paper-maps-20261104/Qin论文_关键论证画布试读.html'
    target.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['scp','-q','research-cluster-xh5:'+report['artifact'],str(target)],check=True,timeout=90)
    if target.name=='Qin论文_关键论证画布试读.html':
        old=target.with_name('Qin引言_内容画布试读.html');old.write_bytes(target.read_bytes())
    report.update(state='COMPLETED',local_artifact=str(target));REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','status','fetch']);parser.add_argument('--target',type=Path);args=parser.parse_args()
    if args.action=='fetch':fetch(args.target)
    else:{'submit':submit,'status':status}[args.action]()
