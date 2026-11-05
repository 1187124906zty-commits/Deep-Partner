"""Own one recoverable project for the interaction acceptance checks."""
from pathlib import Path
import argparse,json,os,subprocess,sys
import httpx
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.local/workspace-interactions';CACHE.mkdir(exist_ok=True)
STATE=CACHE/'fixture.json';ORIGIN='https://tutor.example.invalid'
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote

def login(client):
    jump=['-o','ProxyJump='+os.environ['WORKBENCH_PROXY_JUMP']] if os.environ.get('WORKBENCH_PROXY_JUMP') else []
    account=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',*jump,'papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True,encoding='utf8',timeout=30))
    response=client.post('/api/auth/login',json=account);response.raise_for_status()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','archive']);args=parser.parse_args()
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},timeout=150,trust_env=False) as client:
        login(client)
        if args.action=='archive':
            state=json.loads(STATE.read_text(encoding='utf8'));pid=state['project']['id'];native=state['project']['native_id']
            jobs=client.get('/research/api/projects/'+pid+'/jobs').json()['jobs'];assert not any(j['status'] in ('queued','running') for j in jobs),'Fixture still has active work'
            result=client.patch('/api/settings/workspace/registrations/'+native,json={'archived':True});result.raise_for_status()
            code="""import sqlite3,json
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3')
pid=PID
row=db.execute("select name,config from projects where id=? and owner='local-admin'",(pid,)).fetchone()
assert row and row[0]=='界面联调验收 · 20261102'
config=json.loads(row[1]);config['archived']=True
db.execute("update projects set config=? where id=? and owner='local-admin'",(json.dumps(config),pid));db.commit()
print(json.dumps({'fixture_archived':pid,'data_retained':True}))
""".replace('PID',repr(pid),1)
            report=json.loads(remote(code,root=True));current=client.get('/research/api/projects').json()['projects']
            assert {p['id'] for p in current}==set(state['baseline_projects'])
            report['original_projects_preserved']=[{'id':p['id'],'name':p['name']} for p in current]
            (ROOT/'reports/workspace-interactions-fixture-archive.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return
        current=client.get('/research/api/projects').json()['projects']
        if STATE.exists():
            state=json.loads(STATE.read_text(encoding='utf8'));project=next(p for p in current if p['id']==state['project']['id'])
        else:
            baseline=[p['id'] for p in current];response=client.post('/research/api/projects',json={'name':'界面联调验收 · 20261102'});response.raise_for_status();project=response.json()
            state={'project':project,'baseline_projects':baseline,'test_scope':'Isolated interaction fixture; bilingual manuscript text is test data, not a model translation.'};STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
        prefix='/research/api/projects/'+project['id']
        if not state.get('seeded'):
            doc=client.get(prefix+'/manuscript').json()
            def paragraph(value):return {'type':'paragraph','content':[{'type':'text','text':value}]}
            source=[paragraph('测试作者'),paragraph('界面验证，不作为科研正文'),paragraph('摘要：这份样稿用于检查原生模板、公式和双语阅读交互。'),{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'1 阅读与同步验证'}]}]
            translated=[paragraph('Test author'),paragraph('Interaction verification fixture'),paragraph('Abstract: This document verifies manuscript templates, equations, annotations and bilingual scrolling.'),{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'1 Reading and alignment'}]}]
            for i in range(18):
                source.append(paragraph('第'+str(i+1)+'段。'+'双语稿件应在同一段落位置同步，批注需要保留选文和所属项目。'*(2+i%3)))
                translated.append(paragraph('Paragraph '+str(i+1)+'. '+'The reading panes should remain aligned by paragraph while annotations retain their selected text and project context. '*(3+(i%3)*3)))
                if i==7:
                    equation={'type':'blockMath','attrs':{'latex':r'\frac{\partial c}{\partial t}=\nabla\cdot(D\nabla c),\qquad c(0,t)=c_s'}}
                    source.append(equation);translated.append(equation)
            source.append({'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'2 公式与导出'}]});translated.append({'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'2 Equations and export'}]})
            doc.update(title='阅读与排版验收',template='journal-zh',content={'type':'doc','content':source},translation={'title':'Bilingual interaction fixture','content':{'type':'doc','content':translated},'comments':[],'language':'en','template':'journal-en','source_revision':doc['revision'],'stale':False,'generation_id':'interaction-fixture-v1'},reason='Isolated UI acceptance fixture')
            response=client.put(prefix+'/manuscript',json=doc);response.raise_for_status()
            for path,content in [('src/reader_probe.py','print("interaction fixture")\n'),('results/values.csv','x,y\n0,0\n1,1\n')]:
                response=client.put(prefix+'/file',json={'path':path,'content':content});response.raise_for_status()
            # Reuse the two publications already downloaded and verified in the author's project.
            original=next(p for p in current if p['id']=='638495c5ba024a93a305ff69b4658811');records=client.get('/research/api/projects/'+original['id']+'/literature/items').json()
            chosen=[r for r in records['references'] if r.get('doi') and any(v in r['title'].lower() for v in ['limited memory bfgs','adam:'])]
            if len(chosen)<2:chosen=[r for r in records['references'] if r.get('doi')][:2]
            state['reference_titles']=[r['title'] for r in chosen]
            for record in chosen:
                doc=client.get(prefix+'/manuscript').json();response=client.post(prefix+'/references',json={'revision':doc['revision'],'entry':{k:v for k,v in record.items() if k not in ('id','number','attachment')}});response.raise_for_status()
            bfgs=next((r for r in records['files'] if 'limited memory' in r.get('metadata',{}).get('title','').lower()),None)
            if bfgs:
                response=client.get('/research/api/projects/'+original['id']+'/literature/file',params={'asset':bfgs['name']});response.raise_for_status();path=CACHE/'verified-bfgs.pdf';path.write_bytes(response.content);state['bfgs_pdf']=str(path)
            state['seeded']=True;STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'project_id':project['id'],'native_id':project['native_id'],'reference_titles':state.get('reference_titles'),'bfgs_pdf':state.get('bfgs_pdf')},ensure_ascii=False))

if __name__=='__main__':main()
