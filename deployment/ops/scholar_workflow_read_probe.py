"""Inspect and call both real Scholar tools; no custom scraping or credentials."""
from pathlib import Path
import asyncio,json,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    gateway='D:/Development/research-workbench/server/scholar_mcp_gateway.py'
    params=StdioServerParameters(command=sys.executable,args=['-X','utf8',gateway],env={'PYTHONUNBUFFERED':'1','SCHOLAR_TIMEOUT':'25','SCHOLAR_MAX_RETRIES':'1','SCHOLAR_MIN_DELAY':'2'})
    report={'tools':[],'calls':[]}
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize();catalog=await session.list_tools();report['tools']=[t.name for t in catalog.tools]
            for name,args in [('search_papers_by_topic',{'query':'phase field reactive transport dissolution','page_size':2}),('get_author_papers',{'author':'Christian Miehe','page_size':2})]:
                assert name in report['tools']
                result=await session.call_tool(name,args);value=result.structuredContent
                if value is None:value=json.loads(next(c.text for c in result.content if c.type=='text'))
                report['calls'].append({'tool':name,'ok':value.get('ok'),'error':value.get('error'),'count':len((value.get('data') or {}).get('results',[])),'next_cursor':(value.get('data') or {}).get('next_cursor')})
                print(json.dumps(report['calls'][-1],ensure_ascii=False),flush=True)
    target=Path(__file__).resolve().parents[1]/'reports/partner-scholar-tools-live.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':asyncio.run(main())
