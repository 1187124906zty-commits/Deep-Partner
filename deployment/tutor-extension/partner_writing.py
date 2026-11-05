"""Opt-in/out product mode on the existing per-turn extension interface."""
from __future__ import annotations
import asyncio
import json
import os
import httpx
from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.tool_protocol import BaseTool,ToolDefinition,ToolParameter,ToolResult
from deeptutor.multi_user.context import get_current_user_or_none
from deeptutor.services.auth import create_token
from deeptutor.services.workspace.context import current_workspace_id

BASE=os.environ.get('PARTNER_WRITING_URL','https://tutor.example.invalid').rstrip('/')
PHASES={'intent':'理解任务','exemplar':'标杆解构','alignment':'主题与沙漏架构','narrow':'方法与结果','wide':'引言与首尾','review':'期刊表达与审稿','deliver':'保存成果'}


def auth():
    user=get_current_user_or_none()
    if not user:return None
    return {'Authorization':'Bearer '+create_token(user.username,user.role,user.id),'Origin':'https://tutor.example.invalid'}


def phase_config(context):
    return context.config_overrides or {}


class PartnerWriting:
    name='partner_writing'
    owned_tools=('partner_writing_workflow',)

    def is_active(self,context):
        return bool(get_current_user_or_none() and current_workspace_id()) and phase_config(context).get('partner_mode','research')=='writing'

    def system_block(self,context,**kwargs):
        return PromptBlock(self.name,'Partner当前为用户选定的写作模式。按当前任务范围执行初稿、投稿或返修；实际阶段以任务计划和回执为准。'
            'pre_loop提供本轮已完成的写作成果、项目位置及状态；沿用这些产物继续回应用户，具体内容与用户当前任务对应。')

    def augment_kwargs(self,tool_name,kwargs,context):
        if tool_name!='partner_writing_workflow':return kwargs
        return {**kwargs,'_headers':auth(),'_context':context}

    def pre_loop_seed(self,context):return ''

    async def pre_loop(self,context,stream,**kwargs):
        cfg=phase_config(context);namespace=context.extension(self.name)
        async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
            await stream.progress('正在接入写作工作流：理解当前任务',source='partner_writing',stage='writing',metadata={'trace_kind':'call_status','call_state':'running','label':'写作工作流'})
            selected=None
            # The request snapshot carries the exact selected profile; use it when supplied.
            selected=cfg.get('partner_llm_selection')
            if not selected:
                snapshot=context.metadata.get('request_snapshot') or {}
                selected=snapshot.get('llmSelection') or snapshot.get('llm_selection')
            result=await client.post(BASE+'/research/api/writing/dispatch',headers=auth(),json={
                'workspace_id':current_workspace_id(),'session_id':context.session_id,
                'turn_id':getattr(context,'turn_id','') or context.runtime.turn_id,
                'operation_id':getattr(context,'turn_id','') or context.runtime.turn_id,'request':context.user_message,
                'phase':cfg.get('partner_writing_phase','auto'),'mode':cfg.get('partner_mode','research'),
                'engine':'agentic','author_round':True,'proposal':True,
                'history':[{'role':m.get('role'),'content':str(m.get('content',''))[:4000]} for m in context.conversation_history[-6:]],
                'model_selection':selected})
            result.raise_for_status();run=result.json()
            if run.get('status')=='disabled':return None
            namespace.update(run_id=run['id'],project_id=run['project_id'])
            previous=''
            try:
                while run['status'] not in ('completed','failed','cancelled','interrupted'):
                    if run['stage']!=previous:
                        previous=run['stage']
                        await stream.progress('写作工作流 · '+PHASES.get(previous,previous),source='partner_writing',stage='writing',
                            metadata={'trace_kind':'call_status','call_state':'running','label':PHASES.get(previous,previous),'writing_run_id':run['id'],'writing_phase':run.get('phase')})
                    await asyncio.sleep(2)
                    result=await client.get(BASE+'/research/api/projects/'+run['project_id']+'/writing/runs/'+run['id'],headers=auth())
                    result.raise_for_status();run=result.json()
            except asyncio.CancelledError:
                await asyncio.shield(client.post(BASE+'/research/api/projects/'+run['project_id']+'/writing/runs/'+run['id']+'/cancel',headers=auth()))
                raise
            namespace['result']=run
            if run['status']!='completed':raise RuntimeError('写作工作流'+('已停止' if run['status']=='cancelled' else '未完成：'+str(run.get('error',''))))
            await stream.progress('写作工作流已完成并保存',source='partner_writing',stage='writing',metadata={'trace_kind':'call_status','call_state':'complete','writing_run_id':run['id']})
            return PromptBlock(self.name,json.dumps({'writing_run_id':run['id'],'phase':run['phase'],
                'intent':run.get('intent'),'outputs':run['outputs'],'stage_history':run.get('stage_history')},ensure_ascii=False))


class PartnerWritingTool(BaseTool):
    def get_definition(self):
        return ToolDefinition('partner_writing_workflow','继续本轮已绑定的初稿、投稿或返修写作工作流；status读取真实状态，result回读已保存成果。',
            parameters=[ToolParameter('action','string',enum=['status','result'])])

    async def execute(self,action='status',_headers=None,_context=None,**kwargs):
        state=_context.extension('partner_writing') if _context else {}
        if not _headers or not state.get('run_id'):return ToolResult(content='当前轮没有已绑定写作任务',success=False)
        async with httpx.AsyncClient(timeout=None,trust_env=False) as client:
            response=await client.get(BASE+'/research/api/projects/'+state['project_id']+'/writing/runs/'+state['run_id'],headers=_headers)
            response.raise_for_status();value=response.json()
        return ToolResult(content=json.dumps(value if action=='status' else value.get('outputs',{}),ensure_ascii=False),success=value.get('status')!='failed')
