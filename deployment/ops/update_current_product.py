"""Replace the current product in place, without retaining a previous release."""
from pathlib import Path
import json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE/'scripts'))
from deploy import remote,start

def main():
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    candidate=json.loads((ROOT/'reports/unified-ui-candidate.json').read_text(encoding='utf8'))
    dito=json.loads((ROOT/'reports/ui-fixes-candidate.json').read_text(encoding='utf8'))
    assert build['state']=='COMPLETED' and build['exit_code']=='0:0'
    assert candidate['passed'] and candidate['frontend_job_id']==build['job_id']
    assert dito['passed'] and dito['frontend_job_id']==build['job_id'] and dito.get('side_stream',{}).get('persisted_marker')
    files=['server/app.py','server/reviews.py','server/material_import.py','server/snapshot_import.py','server/desktop_manifest.py']
    archive=ROOT/'.local/current-product-backend.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for name in files:bundle.add(SOURCE/name,arcname=name)
    for local,name in [(archive,'current-product-backend.tar.gz'),(Path(build['local_artifact']),'current-product-static.tar.gz')]:
        subprocess.run(['scp','-q',str(local),'papers-research:/srv/research-workbench/'+name],check=True,timeout=150)
    code=r'''from pathlib import Path
import json,subprocess,tarfile,shutil,uuid
root=Path('/srv/research-workbench');source=root/'source'
probe="from server.app import store\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
staged=root/('current-update-'+uuid.uuid4().hex);staged.mkdir()
with tarfile.open(root/'current-product-static.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file() and (staged/'assets').is_dir()
with tarfile.open(root/'current-product-backend.tar.gz') as bundle:
 assert all(m.isfile() and (source/m.name).resolve().is_relative_to((source/'server').resolve()) for m in bundle.getmembers())
 bundle.extractall(source,filter='data')
static=(source/'static').resolve();assert static==Path('/srv/research-workbench/source/static')
shutil.rmtree(static);staged.rename(static)
for name in ('current-product-backend.tar.gz','current-product-static.tar.gz'):(root/name).unlink()
print(json.dumps({'replaced_current':True,'retained_previous_release':False,'index':(static/'index.html').read_text()}))
'''
    prepared=json.loads(remote(code,timeout=90,root=True))
    start()
    report={**prepared,'version':'0.4.2','status':'deployed','frontend_job':build['job_id'],'backend_files':files,
            'native_tutor_restarted':False,'url':'https://tutor.example.invalid/research/'}
    (ROOT/'reports/unified-product-release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
