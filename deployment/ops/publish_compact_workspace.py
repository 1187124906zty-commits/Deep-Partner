"""Publish the verified compact UI into the current shared site."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE/'scripts'))
from deploy import remote

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['compact','beginner','connections','tasks'],default='compact');args=parser.parse_args()
    build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
    names={'compact':'compact-ui-candidate.json','beginner':'beginner-workflow-candidate.json','connections':'connection-previews-candidate.json','tasks':'task-panel-candidate.json'}
    qa=json.loads((ROOT/'reports'/names[args.profile]).read_text(encoding='utf8'))
    assert build['state']=='COMPLETED' and build['exit_code']=='0:0'
    assert qa['passed'] and qa['frontend_job_id']==build['job_id']
    if args.profile=='compact':
        controls=json.loads((ROOT/'reports/theme-model-candidate.json').read_text(encoding='utf8'))
        assert controls['passed'] and controls['frontend_job_id']==build['job_id']
    elif args.profile=='beginner':
        figure=json.loads((ROOT/'reports/figure-dito-candidate.json').read_text(encoding='utf8'))
        assert figure['passed'] and figure['frontend_job_id']==build['job_id']
    subprocess.run(['scp','-q',build['local_artifact'],'papers-research:/srv/research-workbench/current-workspace-ui.tar.gz'],check=True,timeout=150)
    code=r'''from pathlib import Path
import json,tarfile,shutil,uuid
root=Path('/srv/research-workbench');staged=root/('workspace-ui-'+uuid.uuid4().hex);staged.mkdir()
archive=root/'current-workspace-ui.tar.gz'
with tarfile.open(archive) as bundle:
 assert all((staged/member.name).resolve().is_relative_to(staged.resolve()) for member in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file() and (staged/'assets').is_dir()
static=(root/'source/static').resolve();assert static==Path('/srv/research-workbench/source/static')
shutil.rmtree(static);staged.rename(static);archive.unlink()
print(json.dumps({'current_site_replaced':True,'build':json.loads((static/'build-info.json').read_text())}))
'''
    result=json.loads(remote(code,timeout=90,root=True))
    result.update({'url':'https://tutor.example.invalid/research/','frontend_job_id':build['job_id'],'backend_restarted':False})
    (ROOT/'reports/compact-ui-release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
