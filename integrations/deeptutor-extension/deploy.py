"""Run on the existing deployment host after source upload."""
from pathlib import Path
import json
import os
import secrets
import shutil
import subprocess
import yaml

ROOT=Path('/srv/deeptutor')
SRC=ROOT/'workbench-src'
SECRETS=ROOT/'secrets'
SECRETS.mkdir(exist_ok=True,mode=0o700)
token_file=SECRETS/'coder-token'
if not token_file.exists():
    token_file.write_text(secrets.token_urlsafe(48))
catalog=json.loads((ROOT/'data/user/settings/model_catalog.json').read_text())['services']['llm']
profile=next(p for p in catalog['profiles'] if p['id']==catalog['active_profile_id'])
model=next(m for m in profile['models'] if m['id']==catalog['active_model_id'])
provider={'base_url':profile['base_url'],'api_key':profile['api_key'],'model':model['model']}
(SECRETS/'coder-provider.json').write_text(json.dumps(provider))
for file in (token_file,SECRETS/'coder-provider.json'):
    os.chown(file,0,1000);os.chmod(file,0o640)
os.chown(SECRETS/'registration-mail.json',0,1000)
os.chmod(SECRETS/'registration-mail.json',0o640)

metadata=SRC/'deeptutor_research_workbench-0.1.0.dist-info'
metadata.mkdir(exist_ok=True)
for name in ('METADATA','entry_points.txt'):
    shutil.copyfile(SRC/name,metadata/name)
home=ROOT/'coder-home'
workspace=ROOT/'workspaces/coder'
for path in (home,workspace,workspace/'projects',home/'research-context'):
    path.mkdir(parents=True,exist_ok=True)
    os.chown(path,1000,1000)
shutil.copyfile(SRC/'coder-AGENTS.md',workspace/'AGENTS.md')
os.chown(workspace/'AGENTS.md',1000,1000)
global_rules=home/'.deepcode'
global_rules.mkdir(exist_ok=True)
shutil.copyfile(SRC/'coder-AGENTS.md',global_rules/'AGENTS.md')
os.chown(global_rules,1000,1000);os.chown(global_rules/'AGENTS.md',1000,1000)

compose_path=ROOT/'compose.yaml'
compose=yaml.safe_load(compose_path.read_text())
dt=compose['services']['deeptutor']
volumes=dt.setdefault('volumes',[])
volumes[:]=[m for m in volumes if m not in {
    './workbench-src:/app/workbench_plugins:ro',
    './workbench-src/pages:/app/workbench_pages:ro',
    './secrets/coder-token:/run/secrets/coder-token:ro',
}]
mounts=[
    './workbench-src/registration_admin.py:/app/registration_admin.py:ro',
    './workbench-src/trusted_devices.py:/app/trusted_devices.py:ro',
    './workbench-src/coder_bridge.py:/app/coder_bridge.py:ro',
    './workbench-src/code_mode.py:/app/code_mode.py:ro',
    './workbench-src/pages:/app/workbench_pages:ro',
    './workbench-src/deeptutor_research_workbench-0.1.0.dist-info:/app/deeptutor_research_workbench-0.1.0.dist-info:ro',
    './secrets/registration-mail.json:/run/secrets/registration-mail.json:ro',
    './secrets/coder-token:/run/secrets/coder-token:ro',
]
for mount in mounts:
    if mount not in volumes:volumes.append(mount)
dt['environment'].pop('PYTHONPATH',None)
dt['environment'].pop('CODER_WORKER_URL',None)
compose['services']['coder']={
    'image':'deeptutor-coder:2.3.1','container_name':'deeptutor-coder',
    'restart':'unless-stopped','init':True,
    'volumes':[
        './workspaces/coder:/workspace/coder',
        './coder-home:/home/coder',
        './secrets/coder-token:/run/secrets/coder-token:ro',
        './secrets/coder-provider.json:/run/secrets/coder-provider.json:ro',
    ],
    'ports':['127.0.0.1:8010:8010'],
    'environment':{'TZ':'Asia/Shanghai','HOME':'/home/coder','DEEPTUTOR_API_URL':'http://deeptutor:8001'},
    'mem_limit':'256m','mem_reservation':'64m','memswap_limit':'768m','cpus':0.5,'cpu_shares':128,
    'pids_limit':128,'security_opt':['no-new-privileges:true'],
    'logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'2'}},
    'healthcheck':{'test':['CMD','python','-c','import urllib.request; urllib.request.urlopen("http://127.0.0.1:8010/health",timeout=3)'],
                   'interval':'30s','timeout':'5s','retries':4,'start_period':'60s'},
}
compose_path.write_text(yaml.safe_dump(compose,sort_keys=False,allow_unicode=True))
main=ROOT/'compat/main-registration.py'
text=main.read_text()
text=text.replace('from workbench import install as install_workbench\ninstall_workbench(app)\n','')
main.write_text(text)
compile(main.read_text(),str(main),'exec')
subprocess.run(['docker','compose','-f',str(compose_path),'config','--quiet'],check=True)
subprocess.run(['docker','compose','-f',str(compose_path),'up','-d'],check=True)
print('Code mode installed through native extension entry points; other modes keep their existing composition.')
