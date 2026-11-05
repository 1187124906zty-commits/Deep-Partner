"""Download pinned public Go source modules for an offline Slurm compilation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,re,tarfile,time,urllib.request

ROOT=Path(__file__).resolve().parents[1]
modules=re.findall(r'^\s*([^\s()]+)\s+(v[^\s]+)',(ROOT/'build/neoread-source/apps/server/go.mod').read_text(),re.M)
cache=ROOT/'build/go-proxy-cache'


def download(pair):
    module,version=pair;escaped=''.join('!'+c.lower() if c.isupper() else c for c in module)
    size=0
    for suffix in ('mod','info','zip'):
        relative=escaped+'/@v/'+version+'.'+suffix;dest=cache/relative
        if dest.is_file():size+=dest.stat().st_size;continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        error=None
        for attempt in range(3):
            try:
                with urllib.request.urlopen('https://proxy.golang.org/'+relative,timeout=60) as response:
                    data=response.read()
                dest.write_bytes(data);size+=len(data);error=None;break
            except Exception as e:error=e;time.sleep(attempt+1)
        if error:raise error
    return module,size


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=6) as pool:
        for future in as_completed([pool.submit(download,m) for m in modules]):
            name,size=future.result();print(name,round(size/1024**2,2),'MiB',flush=True)
    archive=ROOT/'build/go-proxy-cache.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path in cache.rglob('*'):
            if path.is_file():tar.add(path,arcname=path.relative_to(cache))
    print(json.dumps({'modules':len(modules),'archive':str(archive),'bytes':archive.stat().st_size,'integrity':'Go verifies committed go.sum during offline build'}),flush=True)
