"""Apply the tested compatibility mount after checking for active user turns."""
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from desktop_bridge_ctl import login

base, client, cookie, _ = login()
request=urllib.request.Request(base+'/api/sessions?all_workspaces=true&limit=200',headers={'Cookie':cookie})
sessions=json.loads(client.open(request,timeout=20).read()).get('sessions',[])
active=[s.get('session_id',s.get('id')) for s in sessions if s.get('active_turn_id') and s.get('status') in ('running','queued')]
if active:
    print(json.dumps({'applied':False,'active_turns':active}))
    raise SystemExit(2)
subprocess.run(['docker','compose','-f','/srv/deeptutor/compose.yaml','config','--quiet'],check=True)
subprocess.run(['docker','compose','-f','/srv/deeptutor/compose.yaml','up','-d','deeptutor'],check=True)
for _ in range(60):
    try:
        urllib.request.urlopen('http://127.0.0.1:8008/health/ready',timeout=2).read()
        break
    except OSError:
        time.sleep(1)
else:
    raise RuntimeError('DeepTutor health did not recover')
output=subprocess.check_output(['docker','exec','deeptutor','python','-c','import sys;sys.path.insert(0,"/app");from deeptutor.services.mcp import manager;assert hasattr(manager,"_DesktopImageText");print("visual-bridge-ready")']).decode().strip()
report={'applied':True,'active_turns_before_restart':0,'health_ready':True,'live_image_adapter':output}
Path('/srv/deeptutor/migration/desktop-visual-mount-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
