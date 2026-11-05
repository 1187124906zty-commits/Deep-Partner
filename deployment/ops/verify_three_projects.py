"""Read back the requested project snapshots and their actual native indices."""
from pathlib import Path
from urllib.parse import quote
import argparse,base64,json,subprocess,sys,time,zipfile
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--semantic',action='store_true')
    args=parser.parse_args()
    imports=json.loads((ROOT/'reports/three-project-import.json').read_text(encoding='utf8'))
    assert set(imports['projects'])=={'moisture','micro','coupled'}
    report={'checked':time.time(),'projects':{},'new_model_turn':False}
    expected={}
    for key,item in imports['projects'].items():
        assert item.get('imported') and item.get('knowledge_uploaded'),key
        with zipfile.ZipFile(ROOT/'.local/project-onboarding'/(key+'-materials.zip')) as archive:
            files=[member for member in archive.infolist() if not member.is_dir() and member.filename not in {'workbench-import.json','manuscript/main.json'}]
            sources=[m for m in files if m.filename.endswith(('.py','.m','.md','.yaml','.toml'))]
            selected=sources[:3]+sources[-3:]
            expected[key]={'project':item['project']['id'],'files':{m.filename:m.file_size for m in files},
                           'exact_text':{m.filename:base64.b64encode(archive.read(m)).decode() for m in selected}}
    code='''from pathlib import Path
import base64,json,sqlite3
expected=EXPECTED
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
result={}
for key,spec in expected.items():
 row=db.execute("select * from projects where id=? and owner='local-admin'",(spec['project'],)).fetchone();assert row
 container=Path(json.loads(row['config'])['project_root']);root=Path('/srv/deeptutor/workspaces')/container.relative_to('/workspace')
 assert root.resolve().is_relative_to(Path('/srv/deeptutor/workspaces').resolve())
 bad=[name for name,size in spec['files'].items() if not (root/name).is_file() or (root/name).stat().st_size!=size]
 exact_bad=[name for name,encoded in spec['exact_text'].items() if (root/name).read_bytes()!=base64.b64decode(encoded)]
 record={'expected_files':len(spec['files']),'all_paths_and_sizes_match':not bad,'mismatches':bad,
         'exact_source_samples':len(spec['exact_text']),'exact_source_samples_match':not exact_bad}
 if key=='moisture':
  doc=json.loads((root/'manuscript/main.json').read_text());registry=json.loads((root/'.workbench/figures/registry.json').read_text())
  record.update(manuscript_revision=doc['revision'],manuscript_title=doc['title'],editable_figures=len(registry))
 result[key]=record
print(json.dumps(result,ensure_ascii=False))
'''.replace('EXPECTED',repr(expected),1)
    snapshots=json.loads(remote(code,timeout=60,root=True))
    account=json.loads(subprocess.run(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    with httpx.Client(base_url='https://tutor.example.invalid',headers={'Origin':'https://tutor.example.invalid'},timeout=150) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        projects=client.get('/research/api/projects').json()['projects']
        for key,item in imports['projects'].items():
            project=next(p for p in projects if p['id']==item['project']['id']);prefix='/research/api/projects/'+project['id']
            record={'id':project['id'],'name':project['name'],'url':'https://tutor.example.invalid/research/?project='+project['id'],
                    'snapshot':snapshots[key],'source_pdfs':item['literature_sources'],'knowledge':[]}
            for kb in project['config'].get('knowledge_bases',[]):
                route='/api/knowledge-bases/'+quote(kb,safe='');scope={'dt_workspace':project['native_id']}
                details=client.get(route,params=scope);details.raise_for_status()
                run=client.get(route+'/indexing-run',params=scope);run.raise_for_status();run=run.json().get('run') or {}
                files=client.get(route+'/files',params=scope);files.raise_for_status()
                rows=files.json().get('files',[])
                result={'id':kb,'status':details.json().get('status'),'run_state':run.get('state'),
                        'usable_version':run.get('usable_version'),'files':len([f for f in rows if f.get('type')!='folder']),
                        'error':run.get('error'),'activity':run.get('activity')}
                if args.semantic and kb==project['config'].get('attachment_knowledge_base') and result['run_state']=='completed':
                    query={'moisture':'moisture diffusion concrete','micro':'Feng sulfate attack microstructure','coupled':'chloride sulfate coupled transport phase field'}[key]
                    found=client.post(prefix+'/knowledge/search',json={'mode':'semantic','knowledge_base':kb,'query':query,'limit':3})
                    result['semantic_status']=found.status_code
                    result['semantic']=found.json()
                record['knowledge'].append(result)
            report['projects'][key]=record
    report['snapshots_passed']=all(p['snapshot']['all_paths_and_sizes_match'] and p['snapshot']['exact_source_samples_match'] for p in report['projects'].values())
    report['indexing_complete']=all(k['status']=='ready' and k['run_state']=='completed' for p in report['projects'].values() for k in p['knowledge'])
    if args.semantic:
        report['semantic_passed']=all(any(k.get('semantic_status')==200 and k.get('semantic',{}).get('result') for k in p['knowledge']) for p in report['projects'].values())
    (ROOT/'reports/three-project-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({**report,'projects':{k:{**v,'knowledge':[{kk:vv for kk,vv in kb.items() if kk!='semantic'} for kb in v['knowledge']]} for k,v in report['projects'].items()}},ensure_ascii=False))
    assert report['snapshots_passed']


if __name__=='__main__':main()
