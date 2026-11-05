"""Receive a completed Slurm build and publish only its current web assets."""
from pathlib import Path
import json,subprocess,tarfile,time,shlex
from cluster_build import ROOT,SSH,SCP,remote

v=json.loads((ROOT/'verification/build.json').read_text())
status=remote('sacct -j '+v['job_id']+' --format=JobID,State,ExitCode -P')
if not any(line.startswith(v['job_id']+'|COMPLETED|0:0') for line in status.splitlines()):raise RuntimeError(status)
archive=ROOT/'build/research-workbench-runtime.tar.gz'
# Content-addressed Vite assets already installed on the app server are reusable.
# Ship the new entry and changed assets; the complete build stays on the cluster.
code="from pathlib import Path\nimport json\nr=Path('/srv/research-workbench/source/static')\nprint(json.dumps(['static/'+p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file()]))\n"
known_result=subprocess.run([SSH,'-o','BatchMode=yes','-o','ConnectTimeout=12','papers-research','python3 -'],input=code,text=True,encoding='utf8',capture_output=True,check=True,timeout=40)
known=json.loads(known_result.stdout)
incremental=v['runtime'].replace('research-workbench-runtime.tar.gz','research-workbench-web-current.tar.gz')
code=f'''from pathlib import Path
import json,re,tarfile
known=set({known!r})
with tarfile.open({v['runtime']!r}) as source, tarfile.open({incremental!r},'w:gz') as target:
 selected=[]
 for member in source.getmembers():
  if not member.isfile():continue
  assert member.name.startswith('static/') and '..' not in Path(member.name).parts
  immutable=re.fullmatch(r'static/assets/[^/]+-[A-Za-z0-9_-]{{8,}}\\.[^/]+',member.name)
  if immutable and member.name in known:continue
  target.addfile(member,source.extractfile(member));selected.append({{'path':member.name,'bytes':member.size}})
assert any(p['path']=='static/index.html' for p in selected)
print(json.dumps({{'files':selected,'archive_bytes':Path({incremental!r}).stat().st_size}}))
'''
selection=json.loads(remote('/public/software/apps/anaconda3/2023.09/bin/python -',code,timeout=50))
# Use the already authorized SSH channel for this small binary build artifact.
# The cluster SFTP download stalled although queries and uploads worked.
pending=archive.with_suffix('.incoming')
try:
    with pending.open('wb') as stream:
        subprocess.run([SSH,'-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=15','research-cluster-xh5','cat -- '+shlex.quote(incremental)],stdout=stream,stderr=subprocess.PIPE,check=True,timeout=300)
    with tarfile.open(pending) as candidate:
        if 'static/index.html' not in candidate.getnames():raise ValueError('Build archive has no frontend entry')
        assert {m.name:m.size for m in candidate.getmembers() if m.isfile()}=={p['path']:p['bytes'] for p in selection['files']}
    pending.replace(archive)
finally:pending.unlink(missing_ok=True)
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        if member.isfile() and member.name.startswith('static/'):
            relative=member.name.removeprefix('static/');target=ROOT/'build/preview-static'/relative
            assert target.resolve().is_relative_to((ROOT/'build/preview-static').resolve())
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tar.extractfile(member).read())
subprocess.run([SCP,'-q',str(archive),'papers-research:/srv/research-workbench/runtime-current.tar.gz'],check=True,timeout=90)
code="from pathlib import Path\nimport tarfile\nr=Path('/srv/research-workbench')\nwith tarfile.open(r/'runtime-current.tar.gz') as t:t.extractall(r/'source',members=[m for m in t.getmembers() if m.name.startswith('static/')],filter='data')\nprint('Current web assets installed')\n"
r=subprocess.run([SSH,'-o','ConnectTimeout=12','papers-research','python3 -'],input=code,text=True,encoding='utf8',capture_output=True,timeout=35)
if r.returncode:raise RuntimeError(r.stderr[-900:])
v.update(state='COMPLETED',exit_code='0:0',deployment='new entry and changed Vite assets',transferred=selection,transfer_archive=incremental);(ROOT/'verification/build.json').write_text(json.dumps(v,indent=2))
(ROOT/'build/preview-revision.json').write_text(json.dumps({'updated':time.time_ns()}));print(r.stdout,flush=True)
