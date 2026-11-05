"""Collect source snapshots of the two active studies, keeping running data remote."""
from pathlib import Path
import json,subprocess,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'.local/project-onboarding';DEST.mkdir(parents=True,exist_ok=True)
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration'

def main():
    code=r'''from pathlib import Path
import os,json,tarfile,io
base=Path('/work/home/cluster_user/research-projects')
extensions={'.py','.cpp','.cc','.c','.h','.hpp','.f','.f90','.m','.sh','.sbatch','.cmake','.pro','.txt','.md','.json','.yaml','.yml','.toml','.csv','.xml','.dat','.inp','.pdf','.png','.svg'}
for name,folders in [('feng2015-vcctl-sulfate',['src','scripts','configs','software','sources','research']),('chloride-sulfate-3d-bayes-phasefield',['src','jobs','preparation','research'])]:
 root=base/name;selected=[];omitted=[]
 for folder in folders:
  for current,dirs,files in os.walk(root/folder):
   dirs[:]=[d for d in dirs if d not in {'.git','node_modules','__pycache__','.venv','.pytest_cache'} and not d.startswith(('build','cmake-build'))]
   for filename in files:
    path=Path(current)/filename
    if path.is_symlink():continue
    if path.suffix.lower() not in extensions and path.name not in {'Makefile','CMakeLists.txt'}:continue
    if path.stat().st_size>24*1024**2:omitted.append(path.relative_to(root).as_posix());continue
    selected.append((path,'project/'+path.relative_to(root).as_posix()))
 for path in root.glob('*'):
  if path.is_file() and path.suffix in {'.md','.json','.toml'}:selected.append((path,'project/'+path.name))
 output=base/'deeptutor-integration'/(name+'-onboarding.tar.gz')
 manifest={'project':name,'authoritative_root':str(root),'files':[],'omitted_large_or_runtime':'running results, raw fields, environments, binaries and caches remain in the authoritative cluster project','omitted_large_files':omitted}
 with tarfile.open(output,'w:gz') as bundle:
  for path,relative in selected:
   try:
    stat=path.stat();data=path.read_bytes()
   except FileNotFoundError:continue
   info=tarfile.TarInfo(relative);info.size=len(data);bundle.addfile(info,io.BytesIO(data));manifest['files'].append({'path':relative,'bytes':len(data),'source_mtime':stat.st_mtime})
  content=json.dumps(manifest,ensure_ascii=False,indent=2).encode();info=tarfile.TarInfo('source-snapshot.json');info.size=len(content);bundle.addfile(info,io.BytesIO(content))
 print(json.dumps({'name':name,'archive':str(output),'files':len(manifest['files']),'source_bytes':sum(f['bytes'] for f in manifest['files']),'archive_bytes':output.stat().st_size}))
'''
    script=DEST/'collect_cluster_sources.py';script.write_text(code,encoding='utf8',newline='\n')
    subprocess.run(['scp','-q',str(script),'research-cluster-xh5:'+REMOTE+'/collect_cluster_sources.py'],check=True)
    result=subprocess.run(['ssh','-o','BatchMode=yes','research-cluster-xh5','/public/software/apps/anaconda3/2023.09/bin/python '+REMOTE+'/collect_cluster_sources.py'],capture_output=True,text=True,encoding='utf8',check=True,timeout=150)
    reports=[]
    for line in result.stdout.splitlines():
        row=json.loads(line);archive=DEST/(row['name']+'.tar.gz')
        subprocess.run(['scp','-q','research-cluster-xh5:'+row['archive'],str(archive)],check=True,timeout=180)
        folder=DEST/row['name'];folder.mkdir(exist_ok=True)
        with tarfile.open(archive) as bundle:
            assert all((folder/m.name).resolve().is_relative_to(folder.resolve()) for m in bundle.getmembers())
            bundle.extractall(folder,filter='data')
        row.update(local_folder=str(folder),local_archive=str(archive));reports.append(row)
    # The coupled study also depends on these already acquired full texts.
    coupled=DEST/'chloride-sulfate-3d-bayes-phasefield/project/references';coupled.mkdir(exist_ok=True)
    source=Path('D:/Development/references/chloride-sulfate-models')
    import shutil
    for file in source.iterdir():
        if file.is_file() and file.suffix in {'.pdf','.md','.json'}:shutil.copy2(file,coupled/file.name)
    for name in ['Chen2025_Hydraulic.md','Bae2025_BPINN.md']:
        file=Path('C:/Users/DEVELOPER/.codex/idea-memo/tmp')/name
        if file.is_file():shutil.copy2(file,coupled/file.name)
    (ROOT/'reports/three-project-sources.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(reports,ensure_ascii=False))

if __name__=='__main__':main()
