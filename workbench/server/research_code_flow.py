"""Direct DeepCode task dispatch and factual publication, without an outer LLM loop."""
from pathlib import Path,PurePosixPath
from urllib.parse import quote
import asyncio,base64,json
import httpx
from .native import BASE
from .storage import child

CODER='http://127.0.0.1:8010/api/coder'

def relative(value):
    value=str(value or '');path=PurePosixPath(value)
    if not value or path.is_absolute() or '\\' in value or ':' in value or any(p in ('','..','.') or p.startswith('.') for p in value.split('/')):raise ValueError('代码产物需要项目内的相对路径')
    return path.as_posix()

async def run(store,owner,pid,jid,payload,auth,state,persist):
    project=store.get(owner,pid);root=store.path(owner,pid);versions={};inputs=[]
    async with httpx.AsyncClient(headers=auth,timeout=40,trust_env=False) as client:
        if payload.code_task_id:
            response=await client.get(CODER+'/tasks/'+quote(payload.code_task_id,safe=''));response.raise_for_status();code=response.json()
            if code.get('owner_id')!=owner or code.get('workspace_id')!=project['native_id'] or code.get('logical_project')!='research_'+pid:raise ValueError('代码任务不属于当前项目')
            sid=payload.session_id or code['tutor_session_id']
            if sid!=code['tutor_session_id']:raise ValueError('代码任务属于另一会话')
        else:
            sid=payload.session_id
            if not sid:
                response=await client.get(BASE+'/api/sessions',params={'dt_workspace':project['native_id'],'workspace_id':project['native_id'],'limit':1});response.raise_for_status()
                sessions=response.json().get('sessions',[])
                if sessions:sid=sessions[0].get('id') or sessions[0].get('session_id')
            if not sid:raise ValueError('先用 dp chat send 建立本项目研究会话，或提供 session_id')
            response=await client.get(BASE+'/api/sessions/'+quote(sid,safe=''),params={'dt_workspace':project['native_id']});response.raise_for_status();conversation=response.json()
            workspace=conversation.get('workspace_id') or conversation.get('preferences',{}).get('workspace_id')
            if workspace and workspace!=project['native_id']:raise ValueError('代码会话不属于当前项目')
            for path in payload.input_paths:
                path=relative(path);source=child(root/'project',path)
                if not source.is_file() or source.stat().st_size>256000:raise ValueError('代码输入应为不超过256KB的项目文件：'+path)
                versions[path]=source.stat().st_mtime
                inputs.append({'path':path,'content_b64':base64.b64encode(source.read_bytes()).decode(),'source_id':'project:'+pid+':'+path})
                if sum(len(v['content_b64']) for v in inputs)>1_000_000:raise ValueError('请缩小本轮代码输入材料')
            instruction=payload.instruction or payload.query
            instruction+='\n\n完成已授权的具体任务。只读取本次输入及确有必要的原文，不扫描或复制整库。输出可公开的验证与理由摘要。工作目录是代码执行副本，正式产物只写入任务要求的 src/data/results/docs 目录。大型计算沿用已配置的集群工具和 Slurm。完成后在执行副本控制区写 research-handoff.json，格式为 {"schema_version":1,"task_id":"从授权上下文读取的当前task_id","artifacts":[{"path":"要保存的项目相对文件","summary":"用途"}],"validation":[],"limitations":[]}。不为交接机械增加说明文件；只列实际需要发布的文件。执行副本的 verification.json 和 handoff 清单由系统留存，未列入 artifacts 就不进入正式项目。保存状态由后续应用回执确认。'
            context={'project':{'id':pid,'name':project['name'],'workspace_id':project['native_id']},'source_scope':{'paths':payload.input_paths},'instruction':payload.instruction or payload.query,
                     'conversation':[{'role':m['role'],'content':str(m.get('content') or '')[:2000]} for m in conversation.get('messages',[])[-4:] if m.get('role') in ('user','assistant')]}
            envelope={'protocol_version':1,'project':'research_'+pid,'mode':'code','task':instruction,'identity':{'owner_id':owner,'workspace_id':project['native_id'],'session_id':sid,'turn_id':'workflow_'+jid,'command_id':jid,'ancestor_turn_ids':[]},'context':context,'inputs':inputs}
            response=await client.post(CODER+'/tasks',json=envelope);response.raise_for_status();code=response.json()
        # Validate the real conversation, including for publication recovery.
        response=await client.get(BASE+'/api/sessions/'+quote(sid,safe=''),params={'dt_workspace':project['native_id']});response.raise_for_status()
        conversation=response.json();workspace=conversation.get('workspace_id') or conversation.get('preferences',{}).get('workspace_id')
        if workspace and workspace!=project['native_id']:raise ValueError('代码会话不属于当前项目')
        state['dispatch']={'task_id':code['id'],'session_id':sid,'mode':'direct_deepcode'};persist(state)
        while code['status'] in ('queued','running'):
            await asyncio.sleep(2)
            response=await client.get(CODER+'/tasks/'+code['id']);response.raise_for_status();code=response.json()
            if code.get('question'):break
        if code['status']=='waiting_input' or code.get('question'):
            return {'status':'requires_input','task_id':code['id'],'question':code.get('question'),'session_id':sid}
        if code['status']!='completed':raise ValueError(code.get('error') or 'DeepCode 执行未完成：'+code['status'])
        state['executor_result']={k:code.get(k) for k in ('id','status','exit_code','verification','execution')};persist(state)
        base=CODER+'/projects/'+quote(code['project'],safe='')+'/files'
        response=await client.get(base,params={'path':'research-handoff.json'});response.raise_for_status();manifest=response.json()
        if manifest.get('schema_version')!=1 or manifest.get('task_id')!=code['id']:raise ValueError('代码回交清单身份不一致')
        artifacts=manifest.get('artifacts')
        if not isinstance(artifacts,list) or not 1<=len(artifacts)<=40:raise ValueError('代码回交清单需要1至40个实际产物')
        saved=[];seen=set()
        for item in artifacts:
            path=relative(item.get('path'))
            if path.split('/')[0] not in ('src','data','results','docs') or path in seen:raise ValueError('代码产物目录或重复路径无效')
            seen.add(path);destination=child(root/'project',path)
            if destination.exists() and (path not in versions or abs(destination.stat().st_mtime-versions[path])>.01):raise ValueError('目标已存在且不属于本轮明确输入，请回读版本后定向更新：'+path)
            response=await client.get(base,params={'path':path});response.raise_for_status();data=response.content
            if len(data)>16_000_000:raise ValueError('大结果保留集群，只回交必要产物')
            store.replace(owner,pid,destination,data,str(item.get('summary') or 'DeepCode 项目产物')[:160])
            if destination.read_bytes()!=data:raise ValueError('项目文件回读不一致：'+path)
            saved.append({'path':path,'saved':True,'bytes':len(data),'read_back':True})
        return {'status':'completed','task_id':code['id'],'session_id':sid,'files':saved,'validation':manifest.get('validation',[]),'limitations':manifest.get('limitations',[]),
                'verification':code.get('verification'),'published_reply':str(code.get('result') or '')[-30000:]}
