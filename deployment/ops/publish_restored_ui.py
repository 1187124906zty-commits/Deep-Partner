"""Publish the restored visual style only after its contrast and layout checks."""
from pathlib import Path
import json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote


def main():
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    checks=json.loads((ROOT/'reports/restored-ui-candidate.json').read_text(encoding='utf8'))
    assert build['state']=='COMPLETED' and build['exit_code']=='0:0' and checks['passed'] and checks['build']['slurm_job_id']==build['job_id']
    jump=['-o','ProxyJump='+os.environ['WORKBENCH_PROXY_JUMP']] if os.environ.get('WORKBENCH_PROXY_JUMP') else []
    subprocess.run(['scp','-q',*jump,build['local_artifact'],'papers-research:/srv/research-workbench/restored-ui.tar.gz'],check=True,timeout=150)
    code="""from pathlib import Path
import tarfile,shutil,json,uuid
root=Path('/srv/research-workbench');source=root/'source';staged=root/('restored-'+uuid.uuid4().hex);staged.mkdir()
with tarfile.open(root/'restored-ui.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file() and (staged/'assets').is_dir()
static=(source/'static').resolve();assert static==Path('/srv/research-workbench/source/static')
shutil.rmtree(static);staged.rename(static)
print(json.dumps({'published':True,'build':json.loads((static/'build-info.json').read_text()),'url':'https://tutor.example.invalid/research/'}))
"""
    result=json.loads(remote(code,root=True,timeout=60));(ROOT/'reports/restored-ui-deployment.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
