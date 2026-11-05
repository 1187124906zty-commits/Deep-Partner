"""Repair false parser rejections inside the same authorized editorial round."""
from pathlib import Path
import json
import os
import subprocess
import sys
import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    runs=json.loads((ROOT/'.local/writing-real/agentic-tests.json').read_text(encoding='utf8'))
    index=json.loads((ROOT/'.local/writing-real-session-index.json').read_text(encoding='utf8'))
    roots={row['project']['id']:row['project']['root'] for row in index}
    code='RUNS='+repr(list(runs.values()))+'\nROOTS='+repr(roots)+r'''
from pathlib import Path
from copy import deepcopy
import json,shutil,urllib.request
from server.storage import atomic_json,now
from server.writing_revision import apply_edits,edit_issue_ids,difference
from server.writing_scores import normalize_score
with urllib.request.urlopen('http://172.19.0.3:47931/health',timeout=10) as response:health=json.load(response)
assert not any(any(key.startswith(r['id']+':') for key in health['active_runs']) for r in RUNS)
for item in RUNS:
 root=Path(ROOTS[item['project_id']]);folder=root/'.workbench/writing/runs'/item['id']
 state=json.loads((folder/'state.json').read_text());assert state['status'] in ['cancelled','failed','interrupted','completed']
 assert not (folder/'parser-repair.json').exists(),'This repair has already been applied'
 backup=folder/'before-parser-repair';backup.mkdir()
 for name in ['state.json','alignment.json','narrow-edits.json','wide-edits.json','narrow.json','wide.json','review.json','review-1.json']:
  p=folder/name
  if p.is_file():shutil.copyfile(p,backup/name)
 before=deepcopy(state['candidate_document']);candidate=deepcopy(before);repairs=[]
 assessment=normalize_score(state['l2']['editorial_assessment'],use_baseline=True)
 selected={i['id'] for i in assessment['issues'] if i['classification']=='necessary' and i.get('selected_for_this_round',True)}
 all_accepted=[]
 for stage in ['narrow','wide']:
  p=folder/(stage+'-edits.json')
  if not p.exists():continue
  value=json.loads(p.read_text());history=[]
  for report in value['reports']:
   pending=[];retained=[]
   for edit in report['rejected']:
    ids=edit_issue_ids(edit)
    if ids and set(ids)<=selected:pending.append({**edit,'issue_ids':ids})
    else:retained.append(edit)
   if pending:
    candidate,applied=apply_edits(candidate,pending)
    assert not applied['rejected'],applied['rejected']
    repairs.extend(applied['accepted']);history.extend(report['rejected'])
    report['accepted'].extend(applied['accepted']);report['rejected']=retained
    report['edited_fragments']=len(report['accepted'])
   all_accepted.extend(report['accepted'])
  value['parser_repair']={'previous_rejections':history,'basis':'组合问题编号及同身份引用分组被误拒；仅接回已经选定的必要建议'}
  atomic_json(p,value)
  state[stage]['edited_fragments']=sum(r['edited_fragments'] for r in value['reports'])
  state[stage]['rejected_edits']=[e for r in value['reports'] for e in r['rejected']]
  atomic_json(folder/(stage+'.json'),state[stage])
 applied_ids=sorted({i for edit in all_accepted for i in edit_issue_ids(edit)})
 record={'performed':now(),'reason':'修复评分与候选接回的接口错误；不重新生成正文，不开始作者第二轮',
  'newly_applied_fragments':len(repairs),'newly_applied_patches':repairs,'all_applied_issue_ids':applied_ids,
  'selected_necessary_issue_ids':sorted(selected),'selected_but_not_applied':sorted(selected-set(applied_ids)),
  'original_score':assessment['total_score'],'author_approval':'pending'}
 state['candidate_document']=candidate;state['l2']['editorial_assessment']=assessment
 state['l2'].pop('chinese_introduction_candidate',None)
 notes=state['l2'].get('workflow_and_source_notes',{})
 if 'execution_stages' in notes:notes['unverified_model_stage_self_reports']=notes.pop('execution_stages')
 state['l2']['actual_round_handoff']=record
 state.update(status='interrupted',stage='review',review={},outputs={},error='',agent_stage='review_after_parser_repair')
 state['stage_history'].append({'stage':'candidate_integration_repair','completed':now(),'output':'parser-repair.json',
  'basis':'保留原建议；修复误拒后重新复评同一轮实际候选'})
 atomic_json(folder/'parser-repair.json',record);atomic_json(folder/'alignment.json',state['l2'])
 atomic_json(folder/'repaired-candidate.json',candidate)
 (folder/'parser-repair-diff.html').write_text(difference(before,candidate,'同一轮必要项接回修复'),encoding='utf8')
 atomic_json(folder/'state.json',state)
 print(json.dumps({'id':state['id'],'repaired_fragments':len(repairs),'applied_issue_ids':applied_ids,
  'pending_necessary':record['selected_but_not_applied'],'original_score':assessment['total_score']},ensure_ascii=False))
'''
    result=subprocess.run(['ssh','-o','ProxyJump=research-cluster-xh5','papers-research','docker exec -i research-workbench python -'],
        input=code,capture_output=True,text=True,encoding='utf8',timeout=45)
    print(result.stdout);print(result.stderr[-1500:]);assert result.returncode==0
    (ROOT/'reports/writing-parser-repair.jsonl').write_text(result.stdout,encoding='utf8')
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=120,trust_env=False) as client:
        login(client)
        for name,item in runs.items():
            response=client.post('/research/api/projects/'+item['project_id']+'/writing/runs/'+item['id']+'/resume');response.raise_for_status()
            state=response.json();print(json.dumps({'task':name,'status':state['status'],'stage':state['stage']},ensure_ascii=False))


if __name__=='__main__':main()
