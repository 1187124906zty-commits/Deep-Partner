"""Publish the verified workflow controls and scoped product instructions."""
from pathlib import Path
import json,subprocess,tarfile,sys
from publish_agentic_fixes import remote

ROOT=Path(__file__).resolve().parents[1]
WB=Path('D:/Development/research-workbench')
FILES=['server/workflow_control.py','server/research_flow.py','server/task_workflows.py',
       'server/research_tool_flow.py','server/standards.py','server/writing.py',
       'vendor/workbench-skills/OUTPUT_STANDARD.md','vendor/workbench-skills/deepcode/SKILL.md']


def main():
    if '--verify' in sys.argv:
        code='FILES='+repr(FILES)+'\n'+r'''from pathlib import Path
import json,subprocess,sqlite3
root=Path('/srv/research-workbench');stage=root/'flow-controls-candidate'
for rel in FILES:assert (stage/'workbench'/rel).read_bytes()==(root/'source'/rel).read_bytes(),rel
services=['research-flow','research-flow-project','research-flow-recovery','research-workbench','deeptutor']
for name in services:
 row=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
 assert row['State']['Health']['Status']=='healthy',name
probe="from unittest.mock import patch\nfrom types import SimpleNamespace\nimport partner_writing as p\nwith patch.object(p,'get_current_user_or_none',return_value=object()),patch.object(p,'current_workspace_id',return_value='ws'):\n assert not p.PartnerWriting().is_active(SimpleNamespace(config_overrides={}))\n assert p.PartnerWriting().is_active(SimpleNamespace(config_overrides={'partner_mode':'writing'}))"
subprocess.run(['docker','exec','deeptutor','python','-c',probe],check=True,capture_output=True)
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
retained=[dict(r) for r in db.execute("SELECT id,status FROM jobs WHERE id IN ('5ee9e9613b85474d90917323b65d14ae','fc565d0cee924b4296b29cd137e835dc')")]
assert all(r['status']=='waiting_input' for r in retained)
print(json.dumps({'published':FILES+['tutor-extension/dify_delivery.py','tutor-extension/partner_writing.py'],'services_ready':services,'retained_jobs':retained,'native_mode_activation_passed':True,'probe_note':'Native port is container-only; used actual Docker health and extension activation checks.'},ensure_ascii=False))
'''
        result=json.loads(remote(code,40))
        (ROOT/'reports/agentic-product/flow-controls-published.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(result,ensure_ascii=False));return
    archive=ROOT/'.local/flow-controls.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for rel in FILES:
            bundle.add(WB/rel,arcname='workbench/'+rel)
            before=ROOT/'.local/flow-controls-before'/rel
            if before.is_file():bundle.add(before,arcname='before/'+rel)
        for name in ['dify_delivery.py','partner_writing.py']:
            bundle.add(ROOT/'tutor-extension'/name,arcname='tutor-extension/'+name)
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/flow-controls.tar.gz'],check=True,timeout=60)
    code='FILES='+repr(FILES)+'\n'+r'''from pathlib import Path
import json,sqlite3,subprocess,tarfile,shutil,time,urllib.request
root=Path('/srv/research-workbench');stage=root/'flow-controls-candidate'
with tarfile.open(root/'flow-controls.tar.gz') as bundle:bundle.extractall(stage,filter='data')
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute("SELECT id,kind,status FROM jobs WHERE status IN ('running','queued','waiting_input','waiting_service','paused')")]
assert not any(r['status']=='running' or r['status']=='queued' and r['kind'] not in ('research-flow','simulation','literature-download','cluster-pdf-parse') for r in rows),'A running in-process job must finish'
active=[]
for path in Path('/srv/deeptutor/data').rglob('chat_history.db'):
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as connection:
  if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='turns'").fetchone():
   active.extend(connection.execute("SELECT id,status FROM turns WHERE status IN ('queued','running')").fetchall())
assert not active,'A native turn must finish before reloading extensions'
for rel in FILES:
 source=stage/'workbench'/rel;destination=root/'source'/rel;before=stage/'before'/rel
 if before.is_file() and destination.is_file():
  assert destination.read_text() in (before.read_text(),source.read_text()),'Concurrent source change: '+rel
 if source.suffix=='.py':compile(source.read_text(),str(source),'exec')
for rel in FILES:
 destination=root/'source'/rel;destination.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(stage/'workbench'/rel,destination)
for name in ['dify_delivery.py','partner_writing.py']:
 source=stage/'tutor-extension'/name;compile(source.read_text(),name,'exec')
 shutil.copyfile(source,Path('/srv/dify-research/tutor-extension')/name)
services=['research-flow','research-flow-project','research-flow-recovery','research-workbench','deeptutor']
for name in services:
 subprocess.run(['docker','restart',name],check=True,capture_output=True)
 if name!='deeptutor':
  command=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]['Config']['Cmd']
  url='http://127.0.0.1:'+command[command.index('--port')+1]+'/health'
 for _ in range(80):
  try:
   if name=='deeptutor':
    health=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]['State']['Health']['Status']
    if health=='healthy':break
   else:
    with urllib.request.urlopen(url,timeout=2) as response:
     if response.status==200:break
  except OSError:pass
  time.sleep(.5)
 else:raise RuntimeError(name+' has not become ready')
 if name!='deeptutor':subprocess.run(['docker','exec',name,'python','/app/healthcheck.py'],check=True,capture_output=True)
probe="from unittest.mock import patch\nfrom types import SimpleNamespace\nimport partner_writing as p\nwith patch.object(p,'get_current_user_or_none',return_value=object()),patch.object(p,'current_workspace_id',return_value='ws'):\n assert not p.PartnerWriting().is_active(SimpleNamespace(config_overrides={}))\n assert p.PartnerWriting().is_active(SimpleNamespace(config_overrides={'partner_mode':'writing'}))\nprint('Native writing activation passed')"
subprocess.run(['docker','exec','deeptutor','python','-c',probe],check=True,capture_output=True)
after=[dict(r) for r in db.execute('SELECT id,status FROM jobs WHERE id IN ('+','.join('?' for _ in rows)+')',[r['id'] for r in rows])] if rows else []
assert not any(r['status']=='interrupted' for r in after),'A retained task was interrupted'
print(json.dumps({'published':FILES+['tutor-extension/dify_delivery.py','tutor-extension/partner_writing.py'],
 'services_ready':services,'retained_jobs':after,'native_mode_activation_passed':True},ensure_ascii=False))
'''
    result=json.loads(remote(code,150))
    (ROOT/'reports/agentic-product/flow-controls-published.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
