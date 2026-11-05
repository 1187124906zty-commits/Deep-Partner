from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import httpx,json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tutor-extension"))
import dify_delivery as native


@pytest.mark.asyncio
async def test_model_cannot_supply_native_account_authority():
    result = await native.ResearchWorkbenchTool().execute("projects", _authority={"user_id": "another-account", "role": "admin"})
    assert not result.success


def test_runtime_overwrites_model_supplied_identity(monkeypatch):
    current = native.Authority("actual-user", "person", "user", "actual-workspace", "actual-session", "actual-turn")
    monkeypatch.setattr(native, "authority", lambda context: current)
    result = native.WorkbenchDelivery().augment_kwargs("research_workbench", {"_authority": {"role": "admin"}}, object())
    assert result["_authority"] is current


def test_plain_question_does_not_require_artifact_schema():
    definition = native.ResearchWorkbenchTool().get_definition().to_openai_schema()
    assert definition["function"]["parameters"]["required"] == ["action"]
    assert definition["function"]["parameters"]["properties"]["artifact_json"]["type"] == "string"


@pytest.mark.asyncio
async def test_search_does_not_start_delivery_and_preserves_failure(monkeypatch):
    calls=[]
    async def upstream(request):
        calls.append(request.url.path)
        assert request.method=='GET'
        return httpx.Response(200,json={'items':[],'status':'unavailable',
            'error':{'code':'rate_limited','retryable':True,'next_action':'等待后重试'}})
    client=httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(native.httpx,'AsyncClient',lambda **kwargs:client)
    monkeypatch.setattr(native,'create_token',lambda *args:'test-token')
    auth=native.Authority('user','person','user','workspace','session','turn')
    result=await native.ResearchWorkbenchTool().execute('search',search_kind='web',query='actual query',_authority=auth)
    assert not result.success
    assert json.loads(result.content)['error']['code']=='rate_limited'
    assert calls==['/research/api/search/web']


@pytest.mark.asyncio
async def test_library_organization_uses_current_project_api_and_saved_readback(monkeypatch):
    calls=[]
    async def upstream(request):
        calls.append((request.method,request.url.path))
        if request.url.path.endswith('/context'):return httpx.Response(200,json={'project':{'id':'owned-project'}})
        assert request.method=='PATCH' and request.url.path=='/research/api/projects/owned-project/literature/folders'
        assert json.loads(request.content)['memberships']=={'workspace/reading/source.pdf':['topic']}
        return httpx.Response(200,json={'status':'saved','verified':True,'revision':1})
    client=httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(native.httpx,'AsyncClient',lambda **kwargs:client)
    monkeypatch.setattr(native,'create_token',lambda *args:'test-token')
    result=await native.ResearchWorkbenchTool().execute('library',library_action='organize',organization_json=json.dumps({'expected_revision':0,'memberships':{'workspace/reading/source.pdf':['topic']}}),_authority=native.Authority('user','person','user','workspace','session','turn'))
    assert result.success and json.loads(result.content)['verified']
    assert calls==[('GET','/research/dify/api/context'),('PATCH','/research/api/projects/owned-project/literature/folders')]
