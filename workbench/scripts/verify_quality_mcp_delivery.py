"""Verify the published ZIP in a fresh directory against read-only live APIs."""
from pathlib import Path
import asyncio
import json
import subprocess
import sys
import zipfile
import httpx

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://tutor.example.invalid'


async def main():
    credentials=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True)
    account=json.loads(credentials.stdout)
    async with httpx.AsyncClient(headers={'Origin':ORIGIN},trust_env=False,timeout=45) as http:
        login=await http.post(ORIGIN+'/api/auth/login',json={'username':account['username'],'password':account['password']})
        login.raise_for_status()
        response=await http.get(ORIGIN+'/research/api/integrations/mcp-package');response.raise_for_status()
        assert response.content==(ROOT/'mcp-package/dist/research-workbench-mcp.zip').read_bytes()
        output=ROOT/'mcp-package/tmp/quality-delivery-test';output.mkdir(parents=True,exist_ok=True)
        archive=output/'published.zip';archive.write_bytes(response.content)
        with zipfile.ZipFile(archive) as bundle:
            assert all((output/name).resolve().is_relative_to(output.resolve()) for name in bundle.namelist())
            bundle.extractall(output)
        sys.path.insert(0,str(output/'research-workbench-mcp/src'))
        from fastmcp import Client
        import project_mcp
        project_mcp.client._session=http
        projects=(await http.get(ORIGIN+'/research/api/projects')).json()['projects']
        assert projects
        project=next((x for x in projects if 'qa' in x['name'].lower() or '验收' in x['name']),projects[0])
        pid=project['id']
        async with Client(project_mcp.mcp) as mcp:
            names=[t.name for t in await mcp.list_tools()]
            assert len(names)==37
            results={}
            calls=[('rubric',{'project_id':pid,'action':'quality_rubric','stage':'slides-plan','purpose':'group'}),
                   ('reviews',{'project_id':pid,'action':'quality_list','stage':'slides-plan','purpose':'group'}),
                   ('gate',{'project_id':pid,'action':'quality_gate','stage':'slides-plan','purpose':'group'})]
            for name,arguments in calls:
                result=await mcp.call_tool('workbench_review',arguments)
                data=result.data
                if hasattr(data,'model_dump'):data=data.model_dump()
                assert isinstance(data,dict) and isinstance(data.get('data'),dict),(name,type(data))
                results[name]=data['data']
            context=await mcp.call_tool('workbench_rules',{'project_id':pid,'action':'context','task':'paper'})
            value=context.data
            if hasattr(value,'model_dump'):value=value.model_dump()
            assert value['data']['receipt_schema']['stage']=='writing'
            assert value['data']['receipt_schema']['operation_id']=='stable-action-id'
            assert results['rubric']['core_minimum']==3
            assert results['gate']['can_proceed'] is False
    report={'status':'passed','tool_count':37,'published_zip_matches_local':True,
            'published_bytes':archive.stat().st_size,'fresh_extraction':str(output),
            'read_only':True,'paid_model_calls':0,'project_id':pid,
            'quality_actions':['quality_rubric','quality_list','quality_gate'],
            'context_receipt_stage':'writing','gate_decision':results['gate']['decision']}
    (ROOT/'mcp-package/reports/quality-delivery-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
