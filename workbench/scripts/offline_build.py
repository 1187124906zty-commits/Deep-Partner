from pathlib import Path
import argparse
import json
import subprocess
from cluster_build import ROOT,REMOTE,SSH,SCP,remote

p=argparse.ArgumentParser();p.add_argument('--upload-dependencies',action='store_true');args=p.parse_args()
if args.upload_dependencies:
    subprocess.run([SCP,'-q',str(ROOT/'build/offline-packages.tar.gz'),'research-cluster-xh5:'+REMOTE+'/offline-packages.tar.gz'],check=True,timeout=120)
    code=f'''from pathlib import Path
import tarfile,shutil
root=Path({REMOTE!r})
with tarfile.open(root/'offline-packages.tar.gz') as tar:
 for member in tar.getmembers():
  assert member.isfile() and (root/member.name).resolve().is_relative_to(root)
 tar.extractall(root)
shutil.copyfile(root/'offline-package-lock.json',root/'src/web/package-lock.json')
p=root/'run-build.sh'
s=p.read_text();s=s.replace('install --no-fund --no-audit','ci --offline --no-fund --no-audit')
p.write_text(s)
print('Verified dependency archives received; build is offline')
'''
    print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',code),flush=True)
patch=ROOT/'build/frontend-current.tar.gz'
import tarfile
with tarfile.open(patch,'w:gz') as tar:
    for path in (ROOT/'web/src').rglob('*'):
        if path.is_file():tar.add(path,arcname=path.relative_to(ROOT))
subprocess.run([SCP,'-q',str(patch),'research-cluster-xh5:'+REMOTE+'/frontend-current.tar.gz'],check=True,timeout=45)
print(remote('tar -xzf '+REMOTE+'/frontend-current.tar.gz -C '+REMOTE+'/src').strip(),flush=True)
print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',f"from pathlib import Path\np=Path({REMOTE!r})/'run-build.sh'\ns=p.read_text().replace('static server templates vendor licenses','static')\nif 'vitest.mjs run' not in s:s=s.replace('node node_modules/typescript/bin/tsc --noEmit','node node_modules/typescript/bin/tsc --noEmit\\nnode node_modules/vitest/vitest.mjs run')\np.write_text(s)\n").strip(),flush=True)
job=remote('sbatch --parsable '+REMOTE+'/build.sbatch').strip().split(';')[0]
report={'job_id':job,'connection':'research-cluster-xh5','source_root':REMOTE+'/src','runtime':REMOTE+'/artifacts/research-workbench-runtime.tar.gz','log':REMOTE+'/logs/build-'+job+'.log','state':'submitted','offline':True}
(ROOT/'verification/build.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
