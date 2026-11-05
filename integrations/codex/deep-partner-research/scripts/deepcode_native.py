"""Thin client of the installed DeepCode service and its real MCP server."""
from pathlib import Path
import asyncio,importlib.util,json,os,sys

INSTALL=Path('C:/Users/DEVELOPER/Documents/ChatGPT/小研究/DeepCode_MCP')
PYTHON=INSTALL/'DeepCode-env/Scripts/python.exe'
LAUNCHER=INSTALL/'run_deepcode.py'
_prepared=False

def prepare():
    global _prepared
    if not _prepared:
        sys.path.insert(0,str(INSTALL))
        spec=importlib.util.spec_from_file_location('installed_deepcode_launcher',LAUNCHER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.prepare_runtime()
        from compat.krill_compat import install
        install();_prepared=True

async def mcp_call(name,arguments):
    """Discover then call the upstream tool; never emulate its agent loop."""
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    async with stdio_client(StdioServerParameters(command=str(PYTHON),args=['-X','utf8',str(LAUNCHER)])) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();catalog=await session.list_tools()
            names=[tool.name for tool in catalog.tools]
            if name not in names:raise ValueError('Installed DeepCode does not expose '+name)
            result=await session.call_tool(name,arguments)
            structured=result.structuredContent or {}
            if result.isError or structured.get('error'):raise ValueError('DeepCode '+str(structured.get('error') or 'tool_error')+': '+''.join(c.text for c in result.content if c.type=='text')[:1500])
            return {'tool':name,'discovered_tools':names,'result':structured,
                    'summary':'\n'.join(c.text for c in result.content if c.type=='text')[-30000:]}

def code_prompt(instruction):
    prepare()
    from workflows.research_guidance import research_code_prompt
    return research_code_prompt(instruction)

def configure_workflow_tools():
    """Use the installed kernel's bundled code and execution MCP servers."""
    prepare()
    path=Path(os.environ['DEEPCODE_HOME'])/'deepcode_config.json'
    settings=json.loads(path.read_text(encoding='utf8'))
    servers=settings.setdefault('tools',{}).setdefault('mcpServers',{})
    import core
    package_root=Path(core.__file__).resolve().parent.parent
    changed=[]
    for name,module in [('code-implementation','tools.code_implementation_server'),('command-executor','tools.command_executor')]:
        if name not in servers:
            servers[name]={'command':str(PYTHON),'args':['-m',module],'env':{'PYTHONPATH':str(package_root)}};changed.append(name)
    if changed:path.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return {'configured':sorted(servers),'added':changed}

async def rpc(method,params):
    prepare()
    from app_server.native_client import NativeRpcClient
    from app_server.service_state import ServiceFiles
    from core.persistence.database import default_database_path
    client=NativeRpcClient(ServiceFiles(default_database_path()))
    try:
        await client.connect({'protocolVersion':'1.0','clientInfo':{'name':'DeepPartner workflow adapter','version':'1','surface':'desktop'}},start=True)
        return await client.request(method,params)
    finally:await client.close()

async def agent_turn(workspace,marker):
    """Locate an admitted native Turn after an MCP client detaches."""
    rows=await rpc('thread/list',{'cwd':str(Path(workspace).resolve()),'limit':100})
    for thread in rows['threads']:
        if Path(thread['workspacePath']).resolve()!=Path(workspace).resolve():continue
        turns=await rpc('turn/list',{'threadId':thread['id'],'limit':100})
        for turn in reversed(turns['turns']):
            if marker in turn.get('prompt',''):return turn
    return None

async def read_agent_turn(turn_id):
    snapshot=await rpc('turn/read',{'turnId':turn_id});turn=snapshot['turn']
    text='\n'.join(row.get('payload',{}).get('text','') for row in snapshot.get('items',[])
                   if row.get('kind')=='assistant_message' and row.get('payload',{}).get('phase')=='final_answer')
    return {'turn':turn,'summary':text,'approvals':snapshot.get('approvals',[])}

async def workflow(action,workspace='',run_id='',source='',source_type='requirement',options=None,interaction_id='',response=None,thread_id=''):
    """Expose only the official workflow lifecycle and artifact inspection."""
    if action=='capabilities':
        configured=configure_workflow_tools()
        return {'upstream_mcp_tools':['deepcode','deepcode-reply'],'workflow_kind':'paper2code',
                'native_methods':['workflow/start','workflow/read','workflow/respond','workflow/retry','workflow/interrupt','artifact/list','artifact/read'],**configured}
    if action=='start':
        configure_workflow_tools()
        if not thread_id:
            project=await rpc('project/add',{'path':str(Path(workspace).resolve()),'displayName':'Deep Partner research','trustState':'trusted'})
            if project['project'].get('trustState')!='trusted':
                project=await rpc('project/update',{'projectId':project['project']['id'],'trustState':'trusted'})
            thread=await rpc('thread/start',{'projectId':project['project']['id'],'mode':'paper','title':'Deep Partner · Paper2Code'})
            thread_id=thread['thread']['id']
        result=await rpc('workflow/start',{'threadId':thread_id,'kind':'paper2code','sourceType':source_type,'source':source,'options':options or {}})
        return {'tool':'deepcode_workflow','method':'workflow/start',**result}
    if action in ('read','retry','interrupt'):
        return {'tool':'deepcode_workflow','method':'workflow/'+action,**await rpc('workflow/'+action,{'workflowRunId':run_id})}
    if action=='verify':
        snapshot=await rpc('workflow/read',{'workflowRunId':run_id});root=Path(workspace).resolve()
        artifact=next((a for a in snapshot['artifacts'] if a['kind']=='codebase'),None)
        if not artifact:raise ValueError('Native workflow has no codebase artifact to verify')
        code=(root/artifact['storagePath']).resolve()
        if not code.is_relative_to(root) or not code.is_dir():raise ValueError('Verification artifact is outside the bound workspace')
        from workflows.code_implementation_workflow import CodeImplementationWorkflow
        checks=await CodeImplementationWorkflow._verify_generated_code(None,code)
        if not checks or not all(c.get('passed') for c in checks):raise ValueError('Native verification did not pass: '+json.dumps(checks,ensure_ascii=False)[-1500:])
        return {'tool':'deepcode_workflow','method':'native verification stage','native_status':snapshot['workflow']['status'],
                'verification_recovered':True,'checks':checks,'workflow':snapshot['workflow'],'artifacts':snapshot['artifacts']}
    if action=='respond':
        return {'tool':'deepcode_workflow','method':'workflow/respond',**await rpc('workflow/respond',{'workflowRunId':run_id,'interactionId':interaction_id,'response':response or {}})}
    if action=='artifacts':return await rpc('artifact/list',{'threadId':thread_id})
    raise ValueError('Unsupported DeepCode workflow action')
