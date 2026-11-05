"""Independent MCP verification for workbench_literature; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_literature'

@pytest.mark.asyncio
@pytest.mark.parametrize("label,arguments", CASES[TOOL], ids=[x[0] for x in CASES[TOOL]])
async def test_full_native_values(label, arguments):
    await verify_reference(TOOL, label, arguments)

@pytest.mark.asyncio
async def test_schema_missing_invalid_and_http_failure():
    label, arguments = CASES[TOOL][0]
    await verify_schema_and_errors(TOOL, label, arguments, REQUIRED[TOOL])
    source_format(TOOL)

@pytest.mark.asyncio
async def test_two_downloads_keep_full_bytes_and_unique_paths(tmp_path):
    from .support import verify_artifact_repeats
    from .contracts import p, k, ASSET
    await verify_artifact_repeats(TOOL, 'literature_preview', p("preview",asset=ASSET), tmp_path)

@pytest.mark.asyncio
async def test_bound_library_original_and_unbound_error(tmp_path):
    import httpx
    from pathlib import Path
    from .support import native_contract
    pid="changed-project-42";kb="workspace:ws_changed_42:kb:changed"
    data=b"%PDF-1.7\nsource contract original\n"
    seen=[]
    def handler(req):
        if req.url.path=="/research/api/projects":
            return httpx.Response(200,json={"projects":[{"id":pid,"native_id":"ws_changed_42","config":{"knowledge_bases":[kb]}}]})
        seen.append(req)
        assert req.url.path=="/api/knowledge-bases/"+kb+"/files/changed/source.pdf"
        assert req.url.params["dt_workspace"]=="ws_changed_42"
        return httpx.Response(200,content=data,headers={"content-type":"application/pdf"})
    async with native_contract(handler) as c:
        args={"project_id":pid,"action":"read","library":kb,"asset":"changed/source.pdf","output_dir":str(tmp_path)}
        r=(await c.call_tool(TOOL,args)).data
        assert Path(r["artifacts"][0]["path"]).read_bytes()==data
        with pytest.raises(Exception,match="not bound"):
            await c.call_tool(TOOL,{**args,"library":"not-bound"})
    assert len(seen)==1

@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,fragment", [({'project_id': 'x', 'action': 'read'}, 'asset'), ({'project_id': 'x', 'action': 'upload'}, 'file path')])
async def test_action_specific_missing_inputs_are_mcp_errors(arguments, fragment):
    from .support import native_contract
    from fastmcp.exceptions import ToolError
    def handler(req):
        raise AssertionError("Invalid action-specific input must fail before native HTTP")
    async with native_contract(handler) as c:
        with pytest.raises(ToolError,match=fragment):
            await c.call_tool(TOOL,arguments)
