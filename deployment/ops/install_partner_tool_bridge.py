"""Install the protected local tool bridge reference without exporting its secret."""
from pathlib import Path
import base64,json,subprocess,sys

local=json.loads(Path('C:/Users/DEVELOPER/.codex/deep-partner/tool-runtime/bridge.json').read_text(encoding='utf8'))
config={'url':'http://127.0.0.1:47906','token':local['token'],'native_execution_enabled':False}
blob=base64.b64encode(json.dumps(config).encode()).decode()
code="""import base64,subprocess
payload=base64.b64decode(BLOB)
script=\"from pathlib import Path;import os,sys,json;p=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/tool-bridge/bridge.json';p.parent.mkdir(parents=True,exist_ok=True);d=json.load(sys.stdin);p.write_text(json.dumps(d));p.chmod(0o600);print('Tool bridge reference installed; native execution remains pending permission')\"
subprocess.run(['docker','exec','-i','research-workbench','python','-c',script],input=payload,check=True)
""".replace('BLOB',repr(blob))
r=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n python3 -'],input=code,text=True,capture_output=True,encoding='utf8',timeout=45)
if r.returncode:raise RuntimeError(r.stderr[-1500:])
print(r.stdout.strip())
