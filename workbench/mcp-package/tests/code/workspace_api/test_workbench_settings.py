"""Independent MCP verification for workbench_settings; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_settings'

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
