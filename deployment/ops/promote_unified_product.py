"""Publish the verified shared UI and explicitly listed backend files."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Development/research-workbench')
sys.path.insert(0, str(SOURCE / 'scripts'))
from deploy import remote, start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--files', nargs='+', required=True)
    parser.add_argument('--bridge', action='store_true')
    args = parser.parse_args()
    build = json.loads((ROOT / 'reports/unified-ui-build.json').read_text(encoding='utf8'))
    candidate = json.loads((ROOT / 'reports/unified-ui-candidate.json').read_text(encoding='utf8'))
    assert build.get('state') == 'COMPLETED' and build.get('exit_code') == '0:0'
    assert candidate.get('passed'), 'Candidate browser checks must pass before publication'
    assert candidate.get('frontend_job_id') == build['job_id'], 'Candidate browser check belongs to another build'
    archive = ROOT / '.local/unified-release.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for name in args.files:
            path = (SOURCE / name).resolve()
            assert path.is_relative_to((SOURCE / 'server').resolve()) and path.is_file()
            bundle.add(path, arcname=name)
    uploads = [(archive, '/srv/research-workbench/unified-release.tar.gz'),
               (Path(build['local_artifact']), '/srv/research-workbench/unified-static.tar.gz')]
    if args.bridge:
        uploads.append((ROOT / 'bridge/delivery.py', '/srv/research-workbench/unified-delivery.py'))
    for path, target in uploads:
        subprocess.run(['scp', '-q', str(path), 'papers-research:' + target], check=True, timeout=150)
    code = r'''from pathlib import Path
import datetime,json,sqlite3,subprocess,tarfile,shutil
root=Path('/srv/research-workbench');source=root/'source'
probe="from server.app import store\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
if BRIDGE:
 for candidate in Path('/srv/dify-research/state').glob('*.sqlite*'):
  with sqlite3.connect(candidate) as db:
   if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deliveries'").fetchone():
    assert not db.execute("SELECT id FROM deliveries WHERE state IN ('pending','prepared','written')").fetchall(),'Bridge has active deliveries'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
rollback=root/'releases'/('before-unified-'+stamp);rollback.mkdir(parents=True)
with tarfile.open(root/'unified-release.tar.gz') as bundle:
 members=bundle.getmembers()
 assert members and all(m.isfile() and (source/m.name).resolve().is_relative_to((source/'server').resolve()) for m in members)
 with tarfile.open(rollback/'source.tar.gz','w:gz') as saved:
  for member in members:
   if (source/member.name).is_file():saved.add(source/member.name,arcname=member.name)
 (rollback/'new-files.json').write_text(json.dumps([m.name for m in members if not (source/m.name).exists()]))
 bundle.extractall(source,filter='data')
staged=rollback/'new-static';staged.mkdir()
with tarfile.open(root/'unified-static.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file() and (staged/'assets').is_dir()
(source/'static').rename(rollback/'static')
staged.rename(source/'static')
if BRIDGE:
 bridge=Path('/srv/dify-research/bridge/delivery.py')
 shutil.copyfile(bridge,rollback/'delivery.py')
 shutil.copyfile(root/'unified-delivery.py',bridge)
print(json.dumps({'rollback':str(rollback),'backend_files':[m.name for m in members],'frontend_index':(source/'static/index.html').read_text()}))
'''.replace('if BRIDGE:', 'if ' + repr(args.bridge) + ':')
    prepared = json.loads(remote(code, timeout=90, root=True).strip())
    try:
        start()
        if args.bridge:
            remote("import subprocess\nsubprocess.run(['docker','restart','dify-workbench-bridge'],check=True,capture_output=True)\nprint('bridge-restarted')", timeout=70, root=True)
    except Exception:
        rollback_code = """from pathlib import Path
import json,tarfile,shutil,subprocess
source=Path('/srv/research-workbench/source')
rollback=Path(ROLLBACK_PATH)
for name in json.loads((rollback/'new-files.json').read_text()):
 path=(source/name).resolve()
 assert path.is_relative_to((source/'server').resolve())
 path.unlink(missing_ok=True)
with tarfile.open(rollback/'source.tar.gz') as bundle:bundle.extractall(source,filter='data')
(source/'static').rename(rollback/'failed-static')
(rollback/'static').rename(source/'static')
if (rollback/'delivery.py').is_file():
 shutil.copyfile(rollback/'delivery.py','/srv/dify-research/bridge/delivery.py')
 subprocess.run(['docker','restart','dify-workbench-bridge'],check=True,capture_output=True)
print('restored-original-release')
""".replace('ROLLBACK_PATH', repr(prepared['rollback']))
        remote(rollback_code, timeout=90, root=True)
        start()
        raise
    report = {**prepared, 'version': '0.4.0', 'status': 'deployed',
              'frontend_job': build['job_id'], 'native_tutor_restarted': False,
              'bridge_restarted': args.bridge, 'url': 'https://tutor.example.invalid/research/'}
    (ROOT / 'reports/unified-product-release.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
