"""Independent MCP verification for workbench_project_import; frozen native HTTP results are the oracle."""
import pytest
from .support import verify_reference, verify_schema_and_errors, source_format
from .contracts import CASES, REQUIRED
TOOL = 'workbench_project_import'

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
async def test_changed_zip_uses_file_field_and_exact_bytes(tmp_path):
    import httpx,zipfile
    from .support import PID,native_contract,body_fields
    path=tmp_path/"changed-synthetic.zip"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("workbench-import.json",'{"manuscript":"manuscript/source.docx"}')
        z.writestr("manuscript/source.docx",b"test transport bytes; source validation remains native")
    def handler(req):
        assert req.method=="POST" and req.url.path==f"/research/api/projects/{PID}/import"
        fields,files=body_fields(req)
        assert fields=={} and files==[("file",path.name,path.read_bytes())]
        return httpx.Response(200,json={"job_id":"changed-native-job"})
    async with native_contract(handler) as c:
        got=(await c.call_tool(TOOL,{"project_id":PID,"file_path":str(path)})).data
        assert got["data"]=={"job_id":"changed-native-job"}
        with pytest.raises(Exception,match="does not exist"):
            await c.call_tool(TOOL,{"project_id":PID,"file_path":str(tmp_path/"absent.zip")})
