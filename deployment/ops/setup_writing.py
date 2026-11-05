"""Publish Partner's writing stage router in the existing Dify installation."""
from pathlib import Path
import json
import os
import shutil
from optimize_workflow import ROOT,api,login,node,note,code
from workflow_guards import STAGE_GUARD
from setup_web_reader import workflow
from setup_automation import edge,publish

STAGES=[('intent','理解用户意图：初稿 / 投稿 / 返修'),('exemplar','Agent 0：标杆解构与期刊基因'),
        ('alignment','Agent 1：主题对标与沙漏架构'),('narrow','Agent 2：方法与展示性结果'),
        ('wide','Agent 3：引言、摘要、标题与结论'),('review','Agent 4：期刊语感与审稿红蓝对抗'),('deliver','保存当前写作成果')]


def definition():
    start=node('start','start','Partner 写作任务事件',40,350,variables=[
        {'variable':k,'label':label,'type':'text-input','required':True,'max_length':300,'options':[]}
        for k,label in [('run_id','当前写作任务编号'),('ticket','项目与任务绑定凭证'),('stage','当前阶段')]])
    route=node('stage_route','if-else','按当前执行阶段调度',370,350,cases=[{
        'case_id':name,'logical_operator':'and','conditions':[{'id':name,'varType':'string',
            'variable_selector':['start','stage'],'comparison_operator':'is','value':name}]} for name,_ in STAGES])
    nodes=[start,route];edges=[edge(start,route)]
    for i,(name,title) in enumerate(STAGES):
        task=node(name,'http-request',title,720,i*160,method='post',
            url='https://tutor.example.invalid/research/api/writing/internal/runs/{{#start.run_id#}}/dispatch',
            authorization={'type':'no-auth','config':None},headers='Content-Type:application/json\nX-Writing-Ticket:{{#start.ticket#}}\nX-Dify-Workflow-Run-Id:{{#sys.workflow_run_id#}}',
            params='',body={'type':'json','data':[{'id':'body','key':'','type':'text','value':json.dumps({'stage':name})}]},
            timeout={'connect':20,'read':60,'write':20},ssl_verify=True)
        task['data']['desc']='提交当前阶段的异步任务后立即返回。模型生成无本地固定超时；完成事件接续同一写作任务。'
        accepted=code('accepted_'+name,'核对阶段受理回执',1040,i*160,STAGE_GUARD,
            {'status_code':[name,'status_code'],'body':[name,'body'],'run_id':['start','run_id'],'stage':['start','stage']},{'receipt':'string'})
        end=node('end_'+name,'end','阶段任务已接入',1360,i*160,outputs=[{'variable':'receipt_'+name,'value_selector':[accepted['id'],'receipt']}])
        nodes.extend([task,accepted,end]);edges.extend([edge(route,task,name),edge(task,accepted),edge(accepted,end)])
    invalid=code('invalid','拒绝未知阶段',720,1180,'def main(stage: str) -> dict:\n    raise ValueError("未知写作阶段：" + stage)\n',{'stage':['start','stage']},{'error':'string'})
    invalid_end=node('invalid_end','end','阶段未被接受',1040,1180,outputs=[{'variable':'error','value_selector':['invalid','error']}])
    nodes.extend([invalid,invalid_end]);edges.extend([edge(route,invalid,'false'),edge(invalid,invalid_end)])
    nodes.append(note('roles','PDF 原方案\n外部标杆解构与期刊基因；内部资产主题对齐、窄口证据、宽口写作、期刊语感与审稿对抗。',30,'blue'))
    nodes[-1]['position']['y']=-190
    dsl=workflow();dsl['app'].update(name='DeepPartner · 内置写作工作流',description='初稿、投稿和返修：Agent理解任务意图，按1111.pdf五角色工作流组织写作；复用Tutor模型和项目资料，异步执行并保存L1/L2/L3状态。',icon='✍️')
    dsl['workflow']['graph']={'nodes':nodes,'edges':edges,'viewport':{'x':10,'y':90,'zoom':.6}}
    return dsl


def main():
    login();app=publish(definition(),ROOT/'writing-app.json')
    key=ROOT/'private/writing-key'
    if not key.is_file():
        result=api.call('POST','/apps/'+app['app_id']+'/api-keys',{})
        key.write_text((result.get('token') or result['api_key'])+'\n');key.chmod(0o600)
    target=Path('/srv/research-workbench/tools/writing');target.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(key,target/'dify-key');os.chown(target/'dify-key',1000,1000);(target/'dify-key').chmod(0o600)
    (target/'app.json').write_text(json.dumps(app,ensure_ascii=False,indent=2))
    (ROOT/'reports/writing-workflow.dsl.json').write_text(json.dumps(definition(),ensure_ascii=False,indent=2))
    print(json.dumps(app,ensure_ascii=False))


if __name__=='__main__':main()
