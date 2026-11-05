"""Run diagnosis, selected edits and review with the deployed agent/MCP workflow."""
from pathlib import Path
import json
import os
import subprocess
import sys
import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/关键句工作流回归'


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    OUT.mkdir(exist_ok=True)
    index=json.loads((ROOT/'.local/writing-real-session-index.json').read_text(encoding='utf8'))
    roots={row['project']['id']:row['project']['root'] for row in index}
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=90,trust_env=False) as client:
        login(client);auth={'Origin':ORIGIN,'Cookie':'; '.join(k+'='+v for k,v in client.cookies.items())}
    # The three reported sentences are deliberately absent from this instruction.
    # They are ordinary manuscript context, not hard-coded replacements or bans.
    request='这是工作流表达能力回归。关键位置太弱、绕，读起来别扭。请在相近意思的基础上让关键句更直接、顺畅、有力度；不是提升贡献、换研究主线或增加科学承诺。摘要收尾应把已有能力的用途说清。只做一轮评分、选中表达问题、局部编辑与复评。'
    code='AUTH='+repr(auth)+'\nROOTS='+repr(roots)+'\nREQUEST='+repr(request)+r'''
import asyncio,json,copy,time
from pathlib import Path
import httpx
from server import writing_prompts as prompts,writing_scores as scoring
from server.writing import decode_json
from server.writing_revision import revision_sections,apply_edits,edit_issue_ids,difference,text
from server.writing_expression import selected_issue_ids,key_sentence_windows

CASES=[('chloride','1ea03384007d4bb9b88d43e3368099f3','7f057f9e0e5a441aa7e9238337d93f3e',None),
       ('moisture','638495c5ba024a93a305ff69b4658811','f4daf4284d7448e0824b281f059bf938',[3,6,9,11,13])]

def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

async def run_case(label,pid,rid,indices):
 root=Path(ROOTS[pid]);folder=root/'.workbench/writing/runs'/rid
 state=json.loads((folder/'state.json').read_text());assert state['status']=='completed'
 out=folder/'expression-workflow-regression';out.mkdir(exist_ok=True)
 status={'status':'running','case':label,'prompt_version':prompts.VERSION,'stage':'diagnosis','request':REQUEST};write(out/'status.json',status)
 document=copy.deepcopy(state['candidate_document'])
 if indices is None:document['content']['content']=document['content']['content'][:5]
 else:
  kept=set(indices);nodes=document['content']['content']
  # Retain original native paths, supplying only selected paragraphs as editable.
  for i,node in enumerate(nodes):
   if i not in kept:node.clear();node.update({'type':'regressionOmitted'})
  document['content']['content'].append({'type':'heading','content':[{'type':'text','text':'References'}]})
 sections=revision_sections(document)
 if label=='moisture':
  # Retained placeholders preserve native coordinates; the abstract and body
  # paragraphs are provided as one test section without changing the manuscript.
  sections=[{'title':'Abstract and selected manuscript paragraphs','paragraphs':[
    {'id':'p'+str(i),'context':text(document['content']['content'][i]),
     'fragments':[{'path':[i,j],'text':n['text']} for j,n in enumerate(document['content']['content'][i].get('content',[])) if n.get('type')=='text' and n.get('text','').strip()]}
    for i in indices]}]
  # apply_edits recognizes a heading-free body followed by references.
 l3=state['l3']
 compact={'journal_profile':l3.get('journal_profile',{}),'native_expression_bank':{
  key:{'name':bank.get('name',bank.get('principle','')),'patterns':bank.get('patterns',[])[:1]}
  for key,bank in l3.get('native_expression_bank',{}).items()}}
 payload={'user_request':REQUEST,'phase':'draft','current_manuscript':sections,
  'sections':sections,'key_sentence_context':key_sentence_windows(sections),'rubric':scoring.RUBRIC,
  'L3_Genome':compact,'intent':{'task_kind':'polish','goal':REQUEST},
  'test_scope':'表达回归，原段落提供科学内容。保留内容和已确认条件，不重做研究架构、整篇文献调查或科学审查。'}
 write(out/'input.json',payload);write(out/'baseline.json',document)
 async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
  async def generate(stage,prompt,body):
   status.update(stage=stage,updated=time.time());write(out/'status.json',status)
   response=await client.post('http://172.19.0.3:47931/generate',headers=AUTH,json={
    'run_id':rid,'project_id':pid,'stage':'expression_regression_'+stage,'prompt':prompt,
    'payload':body,'model_selection':state['model_selection']})
   response.raise_for_status();value=response.json();result=decode_json(value['text'])
   write(out/(stage+'.json'),result);write(out/(stage+'-execution.json'),{k:v for k,v in value.items() if k!='text'})
   return result
  diagnosis=await generate('diagnosis',prompts.ALIGNMENT+'\n'+scoring.ALIGNMENT_NOTE+
   '\n本次只返回editorial_assessment与key_sentence_review，不另写L2科学架构。实际读取适用表达skill并检索表达语料，已有原段足够时完成当前诊断。',payload)
  assessment=scoring.normalize_score(diagnosis['editorial_assessment'],use_baseline=True)
  write(out/'before-assessment.json',assessment);selected=sorted(selected_issue_ids(assessment,REQUEST))
  proposed=await generate('edit',__import__('server.writing_revision',fromlist=['INCREMENTAL']).INCREMENTAL,
   {**payload,'L2_State':diagnosis,'editorial_assessment':assessment,'selected_issue_ids':selected,'round_instructions':scoring.EDIT_NOTE})
  eligible=[e for e in proposed.get('edits',[]) if edit_issue_ids(e) and set(edit_issue_ids(e))<=set(selected)]
  candidate,report=apply_edits(document,eligible)
  report['not_selected']=[e for e in proposed.get('edits',[]) if e not in eligible]
  write(out/'applied-edits.json',report);write(out/'candidate.json',candidate)
  (out/'changes.html').write_text(difference(document,candidate,'关键句工作流回归 · '+label),encoding='utf8')
  review=await generate('review',prompts.REVIEW+'\n'+scoring.REVIEW_NOTE,
   {**payload,'Manuscript_Draft':[{ 'id':'p'+str(i),'context':text(n)} for i,n in enumerate(candidate['content']['content']) if n.get('type')=='paragraph'],
    'L2_State':diagnosis,'before_assessment':assessment,'actual_applied_edits':report['accepted'],
    'round_instructions':'只复评actual_applied_edits，输入中的current_manuscript为修改前上下文；当前候选以Manuscript_Draft为准。保留原意和清楚的对照段落，不按语气强弱自行拔高分数。'})
  after=scoring.normalize_score(review['after_assessment']);write(out/'after-assessment.json',after)
 status.update(status='completed',stage='done',before_score=assessment['total_score'],after_score=after['total_score'],
  selected_issue_ids=selected,applied_fragments=len(report['accepted']),rejected=len(report['rejected']),
  author_approval='pending',scientific_manuscript_overwritten=False)
 write(out/'status.json',status)
 print(json.dumps(status,ensure_ascii=False),flush=True)

async def main():
 results=await asyncio.gather(*(run_case(*case) for case in CASES),return_exceptions=True)
 failed=[str(r) for r in results if isinstance(r,BaseException)]
 if failed:raise RuntimeError(json.dumps(failed,ensure_ascii=False))
asyncio.run(main())
'''
    result=subprocess.run(['ssh','-o','ProxyJump=research-cluster-xh5','papers-research','docker exec -i research-workbench python -'],
        input=code,capture_output=True,text=True,encoding='utf8')
    (OUT/'execution.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    print(result.stdout);print(result.stderr[-2000:]);assert result.returncode==0


if __name__=='__main__':main()
