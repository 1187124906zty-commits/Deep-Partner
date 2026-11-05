"""Independent MCP verification for workbench_author_profile; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_author_profile'

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
@pytest.mark.parametrize("arguments,fragment", [({'action': 'institutions'}, 'q'), ({'action': 'preview'}, 'project_id')])
async def test_action_specific_missing_inputs_are_mcp_errors(arguments, fragment):
    from .support import native_contract
    from fastmcp.exceptions import ToolError
    def handler(req):
        raise AssertionError("Invalid action-specific input must fail before native HTTP")
    async with native_contract(handler) as c:
        with pytest.raises(ToolError,match=fragment):
            await c.call_tool(TOOL,arguments)
