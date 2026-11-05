"""Stream selected development files to the cluster without a local archive."""
from pathlib import Path
import argparse,json,os,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration/development'
WB=Path('D:/Development/research-workbench')
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
SOURCE_FOLDERS=['server','web/src','unified-ui/src','unified-ui/scripts','scripts','templates','tests','docs','licenses','vendor']
SOURCE_FILES=['README.md','requirements.txt','web/package.json','web/tsconfig.json','unified-ui/package.json','unified-ui/tsconfig.json','unified-ui/vite.config.ts','unified-ui/index.html']
DATA_FOLDERS=[('workbench-build',WB/'build'),('project-onboarding',ROOT/'.local/project-onboarding'),('document-parse-results',ROOT/'reports/mineru-books')]


def included(path):
    return not any(part in ('node_modules','__pycache__','.git','.pytest_cache','dist') for part in path.parts) and path.name not in ('admin-login.json','api-settings.json','device-credential','bridge-token') and not path.name.startswith('.env')


def source_files():
    for name in SOURCE_FOLDERS:
        for p in (WB/name).rglob('*'):
            if p.is_file() and included(p):yield p,'workbench/'+p.relative_to(WB).as_posix()
    for name in SOURCE_FILES:
        p=WB/name
        if p.is_file():yield p,'workbench/'+name
    for folder in ['src','assets','icons','licenses','scripts']:
        for p in (NATIVE/folder).rglob('*'):
            if p.is_file() and included(p):yield p,'desktop/'+p.relative_to(NATIVE).as_posix()
    for name in ['Cargo.toml','Cargo.lock','tauri.conf.json','build.rs']:
        yield NATIVE/name,'desktop/'+name
    for folder in ['ops','docs','tests','quality-skills','quality-knowledge']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and included(p):yield p,'deployment/'+p.relative_to(ROOT).as_posix()
    for p in (ROOT/'reports').glob('*.json'):
        if included(p):yield p,'deployment/reports/'+p.name


def transfer(label,files):
    manifest=[]
    target=REMOTE+'/'+label
    remote_script="""import sys,tarfile,json,os
from pathlib import Path
root=Path(TARGET);root.mkdir(parents=True,exist_ok=True)
files=0;size=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz') as tar:
 for member in tar:
  if not member.isfile() or not (root/member.name).resolve().is_relative_to(root.resolve()):raise ValueError('Invalid development archive member')
  tar.extract(member,root);files+=1;size+=member.size
print(json.dumps({'remote_root':str(root),'files':files,'bytes':size}))
""".replace('TARGET',repr(target))
    child=subprocess.Popen(['ssh','-o','BatchMode=yes','research-cluster-xh5','/public/software/apps/anaconda3/2023.09/bin/python -c '+__import__('shlex').quote(remote_script)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=child.stdin,mode='w|gz',compresslevel=1) as bundle:
            for path,name in files:
                with path.open('rb') as content:
                    item=bundle.gettarinfo(fileobj=content,arcname=name)
                    bundle.addfile(item,content)
                    manifest.append({'path':name,'bytes':item.size})
        child.stdin.close();stdout=child.stdout.read();stderr=child.stderr.read();child.wait(timeout=180)
    except Exception:
        child.terminate();raise
    if child.returncode:raise RuntimeError(stderr.decode('utf8',errors='replace')[-2500:])
    result=json.loads(stdout);assert result['files']==len(manifest) and result['bytes']==sum(row['bytes'] for row in manifest)
    result['label']=label;result['verified_names_and_sizes']=True
    (ROOT/'reports'/('cluster-development-'+label+'.json')).write_text(json.dumps({'result':result,'files':manifest},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('scope',choices=['source','data']);args=parser.parse_args()
    if args.scope=='source':transfer('source',list(source_files()))
    else:
        for label,folder in DATA_FOLDERS:
            files=[(p,p.relative_to(folder).as_posix()) for p in folder.rglob('*') if p.is_file() and included(p)]
            transfer(label,files)


if __name__=='__main__':main()
