"""Authenticated adapter between the native DeepTutor tool and Dify Workflow."""
from pathlib import Path
from contextlib import asynccontextmanager
import os
import asyncio
from contextlib import suppress

from fastapi import Depends, FastAPI, HTTPException, Request

from delivery import Delivery, DeliveryService
from evidence import EvidenceRequest

PREFIX = "/research/dify"
service = DeliveryService(
    Path(os.environ.get("DIFY_DELIVERY_STATE", "/state/deliveries.sqlite3")),
    workbench_url=os.environ.get("WORKBENCH_URL", "http://127.0.0.1:47900"),
    native_url=os.environ.get("NATIVE_URL", "http://127.0.0.1:8008"),
    dify_url=os.environ.get("DIFY_URL", "http://127.0.0.1:8088"),
    dify_key=Path(os.environ.get("DIFY_API_KEY_FILE", "/run/secrets/workflow-key")),
    origin=os.environ.get("PUBLIC_ORIGIN", "https://tutor.example.invalid"),
)
app = FastAPI(title="Research Workbench Dify Delivery", version="0.1.0")

from mcp_server import create_mcp
mcp_server = create_mcp(service, Path(os.environ.get("WORKBENCH_MCP_KEY_FILE", "/run/secrets/mcp-key")))
mcp_http = mcp_server.http_app(path="/", stateless_http=True, json_response=True)


@asynccontextmanager
async def lifespan(app):
    async with mcp_http.lifespan(app):
        worker = asyncio.create_task(service.automation.worker())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


app.router.lifespan_context = lifespan
app.mount(PREFIX + "/mcp", mcp_http)


async def credentials(request: Request):
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and origin.rstrip("/") != service.origin:
        raise HTTPException(403, "请求来源与研究工作台不一致")
    auth = {key: request.headers[key] for key in ["authorization", "cookie"] if key in request.headers}
    if not auth:
        raise HTTPException(401, "请先登录 DeepTutor")
    return auth


@app.get("/health")
def health():
    return {"ok": True, "version": "0.1.0", "workflow_configured": service.dify_key.is_file()}


@app.get(PREFIX + "/api/projects")
async def projects(auth=Depends(credentials)):
    rows = await service.projects(auth)
    return {"projects": [{k: p[k] for k in ("id", "name", "native_id")} for p in rows]}


@app.get(PREFIX + '/api/web-evidence')
async def web_evidence(url: str, auth=Depends(credentials)):
    return await service.read_webpage(auth,url)


@app.get(PREFIX + "/api/context")
async def context(project_id: str = "", task: str = "review", workspace_id: str = "", auth=Depends(credentials)):
    if task not in Delivery.model_fields["task"].annotation.__args__:
        raise HTTPException(400, "研究任务类型无效")
    return await service.context(auth, project_id, task, workspace_id)


@app.post(PREFIX + "/api/deliver")
async def deliver(body: Delivery, auth=Depends(credentials)):
    return await service.deliver(auth, body)


@app.get(PREFIX + "/api/runs/{run_id}")
async def status(run_id: str, auth=Depends(credentials)):
    return await service.status(auth, run_id)


@app.post(PREFIX + '/api/runs/{run_id}/acknowledge')
async def acknowledge(run_id: str, body: dict, auth=Depends(credentials)):
    reason=body.get('reason')
    if not isinstance(reason,str):raise HTTPException(400,'需要处理原因')
    return await service.automation.acknowledge(auth,run_id,reason)


@app.get(PREFIX + '/api/activity')
async def activity(project_id: str = '', workspace_id: str = '', auth=Depends(credentials)):
    return await service.automation.activity(auth, project_id, workspace_id)


@app.post(PREFIX + '/api/evidence')
async def evidence(body: EvidenceRequest, auth=Depends(credentials)):
    return await service.evidence.search(auth, body)


@app.get(PREFIX + '/api/evidence/{run_id}')
async def evidence_status(run_id: str, auth=Depends(credentials)):
    return await service.evidence.status(auth, run_id)


@app.get(PREFIX + "/internal/runs/{run_id}/context")
async def prepare(run_id: str, request: Request):
    return await service.prepare(run_id, request.headers.get("x-run-ticket", ""),request.headers.get('x-dify-workflow-run-id',''))


@app.post(PREFIX + "/internal/runs/{run_id}/commit")
async def commit(run_id: str, request: Request):
    return await service.commit(run_id, request.headers.get("x-run-ticket", ""))
