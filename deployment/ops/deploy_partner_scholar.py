"""Deploy the Scholar contract without interrupting other projects' active jobs."""
from pathlib import Path
import json, subprocess, tarfile
from partner_workflow_dev import remote, ROOT, STAGE, WORKBENCH

PROJECTS = ['c37b9168a0db40e3b258c9c03cd56697', '64c6b5e79b824bc4bf23637e8204446c']
FILES = ['server/scholar_mcp_client.py', 'server/search_mcp.py',
         'server/research_tool_flow.py', 'tests/test_scholar_workflow_contract.py',
         'tests/test_research_tool_flow.py', 'scripts/local_search_bridge.py']


def main():
    archive = STAGE / 'scholar-contract.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for name in FILES:
            bundle.add(WORKBENCH / name, arcname=name)
    subprocess.run(['scp', '-q', str(archive), 'papers-research:/srv/research-workbench/scholar-contract.tar.gz'],
                   check=True, timeout=60)
    code = 'PROJECTS='+repr(PROJECTS)+'\nFILES='+repr(FILES)+'\n'+'''from pathlib import Path
import json,subprocess,tarfile,shutil,time,urllib.request
root=Path('/srv/research-workbench');candidate=root/'scholar-contract-candidate';candidate.mkdir(exist_ok=True)
with tarfile.open(root/'scholar-contract.tar.gz') as bundle:bundle.extractall(candidate,filter='data')
(candidate/'server/__init__.py').write_text("__path__.append('/workbench/server')\\n")
subprocess.run(['docker','exec','research-workbench','mkdir','-p','/tmp/scholar-contract-candidate'],check=True,capture_output=True)
subprocess.run(['docker','cp',str(candidate)+'/.','research-workbench:/tmp/scholar-contract-candidate'],check=True,capture_output=True)
tests=subprocess.run(['docker','exec','-e','PYTHONPATH=/tmp/scholar-contract-candidate:/opt/workbench-tools/python-libs','-w','/tmp/scholar-contract-candidate','research-workbench','python','-m','unittest','discover','-s','tests','-p','test_*flow*.py','-v'],capture_output=True,text=True)
print(tests.stdout+tests.stderr);assert tests.returncode==0,'Candidate tests failed'
for name in FILES:
    source=candidate/name;compile(source.read_text(),str(source),'exec')
    if name.startswith('server/'):shutil.copyfile(source,root/'source'/name)
config_script="from pathlib import Path;import os,json;p=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))/'runtime-home/tool-bridge/bridge.json';d=json.loads(p.read_text());d['native_execution_projects']=PROJECTS;p.write_text(json.dumps(d));p.chmod(0o600);print('Project execution grants saved')"
subprocess.run(['docker','exec','research-workbench','python','-c',config_script.replace('PROJECTS',repr(PROJECTS))],check=True,capture_output=True)
# Other projects are still running in research-flow: keep that worker alive.
name='research-flow-project';existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
if existing.returncode==0:raise RuntimeError('Project worker already exists; inspect its active work before replacing')
source=json.loads(subprocess.check_output(['docker','inspect','research-workbench'],text=True))[0]
command=['docker','run','-d','--name',name,'--restart','unless-stopped','--network','host','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','1','--memory','2g','--workdir','/workbench']
for key in source['Config']['Env']:
    if key.startswith(('WORKBENCH_','HOME=','PYTHONPATH=')) and not key.startswith('WORKBENCH_FLOW_RECOVERY='):command+=['-e',key]
for mount in source['Mounts']:command+=['-v',mount['Source']+':'+mount['Destination']+('' if mount['RW'] else ':ro')]
command+=['--entrypoint','python',source['Image'],'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','47907','--lifespan','off']
subprocess.run(command,check=True,capture_output=True)
for _ in range(35):
    try:
        with urllib.request.urlopen('http://127.0.0.1:47907/health',timeout=2) as response:
            if json.load(response).get('ok'):break
    except OSError:pass
    time.sleep(.5)
else:raise RuntimeError('Project worker did not become ready')
caddy=Path('/etc/caddy/deeptutor.caddy');text=caddy.read_text()
marker='    # Deep Partner typed research workflows; existing jobs keep their worker.'
assert marker in text
block='    # Project-scoped native tools upgrade while other projects keep active jobs.\\n    @partner_project_flow path_regexp partner_project_flow ^/research/api/projects/('+ '|'.join(PROJECTS)+')/research-flow(/.*)?$\\n    handle @partner_project_flow {\\n        reverse_proxy 127.0.0.1:47907\\n    }\\n'
caddy.write_text(text.replace(marker,block+marker,1))
subprocess.run(['caddy','validate','--config',str(caddy),'--adapter','caddyfile'],check=True,capture_output=True)
subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
print(json.dumps({'deployed':True,'projects':PROJECTS,'worker':name,'original_workers_restarted':False}))
'''
    print(remote('papers-research', code))


if __name__ == '__main__':
    main()
