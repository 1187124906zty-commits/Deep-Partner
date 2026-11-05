"""Exercise the installed CLI against an isolated real project, then archive it."""
from pathlib import Path
import json,os,shutil,subprocess,sys
from urllib.parse import quote
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ops'))
from workspace_interactions_fixture import ORIGIN,remote


def main():
    build=json.loads((ROOT/'reports/cluster-native-build.json').read_text(encoding='utf8'))
    executable=Path(os.environ['CLI_UPLOAD_EXE']) if os.environ.get('CLI_UPLOAD_EXE') else Path(build['local_release'])/'dp.exe'
    stage=ROOT/'.local/cli-project-upload';stage.mkdir(parents=True,exist_ok=True)
    home=stage/'profile';home.mkdir(exist_ok=True)
    (home/'config.json').write_text(json.dumps({'server_url':ORIGIN,'workspace':str(home/'workspace'),'ssh_host':'isolated-cli-qa.invalid','desktop_control':False}),encoding='utf8')
    env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy','no_proxy')}
    env['DEEP_PARTNER_HOME']=str(home)
    jump=['-o','ProxyJump='+os.environ['WORKBENCH_PROXY_JUMP']] if os.environ.get('WORKBENCH_PROXY_JUMP') else []
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes',*jump,'papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=40))
    report={'checks':{},'native_job_id':build['job_id'],'mode':'actual_windows_cli_real_upload_and_readback','process_proxy_environment_removed':True}
    def cli(*arguments,secret=None,expected=0):
        result=subprocess.run([str(executable),*arguments],input=secret,capture_output=True,text=True,encoding='utf8',env=env,timeout=240)
        assert result.returncode==expected,(arguments,result.returncode,result.stdout[-1500:],result.stderr[-1500:])
        return json.loads(result.stdout) if result.stdout.strip().startswith('{') else result.stdout
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy=os.environ.get('WORKBENCH_HTTP_PROXY','http://127.0.0.1:12000'),trust_env=False,timeout=120) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        baseline={p['id'] for p in client.get('/research/api/projects').json()['projects']}
        title='命令行上传验收 · 20261103'
        response=client.post('/research/api/projects',json={'name':title});response.raise_for_status();project=response.json();pid=project['id'];prefix='/research/api/projects/'+pid
        report['fixture_project_id']=pid
        try:
            cli('login','--username',account['username'],'--password-stdin',secret=account['password']+'\n')
            report['checks']['login_persists_an_encrypted_cli_session']=(home/'cli-session').is_file()
            listing=cli('project','list','--json');report['checks']['list_real_projects']=any(p['id']==pid for p in listing['projects'])
            material=stage/'材料';(material/'sub').mkdir(parents=True,exist_ok=True)
            (material/'sub/main.py').write_text('print("isolated CLI upload verification")\n',encoding='utf8')
            (material/'values.csv').write_text('x,y\n0,0\n1,1\n',encoding='utf8')
            from PIL import Image
            Image.new('RGB',(40,30),(42,75,130)).save(material/'chart.png')
            from docx import Document
            doc=Document();doc.add_paragraph('Isolated CLI upload verification.');doc.save(material/'notes.docx')
            from pptx import Presentation
            deck=Presentation();deck.slides.add_slide(deck.slide_layouts[6]);deck.save(material/'talk.pptx')
            shutil.copyfile(ROOT/'.local/workspace-interactions/verified-bfgs.pdf',material/'method.pdf')
            before=client.get(prefix+'/files').json()
            preview=cli('project','upload','--project',title,str(material),'--recursive','--purpose','methods','--dry-run','--json')
            after=client.get(prefix+'/files').json()
            report['checks']['dry_run_does_not_write']=before==after and len(preview['files'])==6
            cli('project','upload','--project','missing-project',str(material/'values.csv'),'--dry-run','--json',expected=1)
            result=cli('project','upload','--project',pid,str(material),'--recursive','--purpose','methods','--json')
            report['checks']['six_real_files_saved']=result['saved']==6 and result['failed']==0
            expected={
                'src/材料/sub/main.py':material/'sub/main.py',
                'data/材料/values.csv':material/'values.csv',
                'figures/材料/chart.png':material/'chart.png',
                'docs/材料/notes.docx':material/'notes.docx',
                'slides/材料/talk.pptx':material/'talk.pptx',
            }
            for path,source in expected.items():
                response=client.get(prefix+'/file',params={'path':path});response.raise_for_status();assert response.content==source.read_bytes(),path
            report['checks']['all_five_classified_files_read_back_identically']=True
            library=client.get(prefix+'/literature/items').json()['files']
            entry=next(r for r in library if r['name']=='methods/method.pdf')
            pdf=client.get(prefix+'/literature/file',params={'asset':entry['name']});pdf.raise_for_status();assert pdf.content==(material/'method.pdf').read_bytes()
            report['checks']['pdf_in_methods_library_read_back_identically']=True
            report['checks']['pdf_identification_status_is_reported']=entry['metadata'].get('identity_status') in ('matched','pending','unmatched') and bool(entry['metadata'].get('title'))
            report['pdf_external_metadata_matched']=entry['metadata'].get('identity_status')=='matched'
            report['pdf_metadata']={k:entry['metadata'].get(k) for k in ['title','authors','doi','identity_status','match_method']}
            override=cli('project','upload','--project',title,str(material/'values.csv'),'--category','documents','--path','docs/custom','--json')
            response=client.get(prefix+'/file',params={'path':'docs/custom/values.csv'});response.raise_for_status()
            report['checks']['manual_category_and_destination']=override['saved']==1 and response.content==(material/'values.csv').read_bytes()
            files=cli('project','files','--project',title,'--path','src/材料/sub','--json')
            report['checks']['cli_lists_uploaded_files']=any(r['path']=='src/材料/sub/main.py' for r in files['items'])
            report['upload_summary']={'saved':result['saved'],'failed':result['failed'],'destinations':[r['destination'] for r in result['items']]}
            cli('logout');report['checks']['logout_clears_cli_session']=not (home/'cli-session').exists()
        except Exception as error:
            report['failure']=type(error).__name__+': '+str(error)
            raise
        finally:
            native=project['native_id']
            response=client.patch('/api/settings/workspace/registrations/'+native,json={'archived':True});response.raise_for_status()
            code="""import sqlite3,json
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3')
pid=PID
row=db.execute("select name,config from projects where id=? and owner='local-admin'",(pid,)).fetchone()
assert row and row[0]==TITLE
config=json.loads(row[1]);config['archived']=True
db.execute("update projects set config=? where id=? and owner='local-admin'",(json.dumps(config),pid));db.commit()
print(json.dumps({'archived':pid,'files_retained':True}))
""".replace('PID',repr(pid),1).replace('TITLE',repr(title),1)
            report['archive']=json.loads(remote(code,root=True))
            current={p['id'] for p in client.get('/research/api/projects').json()['projects']}
            report['checks']['fixture_archived_original_projects_preserved']=current==baseline
            report['passed']=not report.get('failure') and all(report['checks'].values())
            (ROOT/'reports/cli-upload-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(report,ensure_ascii=False),flush=True)
    assert report['passed']


if __name__=='__main__':main()
