"""Test the actual MCP worker and manuscript-preserving edits before activation."""
from pathlib import Path
import argparse,json,subprocess,sys,tarfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
SSH=['ssh','-o','ProxyJump=research-cluster-xh5','papers-research']


def remote(code,timeout=60):
    r=subprocess.run([*SSH,'sudo -n python3 -'],input=code,capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return r.stdout


def main():
    sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['test','install']);args=parser.parse_args()
    if args.action=='test':
        target=ROOT/'.local/writing-agent-candidate.tar.gz'
        with tarfile.open(target,'w:gz') as tar:
            for p in (SOURCE/'server').glob('*.py'):tar.add(p,arcname='server/'+p.name)
            for name in ['test_writing.py','test_writing_revision.py','test_writing_scores.py','test_writing_expression.py','test_writing_synthesis.py','test_task_workflows.py']:tar.add(SOURCE/'tests'/name,arcname='tests/'+name)
            for p in (ROOT/'tutor-extension/writing_agent').rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:tar.add(p,arcname='writing_agent/'+p.relative_to(ROOT/'tutor-extension/writing_agent').as_posix())
        subprocess.run(['scp','-q','-o','ProxyJump=research-cluster-xh5',str(target),'papers-research:/srv/research-workbench/writing-agent-candidate.tar.gz'],check=True,timeout=60)
        code=r'''from pathlib import Path
import subprocess,tarfile,json
root=Path('/srv/research-workbench/tools/writing-agent-candidate');root.mkdir(exist_ok=True)
with tarfile.open('/srv/research-workbench/writing-agent-candidate.tar.gz') as tar:tar.extractall(root,filter='data')
cmd=['docker','exec','-e','PYTHONPATH=/opt/workbench-tools/writing-libs:/opt/workbench-tools/python-libs','-w','/opt/workbench-tools/writing-agent-candidate','research-workbench','python','-m','pytest','tests/test_writing.py','tests/test_writing_revision.py','tests/test_writing_scores.py','tests/test_writing_expression.py','tests/test_writing_synthesis.py','tests/test_task_workflows.py','-q','-p','no:cacheprovider']
r=subprocess.run(cmd,capture_output=True,text=True);print(r.stdout);print(r.stderr);assert r.returncode==0
'''
        log=remote(code,90);(ROOT/'reports/writing-agent-candidate-tests.log').write_text(log,encoding='utf8');print(log)
    else:
        assert 'passed' in (ROOT/'reports/writing-agent-candidate-tests.log').read_text(encoding='utf8')
        code=r'''from pathlib import Path
import subprocess,shutil,json,urllib.request,time
wb=Path('/srv/research-workbench');candidate=wb/'tools/writing-agent-candidate'
probe="from server.app import store\nwith store.db() as c:rows=c.execute(\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\").fetchall()\nassert not rows,'Workbench has active work'"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
for name in ['writing.py','writing_prompts.py','writing_tools.py','writing_revision.py','writing_scores.py','writing_expression.py','writing_synthesis.py']:
 p=candidate/'server'/name;compile(p.read_text(),str(p),'exec');shutil.copyfile(p,wb/'source/server'/name)
target=Path('/srv/dify-research/tutor-extension/writing_agent');shutil.copytree(candidate/'writing_agent',target,dirs_exist_ok=True)
(wb/'tools/writing/agent-url').write_text('http://172.19.0.3:47931\n')
stop="""from pathlib import Path
import os,signal
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(b'\\0')
 except OSError:continue
 if b'writing_agent.agent_service:app' in args:os.kill(int(p.name),signal.SIGTERM)
"""
subprocess.run(['docker','exec','-i','deeptutor','python','-'],input=stop,text=True,check=True,capture_output=True)
time.sleep(.5)
cmd=['docker','exec','-d','-w','/app','-e','PYTHONPATH=/opt/dify-delivery:/app','deeptutor','python','-m','uvicorn','writing_agent.agent_service:app','--host','0.0.0.0','--port','47931','--log-level','warning']
subprocess.run(cmd,check=True,capture_output=True)
for _ in range(40):
 try:
  with urllib.request.urlopen('http://172.19.0.3:47931/health',timeout=2) as r:
   status=json.load(r)
  if status['ok']:break
 except OSError:pass
 time.sleep(.3)
else:raise RuntimeError('Writing worker health failed')
subprocess.run(['docker','restart','research-workbench'],check=True,capture_output=True)
print(json.dumps({'worker':status,'candidate_tested':True,'native_core_restarted':False,'chat_extension_activated':False,'new_ui_published':False}))
'''
        result=remote(code,90);(ROOT/'reports/writing-agent-stage.json').write_text(result,encoding='utf8');print(result)


if __name__=='__main__':main()
