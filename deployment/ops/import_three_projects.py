"""Create the three requested admin projects and import their selected sources."""
from pathlib import Path
import argparse,json,subprocess,time,zipfile
import httpx
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.local/project-onboarding'
STATE=ROOT/'reports/three-project-import.json'
SPECS=[
 ('moisture','水分扩散',Path('D:/博士工作/博士项目/水分扩散/2026-11-2/网站项目')),
 ('micro','硫酸盐侵蚀微观建模',STAGE/'feng2015-vcctl-sulfate'),
 ('coupled','氯硫耦合传输损伤代理建模',STAGE/'chloride-sulfate-3d-bayes-phasefield'),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['moisture','micro','coupled']);args=parser.parse_args()
    account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
    report=json.loads(STATE.read_text(encoding='utf8')) if STATE.exists() else {'projects':{}}
    def persist():STATE.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    with httpx.Client(base_url='https://tutor.example.invalid',headers={'Origin':'https://tutor.example.invalid'},timeout=180) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        me=client.get('/research/api/me').json();assert me['id']=='local-admin',me
        for key,name,folder in SPECS:
            if args.only and args.only!=key:continue
            item=report['projects'].setdefault(key,{})
            if not item.get('project'):
                result=client.post('/research/api/projects',json={'name':name});result.raise_for_status();item['project']=result.json();persist()
            project=item['project'];prefix='/research/api/projects/'+project['id']
            if item.get('import_job_id') and not item.get('imported'):
                rows=client.get(prefix+'/jobs').json()['jobs'];previous=next(row for row in rows if row['id']==item['import_job_id'])
                if previous['status']=='completed':item['imported']=True;item['import_receipt']=previous['result'];persist()
            if not item.get('imported') and not item.get('import_job_id'):
                archive=STAGE/(key+'-materials.zip')
                if not archive.exists():
                    if key=='moisture':meta=json.loads((folder/'workbench-import.json').read_text(encoding='utf8'))
                    else:meta={'format':'workbench-project.v2','name':name,'source':json.loads((folder/'source-snapshot.json').read_text(encoding='utf8'))['authoritative_root'],'source_project_id':'','snapshot_time':time.time()}
                    files=[]
                    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3,strict_timestamps=False) as bundle:
                        bundle.writestr('workbench-import.json',json.dumps(meta,ensure_ascii=False))
                        for file in folder.rglob('*'):
                            if not file.is_file() or file.is_symlink():continue
                            relative=file.relative_to(folder)
                            if relative.parts[0] not in {'project','manuscript','slides','literature'}:continue
                            if any(part in {'.git','.venv','node_modules','__pycache__','.trash','.env'} for part in relative.parts):continue
                            if file.suffix.lower() in {'.pkl','.pickle','.pyc','.so','.a','.o','.exe','.dll'}:continue
                            bundle.write(file,relative.as_posix());files.append(relative.as_posix())
                    item['packaged_files']=len(files);persist()
                with archive.open('rb') as stream:
                    result=client.post(prefix+'/import',files={'file':(archive.name,stream,'application/zip')});result.raise_for_status()
                jid=result.json()['job_id'];item['import_job_id']=jid;persist()
            if not item.get('imported'):
                jid=item['import_job_id']
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    jobs=client.get(prefix+'/jobs').json()['jobs'];job=next(row for row in jobs if row['id']==jid)
                    if job['status'] in {'failed','interrupted'}:raise RuntimeError(job)
                    if job['status']=='completed':item['imported']=True;item['import_receipt']=job['result'];persist();break
                    time.sleep(2)
                else:raise RuntimeError('Import still in progress; retain job ID and resume')
            if not item.get('knowledge_uploaded'):
                pdfs=list((folder/'literature').rglob('*.pdf')) if key=='moisture' else list((folder/'project'/('sources' if key=='micro' else 'references')).rglob('*.pdf'))
                if key=='moisture' and (folder/'manuscript/source.pdf').exists():pdfs.append(folder/'manuscript/source.pdf')
                # Keep one copy of each identified source filename.
                unique={file.name:file for file in pdfs};pdfs=list(unique.values())
                top_docs=list((folder/'project').glob('*.md'))
                if key!='moisture':top_docs+=list((folder/'project/research').glob('STATE.md'))+list((folder/'project/research').glob('BRIEF.md'))
                materials=pdfs+top_docs[:8]
                batches=[materials[i:i+12] for i in range(0,len(materials),12)]
                receipts=[]
                for batch in batches:
                    streams=[file.open('rb') for file in batch]
                    try:
                        result=client.post(prefix+'/attachments',files=[('files',(file.name,stream,'application/pdf' if file.suffix.lower()=='.pdf' else 'text/markdown')) for file,stream in zip(batch,streams)])
                        result.raise_for_status();receipts.append(result.json())
                    finally:
                        for stream in streams:stream.close()
                item['knowledge_uploaded']=True;item['knowledge_receipts']=receipts;item['literature_sources']=len(pdfs);persist()
            item['project']=next(row for row in client.get('/research/api/projects').json()['projects'] if row['id']==project['id']);item['files']=client.get(prefix+'/files').json()
            item['literature_count']=len(client.get(prefix+'/literature/items').json()['files'])
            item['checked']=time.time();persist()
            print(json.dumps({'project':name,'id':project['id'],'imported':item.get('imported'),'files':item.get('packaged_files'),'pdfs':item.get('literature_sources'),'knowledge_bases':item['project']['config'].get('knowledge_bases',[])},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
