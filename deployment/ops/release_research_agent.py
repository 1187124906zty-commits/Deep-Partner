"""Install research tools and the explicit native chat extension contract."""
from pathlib import Path
import json,subprocess
from publish_agentic_fixes import remote,ROOT,OUT

subprocess.run(['scp','-q',str(ROOT/'tutor-extension/dify_delivery.py'),'papers-research:/srv/dify-research/dify_delivery.candidate.py'],check=True,timeout=40)
code=r'''from pathlib import Path
import json,sqlite3,subprocess,time,shutil
for path in Path('/srv/deeptutor/data').rglob('chat_history.db'):
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='turns'").fetchone():
   assert not db.execute("SELECT 1 FROM turns WHERE status IN ('queued','running') LIMIT 1").fetchone(),'A native turn is still active'
target=Path('/srv/dify-research/native-request-contract');target.mkdir(exist_ok=True)
current=subprocess.check_output(['docker','exec','deeptutor','cat','/app/deeptutor/runtime/request_contracts.py'],text=True)
old='class ChatRequestConfig(EmptyConfig):\n    pass'
new="""class ChatRequestConfig(EmptyConfig):
    # Explicit product extension settings; unrelated fields remain forbidden.
    partner_mode: Literal["research", "writing"] = "research"
    partner_writing_phase: Literal["auto", "draft", "submission", "revision"] = "auto"
    partner_llm_selection: LLMSelection | None = None"""
if old in current:
 current=current.replace('from deeptutor.runtime.capability_catalog import EmptyConfig','from deeptutor.runtime.capability_catalog import EmptyConfig\nfrom deeptutor.core.turn_request import LLMSelection').replace(old,new)
else:assert 'partner_mode: Literal["research", "writing"]' in current
compile(current,'request_contracts.py','exec');(target/'request_contracts.py').write_text(current)
probe="""import importlib.util,sys
spec=importlib.util.spec_from_file_location('candidate_contract','/tmp/partner-request-contract.py');r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)
assert r.validate_chat_request_config({'partner_mode':'research','partner_writing_phase':'auto'}).partner_mode=='research'
assert r.validate_chat_request_config({'partner_mode':'writing','partner_writing_phase':'revision','partner_llm_selection':{'profile_id':'p','model_id':'m'}}).partner_mode=='writing'
try:r.validate_chat_request_config({'unexpected':1})
except ValueError:pass
else:raise AssertionError('Unknown configuration was accepted')
print('Research, explicit writing and strict unknown-field rejection passed')
"""
subprocess.run(['docker','cp',str(target/'request_contracts.py'),'deeptutor:/tmp/partner-request-contract.py'],check=True,capture_output=True)
result=subprocess.run(['docker','exec','deeptutor','python','-c',probe],capture_output=True,text=True);assert result.returncode==0,result.stderr
extension=Path('/srv/dify-research/dify_delivery.candidate.py');compile(extension.read_text(),str(extension),'exec')
shutil.copyfile(extension,'/srv/dify-research/tutor-extension/dify_delivery.py')
override=Path('/srv/deeptutor/compose.override.yaml');config=json.loads(override.read_text());volumes=config['services']['deeptutor'].setdefault('volumes',[])
destination='/app/deeptutor/runtime/request_contracts.py';volumes[:]=[v for v in volumes if not (isinstance(v,str) and v.split(':')[1]==destination)]
volumes.append(str(target/'request_contracts.py')+':'+destination+':ro');override.write_text(json.dumps(config,indent=2))
command=['docker','compose','-f','/srv/deeptutor/compose.yaml','-f',str(override)]
subprocess.run(command+['config','--quiet'],check=True,capture_output=True)
subprocess.run(command+['up','-d','--no-deps','--pull','never','deeptutor'],check=True,capture_output=True)
for _ in range(100):
 row=json.loads(subprocess.check_output(['docker','inspect','deeptutor'],text=True))[0]
 if row['State'].get('Health',{}).get('Status')=='healthy':break
 time.sleep(.5)
else:raise RuntimeError('Native service is not ready')
print(json.dumps({'published':True,'native_healthy':True,'request_contract_tests':3,'source':'/srv/dify-research/native-request-contract/request_contracts.py','extension':'/srv/dify-research/tutor-extension/dify_delivery.py'}))
'''
result=json.loads(remote(code,150));(OUT/'research-agent-published.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
