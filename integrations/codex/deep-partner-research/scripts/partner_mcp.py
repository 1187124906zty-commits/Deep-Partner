"""Small, lazy MCP surface over the authenticated dp CLI."""
import asyncio,json,os,tempfile
from pathlib import Path
from typing import Literal
from mcp.server.fastmcp import FastMCP

DP=Path(os.environ.get('DEEP_PARTNER_CLI',str(Path.home()/'AppData/Local/Programs/Deep partner/dp.exe')))
mcp=FastMCP('Deep Partner',instructions='Bind every action to the actual project. Choose the workflow kind once; the runner executes tools and saves materials. Read only the selected route. A submitted task is not a completed result.')

async def cli(*args):
    process=await asyncio.create_subprocess_exec(str(DP),*map(str,args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await process.communicate();stdout=out.decode('utf8',errors='replace');stderr=err.decode('utf8',errors='replace')
    if process.returncode:raise ValueError(stderr[-2500:] or stdout[-1000:])
    try:return json.loads(stdout)
    except ValueError:
        events=[json.loads(line) for line in stdout.splitlines() if line.strip().startswith('{')]
        published=''.join(e.get('content','') for e in events if e.get('type')=='content')
        useful=[e for e in events if e.get('type') in ('done','project_receipt','error','protocol_error','wait_for_input')]
        return {'answer':published[:30000],'answer_truncated':len(published)>30000,'events':useful[-12:],'message':stderr[-1000:]}

async def payload_command(command,project,payload):
    with tempfile.TemporaryDirectory(prefix='deep-partner-') as directory:
        path=Path(directory)/'request.json';path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
        return await cli('workflow',command,'--project',project,'--file',path)

@mcp.tool()
async def partner_projects(action:Literal['list','create']='list',name:str='')->dict:
    """List actual owned projects. Reuse their IDs for all later operations."""
    if action=='create':return await cli('project','create','--name',name,'--json')
    value=await cli('project','list','--json')
    return {'projects':[{k:p.get(k) for k in ('id','name','native_id','updated')} for p in value.get('projects',[])]}

@mcp.tool()
async def partner_research(project:str,action:Literal['start','status','routes','reply','resume']='start',kind:Literal['search','survey','download','analyze','code','slides','simulate']='survey',payload:dict|None=None,run_id:str='')->dict:
    """Execute a typed project workflow, read its status, or lazily inspect one route.
    payload fields: query/instruction/entries/assets/max_sources/session_id/confirmation_id/request_id.
    Search, download, bounded reading and archiving are executed by the runner.
    """
    if action=='routes':return await cli('workflow','routes','--project',project,'--kind',kind)
    if action=='status':return await cli('workflow','status','--project',project,'--id',run_id)
    if action=='resume':return await cli('workflow','resume','--project',project,'--id',run_id)
    if action=='reply':
        with tempfile.TemporaryDirectory(prefix='partner-reply-') as directory:
            path=Path(directory)/'reply.json';path.write_text(json.dumps(payload or {},ensure_ascii=False),encoding='utf8')
            return await cli('workflow','reply','--project',project,'--id',run_id,'--file',path)
    return await payload_command('run',project,{**(payload or {}),'kind':kind})

@mcp.tool()
async def partner_record(project:str,record:dict)->dict:
    """Save public research findings/reasons, citations, counterevidence and ideas as project files and graph nodes.
    record: id/title/content/nodes/edges/search_scope. Nodes: id/kind/label/status/evidence_refs.
    Use proposed for ideas and not_found_in_scope with actual search_scope for negative searches.
    """
    return await payload_command('record',project,record)

@mcp.tool()
async def partner_graph(project:str,limit:int=80,offset:int=0)->dict:
    """Read a bounded source-linked research graph, without loading the project's full history."""
    return await cli('workflow','graph','--project',project,'--limit',min(200,max(1,limit)),'--offset',max(0,offset))

@mcp.tool()
async def partner_conversation(project:str,action:Literal['list','history','send','resume','reply','stop']='list',session_id:str='',message:str='',capability:Literal['chat','code']='chat')->dict:
    """Connect to a project conversation. Sending streams the actual answer and archives published messages into that project. Resume never resubmits the question."""
    args=['chat',action,'--project',project]
    if session_id:args+=['--session',session_id]
    if action in ('send','resume','reply','stop'):args+=['--jsonl']
    if action=='send':args+=['--message',message,'--capability',capability]
    if action=='reply':args+=['--message',message]
    result=await cli(*args)
    if action=='history':
        messages=result.get('messages',[])
        return {k:result.get(k) for k in ('id','session_id','title','active_turn_id','workspace_id')}|{'messages':[{k:m.get(k) for k in ('id','role','content','created_at')} for m in messages[-8:]],'total_messages':len(messages)}
    return result

@mcp.tool()
async def partner_memo(project:str,memo_id:str)->dict:
    """Bind a specific existing idea memo to its owning project and sync its current materials. Future memo saves sync automatically."""
    import importlib.util
    path=Path(__file__).with_name('memo_sync.py');spec=importlib.util.spec_from_file_location('partner_memo_sync',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return await asyncio.to_thread(module.sync,memo_id,project)

if __name__=='__main__':mcp.run()
