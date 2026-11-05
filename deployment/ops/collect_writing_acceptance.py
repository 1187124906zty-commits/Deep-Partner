"""Collect real scored-round products without exporting runtime credentials."""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/真实写作验收'
SSH=['ssh','-o','ProxyJump=research-cluster-xh5','papers-research']
RUNS=[('1ea03384007d4bb9b88d43e3368099f3','7f057f9e0e5a441aa7e9238337d93f3e','氯硫'),
      ('638495c5ba024a93a305ff69b4658811','f4daf4284d7448e0824b281f059bf938','水分扩散')]


def remote(code):
    result=subprocess.run([*SSH,'docker exec -i research-workbench python -'],input=code,
        capture_output=True,text=True,encoding='utf8',timeout=60)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return json.loads(result.stdout)


def main():
    sys.stdout.reconfigure(encoding='utf8');OUT.mkdir(exist_ok=True)
    indexed=json.loads((ROOT/'.local/writing-real-session-index.json').read_text(encoding='utf8'))
    roots={row['project']['id']:row['project']['root'] for row in indexed}
    existing={label:[p.name for p in (OUT/(label+'_实际工作流记录')).glob('*')] for _,_,label in RUNS}
    code='RUNS='+repr(RUNS)+'\nROOTS='+repr(roots)+'\nEXISTING='+repr(existing)+'''\n
from pathlib import Path
from collections import Counter
import json
result=[]
for pid,rid,label in RUNS:
 root=Path(ROOTS[pid]);folder=root/'.workbench/writing/runs'/rid
 state=json.loads((folder/'state.json').read_text());files={}
 repair_new=(folder/'parser-repair.json').exists() and 'parser-repair.json' not in EXISTING[label]
 for name in ['exemplar.json','alignment.json','narrow.json','wide.json','review.json','narrow-edits.json','wide-edits.json','review-1.json','parser-repair.json']:
  p=folder/name
  if p.is_file() and (name not in EXISTING[label] or (repair_new and name!='exemplar.json')):files[name]=p.read_text()
 if repair_new:files['original-model-alignment.json']=(folder/'before-parser-repair/alignment.json').read_text()
 for key,name in [('source_document','baseline.json'),('candidate_document','candidate.json')]:
  wanted=name not in EXISTING[label] or (key=='candidate_document' and state['status']=='completed')
  if state.get(key) and wanted:files[name]=json.dumps(state[key],ensure_ascii=False,indent=2)
 for name in ['narrow-diff.html','wide-diff.html']:
  p=folder/name
  if p.is_file() and name not in EXISTING[label]:files[name]=p.read_text()
 actions=[]
 for p in sorted((folder/'agentic').glob('*/actions.jsonl')):
  rows=[json.loads(line) for line in p.read_text().splitlines()]
  actions.append({'stage':p.parent.name,'model_rounds':sum(x['event']=='model_round' for x in rows),
    'tools':dict(Counter(x['name'] for x in rows if x['event']=='tool_call')),
    'native_web_events':sum(x['event']=='native_web_search' for x in rows),
    'output_saved':any(x['event']=='stage_output' for x in rows)})
 summary={k:state.get(k) for k in ['id','project_id','status','stage','error','stage_plan','stage_history','revision_mode','author_round','proposal']}
 summary['actions']=actions;summary['outputs']={k:v for k,v in state.get('outputs',{}).items() if k!='text'}
 native_path=root/'manuscript/main.json'
 summary['native_manuscript_revision']=json.loads(native_path.read_text()).get('revision') if native_path.is_file() else 0
 result.append({'label':label,'files':files,'summary':summary})
print(json.dumps(result,ensure_ascii=False))
'''
    result=remote(code)
    for row in result:
        target=OUT/(row['label']+'_实际工作流记录');target.mkdir(exist_ok=True)
        for name,content in row['files'].items():(target/name).write_text(content,encoding='utf8')
        (target/'run-summary.json').write_text(json.dumps(row['summary'],ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'task':row['label'],'status':row['summary']['status'],'stage':row['summary']['stage'],
            'products':list(row['files'])},ensure_ascii=False))


if __name__=='__main__':main()
