"""Isolated, owner-scoped UI fixture; imports run for real, no model requests."""
from pathlib import Path
import argparse,io,json,subprocess,sys,time,zipfile
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote
FIXTURE=ROOT/'.local/task-panel-fixture.json'

def server(code):
    return json.loads(remote('import subprocess,json\ncode='+repr(code)+"\noutput=subprocess.check_output(['docker','exec','research-workbench','python','-c',code],text=True)\nprint(output)\n",root=True))

def update(mode):
    data=json.loads(FIXTURE.read_text(encoding='utf8'))
    code="from server.app import store\nimport json\npid="+repr(data['project']['id'])+"\nowner='local-admin'\nassert store.get(owner,pid)['name']=='任务面板验收（临时）'\njid="+repr(data['running'])+'\n'
    if mode=='advance':code+="store.set_job(jid,step='check',stage='正在核对译文与原稿版本')\n"
    elif mode=='finish':code+="store.set_job(jid,step='save',stage='正在保存译稿')\nstore.set_job(jid,status='completed',stage='已完成',result={'segments':30})\n"
    elif mode=='reset':code+="store.set_job(jid,status='queued',error='')\nstore.set_job(jid,status='running',step='translate',stage='正在翻译段落',counts={'done':12,'total':30,'unit':'段'})\n"
    elif mode=='close':code+="\nfor row in store.jobs(owner,pid):\n if row['status'] in ('running','queued'):store.set_job(row['id'],status='cancelled',stage='验收演练已结束')\n"
    code+="print(json.dumps({'jobs':store.jobs(owner,pid)},ensure_ascii=False))"
    return server(code)

def attach_output():
    data=json.loads(FIXTURE.read_text(encoding='utf8'));pid=data['project']['id'];jid=data['imports'][0]
    code="from server.app import store\nimport json\npid="+repr(pid)+"\njid="+repr(jid)+"\nrow=next(r for r in store.jobs('local-admin',pid) if r['id']==jid)\nresult={**row['result'],'name':'输入说明.md','url':'/research/api/projects/'+pid+'/file?path=docs%2F输入说明.md'}\nassert (store.path('local-admin',pid)/'project/docs/输入说明.md').is_file()\nstore.set_job(jid,result=result)\nprint(json.dumps({'linked':jid},ensure_ascii=False))"
    return server(code)

def create():
    if FIXTURE.exists():return json.loads(FIXTURE.read_text(encoding='utf8'))
    account=json.loads(subprocess.check_output(['ssh','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],text=True))
    with httpx.Client(base_url='https://tutor.example.invalid',headers={'Origin':'https://tutor.example.invalid'},timeout=60) as client:
        client.post('/api/auth/login',json=account).raise_for_status()
        r=client.post('/research/api/projects',json={'name':'任务面板验收（临时）'});r.raise_for_status();project=r.json()
        data={'project':project,'imports':[],'evidence_scope':'实际导入为真实执行；翻译进度和失败状态为隔离项目的界面事件演练，不调用模型。'}
        FIXTURE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        for name,path in [('源程序与数据.zip','docs/输入说明.md'),('仿真图表.zip','results/结果说明.md')]:
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive:
                archive.writestr('workbench-import.json',json.dumps({'format':'workbench-project.v2','source':'task panel UI acceptance'}))
                archive.writestr('project/'+path,'# 实际导入验收\n此文件只属于临时验收项目。')
            r=client.post('/research/api/projects/'+project['id']+'/import',files={'file':(name,output.getvalue(),'application/zip')});r.raise_for_status();jid=r.json()['job_id']
            for _ in range(50):
                rows=client.get('/research/api/projects/'+project['id']+'/jobs').json()['jobs'];row=next(j for j in rows if j['id']==jid)
                if row['status']=='completed':break
                if row['status']=='failed':raise RuntimeError(row['error'])
                time.sleep(.2)
            else:raise RuntimeError('Import task did not finish')
            assert row['task']['completed_steps']==4
            data['imports'].append(jid)
        code="""from server.app import store
import json
owner='local-admin';pid=PROJECT
assert store.get(owner,pid)['name']=='任务面板验收（临时）'
running=store.job(owner,pid,'manuscript-translate',{'subject':'界面验收：水分扩散讨论稿','target':'en'})
store.set_job(running,status='running',step='translate',stage='正在翻译段落',counts={'done':12,'total':30,'unit':'段'})
failed=store.job(owner,pid,'slides-export',{'subject':'界面验收：组会汇报','format':'pptx'})
store.set_job(failed,status='running',step='build');store.set_job(failed,step='render',stage='正在生成预览')
store.set_job(failed,status='failed',stage='预览生成未完成',error='验收演练：预览渲染进程退出，原文件保留。')
print(json.dumps({'running':running,'failed':failed},ensure_ascii=False))
""".replace('PROJECT',repr(project['id']))
        data.update(server(code));FIXTURE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['create','advance','finish','reset','close']);args=parser.parse_args()
    result=create() if args.action=='create' else update(args.action)
    print(json.dumps(result,ensure_ascii=False))
