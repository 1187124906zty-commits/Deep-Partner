"""Bounded independent tests of the optional run-scoped HTTP MCP adapter."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import time

import httpx
import pytest
from fastmcp import Client, FastMCP

BRIDGE = Path(__file__).resolve().parents[1]
ROOT = BRIDGE.parents[1]
sys.path.insert(0, str(BRIDGE))
import mcp_server as adapter


class FixtureService:
    """Synthetic delivery/auth records; no private account or live service calls."""
    origin = "https://workbench.example"

    def __init__(self, root):
        self.database = root / "synthetic-runs.sqlite3"
        self.events = []
        self.tickets = {}
        self.rows = {}
        self.projects = {}
        for name in ("alpha", "beta"):
            project = {"id": name + "-project", "native_id": name + "-native", "root": str(root / (name + "-project"))}
            Path(project["root"]).mkdir()
            run = name + "-run"
            self.rows[run] = {"project_id": project["id"]}
            self.projects[project["id"]] = project
            self.tickets[run] = {"secret": "synthetic-" + run, "auth": {"Authorization": "Bearer synthetic-" + name}, "expires": time.time() + 600}

    @contextmanager
    def db(self):
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            yield connection

    def ticket(self, run_id, secret):
        self.events.append(("ticket", run_id))
        ticket = self.tickets.get(run_id)
        if not ticket or ticket["expires"] < time.time() or ticket["secret"] != secret:
            raise ValueError("Synthetic delivery ticket expired")
        return ticket

    def row(self, run_id):
        self.events.append(("row", run_id))
        return self.rows[run_id]

    async def project(self, auth, project_id):
        self.events.append(("project", project_id))
        expected = "Bearer synthetic-" + project_id.removesuffix("-project")
        assert auth == {"Authorization": expected}
        await asyncio.sleep(0)
        return self.projects[project_id]


@pytest.fixture
def setup_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_MCP_ARTIFACTS", str(tmp_path / "state" / "mcp-artifacts"))
    monkeypatch.delenv("WORKBENCH_TOKEN", raising=False)
    monkeypatch.delenv("WORKBENCH_SESSION_FILE", raising=False)
    service = FixtureService(tmp_path)
    secret = tmp_path / "synthetic-mcp-key"
    secret.write_text("synthetic-http-adapter-token", encoding="utf-8")
    server = adapter.create_mcp(service, secret)
    return service, secret, server


def install_mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    sessions = []
    def factory(**kwargs):
        client = original(transport=httpx.MockTransport(handler), **kwargs)
        sessions.append(client)
        return client
    monkeypatch.setattr(adapter.httpx, "AsyncClient", factory)
    return sessions


def test_runtime_tool_copies_match_verified_package():
    for source, target in [
        ("src/client.py", "workbench_mcp/client.py"),
        ("src/tools/workspace_api.py", "workbench_mcp/tools/workspace_api.py"),
        ("src/tools/authoring_api.py", "workbench_mcp/tools/authoring_api.py"),
    ]:
        assert (ROOT / "mcp-package" / source).read_bytes() == (BRIDGE / target).read_bytes(), target
    assert json.loads((BRIDGE / "workbench-tool-names.json").read_text()) == json.loads((ROOT / "mcp-package/reports/expected-mcp-tools.json").read_text(encoding="utf-8-sig"))


@pytest.mark.asyncio
async def test_all37_schemas_preserve_original_and_require_run_id(setup_adapter):
    service, secret, server = setup_adapter
    baseline = FastMCP("Independent original schemas")
    baseline.mount(adapter.workspace_api.workspace_api_mcp)
    baseline.mount(adapter.authoring_api.authoring_api_mcp)
    async with Client(baseline) as original, Client(server) as scoped:
        expected = {tool.name: tool for tool in await original.list_tools()}
        actual = {tool.name: tool for tool in await scoped.list_tools()}
    assert len(expected) == len(actual) == 37
    assert expected.keys() == actual.keys()
    for name, tool in actual.items():
        source = expected[name].inputSchema
        result = tool.inputSchema
        assert result["properties"]["run_id"]["type"] == "string"
        assert set(result.get("required", [])) == {"run_id", *source.get("required", [])}, name
        assert {key: value for key, value in result["properties"].items() if key != "run_id"} == source["properties"], name
        assert actual[name].outputSchema == expected[name].outputSchema, name
    assert service.events == []


@pytest.mark.asyncio
async def test_http_bearer_protection_before_tool_execution(setup_adapter):
    service, secret, server = setup_adapter
    http_app = server.http_app(path="/", stateless_http=True, json_response=True)
    request_body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    base_headers = {"Accept": "application/json, text/event-stream"}
    async with http_app.lifespan(http_app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=http_app), base_url="http://adapter.test") as client:
            for auth in (None, "Bearer incorrect-synthetic-token"):
                headers = {**base_headers, **({"Authorization": auth} if auth else {})}
                rejected = await client.post("/", json=request_body, headers=headers)
                assert rejected.status_code == 401
            accepted = await client.post("/", json=request_body, headers={**base_headers, "Authorization": "Bearer " + secret.read_text()})
            assert accepted.status_code == 200, accepted.text
            assert len(accepted.json()["result"]["tools"]) == 37
    assert service.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unknown", "expired"])
async def test_unavailable_run_rejected_before_project_or_native_data(setup_adapter, monkeypatch, kind):
    service, secret, server = setup_adapter
    def forbidden(request):
        raise AssertionError("Unavailable run performed a native request")
    sessions = install_mock_http(monkeypatch, forbidden)
    run = "absent-run" if kind == "unknown" else "alpha-run"
    if kind == "expired":
        service.tickets[run]["expires"] = time.time() - 1
    async with Client(server) as client:
        result = await client.call_tool("workbench_account", {"run_id": run}, raise_on_error=False)
        assert result.is_error
    assert not sessions
    assert not any(event[0] in {"row", "project"} for event in service.events)
    with service.db() as db:
        assert db.execute("SELECT COUNT(*) FROM mcp_calls").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_concurrent_runs_keep_auth_clients_and_native_scopes_separate(setup_adapter, monkeypatch):
    service, secret, server = setup_adapter
    entered = set()
    both_entered = asyncio.Event()
    observed = []
    async def handler(request):
        identity = request.headers["authorization"].removeprefix("Bearer synthetic-")
        observed.append((identity, request.url.path, dict(request.url.params)))
        assert identity in {"alpha", "beta"}
        assert request.url.path == "/api/knowledge-bases"
        assert request.url.params["dt_workspace"] == identity + "-native"
        entered.add(identity)
        if len(entered) == 2:
            both_entered.set()
        await asyncio.wait_for(both_entered.wait(), timeout=5)
        return httpx.Response(200, json={"identity": identity, "workspace": identity + "-native"}, request=request)
    sessions = install_mock_http(monkeypatch, handler)
    async with Client(server) as client:
        results = await asyncio.gather(*[
            client.call_tool("workbench_knowledge_bases", {"run_id": name + "-run", "project_id": name + "-project"})
            for name in ("alpha", "beta")
        ])
    assert [item.data["data"]["identity"] for item in results] == ["alpha", "beta"]
    assert len(sessions) == 2 and all(session.is_closed for session in sessions)
    assert len(observed) == 2
    with pytest.raises(LookupError):
        adapter._current.get()
    with service.db() as db:
        rows = db.execute("SELECT run_id,project_id,state FROM mcp_calls ORDER BY run_id").fetchall()
        assert [tuple(row) for row in rows] == [("alpha-run", "alpha-project", "completed"), ("beta-run", "beta-project", "completed")]


@pytest.mark.asyncio
async def test_project_arguments_creation_and_listing_are_scoped(setup_adapter, monkeypatch):
    service, secret, server = setup_adapter
    observed = []
    def handler(request):
        observed.append(request)
        assert request.method == "GET" and request.url.path == "/research/api/projects"
        return httpx.Response(200, json={"projects": list(service.projects.values())}, request=request)
    sessions = install_mock_http(monkeypatch, handler)
    async with Client(server) as client:
        mismatch = await client.call_tool("workbench_files", {"run_id": "alpha-run", "project_id": "beta-project"}, raise_on_error=False)
        assert mismatch.is_error and not observed
        create = await client.call_tool("workbench_projects", {"run_id": "alpha-run", "action": "create", "name": "must-not-create"}, raise_on_error=False)
        assert create.is_error and not observed
        listing = await client.call_tool("workbench_projects", {"run_id": "alpha-run"})
        assert [row["id"] for row in listing.data["data"]["projects"]] == ["alpha-project"]
    assert all(session.is_closed for session in sessions)


@pytest.mark.asyncio
async def test_upload_paths_reject_other_project_and_external_files(setup_adapter, monkeypatch, tmp_path):
    service, secret, server = setup_adapter
    project = Path(service.projects["alpha-project"]["root"])
    source = project / "source.txt"
    source.write_text("independent allowed upload", encoding="utf-8")
    external = tmp_path / "outside-project.txt"
    external.write_text("must not upload", encoding="utf-8")
    other = Path(service.projects["beta-project"]["root"]) / "source.txt"
    other.write_text("other project must not upload", encoding="utf-8")
    observed = []
    def handler(request):
        observed.append(request)
        assert request.url.path == "/research/api/projects/alpha-project/files"
        assert b"independent allowed upload" in request.content
        return httpx.Response(200, json={"uploaded": 1}, request=request)
    install_mock_http(monkeypatch, handler)
    async with Client(server) as client:
        for forbidden in (external, other, project / ".." / "outside-project.txt"):
            result = await client.call_tool("workbench_files", {"run_id": "alpha-run", "project_id": "alpha-project", "action": "upload", "file_paths": [str(forbidden)]}, raise_on_error=False)
            assert result.is_error and not observed
        allowed = await client.call_tool("workbench_files", {"run_id": "alpha-run", "project_id": "alpha-project", "action": "upload", "file_paths": [str(source)]})
        assert allowed.data["data"] == {"uploaded": 1}
    assert len(observed) == 1


@pytest.mark.asyncio
async def test_explicit_downloads_only_use_current_run_artifact_directory(setup_adapter, monkeypatch):
    service, secret, server = setup_adapter
    artifact_base = Path(__import__("os").environ["WORKBENCH_MCP_ARTIFACTS"])
    output = artifact_base / "alpha-run" / "rendered page.png"
    project_target = Path(service.projects["alpha-project"]["root"]) / "existing.png"
    project_target.write_bytes(b"preserved-project-content")
    cross_run = artifact_base / "beta-run" / "forbidden.png"
    observed = []
    content = b"\x89PNG\r\n\x1a\nindependent-native-preview"
    def handler(request):
        observed.append(request)
        return httpx.Response(200, content=content, headers={"content-type": "image/png"}, request=request)
    install_mock_http(monkeypatch, handler)
    async with Client(server) as client:
        for forbidden in (project_target, cross_run, output.parent / ".." / "escaped.png"):
            result = await client.call_tool("workbench_slides", {"run_id": "alpha-run", "project_id": "alpha-project", "action": "preview", "output_path": str(forbidden)}, raise_on_error=False)
            assert result.is_error and not observed
        allowed = await client.call_tool("workbench_slides", {"run_id": "alpha-run", "project_id": "alpha-project", "action": "preview", "output_path": str(output)})
        assert Path(allowed.data["artifacts"][0]["path"]) == output
        assert output.read_bytes() == content
    assert project_target.read_bytes() == b"preserved-project-content"
    assert not cross_run.exists()
    assert len(observed) == 1


@pytest.mark.asyncio
async def test_binary_fallback_cannot_write_inside_project_even_if_output_env_points_there(setup_adapter, monkeypatch):
    service, secret, server = setup_adapter
    project = Path(service.projects["alpha-project"]["root"])
    monkeypatch.setenv("WORKBENCH_OUTPUT_DIR", str(project))
    content = b"%PDF-independent-fallback"
    def handler(request):
        return httpx.Response(200, content=content, headers={"content-type": "application/pdf"}, request=request)
    install_mock_http(monkeypatch, handler)
    async with Client(server) as client:
        result = await client.call_tool("workbench_files", {"run_id": "alpha-run", "project_id": "alpha-project", "action": "read", "path": "article.pdf"})
    output = Path(result.data["artifacts"][0]["path"])
    expected_root = Path(__import__("os").environ["WORKBENCH_MCP_ARTIFACTS"]) / "alpha-run"
    assert output.is_relative_to(expected_root)
    assert output.read_bytes() == content
    assert not list(project.iterdir())
