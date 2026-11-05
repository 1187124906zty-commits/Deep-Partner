"""Apply the author's cleanup: keep three new projects, archive old entries."""
from pathlib import Path
import argparse,json,subprocess,sys,time
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--keep-test-project',action='store_true');args=parser.parse_args()
    imports=json.loads((ROOT/'reports/three-project-import.json').read_text(encoding='utf8'))
    verified=json.loads((ROOT/'reports/three-project-verification.json').read_text(encoding='utf8'))
    assert verified['snapshots_passed']
    keep=[item['project']['id'] for item in imports['projects'].values()]
    keep_native=[item['project']['native_id'] for item in imports['projects'].values()]
    if args.keep_test_project:
        fixture=json.loads((ROOT/'.local/onboarding-test-project.json').read_text())
        keep.append(fixture['id']);keep_native.append(fixture['native_id'])
    account=json.loads(subprocess.run(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    previous=json.loads((ROOT/'reports/admin-project-cleanup.json').read_text(encoding='utf8')) if (ROOT/'reports/admin-project-cleanup.json').exists() else {}
    report={'time':time.time(),'keep':keep,'mode':'recoverable_archive','applied':False,'native_archived':[]}
    with httpx.Client(base_url='https://tutor.example.invalid',headers={'Origin':'https://tutor.example.invalid'},timeout=90) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        assert client.get('/research/api/me').json()['id']=='local-admin'
        catalog=client.get('/api/settings/workspace/registrations');catalog.raise_for_status()
        old=[w for w in catalog.json()['workspaces'] if w['kind']=='workspace' and w['workspace_id'] not in keep_native]
        report['native_candidates']=[{'id':w['workspace_id'],'name':w['display_name'],'already_archived':w['archived']} for w in old]
        if args.apply:
            for workspace in old:
                if not workspace['archived']:
                    result=client.patch('/api/settings/workspace/registrations/'+workspace['workspace_id'],json={'archived':True})
                    result.raise_for_status();assert result.json()['workspace']['archived']
                report['native_archived'].append(workspace['workspace_id'])
            code='''from pathlib import Path
import sqlite3,json,datetime,shutil
keep=KEEP
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3',timeout=30);db.row_factory=sqlite3.Row
rows=db.execute("select * from projects where owner='local-admin'").fetchall()
old=[r for r in rows if r['id'] not in keep]
active=db.execute("select id,project,status from jobs where owner='local-admin' and status in ('queued','running')").fetchall()
assert not active,[dict(r) for r in active]
base=Path('/srv/deeptutor/workspaces').resolve()
kept=next(row for row in rows if row['id'] in keep)
owner_root=(base/Path(json.loads(kept['config'])['project_root']).relative_to('/workspace')).resolve().parent
assert owner_root.is_relative_to(base) and owner_root.name=='workspaces'
archive=Path('/srv/research-workbench/retired-admin-projects/20261102').resolve();archive.mkdir(parents=True,exist_ok=True)
report=[]
for row in old:
 config=json.loads(row['config']);source=(base/Path(config['project_root']).relative_to('/workspace')).resolve()
 assert source.is_relative_to(owner_root) and source.parent==owner_root and source not in [owner_root,base]
 target=(archive/row['id']).resolve();assert target.parent==archive;target.mkdir(exist_ok=True)
 (target/'project-record.json').write_text(json.dumps(dict(row),ensure_ascii=False,indent=2))
 if source.exists():
  assert not (target/'workspace').exists();shutil.move(str(source),str(target/'workspace'))
 db.execute("delete from projects where id=? and owner='local-admin'",(row['id'],))
 report.append({'id':row['id'],'name':row['name'],'native_id':row['native_id'],'archive':str(target)})
db.commit();print(json.dumps(report,ensure_ascii=False))
'''.replace('KEEP',repr(keep),1)
            report['workbench_archived']=previous.get('workbench_archived',[])+json.loads(remote(code,root=True))
            current=client.get('/research/api/projects');current.raise_for_status()
            report['remaining']=[{'id':p['id'],'name':p['name']} for p in current.json()['projects']]
            assert {p['id'] for p in report['remaining']}==set(keep)
            report['applied']=True
    (ROOT/'reports/admin-project-cleanup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
