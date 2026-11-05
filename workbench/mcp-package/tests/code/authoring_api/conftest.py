"""Independent source HTTP oracles and real FastMCP calls for authoring tools.

Only the explicitly assigned disposable synthetic project may be mutated.
No authentication payload or header is written to evidence.
"""
from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import zlib

from fastmcp import Client
import httpx
import pytest_asyncio

PACKAGE = Path(__file__).resolve().parents[3]
QA = "4959b9a67b324c0eb69ab9c67ee897cb"
FORMAL = "05a893386c09449d88366cf6dfdc825f"
DATA = PACKAGE / "notebooks/authoring_flows/data"
CAPTURED = PACKAGE / "notebooks/authoring_flows/outputs"
RESULTS = PACKAGE / "tests/results/authoring_api"
ORIGIN = "https://tutor.example.invalid"
IMAGE = "results/synthetic.png"

sys.path.insert(0, str(PACKAGE / "src"))
from client import WorkbenchClient

_spec = importlib.util.spec_from_file_location("independent_authoring_api", PACKAGE / "src/tools/authoring_api.py")
MODULE = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = MODULE
_spec.loader.exec_module(MODULE)


def utc():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf8")


def without_clock(value):
    """Only these documented source timestamps are excluded from live read equality."""
    if isinstance(value, dict):
        return {k: without_clock(v) for k, v in value.items() if k not in {"checked", "metrics_checked"}}
    if isinstance(value, list):
        return [without_clock(v) for v in value]
    return value


def text_nodes(node):
    if isinstance(node, list):
        return "".join(text_nodes(n) for n in node)
    return node.get("text", "") + text_nodes(node.get("content", []))


def png_rgb(raw):
    """Decode every RGB pixel in the synthetic 8-bit PNG fixtures without new packages."""
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", raw[16:29])
    assert (depth, color, interlace) == (8, 2, 0)
    parts, offset = [], 8
    while offset + 12 <= len(raw):
        size = struct.unpack(">I", raw[offset:offset + 4])[0]
        if raw[offset + 4:offset + 8] == b"IDAT":
            parts.append(raw[offset + 8:offset + 8 + size])
        offset += size + 12
    encoded, previous, decoded, offset = zlib.decompress(b"".join(parts)), [0] * (width * 3), bytearray(), 0
    for _ in range(height):
        mode, values = encoded[offset], list(encoded[offset + 1:offset + 1 + width * 3])
        offset += 1 + width * 3
        for i in range(len(values)):
            left = values[i - 3] if i >= 3 else 0
            above = previous[i]
            corner = previous[i - 3] if i >= 3 else 0
            if mode == 0:
                prediction = 0
            elif mode == 1:
                prediction = left
            elif mode == 2:
                prediction = above
            elif mode == 3:
                prediction = (left + above) // 2
            elif mode == 4:
                p = left + above - corner
                distances = [abs(p - left), abs(p - above), abs(p - corner)]
                prediction = [left, above, corner][distances.index(min(distances))]
            else:
                raise AssertionError("Unsupported native PNG filter")
            values[i] = (values[i] + prediction) % 256
        decoded.extend(values)
        previous = values
    assert offset == len(encoded)
    return width, height, bytes(decoded)


class Evidence:
    def __init__(self, direct, mcp, root):
        self.direct, self.mcp, self.root = direct, mcp, root
        self.index, self.events = 0, []
        self.outbound = []
        self.root.mkdir(parents=True, exist_ok=True)

    async def record_outbound(self, request):
        """Record only task payloads; authentication headers/cookies stay private."""
        row = {"method": request.method, "path": request.url.path, "params": dict(request.url.params)}
        if request.headers.get("content-type", "").startswith("application/json"):
            row["json"] = json.loads(request.content)
        self.outbound.append(row)

    async def response(self, method, suffix, *, project=True, **kwargs):
        path = f"/research/api/projects/{QA}{suffix}" if project else suffix
        response = await self.direct.request(method, path, **kwargs)
        self.index += 1
        # Keep evidence names inside the native Windows path limit, including
        # parametrized pytest test-directory names. Index preserves uniqueness.
        label = f"{self.index:03d}_native_{method.lower()}_{re.sub('[^a-zA-Z0-9]+', '_', suffix).strip('_')[:42]}"
        kind = response.headers.get("content-type", "")
        if "json" in kind:
            output = self.root / (label + ".json")
            save_json(output, response.json())
        else:
            output = self.root / (label + ".bin")
            output.write_bytes(response.content)
        inputs = {key: copy.deepcopy(kwargs[key]) for key in ("params", "json") if key in kwargs}
        if kwargs.get("files"):
            inputs["files"] = {key: {"name": value[0], "local_path": str(getattr(value[1], "name", "")),
                                     "mime": value[2]} for key, value in kwargs["files"].items()}
        self.events.append({"utc": utc(), "source": "independent_direct_http", "method": method,
                            "path": path, "inputs": inputs, "status": response.status_code, "content_type": kind,
                            "bytes": len(response.content), "response_path": str(output)})
        return response

    async def get(self, suffix, **kwargs):
        response = await self.response("GET", suffix, **kwargs)
        assert response.status_code == 200, response.text
        return response.json()

    async def invoke(self, tool, **arguments):
        original = copy.deepcopy(arguments)
        result = await self.mcp.call_tool(tool, arguments)
        assert arguments == original, "MCP call mutated caller inputs"
        data = result.data
        assert set(data) == {"message", "reference", "artifacts", "data"}
        assert isinstance(data["message"], str) and data["message"]
        assert data["reference"].startswith(ORIGIN + "/research/api/")
        assert isinstance(data["artifacts"], list)
        self.index += 1
        output = self.root / f"{self.index:03d}_{tool}.json"
        save_json(output, data)
        self.events.append({"utc": utc(), "source": "fastmcp_client", "tool": tool,
                            "arguments": original, "is_error": result.is_error, "result_path": str(output)})
        assert not result.is_error
        return data

    async def error(self, tool, contains, **arguments):
        result = await self.mcp.call_tool(tool, arguments, raise_on_error=False)
        message = "\n".join(getattr(item, "text", "") for item in result.content)
        self.events.append({"utc": utc(), "source": "fastmcp_client", "tool": tool,
                            "arguments": arguments, "is_error": result.is_error, "error": message})
        assert result.is_error, "Expected an MCP tool error"
        assert contains in message
        return message

    async def wait_job(self, job_id):
        assert re.fullmatch(r"[a-f0-9]{32}", job_id)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            response = await self.direct.get(f"/research/api/projects/{QA}/jobs")
            assert response.status_code == 200
            job = next(x for x in response.json()["jobs"] if x["id"] == job_id)
            if job["status"] in {"completed", "failed"}:
                save_json(self.root / f"job_{job_id}.json", job)
                assert job["status"] == "completed", job
                return job
            await asyncio.sleep(0.5)
        raise AssertionError("Native export job did not finish within 150 seconds")

    async def restore_manuscript(self, original):
        current = await self.get("/manuscript")
        restore = {**original, "revision": current["revision"], "reason": "Restore independent synthetic verification fixture"}
        response = await self.response("PUT", "/manuscript", json=restore)
        assert response.status_code == 200, response.text
        restored = response.json()
        for key in ("title", "template", "content", "references"):
            assert restored.get(key) == original.get(key)


@pytest_asyncio.fixture
async def live(request):
    """Private cookies are read in memory and never copied to results or logs."""
    session_file = Path(os.environ["WORKBENCH_SESSION_FILE"])
    session = json.loads(session_file.read_text(encoding="utf-8-sig"))
    assert session["origin"].rstrip("/") == ORIGIN
    direct = httpx.AsyncClient(base_url=ORIGIN, headers={"Origin": ORIGIN, "Accept": "application/json"},
                               cookies=session["cookies"], timeout=httpx.Timeout(180, connect=20), trust_env=False)
    transport = WorkbenchClient()
    MODULE.configure_client(transport)
    root = RESULTS / "inprocess" / request.node.name
    async with direct, Client(MODULE.authoring_api_mcp) as mcp:
        evidence = Evidence(direct, mcp, root)
        transport._http().event_hooks["request"].append(evidence.record_outbound)
        try:
            yield evidence
        finally:
            save_json(root / "events.json", evidence.events)
            save_json(root / "outbound-source-contract.json", evidence.outbound)
            await transport.close()
