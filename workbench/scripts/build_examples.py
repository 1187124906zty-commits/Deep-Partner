"""Run the two small data-visualization examples on the verified Slurm channel."""
from pathlib import Path
import json,subprocess,tarfile
from cluster_build import ROOT,REMOTE,SSH,SCP,remote

archive=ROOT/'build/examples-current.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for folder in ['examples/pinn-burgers/project','examples/fno-darcy/project']:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file():tar.add(path,arcname=path.relative_to(ROOT))
subprocess.run([SCP,'-q',str(archive),'research-cluster-xh5:'+REMOTE+'/examples-current.tar.gz'],check=True,timeout=60)
print(remote('tar -xzf '+REMOTE+'/examples-current.tar.gz -C '+REMOTE+'/src'),flush=True)
script=f'''#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --account=cluster_user
#SBATCH --qos=user_cluster_user
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
#SBATCH --output={REMOTE}/logs/examples-%j.log
set -euo pipefail
cd {REMOTE}/src
export MPLCONFIGDIR={REMOTE}/tmp/matplotlib
export OMP_NUM_THREADS=1
/work/home/cluster_user/opensource/openpaso/bin/torch-python examples/pinn-burgers/project/src/plot_reference.py
/work/home/cluster_user/opensource/openpaso/bin/torch-python examples/fno-darcy/project/src/plot_reference.py
tar -czf {REMOTE}/artifacts/examples-results.tar.gz examples/pinn-burgers/project/results examples/fno-darcy/project/results
'''
print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',f'from pathlib import Path\nPath({REMOTE!r}+"/examples.sbatch").write_text({script!r})\n'),flush=True)
job=remote('sbatch --parsable '+REMOTE+'/examples.sbatch').strip().split(';')[0]
report={'job_id':job,'state':'submitted','connection':'research-cluster-xh5','source_root':REMOTE+'/src/examples','log':REMOTE+'/logs/examples-'+job+'.log','scope':'Reference-data visualization only; no neural-network training'}
(ROOT/'verification/examples.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
