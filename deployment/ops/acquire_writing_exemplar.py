"""Coordinator-chosen public exemplar acquired through the same actual MCP."""
import asyncio,json,os,sys
from pathlib import Path
sys.path.insert(0,'/app')
import httpx
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    from deeptutor.services.auth import create_token
    from deeptutor.multi_user.paths import local_admin_user
    user=local_admin_user();auth={'Origin':'https://tutor.example.invalid','Authorization':'Bearer '+create_token(user.username,user.role,user.id)}
    async with httpx.AsyncClient(timeout=30,trust_env=False) as c:
        r=await c.get('https://tutor.example.invalid/research/api/projects',headers=auth);r.raise_for_status()
    pid,rid=sys.argv[1:3];project=next(p for p in r.json()['projects'] if p['id']==pid)
    root=Path(project['root']);folder=root/'.workbench/writing/runs'/rid
    env={**os.environ,'WRITING_PROJECT_ROOT':str(root),'WRITING_RUN_FOLDER':str(folder),'WRITING_PROJECT_ID':pid,'WRITING_RUN_ID':rid,'WRITING_AUTH':json.dumps(auth)}
    params=StdioServerParameters(command=sys.executable,args=['/opt/dify-delivery/writing_agent/mcp_tools.py'],env=env)
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result=await session.call_tool('fetch_resource',{'url':'https://researchportal.northumbria.ac.uk/ws/portalfiles/portal/135961182/1_s2.0_S0008884624000711_main.pdf','purpose':'style'})
            record=result.model_dump(mode='json')
            (folder/'coordinator-exemplar-acquisition.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
            print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
