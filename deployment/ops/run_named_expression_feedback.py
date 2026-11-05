"""Exercise explicit author sentence feedback without a replacement table."""
from pathlib import Path
import os,json,subprocess,sys
import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/关键句工作流回归'/('abstract-feedback' if '--abstract' in sys.argv else 'named-feedback')


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5');OUT.mkdir(exist_ok=True)
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=90,trust_env=False) as client:
        login(client);auth={'Origin':ORIGIN,'Cookie':'; '.join(k+'='+v for k,v in client.cookies.items())}
    code='AUTH='+repr(auth)+'\nABSTRACT='+repr('--abstract' in sys.argv)+r'''
import sys,asyncio,json,copy
from pathlib import Path
sys.path.insert(0,'/opt/workbench-tools/writing-agent-candidate')
import httpx
from server.writing_revision import INCREMENTAL,revision_sections,apply_edits,difference,edit_issue_ids
from server.writing_expression import selected_issue_ids,key_sentence_windows,expression_feedback_coverage
from server.writing import decode_json
from server.writing_prompts import VERSION
from server.writing_scores import EDIT_NOTE

base=Path('/workspace/outputs/.deeptutor/chat/2e1f7a59cda65ffb9355b8afa9e999f9/workspaces')
root=base/('ws_06a666b5802645998b8ad9513dbc10ab' if ABSTRACT else 'ws_0e6fc7aba58a4b258e25e1195702fde3')
rid='f4daf4284d7448e0824b281f059bf938' if ABSTRACT else '7f057f9e0e5a441aa7e9238337d93f3e'
folder=root/'.workbench/writing/runs'/rid;state=json.loads((folder/'state.json').read_text())
out=folder/('abstract-expression-feedback' if ABSTRACT else 'named-expression-feedback');out.mkdir(exist_ok=True)
document=copy.deepcopy(state['candidate_document'])
document['content']['content']=[document['content']['content'][3]] if ABSTRACT else document['content']['content'][:5]
quotes=['有限观测下的损伤反馈识别，要求同时处理未测物理场与待估物理参数。','力学损伤进一步改变了孔隙结构与离子迁移之间的关系。','反应传输模型为描述上述相互作用提供了化学与传输基础。']
request='不是难点和作用、贡献更有力度，而是这些关键位置太弱、绕、读起来别扭。请在相近意思基础上改顺、改直接：'+'\n'.join(quotes)+'\n这是作者已点名的同义表达修改，不改变研究主线或提高科学承诺。'
if ABSTRACT:
 quotes=['该框架为有限观测条件下的混凝土内部湿度评估提供了方法支持，其在湿度—力学耦合问题中的适用性仍需进一步验证。']
 request='作者指出摘要这句把意义收窄了：'+quotes[0]+'\n请在已建立的湿度场重建与扩散特性识别能力上，把意义说清。不要只把提醒挪到倒数第二句；未验证的耦合应用不写成已完成成果。只修这处摘要收尾，保留其余句子、结果和比较条件。'
targets=[{'quote':q,'location':'摘要末句' if ABSTRACT else '原五段引言'} for q in quotes]
assessment={'author_expression_targets':targets,'issues':[{'id':'AEXP'+str(i+1),'classification':'potential','before':q,'selected_for_this_round':True,'selection_basis':'author_request','author_request_quote':q,'reason':'作者点名的同义表达改进'} for i,q in enumerate(quotes)]}
sections=revision_sections(document);selected=sorted(selected_issue_ids(assessment,request))
payload={'user_request':request,'manuscript_title':document['title'],'sections':sections,'selected_issue_ids':selected,
 'editorial_assessment':assessment,'key_sentence_context':key_sentence_windows(sections),'round_instructions':EDIT_NOTE,
 'L3_Expression_Learning':json.loads((folder/'expression-workflow-regression/input.json').read_text())['L3_Genome']}
def write(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
write('input.json',payload);write('baseline.json',document);write('status.json',{'status':'running','workflow_version':VERSION})
async def main():
 async with httpx.AsyncClient(timeout=None,trust_env=False) as c:
  r=await c.post('http://172.19.0.3:47931/generate',headers=AUTH,json={'run_id':rid,'project_id':state['project_id'],
   'stage':'abstract_expression_feedback_v6' if ABSTRACT else 'named_expression_feedback_v5','prompt':INCREMENTAL+'\n另返回key_sentence_checks说明各点名句的原有科学意思、改法及意思是否保持。只处理本轮点名句，不额外修改段内其他内容。',
   'payload':payload,'model_selection':state['model_selection']})
  r.raise_for_status();response=r.json();value=decode_json(response['text']);write('model-output.json',value)
 edits=[e for e in value.get('edits',[]) if edit_issue_ids(e) and set(edit_issue_ids(e))<=set(selected)]
 candidate,report=apply_edits(document,edits);coverage=expression_feedback_coverage(document,candidate,targets,request)
 write('candidate.json',candidate);write('applied-edits.json',report);write('coverage.json',coverage)
 (out/'changes.html').write_text(difference(document,candidate,'作者点名关键句 · 通用工作流处理'),encoding='utf8')
 result={'status':'completed','workflow_version':VERSION,'applied_fragments':len(report['accepted']),
  'rejected_edits':len(report['rejected']),'coverage':coverage,'author_approval':'pending','scientific_manuscript_overwritten':False}
 write('status.json',result)
 files={p.name:p.read_text() for p in out.iterdir() if p.is_file()}
 import base64,gzip
 print(base64.b64encode(gzip.compress(json.dumps(files,ensure_ascii=False).encode())).decode())
asyncio.run(main())
'''
    result=subprocess.run(['ssh','-o','ProxyJump=research-cluster-xh5','papers-research','docker exec -i research-workbench python -'],input=code,capture_output=True,text=True,encoding='utf8')
    if result.returncode:raise RuntimeError(result.stderr[-2000:])
    import base64,gzip
    files=json.loads(gzip.decompress(base64.b64decode(result.stdout)))
    for name,value in files.items():(OUT/name).write_text(value,encoding='utf8')
    print((OUT/'status.json').read_text(encoding='utf8'))


if __name__=='__main__':main()
