"""One bounded stdio MCP call using the isolated search-tool interpreter."""
from pathlib import Path
import asyncio,json,logging,sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    sys.stdout.reconfigure(encoding='utf8');parameters=json.loads(sys.stdin.read());logging.basicConfig(level=logging.WARNING)
    server=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(Path(__file__).with_name('scholar_mcp_gateway.py'))],env={'PYTHONUNBUFFERED':'1','SCHOLAR_TIMEOUT':'18','SCHOLAR_MAX_RETRIES':'0','SCHOLAR_MIN_DELAY':'1.3'})
    async with stdio_client(server) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();result=await session.call_tool('search_papers_by_topic',parameters)
            value=result.structuredContent
            if value is None:value=json.loads(next(c.text for c in result.content if c.type=='text'))
            print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':
    try:asyncio.run(main())
    except Exception:print(json.dumps({'ok':False,'error':{'code':'mcp_transport_error','message':'Scholar MCP transport did not return a usable response'}}))
