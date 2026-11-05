"""Real MCP initialize/list/call through the installed Tutor runtime."""
import asyncio,json,os,sys,tempfile
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    with tempfile.TemporaryDirectory(prefix='writing-mcp-') as tmp:
        root=Path(tmp);run=root/'run';run.mkdir()
        source=root/'project/references';source.mkdir(parents=True)
        (source/'transport.md').write_text('# Reaction transport\n\n损伤反馈改变裂纹连通性和有效扩散率。\n\nChloride binding and sulfate reactions change the phase composition.',encoding='utf8')
        style=root/'project/docs/writing/resources/exemplars';style.mkdir(parents=True)
        (style/'expression.md').write_text('# Expression example\n\nThis comparison links the change in connectivity to the observed transport response.',encoding='utf8')
        env={**os.environ,'WRITING_PROJECT_ROOT':str(root),'WRITING_RUN_FOLDER':str(run),'WRITING_PROJECT_ID':'mcp-smoke','WRITING_RUN_ID':'smoke','WRITING_AUTH':'{}'}
        params=StdioServerParameters(command=sys.executable,args=['/opt/dify-delivery/writing_agent/mcp_tools.py'],env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                init=await session.initialize();catalog=await session.list_tools();names=[t.name for t in catalog.tools]
                checks={}
                fetch=next(t for t in catalog.tools if t.name=='fetch_resource')
                checks['retrieval_purpose_is_enumerated']=set(fetch.inputSchema['properties']['purpose']['enum'])=={'research','style'}
                research=await session.call_tool('rag_search',{'query':'损伤反馈 扩散率','corpus':'research'})
                v=json.loads(research.content[0].text);checks['chinese_retrieval_has_real_source']=v['items'][0]['source']=='project/references/transport.md'
                style=await session.call_tool('rag_search',{'query':'connectivity transport','corpus':'style'})
                v=json.loads(style.content[0].text);checks['expression_corpus_separate']=v['items'][0]['source'].endswith('exemplars/expression.md')
                alias=await session.call_tool('rag_search',{'query':'connectivity transport','corpus':'expression'})
                v=json.loads(alias.content[0].text);checks['expression_alias_retrieves_style_source']=v['items'][0]['source'].endswith('exemplars/expression.md')
                skill=await session.call_tool('read_skill',{'name':'citation-management'})
                checks['external_skill_actual_text']='Citation Management' in skill.content[0].text
                synthesis=await session.call_tool('read_skill',{'name':'journal-literature-synthesis'})
                checks['journal_synthesis_skill_actual_text']='群体' in synthesis.content[0].text and 'Qin' in synthesis.content[0].text
                source=await session.call_tool('read_project_source',{'relative_path':'project/references/transport.md'})
                checks['read_surrounding_paragraphs']='Chloride binding' in source.content[0].text
                denied=await session.call_tool('read_project_source',{'relative_path':'../outside.md'})
                checks['path_ownership_checked']=denied.isError
                checks['four_document_mcp_tools_discovered']=all(n in names for n in ['exemplar_structural_deconstructor','intrinsic_scientific_rigor_auditor','comparative_metric_calculator','rhetorical_alignment_inspector'])
                print(json.dumps({'server':init.serverInfo.model_dump(),'tools':names,'checks':checks,'passed':all(checks.values())},ensure_ascii=False))
                assert all(checks.values())


if __name__=='__main__':asyncio.run(main())
