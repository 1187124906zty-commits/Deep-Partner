"""Publish the same Dify app with one authoritative delivery implementation."""
from copy import deepcopy
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import setup_app as api
from workflow_guards import HTTP_GUARD
ROOT=Path('/srv/dify-research')
api.BASE='https://tutor.example.invalid/dify/console/api'

NAME='DeepTutor 扩展 · 研究成果交付'
DESCRIPTION=('承接 DeepTutor 与 Code Agent 已完成的程序、数据、图表和稿件。'
    '按当前项目规范保存，核对版本、原生处理记录并返回成果位置。'
    '研究对话、知识检索与代码执行由原会话按需调用，不在此流程重复推理。')

FINALIZE='''import json
def main(results: list, run_id: str) -> dict:
    if not isinstance(results,list) or len(results)!=1 or not isinstance(results[0],dict):
        raise ValueError("成果核验工具没有返回唯一的结构化结果")
    result=results[0]
    if result.get("isError") or result.get("error"):
        raise ValueError("成果核验未完成，请查询同一交付任务")
    value=result.get("data")
    if not isinstance(value,dict) or value.get("run_id")!=run_id or value.get("status")!="saved":
        raise ValueError("保存回执与当前交付任务不一致")
    if value.get("processing_history_verified") is not True or not value.get("history_event_id"):
        raise ValueError("成果尚未取得原生处理记录的核验结果")
    artifact=value.get("artifact",{}).get("path")
    if not artifact:raise ValueError("保存回执缺少成果路径")
    return {"receipt":json.dumps(value,ensure_ascii=False),"artifact":artifact,
        "project_id":value["project_id"],"history_event_id":str(value["history_event_id"]),
        "summary":json.dumps(value.get("delivery_summary",{}),ensure_ascii=False)}
'''


def login():
    account=json.loads((ROOT/'private/admin-login.json').read_text())
    value=api.call('POST','/login',{'email':account['email'],
        'password':base64.b64encode(account['password'].encode()).decode(),'remember_me':True})
    assert value.get('result')=='success','Dify console authentication failed'


def node(identifier,kind,title,x,y,**fields):
    return {'id':identifier,'type':'custom','data':{'type':kind,'title':title,'desc':'','selected':False,**fields},
        'position':{'x':x,'y':y},'positionAbsolute':{'x':x,'y':y},'sourcePosition':'right','targetPosition':'left','width':260,'height':102}


def tool(provider,identifier,tool_name,title,x,y,parameters):
    return node(identifier,'tool',title,x,y,provider_id=provider['id'],provider_type='mcp',
        provider_name=provider['server_identifier'],tool_name=tool_name,tool_label=title,tool_configurations={},
        tool_parameters={'run_id':{'type':'mixed','value':'{{#start.run_id#}}'},**parameters},
        tool_node_version='2',is_team_authorization=True)


def code(identifier,title,x,y,source,variables,outputs):
    return node(identifier,'code',title,x,y,code_language='python3',code=source,
        variables=[{'variable':key,'value_selector':selector} for key,selector in variables.items()],
        outputs={key:{'type':kind,'children':None} for key,kind in outputs.items()})


def note(identifier,text,x,theme):
    paragraphs=[{'children':[{'detail':0,'format':1 if i==0 else 0,'mode':'normal','style':'font-size: 16px;','text':line,'type':'text','version':1}],
        'direction':None,'format':'','indent':0,'type':'paragraph','version':1,'textFormat':0,'textStyle':''} for i,line in enumerate(text.splitlines())]
    return {'id':identifier,'type':'custom-note','position':{'x':x,'y':-20},'width':540,'height':140,
        'data':{'type':'','title':'职责说明','desc':'','selected':False,'width':540,'height':140,
            'text':json.dumps({'root':{'children':paragraphs,'direction':None,'format':'','indent':0,'type':'root','version':1}},ensure_ascii=False),
            'theme':theme,'author':'','showAuthor':False}}


def optimize(draft, provider):
    graph=deepcopy(draft['graph'])
    original={node['id']:node for node in graph['nodes']}
    start,prepare,commit,end=[original[name] for name in ('start','prepare','commit','end')]
    prepare['data']['headers']='X-Run-Ticket:{{#start.ticket#}}\nX-Dify-Workflow-Run-Id:{{#sys.workflow_run_id#}}'
    verify=tool(provider,'delivery_verify','workbench_delivery_verify','成果保存与记录核验',1070,180,{})
    final=code('delivery_summary','交付回执生成',1400,180,FINALIZE,
        {'results':['delivery_verify','json'],'run_id':['start','run_id']},
        {'receipt':'string','artifact':'string','project_id':'string','history_event_id':'string','summary':'string'})
    prepared=code('prepare_check','确认项目校验通过',0,180,HTTP_GUARD,
        {'status_code':['prepare','status_code'],'body':['prepare','body']},{'receipt':'string'})
    committed=code('commit_check','确认成果保存回执',0,180,HTTP_GUARD,
        {'status_code':['commit','status_code'],'body':['commit','body']},{'receipt':'string'})
    nodes=[start,prepare,prepared,commit,committed,verify,final,end]
    copy={
        'start':('成果交付请求','由 Tutor 或 Code 自动传入交付编号与会话授权；无需用户手动填写。'),
        'prepare':('项目与版本校验','绑定当前账户和项目，读取规范与任务技能；版本不一致时停止，保留现有成果。'),
        'prepare_check':('确认项目校验通过','非成功HTTP响应在这里停止，保留原始错误；不继续调用保存。'),
        'commit':('成果版本化保存','保存指定成果，保留可恢复版本，回读内容并登记原生处理回执。'),
        'commit_check':('确认成果保存回执','保存被拒绝时原样报告原因；不会将HTTP节点运行结束当成保存成功。'),
        'delivery_verify':('成果保存与记录核验','通过工作台 MCP 核对当前文件或稿件版本及处理记录；此步骤不代表科学结论验证通过。'),
        'delivery_summary':('交付回执生成','将已经核验的成果路径、项目和处理记录整理成结构化回执；不生成新的研究结论。'),
        'end':('交付结果','返回成果位置和实际状态，供 Tutor 继续解释或按需读取。'),
    }
    for index,node in enumerate(nodes):
        x=80+300*index;y=180
        node.update(position={'x':x,'y':y},positionAbsolute={'x':x,'y':y},width=260)
        node['data'].update(title=copy[node['id']][0],desc=copy[node['id']][1],selected=False)
    end['data']['outputs']=[{'variable':key,'value_selector':['delivery_summary',key]}
        for key in ('receipt','artifact','project_id','history_event_id','summary')]
    notes=[
        note('role_tutor','DeepTutor｜研究对话与判断\n理解研究问题与约束，按需检索或委派 Code，结合交接证据解释结果。',80,'blue'),
        note('role_code','Code Agent｜实现与技术验证\n编程、数据处理、计算和测试；整理来源、结果、失败原因及适用范围。',650,'green'),
        note('role_workbench','研究工作台｜共享成果与证据\n保存程序、数据、稿件和版本，供 Tutor 定向读取。下方流程仅负责成果交付。',1220,'yellow'),
    ]
    graph['nodes']=nodes+notes
    graph['edges']=[{'id':a['id']+'-source-'+b['id']+'-target','type':'custom','source':a['id'],
        'sourceHandle':'source','target':b['id'],'targetHandle':'target','data':{
            'sourceType':a['data']['type'],'targetType':b['data']['type'],'isInIteration':False}}
        for a,b in zip(nodes,nodes[1:])]
    graph['viewport']={'x':15,'y':110,'zoom':0.85}
    return graph


def main():
    login()
    app_id=json.loads((ROOT/'app.json').read_text())['app_id']
    provider=json.loads((ROOT/'mcp-registration.json').read_text())
    # Refresh published tool schemas after the adapter has been updated.
    api.call('GET','/workspaces/current/tool-provider/mcp/update/'+provider['id'])
    draft=api.call('GET',f'/apps/{app_id}/workflows/draft')
    evidence=ROOT/'reports';evidence.mkdir(exist_ok=True)
    before=evidence/'workflow-before-optimization.json'
    if not before.exists():before.write_text(json.dumps(draft,ensure_ascii=False,indent=2))
    graph=optimize(draft,provider)
    api.call('POST',f'/apps/{app_id}/workflows/draft',{'graph':graph,'features':draft['features'],
        'hash':draft['hash'],'conversation_variables':draft.get('conversation_variables',[])})
    current=api.call('GET',f'/apps/{app_id}/workflows/draft')
    assert [n['id'] for n in current['graph']['nodes']]==[n['id'] for n in graph['nodes']]
    app=api.call('GET','/apps/'+app_id)
    api.call('PUT','/apps/'+app_id,{'name':NAME,'description':DESCRIPTION,
        **{key:app[key] for key in ('icon_type','icon','icon_background','use_icon_as_answer_icon','max_active_requests') if key in app}})
    published=api.call('POST',f'/apps/{app_id}/workflows/publish',{
        'marked_name':'交付结果逐阶段核验','marked_comment':'项目校验与保存响应必须成功后才进入下一阶段；保留原始错误和同一交付身份。'})
    (evidence/'workflow-after-optimization.json').write_text(json.dumps(current,ensure_ascii=False,indent=2))
    result={'app_id':app_id,'name':NAME,'node_count':sum(n['type']=='custom' for n in graph['nodes']),
        'notes':sum(n['type']=='custom-note' for n in graph['nodes']),
        'nodes':[n['data']['title'] for n in graph['nodes'] if n['type']=='custom'],'published':bool(published),
        'workflow_url':'https://tutor.example.invalid/dify/app/'+app_id+'/workflow'}
    (evidence/'workflow-optimization.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
