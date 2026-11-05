"""Durable author checkpoints and factual progress for the existing flow runner."""
from contextlib import contextmanager
import json
from fastapi import HTTPException
from .storage import atomic_json,now

LABELS={'search':'检索文献','download':'取得全文','parse':'解析原文','read':'读取相关页段',
        'analyze':'综合证据','dispatch':'执行专用任务','prepare':'准备工况','submit':'提交计算',
        'monitor':'等待计算结果','validate':'核对结果','archive':'保存项目成果'}
PAUSE_NOTE='暂停后续步骤；已经提交的外部任务继续运行，恢复时核对同一任务。'


class WorkflowPaused(Exception):
    def __init__(self,step=''):
        super().__init__('已按作者要求暂停后续步骤')
        self.step=step


def controllable_steps(kind,steps):
    # Slurm owns the submitted job's internal phases; local checkpoints cannot
    # stop it between solving and validation.
    return [s for s in steps if kind!='simulate' or s in ('prepare','archive')]


def folder(store,owner,pid,rid):
    return store.path(owner,pid)/'.workbench/research-flow/runs'/rid


def read(path,default):
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else default


def current(root):
    return read(root/'control.json',{'revision':0,'pause_requested':False,'pause_before':[],
                                   'passed_checkpoints':[],'events':[]})


@contextmanager
def editing(root):
    from .research_tool_flow import claim_run,release_run
    handle=claim_run(root/'.control.lock')
    if handle is None:raise HTTPException(409,'任务控制正在更新，请刷新后重试')
    try:yield
    finally:release_run(handle)


def save(root,value,action):
    value['revision']=value.get('revision',0)+1;value['updated']=now()
    value.setdefault('events',[]).append({'action':action,'time':value['updated'],'before':value.get('paused_before','')})
    value['events']=value['events'][-40:];atomic_json(root/'control.json',value)


def checkpoint(root,step=''):
    value=current(root)
    before=step and step in value.get('pause_before',[]) and step not in value.get('passed_checkpoints',[])
    if value.get('pause_requested') or before:
        raise WorkflowPaused(step if before else '')


def mark_paused(store,owner,pid,rid,step=''):
    root=folder(store,owner,pid,rid)
    with editing(root):
        value=current(root);value['pause_requested']=True
        if step:value['paused_before']=step
        save(root,value,'paused')
    state=read(root/'state.json',{});state['status']='paused';atomic_json(root/'state.json',state)
    store.set_job(rid,status='paused',stage='等待作者继续'+('：'+LABELS.get(step,step) if step else ''),result=state,error='')


def resume(root):
    with editing(root):
        value=current(root);before=value.pop('paused_before','')
        if before and before not in value.get('passed_checkpoints',[]):value.setdefault('passed_checkpoints',[]).append(before)
        value['pause_requested']=False;save(root,value,'resumed')
    # A prior transient failure may have a future cooldown or resolved marker.
    # Explicit author resume requests fresh scheduling with the same run identity.
    state=read(root/'state.json',{})
    if state.get('recovery'):
        state['recovery'].update(status='waiting',retry_after=None)
        atomic_json(root/'state.json',state)


def update(store,owner,pid,row,payload,steps):
    from .research_tool_flow import claim_run,release_run
    if row['status'] in ('completed','failed','cancelled'):raise HTTPException(409,'当前任务已结束；请查看结果或恢复失败任务')
    root=folder(store,owner,pid,row['id']);action=payload.get('action')
    if action not in ('pause','checkpoints'):raise HTTPException(400,'操作应为 pause 或 checkpoints')
    if action=='pause' and row['status']=='waiting_input':raise HTTPException(409,'当前任务已等待作者回复，不需要额外暂停')
    with editing(root):
        value=current(root)
        if type(payload.get('expected_revision')) is not int or payload['expected_revision']!=value['revision']:
            raise HTTPException(409,'任务控制已更新，请刷新后重试')
        if action=='checkpoints':
            chosen=payload.get('pause_before')
            if not isinstance(chosen,list) or any(not isinstance(s,str) or s not in steps for s in chosen):
                raise HTTPException(400,'停留点必须属于本任务的实际阶段')
            value['pause_before']=list(dict.fromkeys(chosen))
            value['passed_checkpoints']=[s for s in value.get('passed_checkpoints',[]) if s in chosen]
        else:value['pause_requested']=True
        save(root,value,action)
    status='pause_requested' if action=='pause' else row['status']
    if action=='pause':
        handle=claim_run(root/'.execution.lock')
        if handle is not None:
            try:
                # The completed task may have won the race while we acquired its lease.
                with store.db() as db:fresh=db.execute('SELECT status FROM jobs WHERE id=?',(row['id'],)).fetchone()
                if fresh['status'] not in ('completed','failed','cancelled','waiting_input'):
                    mark_paused(store,owner,pid,row['id']);status='paused'
                else:status=fresh['status']
            finally:release_run(handle)
    return {'id':row['id'],'status':status,'control':current(root),'pause_effect':PAUSE_NOTE}


def progress(store,owner,pid,row,request,steps):
    root=folder(store,owner,pid,row['id']);state=read(root/'state.json',row.get('result') or {})
    control=current(root);receipts=state.get('stage_receipts') or {}
    entered={s['step'] for s in state.get('steps',[]) if s.get('step')}
    tracking=json.loads(row.get('tracking') or '{}');active=tracking.get('current_step')
    stages=[]
    for step in steps:
        done=step in receipts or request.kind=='simulate' and 'simulate' in receipts and step!='archive'
        if step=='archive' and row['status']=='completed':done=True
        status='done' if done else 'waiting' if step==active and row['status'] in ('paused','queued','waiting_input','waiting_service') else 'running' if step==active and row['status']=='running' else 'failed' if step==active and row['status']=='failed' else 'pending'
        if not done and row['status']=='paused' and step==control.get('paused_before'):status='waiting'
        stages.append({'id':step,'label':LABELS[step],'status':status,'entered':step in entered,
                       'can_pause':step in controllable_steps(request.kind,steps),
                       'receipt':receipts.get(step),'pause_before':step in control.get('pause_before',[]),
                       'checkpoint_passed':step in control.get('passed_checkpoints',[])})
    native=state.get('native_code') or {};simulation=state.get('simulation_result') or {}
    external={k:native[k] for k in ('workflow_run_id','mcp_session_id','stage','status') if k in native}
    cluster=(state.get('simulation_progress') or {}).get('cluster') or {}
    external.update({k:cluster[k] for k in ('job_id','slurm_state','stage') if k in cluster})
    external.update({k:simulation[k] for k in ('job_id','slurm_state','project_path') if k in simulation})
    request_view={k:v for k,v in request.model_dump().items() if k in ('kind','query','instruction','session_id','input_paths','assets','publish_root','code_engine','max_sources','read_pages','request_id')}
    return {'id':row['id'],'project_id':pid,'kind':request.kind,'status':row['status'],'summary':row['stage'],
            'request':request_view,'stages':stages,'control':control,'pause_effect':PAUSE_NOTE,
            'external':external,'coverage':state.get('read_coverage',[]),'files':(state.get('code_result') or {}).get('files',[]),
            'error':row.get('error',''),'recovery':{k:v for k,v in (state.get('recovery') or {}).items() if k in ('status','attempts','reason','retry_after')},
            'actions':{'pause':row['status'] in ('queued','running','waiting_service'),
                       'resume':row['status'] in ('paused','failed','interrupted'),
                       'checkpoints':row['status'] not in ('completed','failed','cancelled')}}
