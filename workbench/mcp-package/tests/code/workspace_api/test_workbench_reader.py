"""Independent MCP verification for workbench_reader; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_reader'

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
async def test_changed_inputs_follow_native_contract():
    from .contracts import CHANGED
    from .support import verify_changed_contract
    await verify_changed_contract(TOOL, CHANGED[TOOL])

@pytest.mark.asyncio
async def test_source_pdf_artifacts_and_document_scope(tmp_path):
    import httpx
    from pathlib import Path
    from .support import PID, DOC, LEDGER, native_contract
    raw=Path(LEDGER["literature_pdf"]["output"]).read_bytes()
    def handler(req):
        assert req.url.path==f"/research/reader/{PID}/pub/workbench/{DOC}/original.pdf"
        return httpx.Response(200,content=raw,headers={"content-type":"application/pdf"})
    async with native_contract(handler) as c:
        args={"project_id":PID,"action":"content","document_id":DOC,"view":"source","output_dir":str(tmp_path)}
        rows=[(await c.call_tool(TOOL,args)).data for _ in range(2)]
    paths=[Path(r["artifacts"][0]["path"]) for r in rows]
    assert paths[0]!=paths[1]
    assert all(p.is_absolute() and p.read_bytes()==raw for p in paths)

@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,fragment", [({'project_id': 'x', 'action': 'content'}, 'document_id'), ({'project_id': 'x', 'action': 'image', 'document_id': 'd'}, 'block_id')])
async def test_action_specific_missing_inputs_are_mcp_errors(arguments, fragment):
    from .support import native_contract
    from fastmcp.exceptions import ToolError
    def handler(req):
        raise AssertionError("Invalid action-specific input must fail before native HTTP")
    async with native_contract(handler) as c:
        with pytest.raises(ToolError,match=fragment):
            await c.call_tool(TOOL,arguments)
