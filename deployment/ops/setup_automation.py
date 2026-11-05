"""Publish native Dify webhook and schedule flows without changing Tutor's loop."""
import json
import os
from pathlib import Path

from optimize_workflow import ROOT, api, login, node, code, note
from setup_web_reader import workflow as reader_dsl

UNWRAP = '''import json
def main(results: list) -> dict:
    if not isinstance(results,list) or len(results)!=1:raise ValueError("工具没有返回唯一结果")
    value=results[0]
    if value.get("isError"):raise ValueError("工具执行失败，请检查节点原始输出")
    for _ in range(4):
        if isinstance(value,dict) and ("outcome" in value or "needs_attention" in value):break
        value=value.get("data") if isinstance(value,dict) else None
    if not isinstance(value,dict):raise ValueError("工具缺少结构化业务结果")
    flag=value.get("ready") if "outcome" in value else not value.get("needs_attention",True)
    return {"ready":bool(flag),"detail":json.dumps(value,ensure_ascii=False)}
'''


def mcp(provider, identifier, name, title, x, y, parameters=None):
    return node(identifier,'tool',title,x,y,provider_id=provider['id'],provider_type='mcp',
        provider_name=provider['server_identifier'],tool_name=name,tool_label=title,tool_node_version='2',
        is_team_authorization=True,tool_configurations={},tool_parameters=parameters or {})


def edge(a,b,handle='source'):
    return {'id':a['id']+'-'+handle+'-'+b['id'],'type':'custom','source':a['id'],
        'sourceHandle':handle,'target':b['id'],'targetHandle':'target',
        'data':{'sourceType':a['data']['type'],'targetType':b['data']['type'],'isInIteration':False}}


def branch():
    return node('route','if-else','交付状态分流',1020,220,cases=[{'case_id':'ready','logical_operator':'and',
        'conditions':[{'id':'confirmed','varType':'boolean','variable_selector':['inspect_result','ready'],
            'comparison_operator':'is','value':True}]}])


def definition(provider, scheduled=False):
    if scheduled:
        start=node('timer','trigger-schedule','每五分钟核对',60,220,mode='cron',
            cron_expression='*/5 * * * *',timezone='Asia/Shanghai')
        start['data']['desc']='核对已存在的交付与服务状态；不创建新研究任务，不重复写入成果。'
        inspect=mcp(provider,'inspect','workbench_delivery_reconcile','协调已有任务与服务状态',380,220)
    else:
        start=node('event','trigger-webhook','成果交付事件',60,220,method='POST',content_type='application/json',async_mode=True,
            headers=[],params=[],body=[{'name':name,'type':'string','required':True} for name in ('event_id','event_token')],
            status_code=202,response_body='{"accepted":true}',timeout=10,
            variables=[{'variable':name,'label':'body','value_type':'string','value_selector':[],'required':True}
                for name in ('event_id','event_token')]+[{'variable':'_webhook_raw','label':'raw','value_type':'object','value_selector':[],'required':True}])
        start['data']['desc']='由交付服务在成功、失败或中断后发送事件；收到请求仅表示受理，后续回执才表示流程完成。'
        inspect=mcp(provider,'inspect','workbench_delivery_event','读取事件真实状态',380,220,{
            key:{'type':'mixed','value':'{{#event.'+source+'#}}'} for key,source in [('event_id','event_id'),('event_token','event_token')]})
        inspect['data']['tool_parameters']['action']={'type':'mixed','value':'inspect'}
    parsed=code('inspect_result','提取已核验状态',700,220,UNWRAP,{'results':['inspect','json']},{'ready':'boolean','detail':'string'})
    routing=branch()
    if scheduled:
        routing['data']['title']='是否存在需处理事项'
        success=node('success','template-transform','状态正常',1340,80,template='定时检查已完成。{{ detail }}',
            variables=[{'variable':'detail','value_selector':['inspect_result','detail']}])
        attention=node('attention','template-transform','保留异常与处理入口',1340,370,
            template='检查发现需处理事项。请查看交付 activity 与对应运行日志。{{ detail }}',
            variables=[{'variable':'detail','value_selector':['inspect_result','detail']}])
    else:
        success=mcp(provider,'success','workbench_delivery_event','登记已核验交付',1340,80)
        attention=mcp(provider,'attention','workbench_delivery_event','登记异常与恢复动作',1340,370)
        for current,route in ((success,'success'),(attention,'attention')):
            current['data']['tool_parameters']={
                'event_id':{'type':'mixed','value':'{{#event.event_id#}}'},
                'event_token':{'type':'mixed','value':'{{#event.event_token#}}'},
                'action':{'type':'mixed','value':'settle'},'route':{'type':'mixed','value':route}}
    end_ok=node('end_ok','end','自动处理完成',1660,80,outputs=[{'variable':'detail','value_selector':['inspect_result','detail']}])
    end_attention=node('end_attention','end','问题已记录',1660,370,outputs=[{'variable':'attention_detail','value_selector':['inspect_result','detail']}])
    nodes=[start,inspect,parsed,routing,success,attention,end_ok,end_attention]
    nodes.append(note('scope','自动处理范围\n交付事件与状态协调；不重复执行模型、计算或文件写入。运行日志保留触发来源、分支和原始工具结果。',50,'blue'))
    nodes.append(note('author','作者判断\n研究方案、稿件主张和结论仍由原会话与工作台中的作者确认；技术保存成功不代替科学判断。',690,'yellow'))
    for current in nodes:
        if current['type']=='custom-note':current['position']['y']=-170
    edges=[edge(start,inspect),edge(inspect,parsed),edge(parsed,routing),edge(routing,success,'ready'),edge(routing,attention,'false'),edge(success,end_ok),edge(attention,end_attention)]
    dsl=reader_dsl()
    dsl['app'].update(name='DeepTutor 扩展 · '+('交付协调与健康检查' if scheduled else '交付事件自动处理'),
        description='使用 Dify 原生'+('定时触发器核对既有任务与服务状态，异常可追踪。' if scheduled else 'Webhook、条件分支与运行日志，处理 Tutor/Code 的成果交付事件。'))
    dsl['workflow']['graph']={'nodes':nodes,'edges':edges,'viewport':{'x':25,'y':90,'zoom':0.65}}
    return dsl


def publish(dsl,path):
    if path.exists():
        metadata=json.loads(path.read_text());app_id=metadata['app_id']
        draft=api.call('GET',f'/apps/{app_id}/workflows/draft')
        api.call('POST',f'/apps/{app_id}/workflows/draft',{'graph':dsl['workflow']['graph'],'features':draft['features'],
            'hash':draft['hash'],'conversation_variables':[]})
    else:
        result=api.call('POST','/apps/imports',{'mode':'yaml-content','yaml_content':json.dumps(dsl,ensure_ascii=False)})
        if result.get('status')=='pending':result=api.call('POST','/apps/imports/'+result['id']+'/confirm',{})
        app_id=result['app_id']
        metadata={'app_id':app_id,'name':dsl['app']['name'],'workflow_url':f'https://tutor.example.invalid/dify/app/{app_id}/workflow'}
        path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    api.call('POST',f'/apps/{app_id}/workflows/publish',{'marked_name':'原生触发、条件分支与异常可追踪','marked_comment':dsl['app']['description']})
    triggers=api.call('GET',f'/apps/{app_id}/triggers')['data']
    for trigger in triggers:
        if trigger['status']!='enabled':
            api.call('POST',f'/apps/{app_id}/trigger-enable',{'trigger_id':trigger['id'],'enable_trigger':True})
    metadata['triggers']=api.call('GET',f'/apps/{app_id}/triggers')['data']
    (ROOT/'reports'/('schedule' if 'timer' in [n['id'] for n in dsl['workflow']['graph']['nodes']] else 'events') / 'workflow.json').parent.mkdir(parents=True,exist_ok=True)
    return metadata


def main():
    login();provider=json.loads((ROOT/'mcp-registration.json').read_text())
    api.call('GET','/workspaces/current/tool-provider/mcp/update/'+provider['id'])
    event_dsl=definition(provider)
    event=publish(event_dsl,ROOT/'event-app.json')
    webhook=api.call('GET',f'/apps/{event["app_id"]}/workflows/triggers/webhook?node_id=event')
    event_dsl['workflow']['graph']['nodes'][0]['data'].update(webhook_url=webhook['webhook_url'],webhook_debug_url=webhook['webhook_debug_url'])
    event=publish(event_dsl,ROOT/'event-app.json')
    config=ROOT/'private/automation-config.json'
    config.write_text(json.dumps({'webhook_url':webhook['webhook_url'],'installed_at':__import__('time').time()}))
    config.chmod(0o600)
    owner=(ROOT/'private/workflow-key').stat()
    os.chown(config,owner.st_uid,owner.st_gid)
    scheduled=publish(definition(provider,True),ROOT/'schedule-app.json')
    result={'events':event,'schedule':scheduled}
    (ROOT/'reports/automation-apps.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    for name,ds in [('events',event_dsl),('schedule',definition(provider,True))]:
        (ROOT/'reports'/name/'workflow.json').write_text(json.dumps(ds,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
