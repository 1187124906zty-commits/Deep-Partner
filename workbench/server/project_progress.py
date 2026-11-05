"""One project-facing view over existing jobs; executors retain state ownership."""
from fastapi import Depends
from .storage import now
from . import standards

GROUPS={'running':'active','queued':'active','waiting_service':'active',
        'waiting_input':'attention','paused':'attention','failed':'attention','interrupted':'attention',
        'completed':'done','cancelled':'closed'}
ROUTE_NAMES={'search':'查找文献','download':'获取与读取原文','survey':'文献研究',
             'analyze':'比较已有证据','code':'编程与验证','slides':'制作研究汇报','simulate':'数值仿真'}


def snapshot(store,owner,pid):
    from .research_flow import KINDS
    from .workflow_control import LABELS,controllable_steps
    from .writing_prompts import STAGES as writing_stages
    project=store.get(owner,pid);jobs=store.jobs(owner,pid)
    counts={group:0 for group in ('active','attention','done','closed')}
    for job in jobs:
        group=GROUPS.get(job['status'],'attention')
        quality=(job.get('result') or {}).get('quality') or {}
        if job['status']=='completed' and quality.get('can_proceed') is False:group='attention'
        job['group']=group;counts[group]+=1
    return {'project':{'id':pid,'name':project['name']},'observed_at':now(),'jobs':jobs,
      'counts':counts,'limit':200,
      'routes':[{'id':kind,'label':ROUTE_NAMES[kind],'steps':[{'id':s,'label':LABELS[s],
         'can_pause':s in controllable_steps(kind,value['steps'])} for s in value['steps']]} for kind,value in KINDS.items()]+
        [{'id':'writing','label':'写作（按任务选择阶段）','steps':[{'id':s,'label':label,'can_pause':False} for s,label in writing_stages]}],
      'rules':{'version':standards.VERSION,'content':standards.contract(),
         'scope':'当前请求与明确更正确定任务；历史记忆和模型计划提供背景。',
         'review':'最终或关键阶段产物按来源、用途和判据独立评审；过程检查围绕当前主线。'}}


def install(app,store,actor):
    @app.get('/research/api/projects/{pid}/workflow-overview')
    def overview(pid:str,user=Depends(actor)):
        return snapshot(store,user['id'],pid)
