"""A real scoped native → Dify → MCP → saved artifact round trip on QA only."""
import asyncio
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-package/src"))
from client import WorkbenchClient


async def main():
    project_id = "15289d1656da4c9f8b408609c83cc331"
    client = WorkbenchClient()
    output = ROOT / "verification/dify"
    output.mkdir(parents=True, exist_ok=True)
    path = "docs/dify-mcp-roundtrip.txt"
    marker = "DIFY_MCP_ROUNDTRIP_" + uuid.uuid4().hex
    try:
        project = await client.project(project_id)
        context = await client.request("GET", f"/research/api/projects/{project_id}/agent-context", params={"task":"code"})
        files = await client.request("GET", f"/research/api/projects/{project_id}/files", params={"path":"docs"})
        existing = next((p for p in files.get("items", []) if p.get("path") == path), None)
        payload = {"request_id":"mcp-dify-"+uuid.uuid4().hex, "project_id":project_id, "workspace_id":project["native_id"], "task":"code", "standard_version":context["standard_version"], "artifact":{"type":"file", "path":path, "content":marker+"\n", "summary":"Dify MCP complete delivery verification on isolated QA", "source_paths":[]}, "validation":[], "limitations":["Isolated software fixture; no manuscript or scientific conclusion"]}
        if existing:
            payload["artifact"]["expected_modified"] = existing["modified"]
        result = await client.request("POST", "/research/dify/api/deliver", json=payload)
        (output / "workflow-live-result.json").write_text(json.dumps({"project_id":project_id,"request_id":payload["request_id"],"marker":marker,"result":result},ensure_ascii=False,indent=2),encoding="utf8")
        if result.get("status") != "saved":
            print(json.dumps({"status":result.get("status"),"error":result.get("error"),"run_id":result.get("run_id")},ensure_ascii=False))
            raise AssertionError("Native-to-Dify workflow has no saved receipt; inspect retained result")
        assert result.get("workflow_status") == "succeeded" and result.get("processing_history_verified") is True, "Native saved artifact lacks a verified terminal Dify workflow"
        saved = await client.request("GET", f"/research/api/projects/{project_id}/file", params={"path":path})
        assert saved == marker+"\n", "Actual native readback differs"
        repeat = await client.request("POST", "/research/dify/api/deliver", json=payload)
        assert repeat.get("run_id") == result.get("run_id") and repeat.get("workflow_run_id") == result.get("workflow_run_id"), "Idempotent retry created another workflow"
        print(json.dumps({"saved":True,"exact_readback":True,"idempotent_retry":True,"workflow_status":result["workflow_status"],"processing_history_verified":result["processing_history_verified"],"project_id":project_id,"run_id":result["run_id"],"workflow_run_id":result.get("workflow_run_id"),"artifact":result.get("artifact")},ensure_ascii=False))
    finally:
        await client.close()


asyncio.run(main())
