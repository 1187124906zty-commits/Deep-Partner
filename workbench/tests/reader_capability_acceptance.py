"""The integrated reader verifies its own bridge without a second settings UI."""
from server import neoreader
from unittest.mock import patch
import json

state={'capabilities':{}};calls=[]
def request(item,method,path,**kwargs):
 calls.append((method,path))
 if method=='GET':return state
 state['capabilities']['api:workbench']={'text':True};return {'text':True}
with patch.object(neoreader,'request_engine',request):
 neoreader.prepare_translation({});neoreader.prepare_translation({})
assert len([v for v in calls if v[0]=='POST'])==1
assert calls[1][1].startswith('/api/ai/test/api?model=workbench&capability=text')
with patch.object(neoreader,'request_engine',lambda *a,**k: {'text':False,'error':'fixture'}):
 try:neoreader.prepare_translation({})
 except ValueError:pass
 else:raise AssertionError('An unavailable bridge was accepted')
# A new engine must replace the prior process's bridge secret before reuse.
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock
import os
with TemporaryDirectory() as temporary:
 root=Path(temporary);binary=root/'engine';binary.write_text('fixture')
 store=Mock();store.path.return_value=root
 processes=[];configured=[]
 def start(*args,**kwargs):
  proc=Mock();proc.stdout.readline.return_value=b'{"url":"http://127.0.0.1:1"}';proc.poll.return_value=None;processes.append(proc);return proc
 def config(item,method,path,**kwargs):
  configured.append(kwargs['json']['api']['key']);return {}
 with patch.dict(os.environ,{'WORKBENCH_NEOREAD':str(binary)}),patch.object(neoreader.subprocess,'Popen',start),patch.object(neoreader.secrets,'token_hex',side_effect=['first-fixture','second-fixture']),patch.object(neoreader,'request_engine',config):
  first=neoreader.engine(store,'fixture','fixture-project');assert neoreader.engine(store,'fixture','fixture-project') is first
  processes[0].poll.return_value=0
  second=neoreader.engine(store,'fixture','fixture-project');assert second is not first
  assert configured==['first-fixture','second-fixture'],'The second engine retained the previous authorization'
 first['log'].close();second['log'].close();neoreader.instances.pop('fixture-project',None);neoreader.locks.pop('fixture-project',None)
print(json.dumps({'passed':True,'checks':['real native text capability probe','verified connection reused','failed probe remains visible','restarted engine refreshes its own bridge authorization']}))
