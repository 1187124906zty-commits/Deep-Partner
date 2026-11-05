"""Publish measured latency fixes without touching project data or Tutor."""
from pathlib import Path
import json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE/'scripts'))
from deploy import remote,start


def main():
    target=ROOT/'.local/cluster-native/responsiveness-backend.tar.gz'
    files=['app.py','job_stream.py','response_compression.py']
    with tarfile.open(target,'w:gz') as bundle:
        for name in files:bundle.add(SOURCE/'server'/name,arcname='server/'+name)
    subprocess.run(['scp','-q',str(target),'papers-research:/srv/research-workbench/responsiveness-backend.tar.gz'],check=True,timeout=90)
    code="""from pathlib import Path
import subprocess,tarfile,json
root=Path('/srv/research-workbench');source=root/'source'
probe=\"from server.app import store\\nwith store.db() as db:rows=db.execute(\\\"SELECT id FROM jobs WHERE status='running' OR (status='queued' AND kind!='literature-download')\\\").fetchall()\\nassert not rows,'Active work must finish before restarting'\"
subprocess.run(['docker','exec','research-workbench','python','-c',probe],check=True,capture_output=True)
with tarfile.open(root/'responsiveness-backend.tar.gz') as bundle:
 assert all(m.isfile() and (source/m.name).resolve().is_relative_to(source.resolve()) for m in bundle.getmembers())
 bundle.extractall(source,filter='data')
print(json.dumps({'backend_received':True,'project_data_unchanged':True}))
"""
    result=json.loads(remote(code,root=True,timeout=60));start()
    result.update(files=files,native_tutor_restarted=False)
    (ROOT/'reports/workspace-responsiveness-backend.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
