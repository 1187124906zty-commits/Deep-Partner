"""Publish actual parallel evidence branches and explicit partial-coverage routing."""
import json
import os

from optimize_workflow import ROOT, api, login, node, code, note
from setup_web_reader import workflow as base_dsl
from setup_automation import mcp, edge, publish

MERGE='''import json
def branch(results):
    if not isinstance(results,list) or len(results)!=1:raise ValueError("分支没有返回唯一结果")
    value=results[0]
    for _ in range(4):
        if isinstance(value,dict) and "branch" in value:return value
        value=value.get("data") if isinstance(value,dict) else None
    raise ValueError("分支未返回结构化状态")
def main(knowledge: list, web: list, papers: list, query: str) -> dict:
    branches=[branch(knowledge),branch(web),branch(papers)]
    if {b["branch"] for b in branches}!={"knowledge","web","papers"}:raise ValueError("检索分支身份不完整")
    incomplete=any(b["status"] in {"failed","timed_out","not_configured","partial"} for b in branches)
    value={"query":query,"coverage":[{k:b.get(k) for k in ("branch","status","source","count","error","warnings")} for b in branches],"partial":incomplete}
    counts="；".join(b["branch"]+"="+b["status"]+"("+str(b.get("count",0))+")" for b in branches)
    return {"evidence":json.dumps(value,ensure_ascii=False),"complete":not incomplete,"counts":counts}
'''


def definition(provider):
    start=node('start','start','当前项目检索请求',60,260,variables=[
        {'variable':'run_id','label':'服务器绑定的检索编号','type':'text-input','required':True,'max_length':100,'options':[]},
        {'variable':'query','label':'当前检索问题','type':'text-input','required':True,'max_length':600,'options':[]}])
    nodes=[start]
    branches=[]
    for name,title,y in [('knowledge','项目知识库语义检索',60),('web','公开网页检索',260),('papers','学术题录检索',460)]:
        current=mcp(provider,name,'workbench_evidence_search',title,400,y,{
            'run_id':{'type':'mixed','value':'{{#start.run_id#}}'},'branch':{'type':'mixed','value':name},
            'workflow_run_id':{'type':'mixed','value':'{{#sys.workflow_run_id#}}'}})
        current['data']['desc']='独立执行并返回真实来源、片段和状态；超时或失败不会冒充空结果。'
        branches.append(current);nodes.append(current)
    merged=code('merge','合并来源与覆盖状态',760,260,MERGE,
        {**{name:[name,'json'] for name in ('knowledge','web','papers')},'query':['start','query']},
        {'evidence':'string','complete':'boolean','counts':'string'})
    routing=node('route','if-else','来源是否完整返回',1080,260,cases=[{'case_id':'complete','logical_operator':'and',
        'conditions':[{'id':'all-returned','varType':'boolean','variable_selector':['merge','complete'],
            'comparison_operator':'is','value':True}]}])
    for identifier,title,y,message in [('complete','来源已返回',90,'各来源状态已返回。{{ counts }}'),
            ('partial','标明缺口并保留证据',430,'部分来源未完成，请按缺口补查。{{ counts }}')]:
        current=node(identifier,'template-transform',title,1400,y,template=message,
            variables=[{'variable':'counts','value_selector':['merge','counts']}])
        nodes.append(current)
    nodes += [merged,routing,
        node('end','end','返回来源及定位',1720,90,outputs=[{'variable':'evidence','value_selector':['merge','evidence']}]),
        node('end_partial','end','返回部分证据与缺口',1720,430,outputs=[{'variable':'partial_evidence','value_selector':['merge','evidence']}]),
        note('scope','联合取证\n三路独立并行：项目 RAG、公开网页、学术题录。保留缺失与失败来源，再由 Tutor 定向补查。',60,'blue'),
        note('limits','证据范围\n题录与搜索摘要不等于论文全文。片段保留来源和定位，研究结论由原会话根据原始证据判断。',690,'yellow')]
    for current in nodes:
        if current['type']=='custom-note':current['position']['y']=-170
    lookup={n['id']:n for n in nodes}
    edges=[edge(start,b) for b in branches]+[edge(b,merged) for b in branches]+[edge(merged,routing),
        edge(routing,lookup['complete'],'complete'),edge(routing,lookup['partial'],'false'),
        edge(lookup['complete'],lookup['end']),edge(lookup['partial'],lookup['end_partial'])]
    dsl=base_dsl();dsl['app'].update(name='DeepTutor 扩展 · 多来源联合检索',
        description='按当前账户与项目并行检索 RAG、网页和论文；逐路报告失败、超时、空结果和来源定位，返回 Tutor 定向补查。')
    dsl['workflow']['graph']={'nodes':nodes,'edges':edges,'viewport':{'x':15,'y':100,'zoom':0.62}}
    return dsl


def main():
    login();provider=json.loads((ROOT/'mcp-registration.json').read_text())
    api.call('GET','/workspaces/current/tool-provider/mcp/update/'+provider['id'])
    dsl=definition(provider)
    app=publish(dsl,ROOT/'evidence-app.json')
    key=ROOT/'private/evidence-key'
    if not key.exists() or key.read_text().strip()=='unconfigured':
        result=api.call('POST','/apps/'+app['app_id']+'/api-keys',{})
        key.write_text((result.get('token') or result['api_key'])+'\n');key.chmod(0o600)
    owner=(ROOT/'private/workflow-key').stat()
    os.chown(key,owner.st_uid,owner.st_gid)
    (ROOT/'reports/evidence-workflow.json').write_text(json.dumps(dsl,ensure_ascii=False,indent=2))
    print(json.dumps(app,ensure_ascii=False))


if __name__=='__main__':main()
