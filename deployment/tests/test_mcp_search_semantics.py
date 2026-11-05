"""Run in the deployed FastMCP runtime: upstream failures must set isError."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from fastmcp import Client
from workbench_mcp.tools import workspace_api


class Transport:
    origin = 'https://workbench.test'
    value = {}
    async def request(self, *args, **kwargs):
        self.last_request=(args,kwargs)
        return self.value


class MCPResultTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport=Transport()
        workspace_api.configure_client(self.transport)
        self.client=Client(workspace_api.workspace_api_mcp)
        await self.client.__aenter__()
        self.addAsyncCleanup(self.client.__aexit__,None,None,None)

    async def test_unavailable_web_is_tool_error(self):
        self.transport.value={'items':[],'status':'unavailable','error':{'code':'timeout','retryable':True,'next_action':'稍后重试'}}
        result=await self.client.call_tool('workbench_web_search',{'q':'actual query'},raise_on_error=False)
        self.assertTrue(result.is_error)
        self.assertIn('timeout',str(result.content))

    async def test_valid_empty_search_is_not_tool_error(self):
        self.transport.value={'items':[],'status':'ready','outcome':'empty'}
        result=await self.client.call_tool('workbench_web_search',{'q':'actual query'},raise_on_error=False)
        self.assertFalse(result.is_error)

    async def test_explicit_scholar_failure_is_not_empty_success(self):
        self.transport.value={'items':[],'status':'unavailable','error':{'code':'verification_required','retryable':False,'next_action':'人工验证'}}
        result=await self.client.call_tool('workbench_paper_search',{'project_id':'a'*32,'q':'actual query','source':'scholar_mcp'},raise_on_error=False)
        self.assertTrue(result.is_error)
        self.assertIn('verification_required',str(result.content))

    async def test_organization_uses_real_folder_write_route(self):
        self.transport.value={'status':'saved','verified':True,'revision':2}
        organization={'expected_revision':1,'folders':[{'id':'topic','name':'主题'}],'memberships':{'workspace/reading/source.pdf':['topic']}}
        result=await self.client.call_tool('workbench_literature_organization',{'project_id':'a'*32,'action':'organize','organization':organization})
        self.assertFalse(result.is_error)
        args,kwargs=self.transport.last_request
        self.assertEqual(args,('PATCH','/research/api/projects/'+'a'*32+'/literature/folders'))
        self.assertEqual(kwargs['json'],organization)


if __name__ == '__main__':unittest.main()
