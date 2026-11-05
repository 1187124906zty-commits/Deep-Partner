"""Prepared simulation -> bounded Slurm job -> declared numerical checks -> project."""
from pathlib import PurePosixPath
from typing import Literal
import asyncio,base64,json,math
import httpx
from pydantic import BaseModel,Field,model_validator
from .storage import child
from .research_tool_flow import tool_call,ToolPending,ToolNotFound,authorized_binding,bind_authorization

class Resources(BaseModel):
    cpus:int=Field(default=2,ge=1,le=32)
    memory_mb:int=Field(default=4096,ge=512,le=131072)
    walltime_seconds:int=Field(default=600,ge=60,le=86400)

class Check(BaseModel):
    field:str=Field(min_length=1,max_length=300)
    op:Literal['finite','true','le','ge','close']
    value:float|None=None
    atol:float=Field(default=0,ge=0)
    unit:str=Field(default='',max_length=80)
    basis:str=Field(default='',max_length=1500)
    @model_validator(mode='after')
    def threshold(self):
        if self.op in ('le','ge','close') and (self.value is None or not math.isfinite(self.value)):raise ValueError('数值比较需要有限的预定参考值')
        return self

class Simulation(BaseModel):
    engine:Literal['python','openpaso_mcp']='python'
    runtime:Literal['paso','dune','torch']='paso'
    entrypoint:str=''
    arguments:list[str]=Field(default_factory=list,max_length=40)
    tool_steps:list[dict]=Field(default_factory=list,max_length=20)
    summary_path:str='results/summary.json'
    expected_outputs:list[str]=Field(default_factory=lambda:['results/summary.json'],max_length=40)
    resources:Resources=Field(default_factory=Resources)
    checks:list[Check]=Field(default_factory=list,max_length=40)
    validation_basis:Literal['theoretical','experimental','calibration','unspecified']='unspecified'
    physics:dict=Field(default_factory=dict)
    @model_validator(mode='after')
    def paths(self):
        for value in [self.summary_path,*self.expected_outputs,*([self.entrypoint] if self.entrypoint else [])]:
            path=PurePosixPath(value)
            if not value or path.is_absolute() or '\\' in value or any(p in ('','..','.') for p in value.split('/')):raise ValueError('仿真文件需使用项目内相对路径')
        if self.engine=='python' and not self.entrypoint:raise ValueError('Python仿真需要明确的entrypoint')
        if self.engine=='openpaso_mcp' and not self.tool_steps:raise ValueError('MCP仿真需要工具名及其真实arguments')
        if any(not isinstance(step.get('tool'),str) or not isinstance(step.get('arguments',{}),dict) for step in self.tool_steps):raise ValueError('仿真工具步骤格式无效')
        return self

def prepare(spec,input_paths):
    model=Simulation(**spec)
    if model.engine=='python' and model.entrypoint not in input_paths:raise ValueError('仿真入口必须属于本次明确交接的input_paths')
    return model.model_dump()

async def run(store,owner,pid,jid,payload,auth,state,persist):
    from .native import BASE
    project=store.get(owner,pid)
    binding=state.setdefault('simulation_binding',{'id':'simulate-'+jid})
    if not authorized_binding(binding,owner,pid,project['native_id']):
        async with httpx.AsyncClient(headers=auth,timeout=30,trust_env=False) as client:
            response=await client.get(BASE+'/api/auth/profile');response.raise_for_status();profile=response.json()
            if profile.get('id') and profile['id']!=owner:raise PermissionError('原生账户不属于当前任务')
            if profile.get('role')!='admin' and not profile.get('is_admin'):raise PermissionError('仿真执行沿用现有管理员执行权限')
        bind_authorization(binding,owner,pid,project['native_id']);persist(state)
    spec=prepare(payload.simulation,payload.input_paths);root=store.path(owner,pid);inputs=[];total=0
    for name in ([] if binding.get('submitted') else payload.input_paths):
        source=child(root/'project',name)
        if not source.is_file() or source.stat().st_size>16_000_000:raise ValueError('仿真输入文件缺失或超过本次单文件传输范围')
        total+=source.stat().st_size
        if total>32_000_000:raise ValueError('大仿真数据应复用集群项目中的已有输入')
        inputs.append({'path':name,'content_b64':base64.b64encode(source.read_bytes()).decode()})
    state['simulation_request']={'simulation':spec,'input_paths':payload.input_paths};persist(state)
    operation='simulate-'+jid
    if binding.get('submitted') or state.get('simulation_progress'):
        try:row=await tool_call(owner,pid,operation,'status')
        except ToolNotFound:
            if not binding.get('request'):raise ValueError('原始仿真提交请求缺失，不能重建任务')
            row=await tool_call(owner,pid,operation,'start',payload=binding['request'])
    else:
        binding['request']={'operation':'simulate','simulation':spec,'run_id':jid,'inputs':inputs}
        binding['submitted']=True;persist(state)
        row=await tool_call(owner,pid,operation,'start',payload=binding['request'])
    state['simulation_progress']={k:row.get(k) for k in ('id','status','cluster')};persist(state)
    if row['status'] not in ('completed','failed','cancelled'):raise ToolPending('集群仿真原任务仍在运行，稍后查询同一 ID')
    if row['status']!='completed':raise ValueError('集群仿真未完成：'+str(row.get('error')))
    result=row['result'];base='results/simulations/'+jid+'/';receipt=result['result']
    report='# 集群仿真结果\n\n'+json.dumps(receipt,ensure_ascii=False,indent=2)+'\n\n原始结果留在集群：'+result['remote_root']+'\n'
    for name,content in [('request.json',json.dumps(state['simulation_request'],ensure_ascii=False,indent=2)),('result.json',json.dumps(result,ensure_ascii=False,indent=2)),('report.md',report)]:
        target=child(root/'project',base+name);store.replace(owner,pid,target,content.encode(),'集群仿真工作流产物')
        if target.read_text(encoding='utf8')!=content:raise ValueError('仿真报告保存回读不一致')
    return {**result,'project_path':base,'saved':True,'read_back':True,'status':receipt['status']}
