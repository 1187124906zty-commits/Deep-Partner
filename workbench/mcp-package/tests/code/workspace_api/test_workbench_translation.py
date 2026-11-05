"""Independent MCP verification for workbench_translation; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_translation'

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
async def test_reader_protocol_composition_and_changed_target():
    import httpx,json
    from .support import PID,DOC,native_contract
    seen=[]
    responses=[{"targetLanguage":"en"},{"accepted":True},{"accepted":True,"pending":2}]
    def handler(req):
        index=len(seen);seen.append(req)
        methods=["PUT","POST","POST"]
        suffixes=["translation-options","processing","translations"]
        assert req.method==methods[index]
        assert req.url.path==f"/research/reader/{PID}/api/documents/{DOC}/"+suffixes[index]
        if index==0: assert json.loads(req.content)=={"targetLanguage":"en"}
        if index==2: assert json.loads(req.content)=={"blockId":""}
        return httpx.Response(200,json=responses[index])
    async with native_contract(handler) as c:
        got=(await c.call_tool(TOOL,{"project_id":PID,"action":"reader_start","target":"en","document_id":DOC})).data
        assert got["data"]==dict(zip(["options","processing","translations"],responses))
        with pytest.raises(Exception,match="target must"):
            await c.call_tool(TOOL,{"project_id":PID,"action":"reader_start","target":"fr","document_id":DOC})
    assert len(seen)==3

@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,fragment", [({'project_id': 'x', 'action': 'reader_start'}, 'document_id'), ({'project_id': 'x', 'action': 'export_pdf'}, 'document_id')])
async def test_action_specific_missing_inputs_are_mcp_errors(arguments, fragment):
    from .support import native_contract
    from fastmcp.exceptions import ToolError
    def handler(req):
        raise AssertionError("Invalid action-specific input must fail before native HTTP")
    async with native_contract(handler) as c:
        with pytest.raises(ToolError,match=fragment):
            await c.call_tool(TOOL,arguments)
