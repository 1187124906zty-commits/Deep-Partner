"""Independent MCP verification for workbench_revisions; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_revisions'

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
async def test_preview_artifacts_preserve_native_revision_bytes(tmp_path):
    import httpx
    from pathlib import Path
    from .support import PID, REV, LEDGER, native_contract
    raw=LEDGER["fixture_restored_read"]["value"].encode("utf-8")
    def handler(req):
        assert req.method=="GET"
        assert req.url.path==f"/research/api/projects/{PID}/trash/{REV}/preview"
        return httpx.Response(200,content=raw,headers={"content-type":"text/plain"})
    async with native_contract(handler) as c:
        args={"project_id":PID,"action":"inspect","revision_id":REV,"view":"preview","output_dir":str(tmp_path)}
        rows=[(await c.call_tool(TOOL,args)).data for _ in range(2)]
    paths=[Path(r["artifacts"][0]["path"]) for r in rows]
    assert paths[0]!=paths[1]
    assert all(p.is_absolute() and p.read_bytes()==raw for p in paths)

@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,fragment", [({'project_id': 'x', 'action': 'inspect'}, 'revision_id')])
async def test_action_specific_missing_inputs_are_mcp_errors(arguments, fragment):
    from .support import native_contract
    from fastmcp.exceptions import ToolError
    def handler(req):
        raise AssertionError("Invalid action-specific input must fail before native HTTP")
    async with native_contract(handler) as c:
        with pytest.raises(ToolError,match=fragment):
            await c.call_tool(TOOL,arguments)
