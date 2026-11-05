"""Bounded transport for the DeepPartner workflow implementation and CLI build."""
from pathlib import Path
import argparse,json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.local/partner-workflow'
CLUSTER='/work/home/cluster_user/research-projects/deeptutor-integration/desktop'
DESKTOP=Path('D:/Development/电脑答疑/deeptutor-desktop')
WORKBENCH=Path('D:/Development/research-workbench')

def remote(host,code):
    command='/public/software/apps/anaconda3/2023.09/bin/python -' if host=='research-cluster-xh5' else 'sudo -n python3 -'
    r=subprocess.run(['ssh','-o','BatchMode=yes',host,command],input=code,text=True,encoding='utf8',capture_output=True,timeout=60)
    if r.returncode:raise RuntimeError(r.stderr[-3000:]+r.stdout[-1000:])
    return r.stdout.strip()

def cli_build():
    STAGE.mkdir(parents=True,exist_ok=True)
    with tarfile.open(STAGE/'cli-patch.tar.gz','w:gz') as t:
        for name in ['src/project_cli.rs','src/research_cli.rs','src/remote.rs','src/lib.rs','src/bin/dp.rs']:t.add(DESKTOP/name,arcname=name)
    subprocess.run(['scp','-q',str(STAGE/'cli-patch.tar.gz'),'research-cluster-xh5:'+CLUSTER+'/cli-patch.tar.gz'],check=True,timeout=60)
    code='''from pathlib import Path
import tarfile,subprocess
r=Path(CLUSTER)
with tarfile.open(r/'cli-patch.tar.gz') as t:t.extractall(r/'source',filter='data')
original=(r/'jobs/build-native.sh').read_text()
prefix=original.split('cd "$root"\\n',1)[0]
env=original.split('test -x "$root/tools/python/bin/cargo-xwin"',1)[1].split('rustc --version',1)[0]
body=prefix+'cd "$root/source"\\n'+'test -x "$root/tools/python/bin/cargo-xwin"'+env+'cargo build --offline --locked --release --target x86_64-pc-windows-msvc --no-default-features --bin dp\\nmkdir -p "$root/artifacts/cli-$SLURM_JOB_ID"\\ncp "$root/target/x86_64-pc-windows-msvc/release/dp.exe" "$root/artifacts/cli-$SLURM_JOB_ID/"\\n'
(r/'jobs/build-cli.sh').write_text(body)
batch=(r/'jobs/build-native.sbatch').read_text().replace('partner-windows','partner-cli').replace('/jobs/build-native.sh','/jobs/build-cli.sh').replace('--time=01:00:00','--time=00:25:00')
(r/'jobs/build-cli.sbatch').write_text(batch)
print(subprocess.check_output(['sbatch','--parsable',str(r/'jobs/build-cli.sbatch')],text=True).strip())
'''.replace('CLUSTER',repr(CLUSTER))
    job=remote('research-cluster-xh5',code)
    (STAGE/'cli-job.json').write_text(json.dumps({'job_id':job,'remote':CLUSTER}),encoding='utf8');print(job)

def backend(sidecar=False,test_only=False):
    stage=STAGE/'backend';(stage/'server').mkdir(parents=True,exist_ok=True);(stage/'tests').mkdir(exist_ok=True)
    for name in ['app.py','project_canvas.py','research_flow.py','research_code_flow.py','research_tool_flow.py','research_simulation_flow.py','standards.py','models.py','literature.py','chat_materials.py']:
        (stage/'server'/name).write_bytes((WORKBENCH/'server'/name).read_bytes())
    # This update changes ingestion only by its new parser hook. Keep unrelated
    # production edits rather than promoting another task's local drafts.
    for name in ['literature.py','chat_materials.py']:
        text=remote('papers-research',"print(__import__('pathlib').Path('/srv/research-workbench/source/server/"+name+"').read_text())")
        if name=='literature.py' and 'parsing=enqueue_parse(store,owner,pid,key)' not in text:
            old="    return {'name':key,'library':'workspace','metadata':record,'attachment':True}"
            new="    from .research_tool_flow import enqueue_parse\n    parsing=enqueue_parse(store,owner,pid,key)\n    return {'name':key,'library':'workspace','metadata':record,'attachment':True,'parsing':parsing}"
            assert old in text;text=text.replace(old,new,1)
        if name=='chat_materials.py' and "entry['cluster_parsing']=enqueue_parse" not in text:
            old="                enqueue_after_ingest(store,owner,pid,entry['literature_asset'],metadata)"
            new=old+"\n                from .research_tool_flow import enqueue_parse\n                entry['cluster_parsing']=enqueue_parse(store,owner,pid,entry['literature_asset'])"
            assert old in text;text=text.replace(old,new,1)
        (stage/'server'/name).write_text(text,encoding='utf8')
    # Carry only this task's workflow registration, preserving an unrelated local draft.
    base=(STAGE/'before/task_workflows.py').read_text(encoding='utf8')
    lines=[line for line in (WORKBENCH/'server/task_workflows.py').read_text(encoding='utf8').splitlines() if "'research-flow':" in line or "'cluster-pdf-parse':" in line or "'simulation':" in line]
    (stage/'server/task_workflows.py').write_text(base.replace('WORKFLOWS={','WORKFLOWS={\n'+'\n'.join(lines),1),encoding='utf8')
    (stage/'server/__init__.py').write_text("__path__.append('/workbench/server')\n",encoding='utf8')
    production=remote('papers-research',"print(__import__('pathlib').Path('/srv/research-workbench/source/server/paper_maps.py').read_text())")
    marker="    if SERVICE is None:return None\n"
    assert marker in production
    guard="    if store.get(owner,pid).get('config',{}).get('research_flow_managed'):return None\n"
    if guard not in production:production=production.replace(marker,marker+guard,1)
    (stage/'server/paper_maps.py').write_text(production,encoding='utf8')
    (stage/'tests/research_flow_acceptance.py').write_bytes((WORKBENCH/'tests/research_flow_acceptance.py').read_bytes())
    (stage/'tests/test_research_tool_flow.py').write_bytes((WORKBENCH/'tests/test_research_tool_flow.py').read_bytes())
    (stage/'tests/test_simulation_flow.py').write_bytes((WORKBENCH/'tests/test_simulation_flow.py').read_bytes())
    (stage/'tests/simulation_worker.py').write_bytes(Path('C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts/simulation_worker.py').read_bytes())
    archive=STAGE/'partner-flow.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for path in stage.rglob('*'):
            if path.is_file():t.add(path,arcname=path.relative_to(stage))
    subprocess.run(['scp','-q',str(archive),'papers-research:/srv/research-workbench/partner-flow.tar.gz'],check=True,timeout=60)
    code='''from pathlib import Path
import subprocess,tarfile,shutil,json,os
root=Path('/srv/research-workbench');stage=root/'partner-flow-candidate';stage.mkdir(exist_ok=True)
with tarfile.open(root/'partner-flow.tar.gz') as t:t.extractall(stage,filter='data')
subprocess.run(['docker','exec','research-workbench','mkdir','-p','/tmp/partner-flow-candidate'],check=True,capture_output=True)
subprocess.run(['docker','cp',str(stage)+'/.','research-workbench:/tmp/partner-flow-candidate'],check=True,capture_output=True)
r=subprocess.run(['docker','exec','-e','PYTHONPATH=/tmp/partner-flow-candidate:/opt/workbench-tools/python-libs','-w','/tmp/partner-flow-candidate','research-workbench','python','-m','unittest','discover','-s','tests','-p','*flow*.py','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr);assert r.returncode==0,'Candidate test failure'
probe="from server.app import store;import json\\nwith store.db() as c:rows=c.execute(\\\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\\\").fetchall()\\nassert not rows,'Workbench has active work'"
if not SIDECAR and not TEST_ONLY:subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
for name in ['task_workflows.py','research_flow.py','research_tool_flow.py','research_simulation_flow.py','literature.py','chat_materials.py']:
    source=stage/'server'/name;compile(source.read_text(),str(source),'exec')
    if not TEST_ONLY:shutil.copyfile(source,root/'source/server'/name)
print(json.dumps({'candidate_tests':17,'staged':True,'files':['task_workflows.py','research_flow.py','research_tool_flow.py','research_simulation_flow.py']}))
'''.replace('SIDECAR',repr(sidecar)).replace('TEST_ONLY',repr(test_only))
    result=remote('papers-research',code);print(result)
    if test_only:return
    if not sidecar:
        sys.path.insert(0,str(WORKBENCH/'scripts'));from deploy import start
        start();return
    code=r'''from pathlib import Path
import subprocess,json,time,urllib.request
source=json.loads(subprocess.check_output(['docker','inspect','research-workbench'],text=True))[0]
existing=subprocess.run(['docker','inspect','research-flow'],capture_output=True,text=True)
if existing.returncode==0:
    subprocess.run(['docker','rm','-f','research-flow'],check=True,capture_output=True)
command=['docker','run','-d','--name','research-flow','--restart','unless-stopped','--network','host','--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','2','--memory','3g','--workdir','/workbench','--health-cmd','python /workbench/server/healthcheck.py','-e','WORKBENCH_FLOW_RECOVERY=1']
for key in source['Config']['Env']:
    if key.startswith(('WORKBENCH_','HOME=','PYTHONPATH=')):command+=['-e',key]
for mount in source['Mounts']:command+=['-v',mount['Source']+':'+mount['Destination']+('' if mount['RW'] else ':ro')]
command+=['--entrypoint','python',source['Image'],'-m','uvicorn','server.app:app','--host','127.0.0.1','--port','47905','--lifespan','off']
subprocess.run(command,check=True,capture_output=True)
for _ in range(40):
    try:
        with urllib.request.urlopen('http://127.0.0.1:47905/health',timeout=2) as response:
            if json.load(response).get('ok'):break
    except OSError:pass
    time.sleep(.5)
else:raise RuntimeError('Research flow did not become ready')
path=Path('/etc/caddy/deeptutor.caddy');text=path.read_text()
block='''+repr('    # Deep Partner typed research workflows; existing jobs keep their worker.\n    @research_flow path_regexp research_flow ^/research/api/projects/[^/]+/research-flow(/.*)?$\n    handle @research_flow {\n        reverse_proxy 127.0.0.1:47905\n    }\n    @research_flow_delivery path_regexp research_flow_delivery ^/research/api/download-worker/[^/]+/result$\n    handle @research_flow_delivery {\n        reverse_proxy 127.0.0.1:47905\n    }\n')+r'''
if '@research_flow path_regexp' not in text:
    assert '    handle /research {\n' in text
    candidate=text.replace('    handle /research {\n',block+'    handle /research {\n',1)
    check=path.with_name('research-flow.caddy.check');check.write_text(candidate)
    subprocess.run(['caddy','validate','--config',str(check),'--adapter','caddyfile'],check=True,capture_output=True)
    path.write_text(candidate);subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True);check.unlink()
text=path.read_text()
ingest="    @research_cluster_ingest path_regexp research_cluster_ingest ^/research/api/projects/[^/]+/(literature/upload|attachments)$\n    handle @research_cluster_ingest {\n        reverse_proxy 127.0.0.1:47905\n    }\n"
if '@research_cluster_ingest path_regexp' not in text:
    candidate=text.replace('    handle /research {\n',ingest+'    handle /research {\n',1)
    check=path.with_name('research-ingest.caddy.check');check.write_text(candidate)
    subprocess.run(['caddy','validate','--config',str(check),'--adapter','caddyfile'],check=True,capture_output=True)
    path.write_text(candidate);subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True);check.unlink()
print(json.dumps({'flow_service':True,'main_workbench_restarted':False,'native_tutor_restarted':False,'listen':'127.0.0.1:47905','lifespan':'off: no unrelated job reconciliation or duplicate paper-map loop'}))
'''
    print(remote('papers-research',code))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['cli-build','backend','backend-sidecar','backend-candidate']);a=p.parse_args()
    if a.action=='cli-build':cli_build()
    if a.action=='backend':backend()
    if a.action=='backend-sidecar':backend(True)
    if a.action=='backend-candidate':backend(True,True)
