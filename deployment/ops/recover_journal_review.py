"""Keep the actual read-only review and inherit unchanged issue categories."""
import json
import sys

from run_journal_synthesis_regression import remote, REMOTE_ROOT, STATE, LIVE


def main():
    sys.stdout.reconfigure(encoding='utf8')
    rid=json.loads(STATE.read_text(encoding='utf8'))['run_id']
    code='RID='+repr(rid)+'\nROOT='+repr(REMOTE_ROOT)+r'''
from pathlib import Path
import json
from server.storage import atomic_json,now
from server.writing import decode_json,document_markdown
from server.writing_scores import normalize_score
from server.writing_prompts import VERSION

root=Path(ROOT);folder=root/'.workbench/writing/runs'/RID
state=json.loads((folder/'state.json').read_text())
assert state['status']=='failed' and state['stage']=='review'
assert state['error']=='修改项需要区分必要修改、潜在优化或作者判断'
result=decode_json((folder/'agentic/review/output.txt').read_text())
result['after_assessment']=normalize_score(result['after_assessment'],baseline_assessment=state['l2']['editorial_assessment'])
result['final_text']=document_markdown(state['candidate_document'])
result['all_assertions_passed']=False;result['author_approval']='pending'
result['model_author_feedback_coverage']=result.get('author_feedback_coverage',[])
record={'time':now(),'reason':'复评已返回旧问题的状态与理由；沿用同一问题ID在原稿评审中的necessary/potential/author_decision分类，不改评分或实质意见','raw_output':'agentic/review/output.txt','candidate_score':result['after_assessment']['total_score'],'model_review_rewritten':False,'recovered_using_version':VERSION}
atomic_json(folder/'review-integration-repair.json',record)
atomic_json(folder/'review.json',result);atomic_json(folder/'review-1.json',result)
state['review']=result;state.update(status='interrupted',stage='deliver',error='')
state['stage_history'].append({'stage':'review','completed':now(),'output':'review.json','prompt_version':'1111-20261104.4','integration_repair':'review-integration-repair.json'})
atomic_json(folder/'state.json',state)
print(json.dumps({'record':record,'review':result},ensure_ascii=True))
'''
    value=json.loads(remote(code))
    for name,data in [('review.json',value['review']),('review-integration-repair.json',value['record'])]:
        (LIVE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value['record'],ensure_ascii=False))


if __name__=='__main__':main()
