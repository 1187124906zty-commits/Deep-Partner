"""Exercise the deployed section-restructuring workflow on the author's actual text."""
from pathlib import Path
import argparse
import base64
import gzip
import json
import os
import re
import subprocess
import sys
import uuid

import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/氯硫框架具体化/workflow-20261104'
LIVE=REPORT/'live'
STATE=ROOT/'.local/writing-journal-synthesis-20261104.json'
PID='1ea03384007d4bb9b88d43e3368099f3'
REMOTE_ROOT='/workspace/outputs/.deeptutor/chat/2e1f7a59cda65ffb9355b8afa9e999f9/workspaces/ws_0e6fc7aba58a4b258e25e1195702fde3'
PROJECT_FOLDER='project/docs/writing/regression/journal-synthesis-20261104'
SSH=['ssh','-o','ProxyJump=research-cluster-xh5','papers-research']


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def remote(code,timeout=80):
    r=subprocess.run([*SSH,'docker exec -i research-workbench python -'],input=code,
        capture_output=True,text=True,encoding='utf8',timeout=timeout)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return r.stdout


def prepare():
    manifest=json.loads((REPORT/'source-manifest.json').read_text(encoding='utf8'))
    for row in manifest:
        if row.get('evidence_excerpt') and row.get('access_scope','').startswith('bibliographic record'):
            row['access_scope']='new primary PDF acquired and pages 1–2 read for this source packet; deeper method notes remain separately located'
    save(REPORT/'source-manifest.json',manifest)
    prior=json.loads((ROOT/'reports/氯硫框架具体化/candidate-text.json').read_text(encoding='utf8'))
    by_doi={row['doi'].lower():row for row in manifest}
    references=[]
    for i,entry in enumerate(prior['references']):
        row=by_doi[entry['doi'].lower()]
        references.append({**row,'number':i+1})
    nodes=[]
    for value in prior['paragraphs']:
        content=[];last=0
        for match in re.finditer(r'\[(\d+)\]',value):
            if match.start()>last:content.append({'type':'text','text':value[last:match.start()]})
            row=references[int(match[1])-1]
            content.append({'type':'citation','attrs':{'refId':row['id'],'number':row['number']}})
            last=match.end()
        if last<len(value):content.append({'type':'text','text':value[last:]})
        nodes.append({'type':'paragraph','content':content})
    baseline={'title':prior['title'],'template':'generic-zh','content':{'type':'doc','content':nodes},
        'references':references,'comments':[],'revision':0}
    files={'baseline.json':json.dumps(baseline,ensure_ascii=False,indent=2),
        'source-manifest.json':json.dumps(manifest,ensure_ascii=False,indent=2),
        'current-author-chain.md':(REPORT/'workflow-brief.md').read_text(encoding='utf8'),
        'journal-learning.md':(REPORT/'journal-learning/examples.md').read_text(encoding='utf8'),
        'framework-gap.md':(REPORT/'gap-check/findings.md').read_text(encoding='utf8')}
    for label,path in [('thermo-phase-evidence.md','thermo_phase'),('bayes-evidence.md','bayes_sparse'),('phase-pinn-evidence.md','phase_pinn_speed')]:
        files[label]=(ROOT/'reports/氯硫框架具体化/literature'/path/'understanding.md').read_text(encoding='utf8')
    code='FILES='+repr(files)+'\nFOLDER='+repr(PROJECT_FOLDER)+'''
from pathlib import Path
import os,json
from server.storage import Store
store=Store(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'));root=store.path('local-admin','''+repr(PID)+''')
for name,text in FILES.items():
 p=root/FOLDER/name;raw=text.encode('utf8');store.replace('local-admin','''+repr(PID)+''',p,raw,'作者指定的期刊引言重组回归资料');assert p.read_bytes()==raw
print(json.dumps({'prepared_files':len(FILES),'source_count':len(json.loads(FILES['source-manifest.json']))}))
'''
    print(remote(code))


def collect(rid):
    LIVE.mkdir(parents=True,exist_ok=True)
    existing=[p.name for p in LIVE.iterdir() if p.is_file()]
    code='RID='+repr(rid)+'\nROOT='+repr(REMOTE_ROOT)+'\nEXISTING='+repr(existing)+'''
from pathlib import Path
from collections import Counter
import json,gzip,base64
root=Path(ROOT);folder=root/'.workbench/writing/runs'/RID;state=json.loads((folder/'state.json').read_text());files={}
names=['intent.json','exemplar.json','alignment.json','wide.json','review.json','wide-restructure.json','wide-candidate.json','retrieved-evidence.json','wide-diff.html','review-1.json']
for name in names:
 p=folder/name
 if p.is_file() and name not in EXISTING:files[name]=p.read_text()
if 'source-document.json' not in EXISTING:files['source-document.json']=json.dumps(state.get('source_document'),ensure_ascii=False,indent=2)
if state['status'] in ('completed','failed'):
 files['candidate-document.json']=json.dumps(state.get('candidate_document'),ensure_ascii=False,indent=2)
traces=[]
for p in sorted((folder/'agentic').glob('*/actions.jsonl')):
 rows=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
 traces.append({'stage':p.parent.name,'model_rounds':sum(r.get('event')=='model_round' for r in rows),
   'tools':dict(Counter(r.get('name') for r in rows if r.get('event')=='tool_call')),
   'output_saved':any(r.get('event')=='stage_output' for r in rows)})
safe={k:state.get(k) for k in ['id','status','stage','error','intent','editorial_scope','reference_policy','stage_plan','stage_history','outputs','agentic_calls']}
safe['native_manuscript_revision']=json.loads((root/'manuscript/main.json').read_text())['revision'];safe['traces']=traces
files['status.json']=json.dumps(safe,ensure_ascii=False,indent=2)
print(base64.b64encode(gzip.compress(json.dumps(files,ensure_ascii=False).encode())).decode())
'''
    encoded=remote(code)
    files=json.loads(gzip.decompress(base64.b64decode(encoded)))
    for name,text in files.items():(LIVE/name).write_text(text,encoding='utf8')
    status=json.loads(files['status.json'])
    print(json.dumps({k:status.get(k) for k in ['id','status','stage','error','native_manuscript_revision','traces']},ensure_ascii=False))


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status','collect','resume']);args=parser.parse_args()
    current=json.loads(STATE.read_text(encoding='utf8')) if STATE.exists() else {}
    if args.action=='collect':return collect(current['run_id'])
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=90,trust_env=False) as client:
        login(client)
        if args.action=='start' and not current.get('run_id'):
            prepare()
            choice=json.loads((REPORT/'author-structure-choice.json').read_text(encoding='utf8'))
            request='这是对上一版氯硫引言的本轮正式候选重组，主线与科学承诺沿用，不覆盖原稿。最新作者要求：'+choice['author_reply']+'\n按本项目current-author-chain.md执行，50—60篇独立已登记文献按研究群体综合挂引。前两段即现有预测的难点与不足；随后深度学习→物理信息→Bayesian稀疏含噪，并呼应相场神经求解。段数依论证决定，最终形成具体综合空白与本文回应。少用作者逐篇介绍，保持材料期刊立场；这是方法解决预测问题的论文，细节留方法。一轮原稿评分、章节重组、只读复评后交作者。实际学习journal-literature-synthesis与期刊完整引言，检索研究和表达RAG，源范围不足处读原文，不把取证活动写进正文。'
            if not current:
                current={'operation_id':'journal-synthesis-20261104-'+uuid.uuid4().hex[:12]};save(STATE,current)
            selection=json.loads((ROOT/'.local/writing-real-session-index.json').read_text(encoding='utf8'))[0]['sessions']['sessions'][0]['preferences'].get('llm_selection')
            body={'request':request,'operation_id':current['operation_id'],'phase':'draft','author_round':True,'proposal':True,'engine':'agentic',
                'editorial_scope':{'mode':'section_restructure','sections':['Introduction'],'basis':'作者最新实际回复指定的沙漏链'},
                'reference_policy':{'min_unique':50,'max_unique':60,'basis':'作者本轮50—60篇要求'},
                'baseline_document_path':PROJECT_FOLDER+'/baseline.json','source_manifest_path':PROJECT_FOLDER+'/source-manifest.json',
                'context_paths':[PROJECT_FOLDER+'/'+s for s in ['current-author-chain.md','journal-learning.md','framework-gap.md','thermo-phase-evidence.md','bayes-evidence.md','phase-pinn-evidence.md']],
                'model_selection':selection,'reuse_run_id':'7f057f9e0e5a441aa7e9238337d93f3e'}
            response=client.post('/research/api/projects/'+PID+'/writing/start',json=body);response.raise_for_status();value=response.json()
            current.update(run_id=value['id'],project_id=PID,request=request);save(STATE,current)
            save(REPORT/'live-run-binding.json',{k:v for k,v in current.items() if k!='request'})
        elif args.action=='resume':
            response=client.post('/research/api/projects/'+PID+'/writing/runs/'+current['run_id']+'/resume',json={});response.raise_for_status();value=response.json()
        else:
            response=client.get('/research/api/projects/'+PID+'/writing/runs/'+current['run_id']);response.raise_for_status();value=response.json()
        print(json.dumps({k:value.get(k) for k in ['id','status','stage','error','editorial_scope','reference_policy','stage_plan']},ensure_ascii=False))


if __name__=='__main__':main()
