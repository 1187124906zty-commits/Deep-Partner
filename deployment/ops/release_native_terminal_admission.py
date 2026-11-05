"""Install the tested terminal/admission ordering against observed native sources."""
from pathlib import Path
import json,subprocess
from publish_agentic_fixes import remote,ROOT,OUT

files={'lifecycle':'services/session/turns/lifecycle.py','executor':'services/session/turns/executor.py','memory':'runtime/coordination/memory.py'}
qa=json.loads((OUT/'native-terminal-admission.json').read_text(encoding='utf8'))
assert qa['checks'] and all(qa['checks'].values())
for name in files:
    before='coordinator-memory.py' if name=='memory' else name+'.py'
    subprocess.run(['scp','-q',str(ROOT/'.local/native-completion'/before),'papers-research:/srv/dify-research/'+name+'.observed.py'],check=True,timeout=40)
code='FILES='+repr(files)+'\n'+r'''from pathlib import Path
import json,sqlite3,subprocess,time,shutil
for path in Path('/srv/deeptutor/data').rglob('chat_history.db'):
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='turns'").fetchone():
   assert not db.execute("SELECT 1 FROM turns WHERE status IN ('queued','running','waiting_input') LIMIT 1").fetchone(),'A native turn must finish before reload'
target=Path('/srv/dify-research/native-terminal-admission');target.mkdir(exist_ok=True)
for name,path in FILES.items():
 current=subprocess.check_output(['docker','exec','deeptutor','cat','/app/deeptutor/'+path],text=True)
 observed=Path('/srv/dify-research/'+name+'.observed.py').read_text()
 candidate=Path('/srv/dify-research/'+name+'.candidate.py').read_text()
 assert current==observed,'Native source changed since inspection: '+name
 compile(candidate,path,'exec');(target/(name+'.py')).write_text(candidate)
override=Path('/srv/deeptutor/compose.override.yaml');config=json.loads(override.read_text());volumes=config['services']['deeptutor'].setdefault('volumes',[])
for name,path in FILES.items():
 destination='/app/deeptutor/'+path
 volumes[:]=[v for v in volumes if not (isinstance(v,str) and v.split(':')[1]==destination)]
 volumes.append(str(target/(name+'.py'))+':'+destination+':ro')
override.write_text(json.dumps(config,indent=2))
command=['docker','compose','-f','/srv/deeptutor/compose.yaml','-f',str(override)]
subprocess.run(command+['config','--quiet'],check=True,capture_output=True)
subprocess.run(command+['up','-d','--no-deps','--pull','never','deeptutor'],check=True,capture_output=True)
for _ in range(100):
 row=json.loads(subprocess.check_output(['docker','inspect','deeptutor'],text=True))[0]
 if row['State'].get('Health',{}).get('Status')=='healthy':break
 time.sleep(.5)
else:raise RuntimeError('Native service is not ready')
print(json.dumps({'published':True,'native_healthy':True,'files':list(FILES.values()),'active_native_turns_at_release':0}))
'''
result=json.loads(remote(code,150));(OUT/'native-terminal-admission-published.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
