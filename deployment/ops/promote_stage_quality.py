"""Publish the reviewed stage-quality files and the verified frontend build."""
from pathlib import Path
import json
import subprocess
import tarfile
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Development/research-workbench')
sys.path.insert(0, str(SOURCE / 'scripts'))
from deploy import remote, start


def source_path(relative):
    special={'dist/research-workbench-mcp.zip':'mcp-package/dist/research-workbench-mcp.zip',
             'integrations/workbench-mcp/USAGE.md':'mcp-package/USAGE.md',
             'integrations/workbench-mcp/tool-manifest.json':'mcp-package/reports/quality-tool-manifest.json'}
    return SOURCE/special.get(relative,relative)


def main():
    manifest = json.loads((ROOT/'reports/quality-release-files.json').read_text(encoding='utf8'))
    archive = ROOT/'.local/quality-release.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for relative in manifest['files']:
            bundle.add(source_path(relative), arcname=relative)
    files = [(archive, '/srv/research-workbench/quality-release.tar.gz'),
             (SOURCE/'build/research-workbench-runtime.tar.gz', '/srv/research-workbench/quality-static.tar.gz'),
             (ROOT/'bridge/delivery.py', '/srv/research-workbench/quality-delivery.py')]
    for local, target in files:
        subprocess.run(['scp','-q',str(local),'papers-research:'+target], check=True, timeout=120)
    code = r'''from pathlib import Path
import subprocess,json,tarfile,sqlite3,shutil,datetime
root=Path('/srv/research-workbench');source=root/'source'
probe="from server.app import store\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'\nprint('idle')"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
delivery_db=Path('/srv/dify-research/state/deliveries.sqlite3')
for candidate in Path('/srv/dify-research/state').glob('*.sqlite*'):
 with sqlite3.connect(candidate) as db:
  if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deliveries'").fetchone():
   assert not db.execute("SELECT id FROM deliveries WHERE state IN ('pending','prepared','written')").fetchall(),'Bridge has active deliveries'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
rollback=root/'releases'/('before-quality-'+stamp);rollback.mkdir(parents=True)
with tarfile.open(root/'quality-release.tar.gz') as bundle:
 names=bundle.getnames()
 assert names and all(m.isfile() and (source/m.name).resolve().is_relative_to(source.resolve()) for m in bundle.getmembers())
 with tarfile.open(rollback/'targeted-source.tar.gz','w:gz') as saved:
  for name in names:
   if (source/name).is_file():saved.add(source/name,arcname=name)
 (rollback/'new-files.json').write_text(json.dumps([n for n in names if not (source/n).exists()]))
 bundle.extractall(source,filter='data')
with tarfile.open(rollback/'static.tar.gz','w:gz') as saved:saved.add(source/'static',arcname='static')
with tarfile.open(root/'quality-static.tar.gz') as bundle:
 assert all(m.name=='static' or m.name.startswith('static/') for m in bundle.getmembers())
 bundle.extractall(source,filter='data')
bridge=Path('/srv/dify-research/bridge/delivery.py')
shutil.copyfile(bridge,rollback/'delivery.py')
shutil.copyfile(root/'quality-delivery.py',bridge)
print(json.dumps({'rollback':str(rollback),'files':names,'frontend_index':(source/'static/index.html').read_text()}))
'''
    prepared=json.loads(remote(code, timeout=80, root=True).strip())
    start()
    report=json.loads(remote(r'''import subprocess,json,urllib.request
subprocess.run(['docker','restart','dify-workbench-bridge'],check=True,capture_output=True)
with urllib.request.urlopen('http://127.0.0.1:47900/health',timeout=10) as r:workbench=json.load(r)
from pathlib import Path
print(json.dumps({'workbench':workbench,'bridge_running':subprocess.check_output(['docker','inspect','dify-workbench-bridge','--format','{{.State.Running}}'],text=True).strip()=='true','standard_version':'2026-11-02-quality1','native_tutor_restarted':False}))
''',timeout=60,root=True).strip())
    report.update({'status':'deployed','frontend_job':manifest['frontend_job'],'rollback':prepared['rollback'],'files':manifest['files'],'frontend_index':prepared['frontend_index']})
    (ROOT/'reports/quality-release-files.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
