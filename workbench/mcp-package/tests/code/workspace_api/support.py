"""Independent native-HTTP oracles; no expectations come from wrapper outputs."""
import ast
from contextlib import asynccontextmanager
from copy import deepcopy
from email.parser import BytesParser
from email.policy import default
import json
from pathlib import Path
import sys
from urllib.parse import unquote, parse_qs

import httpx
from fastmcp import Client
from fastmcp.exceptions import ToolError
import pytest

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "src"))
from client import WorkbenchClient
from tools import workspace_api as workspace

PID = "15289d1656da4c9f8b408609c83cc331"
KB = "workspace:ws_84fb4958dab24bd3a17ead349ef301c9:kb:MCP-Execution-Fixture"
NATIVE = "ws_84fb4958dab24bd3a17ead349ef301c9"
EVIDENCE = PACKAGE / "notebooks/workspace_flows"
LEDGER = {r["label"]: r for r in json.loads((EVIDENCE / "outputs/execution-ledger.json").read_text(encoding="utf-8"))}
DOC = LEDGER["reader_open"]["value"]["document_id"]
ASSET = LEDGER["reader_open"]["json"]["asset"]
REV = LEDGER["fixture_trash"]["value"]["trash_id"]
ANNOTATION = LEDGER["annotation_create"]["value"]["id"]


def response(row, request):
    kind = row["content_type"]
    if "json" in kind:
        return httpx.Response(row["status"], json=row["value"], request=request)
    raw = row["value"].encode("utf-8") if isinstance(row["value"], str) else Path(row["output"]).read_bytes()
    return httpx.Response(row["status"], content=raw, headers={"content-type": kind}, request=request)


def body_fields(request):
    kind = request.headers.get("content-type", "")
    if kind.startswith("application/x-www-form-urlencoded"):
        return {k: v for k, v in parse_qs(request.content.decode(), keep_blank_values=True).items()}, []
    if not kind.startswith("multipart/"):
        return {}, []
    msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + kind.encode() + b"\r\n\r\n" + request.content)
    fields, files = {}, []
    for part in msg.iter_parts():
        key = part.get_param("name", header="content-disposition")
        raw = part.get_payload(decode=True)
        if part.get_filename():
            files.append((key, part.get_filename(), raw))
        else:
            fields.setdefault(key, []).append(raw.decode("utf-8"))
    return fields, files


@asynccontextmanager
async def replay(label, *, force_status=None):
    row = LEDGER[label]
    observed = []
    prerequisites = []

    def handler(req):
        if req.method == "GET" and req.url.path == "/research/api/projects" and row["route"] != "/research/api/projects":
            prerequisites.append(req)
            return response(LEDGER["projects"], req)
        if req.method == "GET" and req.url.path == "/research/api/author-profile" and row["method"] == "PUT":
            prerequisites.append(req)
            return response(LEDGER["author_profile_initial"], req)
        observed.append(req)
        assert req.method == row["method"]
        assert req.url.path == unquote(row["route"])
        for key, value in (row.get("params") or {}).items():
            # server/literature.py:file has no library parameter; the executor
            # supplied this unused query field, while the wrapper resolves KB
            # originals through their actual scoped native route instead.
            if label == "literature_pdf" and key == "library":
                continue
            assert req.url.params[key] == (str(value).lower() if isinstance(value, bool) else str(value))
        expected_body = deepcopy(row.get("json"))
        if expected_body is not None:
            if row["tool"] == "workbench_knowledge_search":
                for key, val in {"mode": "fulltext-keyword", "knowledge_base": "", "limit": 8}.items():
                    expected_body.setdefault(key, val)
            if row["tool"] == "workbench_files" and req.method == "PUT":
                expected_body.setdefault("expected_modified", None)
            assert json.loads(req.content) == expected_body
        if row.get("data") is not None or row.get("files"):
            fields, files = body_fields(req)
            for key, value in (row.get("data") or {}).items():
                assert fields[key] == (value if isinstance(value, list) else [str(value)])
            for actual, expected in zip(files, row.get("files") or []):
                assert actual[:2] == (expected["field"], expected["name"])
                assert len(actual[2]) == expected["bytes"]
            assert len(files) == len(row.get("files") or [])
        if force_status:
            return httpx.Response(force_status, json={"detail": "Independent upstream failure"}, request=req)
        return response(row, req)

    transport = WorkbenchClient("https://tutor.example.invalid")
    transport._session = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            yield client, observed, prerequisites
    finally:
        await transport.close()


async def verify_reference(tool, label, arguments):
    original = deepcopy(arguments)
    row = LEDGER[label]
    async with replay(label) as (client, observed, prerequisites):
        if row["status"] >= 400:
            with pytest.raises(ToolError, match=str(row["status"])):
                await client.call_tool(tool, arguments)
        else:
            got = (await client.call_tool(tool, arguments)).data
            assert got["message"]
            assert got["reference"] == "https://tutor.example.invalid" + row["route"]
            if isinstance(row["value"], dict) and "bytes" in row["value"] and "signature" in row["value"]:
                path = Path(got["artifacts"][0]["path"])
                assert path.read_bytes() == Path(row["output"]).read_bytes()
            else:
                assert got["data"] == row["value"]  # Full nested values, IDs, text, floats and metadata.
                assert got["artifacts"] == []
        assert observed
        if row["route"].startswith("/api/knowledge-bases"):
            assert observed[-1].url.params["dt_workspace"] == NATIVE
            assert prerequisites
    assert arguments == original


async def verify_schema_and_errors(tool, label, arguments, required):
    async with replay(label) as (client, observed, _):
        spec = next(s for s in await client.list_tools() if s.name == tool)
        assert set(spec.input_schema.get("required", [])) == set(required)
        assert len(spec.description.strip().splitlines()) == 2
        assert all(p.get("description") for p in spec.input_schema["properties"].values())
        with pytest.raises(ToolError):
            await client.call_tool(tool, {**arguments, "action": "invalid-native-action"})
        for key in required:
            with pytest.raises(ToolError):
                await client.call_tool(tool, {k: v for k, v in arguments.items() if k != key})
        assert observed == []
    async with replay(label, force_status=503) as (client, _, _):
        with pytest.raises(ToolError, match="503.*Independent upstream failure"):
            await client.call_tool(tool, arguments)


def source_format(tool):
    tree = ast.parse(Path(workspace.__file__).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == tool)
    assert all(isinstance(a.annotation, ast.Subscript) and getattr(a.annotation.value, "id", None) == "Annotated" for a in node.args.args)


@asynccontextmanager
async def native_contract(handler):
    """Inject a native-contract property oracle for source-supported changed inputs."""
    t = WorkbenchClient("https://tutor.example.invalid")
    t._session = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    workspace.configure_client(t)
    try:
        async with Client(workspace.workspace_api_mcp) as c:
            yield c
    finally:
        await t.close()


async def verify_changed_contract(tool, case):
    """A second source-bound input must reach the native endpoint unchanged."""
    seen = []
    project = {"id": "changed-project-42", "native_id": "ws_changed_42", "config": {"knowledge_bases": ["workspace:ws_changed_42:kb:changed"]}}
    original = deepcopy(case["arguments"])

    def handler(req):
        if req.method == "GET" and req.url.path == "/research/api/projects" and case["path"] != "/research/api/projects":
            return httpx.Response(200, json={"projects": [project]})
        if req.method == "GET" and req.url.path in {"/research/api/api-settings", "/research/api/author-profile"} and case["method"] == "PUT":
            return httpx.Response(200, json=case["current"])
        seen.append(req)
        assert req.method == case["method"]
        assert req.url.path == case["path"]
        if "params" in case:
            assert dict(req.url.params) == case["params"]
        if "json" in case:
            assert json.loads(req.content) == case["json"]
        return httpx.Response(200, json=case["expected"])

    async with native_contract(handler) as client:
        got = (await client.call_tool(tool, case["arguments"])).data
        assert got["data"] == case["expected"]
    assert len(seen) == 1
    assert case["arguments"] == original


async def verify_artifact_repeats(tool, label, arguments, base):
    row = LEDGER[label]
    expected = row["value"].encode("utf-8") if isinstance(row["value"], str) else Path(row["output"]).read_bytes()
    args = {**arguments, "output_dir": str(base.resolve())}
    async with replay(label) as (client, _, _):
        a = (await client.call_tool(tool, args)).data
        b = (await client.call_tool(tool, args)).data
    paths = [Path(x["artifacts"][0]["path"]) for x in (a, b)]
    assert paths[0] != paths[1]
    for path, value in zip(paths, (a, b)):
        assert path.is_absolute() and path.is_relative_to(base.resolve())
        assert path.read_bytes() == expected
        assert value["data"]["bytes"] == len(expected)
        assert value["artifacts"][0]["bytes"] == len(expected)
