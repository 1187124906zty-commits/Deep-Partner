"""Independent MCP verification for workbench_jobs; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_jobs'

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
async def test_existing_and_absent_recent_job_filters():
    from .support import replay,LEDGER,PID
    jobs=LEDGER["jobs_final"]["value"]["jobs"]
    async with replay("jobs_final") as (c,_,_):
        first=(await c.call_tool(TOOL,{"project_id":PID,"job_id":jobs[0]["id"]})).data
        absent=(await c.call_tool(TOOL,{"project_id":PID,"job_id":"independent-absent"})).data
    assert first["data"]==jobs[0]
    assert absent["data"]=={"status":"not_found_in_recent_jobs","job_id":"independent-absent"}
