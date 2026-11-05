"""Verify the real third adapter tool across the MCP protocol boundary."""
import asyncio,json,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    command=StdioServerParameters(command=sys.executable,args=['-X','utf8','C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts/deepcode_tools_mcp.py'])
    async with stdio_client(command) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();catalog=await session.list_tools()
            result=await asyncio.wait_for(session.call_tool('deepcode_workflow',{'action':'verify','workspace':'C:/Users/DEVELOPER/.codex/deep-partner/acceptance/paper2code','run_id':'wfr_afd71621187c4661bf5f659424214fe8'}),20)
            assert not result.isError
            value=result.structuredContent or json.loads(next(c.text for c in result.content if c.type=='text'))
            assert value['verification_recovered'] and all(c['passed'] for c in value['checks'])
            report={'tools':[tool.name for tool in catalog.tools],'called':'deepcode_workflow','action':'verify','recovered':True,'checks_passed':len(value['checks']),'original_native_status':value['native_status'],'protocol_response_received':True}
            (Path(__file__).resolve().parents[1]/'reports/partner-third-tool-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps(report))

if __name__=='__main__':asyncio.run(main())
