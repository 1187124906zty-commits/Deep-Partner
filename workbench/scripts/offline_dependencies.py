"""Reuse the existing frontend's pinned-tarball workflow for offline Slurm."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import base64
import hashlib
import json
import tarfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench'
cache=ROOT/'build/npm-archives';cache.mkdir(parents=True,exist_ok=True)
lock=json.loads((ROOT/'web/package-lock.json').read_text())
items={}
for item in lock['packages'].values():
    url=item.get('resolved','')
    if not url:continue
    url=url.replace('https://registry.npmmirror.com/','https://registry.npmjs.org/')
    if not url.startswith('https://registry.npmjs.org/'):raise ValueError('Unexpected package origin')
    name=hashlib.sha256(url.encode()).hexdigest()+'.tgz'
    item['resolved']='file://'+REMOTE+'/package-archives/'+name
    oses=item.get('os',[]);cpus=item.get('cpu',[])
    if oses and 'linux' not in oses and not all(x.startswith('!') for x in oses):continue
    if cpus and 'x64' not in cpus and not all(x.startswith('!') for x in cpus):continue
    if '!linux' in oses or '!x64' in cpus:continue
    items[url]=(name,item.get('integrity'))

def fetch(pair):
    url,(name,integrity)=pair;path=cache/name
    if not path.exists():
        for attempt in range(3):
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'Research-workbench-pinned-build'})
                data=urllib.request.urlopen(request,timeout=60).read()
                if integrity:
                    algorithm,expected=integrity.split(' ',1)[0].split('-',1)
                    assert base64.b64encode(hashlib.new(algorithm,data).digest()).decode()==expected
                path.write_bytes(data);break
            except Exception:
                if attempt==2:raise
                time.sleep(1+attempt)
    return path.stat().st_size

size=0;count=0
with ThreadPoolExecutor(max_workers=6) as pool:
    for future in as_completed([pool.submit(fetch,item) for item in items.items()]):
        size+=future.result();count+=1
        if count%75==0:print(json.dumps({'downloaded':count,'of':len(items)}),flush=True)
(ROOT/'build/offline-package-lock.json').write_text(json.dumps(lock,indent=2),encoding='utf8')
with tarfile.open(ROOT/'build/offline-packages.tar.gz','w:gz') as tar:
    for path in cache.glob('*.tgz'):tar.add(path,arcname='package-archives/'+path.name)
    tar.add(ROOT/'build/offline-package-lock.json',arcname='offline-package-lock.json')
report={'packages':count,'bytes':size,'original_integrities_verified':True,'compile_location':'Slurm'}
(ROOT/'verification/offline-dependencies.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
