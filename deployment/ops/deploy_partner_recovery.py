"""Roll out recovery for new workflow runs while old workers finish their jobs."""
from pathlib import Path
import json,subprocess,tarfile
from partner_workflow_dev import ROOT,STAGE,WORKBENCH,remote

PROJECTS=['c37b9168a0db40e3b258c9c03cd56697','64c6b5e79b824bc4bf23637e8204446c']
FILES=['server/research_flow.py','server/research_tool_flow.py','server/research_simulation_flow.py',
       'server/search_mcp.py','server/scholar_mcp_client.py','scripts/local_search_bridge.py',
       'tests/research_flow_acceptance.py','tests/test_research_tool_flow.py','tests/test_simulation_flow.py',
       'tests/test_scholar_workflow_contract.py','tests/test_workflow_recovery.py']


def main():
    archive=STAGE/'tool-recovery.tar.gz'
    with tarfile.open(archive,'w:gz') as bundle:
        for name in FILES:bundle.add(WORKBENCH/name,arcname=name)
        bundle.add(Path('C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts/simulation_worker.py'),arcname='tests/simulation_worker.py')
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/tool-recovery.tar.gz'],check=True,timeout=60)
    code='FILES='+repr(FILES)+'\nPROJECTS='+repr(PROJECTS)+'\n'+'''from pathlib import Path
import json,re,subprocess,tarfile,shutil,time,urllib.request
root=Path('/srv/research-workbench');candidate=root/'tool-recovery-candidate';candidate.mkdir(exist_ok=True)
with tarfile.open(root/'tool-recovery.tar.gz') as bundle:bundle.extractall(candidate,filter='data')
(candidate/'server/__init__.py').write_text("__path__.append('/workbench/server')\\n")
subprocess.run(['docker','exec','research-workbench','mkdir','-p','/tmp/tool-recovery-candidate'],check=True,capture_output=True)
subprocess.run(['docker','cp',str(candidate)+'/.','research-workbench:/tmp/tool-recovery-candidate'],check=True,capture_output=True)
tests=subprocess.run(['docker','exec','-e','WORKBENCH_FLOW_RECOVERY=0','-e','PYTHONPATH=/tmp/tool-recovery-candidate:/opt/workbench-tools/python-libs','-w','/tmp/tool-recovery-candidate','research-workbench','python','-m','unittest','discover','-s','tests','-p','*flow*.py','-v'],capture_output=True,text=True)
print(tests.stdout+tests.stderr);assert tests.returncode==0,'Recovery candidate tests failed'
count=int(re.search(r'Ran (\\d+) tests',tests.stderr)[1])
for name in FILES:
 source=candidate/name;compile(source.read_text(),str(source),'exec')
 if name.startswith('server/'):shutil.copyfile(source,root/'source'/name)
name='research-flow-recovery'
existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
if existing.returncode==0:raise RuntimeError('Recovery worker already exists; inspect its live work before replacing')
source=json.loads(subprocess.check_output(['docker','inspect','research-workbench'],text=True))[0]
command=['docker','run','-d','--name',name,'--restart','unless-stopped','--network','host','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','2','--memory','3g','--workdir','/workbench','--health-cmd','python /workbench/server/healthcheck.py','-e','WORKBENCH_FLOW_RECOVERY=workflows','-e','WORKBENCH_FLOW_RECOVERY_PROJECTS='+json.dumps(PROJECTS)]
for key in source['Config']['Env']:
 if key.startswith(('WORKBENCH_','HOME=','PYTHONPATH=')) and not key.startswith(('WORKBENCH_FLOW_RECOVERY=','WORKBENCH_FLOW_RECOVERY_PROJECTS=')):command+=['-e',key]
for mount in source['Mounts']:command+=['-v',mount['Source']+':'+mount['Destination']+('' if mount['RW'] else ':ro')]
command+=['--entrypoint','python',source['Image'],'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','47909','--lifespan','off']
subprocess.run(command,check=True,capture_output=True)
for _ in range(40):
 try:
  with urllib.request.urlopen('http://127.0.0.1:47909/health',timeout=2) as response:
   if json.load(response).get('ok'):break
 except OSError:pass
 time.sleep(.5)
else:raise RuntimeError('Recovery worker did not become ready')
caddy=Path('/etc/caddy/deeptutor.caddy');text=caddy.read_text()
old='    handle @research_flow {\\n        reverse_proxy 127.0.0.1:47905\\n    }'
new='    handle @research_flow {\\n        reverse_proxy 127.0.0.1:47909\\n    }'
assert old in text;text=text.replace(old,new,1)
text=text.replace('    handle @partner_project_flow {\\n        reverse_proxy 127.0.0.1:47907\\n    }','    handle @partner_project_flow {\\n        reverse_proxy 127.0.0.1:47909\\n    }',1)
caddy.write_text(text)
subprocess.run(['caddy','validate','--config',str(caddy),'--adapter','caddyfile'],check=True,capture_output=True)
subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
print(json.dumps({'deployed':True,'candidate_tests':count,'new_worker':name,'port':47909,'new_run_generation':'automatic-recovery-1','existing_workers_restarted':False}))
'''
    output=remote('papers-research',code)
    print(output)
    result=json.loads(output.splitlines()[-1])
    (ROOT/'reports/partner-recovery-deployment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
