"""Fetch only new bounded regression products and source-labelled action summaries."""
from pathlib import Path
import base64
import gzip
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/关键句工作流回归'


def main():
    sys.stdout.reconfigure(encoding='utf8');OUT.mkdir(exist_ok=True)
    existing={label:[p.name for p in (OUT/label).glob('*')] for label in ['chloride','moisture']}
    code='EXISTING='+repr(existing)+r'''
from pathlib import Path
from collections import Counter
import json,gzip,base64,time
base=Path('/workspace/outputs/.deeptutor/chat/2e1f7a59cda65ffb9355b8afa9e999f9/workspaces');result=[]
for ws,rid,label in [('ws_0e6fc7aba58a4b258e25e1195702fde3','7f057f9e0e5a441aa7e9238337d93f3e','chloride'),('ws_06a666b5802645998b8ad9513dbc10ab','f4daf4284d7448e0824b281f059bf938','moisture')]:
 folder=base/ws/'.workbench/writing/runs'/rid;out=folder/'expression-workflow-regression'
 files={p.name:p.read_text() for p in out.glob('*') if p.is_file() and (p.name not in EXISTING[label] or p.name=='status.json')}
 traces=[]
 for p in sorted((folder/'agentic').glob('expression_regression_*/actions.jsonl')):
  rows=[json.loads(line) for line in p.read_text().splitlines()]
  calls=[r for r in rows if r['event']=='tool_call']
  traces.append({'stage':p.parent.name,'model_rounds':sum(r['event']=='model_round' for r in rows),
   'tools':dict(Counter(r['name'] for r in calls)),'skills':[r['arguments'].get('name') for r in calls if r['name']=='read_skill'],
   'queries':[r['arguments'] for r in calls if r['name']=='rag_search'],
   'age_seconds':round(time.time()-rows[-1]['time']),'last_event':rows[-1]['event'],'model_output_saved':any(r['event']=='stage_output' for r in rows)})
 result.append({'label':label,'files':files,'traces':traces})
print(base64.b64encode(gzip.compress(json.dumps(result,ensure_ascii=False).encode())).decode())
'''
    response=subprocess.run(['ssh','-o','ProxyJump=research-cluster-xh5','papers-research','docker exec -i research-workbench python -'],
        input=code,capture_output=True,text=True,encoding='utf8',timeout=60)
    assert response.returncode==0,response.stderr
    rows=json.loads(gzip.decompress(base64.b64decode(response.stdout)))
    for row in rows:
        target=OUT/row['label'];target.mkdir(exist_ok=True)
        for name,value in row['files'].items():(target/name).write_text(value,encoding='utf8')
        (target/'action-summary.json').write_text(json.dumps(row['traces'],ensure_ascii=False,indent=2),encoding='utf8')
        status=json.loads((target/'status.json').read_text(encoding='utf8'))
        print(json.dumps({'case':row['label'],'status':status,'new_files':list(row['files']),'traces':row['traces']},ensure_ascii=False))


if __name__=='__main__':main()
