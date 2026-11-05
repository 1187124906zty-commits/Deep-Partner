"""Publish the requested interaction changes against the existing product."""
from pathlib import Path
import argparse,json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE/'scripts'))
from deploy import remote,start
FILES=['academic_translation.py','app.py','bibliography_metadata.py','chat_materials.py','knowledge_search.py','knowledge_sources.py','literature.py','manuscripts.py','native_word_templates.py','neoreader.py','project_canvas.py','storage.py','task_workflows.py','translation.py','word_layout.py']
TEMPLATES=['chinese-journal-original.docx','chinese-journal.docx','chinese-journal.pdf','elsevier-research-original.docx','elsevier-research.docx','elsevier-research.pdf','neutral-template-provenance.json']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['backend','static']);args=parser.parse_args()
    target='/srv/research-workbench'
    if args.action=='backend':
        archive=ROOT/'.local/workspace-interactions-backend.tar.gz'
        with tarfile.open(archive,'w:gz') as bundle:
            for name in FILES:bundle.add(SOURCE/'server'/name,arcname='server/'+name)
            for name in TEMPLATES:bundle.add(SOURCE/'templates/manuscripts/source'/name,arcname='templates/manuscripts/source/'+name)
        subprocess.run(['scp','-q',str(archive),'papers-research:'+target+'/interactions-backend.tar.gz'],check=True,timeout=150)
        code="""from pathlib import Path
import subprocess,tarfile,json
root=Path('/srv/research-workbench');source=root/'source'
probe=\"from server.app import store\\nwith store.db() as db:rows=db.execute(\\\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\\\").fetchall()\\nassert not rows,'Active work must finish before restarting'\"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
with tarfile.open(root/'interactions-backend.tar.gz') as bundle:
 assert all(m.isfile() and (source/m.name).resolve().is_relative_to(source.resolve()) for m in bundle.getmembers())
 bundle.extractall(source,filter='data')
print(json.dumps({'backend_received':True,'user_data_unchanged':True}))
"""
        result=json.loads(remote(code,root=True,timeout=60));start()
        result.update(backend_files=FILES,templates=TEMPLATES,native_tutor_restarted=False)
        (ROOT/'reports/workspace-interactions-backend.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    else:
        build=json.loads((ROOT/'reports/unified-ui-build.json').read_text(encoding='utf8'))
        candidate=json.loads((ROOT/'reports/workspace-interactions-candidate.json').read_text(encoding='utf8'))
        assert build['state']=='COMPLETED' and build['exit_code']=='0:0'
        assert candidate['passed'] and candidate['frontend_job_id']==build['job_id']
        subprocess.run(['scp','-q',build['local_artifact'],'papers-research:'+target+'/interactions-static.tar.gz'],check=True,timeout=150)
        code="""from pathlib import Path
import tarfile,shutil,json,uuid
root=Path('/srv/research-workbench');source=root/'source';staged=root/('interactions-'+uuid.uuid4().hex);staged.mkdir()
with tarfile.open(root/'interactions-static.tar.gz') as bundle:
 assert all((staged/m.name).resolve().is_relative_to(staged.resolve()) for m in bundle.getmembers())
 bundle.extractall(staged,filter='data')
assert (staged/'index.html').is_file() and (staged/'assets').is_dir()
static=(source/'static').resolve();assert static==Path('/srv/research-workbench/source/static')
shutil.rmtree(static);staged.rename(static)
print(json.dumps({'published':True,'build':json.loads((static/'build-info.json').read_text()),'url':'https://tutor.example.invalid/research/'}))
"""
        result=json.loads(remote(code,root=True,timeout=60))
        (ROOT/'reports/workspace-interactions-published.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
