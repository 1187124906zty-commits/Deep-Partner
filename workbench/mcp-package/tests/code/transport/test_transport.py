"""Independent checks of shared transport, auth storage, and the mounted server."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
import pytest
from fastmcp import Client

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "src"))
from client import WorkbenchClient, session_path


def mock_client(handler):
    value = WorkbenchClient("https://workbench.example")
    value._session = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    return value


@pytest.mark.parametrize("target", ["https://other.example/api", "//other.example/api", "http://workbench.example/api", "https://user:secret@workbench.example/api"])
def test_cross_origin_never_requested(target):
    with pytest.raises(ValueError, match="configured Workbench origin"):
        WorkbenchClient("https://workbench.example").url(target)


@pytest.mark.parametrize("origin", ["https://workbench.example/path", "https://user:secret@workbench.example", "https://workbench.example?q=1", "http://workbench.example"])
def test_origin_contract(origin):
    with pytest.raises(ValueError):
        WorkbenchClient(origin)


def test_loopback_origin_and_same_origin_url():
    assert WorkbenchClient("http://127.0.0.1:8765").url("/research/api/me") == "http://127.0.0.1:8765/research/api/me"
    assert WorkbenchClient("https://workbench.example/").url("https://workbench.example/research/api/me") == "https://workbench.example/research/api/me"


def test_auth_cli_synthetic_login_logout_and_failed_login(tmp_path, monkeypatch, capsys):
    import workbench_auth
    private = tmp_path / "private sign in" / "session.json"
    monkeypatch.setenv("WORKBENCH_SESSION_FILE", str(private))
    monkeypatch.setenv("WORKBENCH_USERNAME", "synthetic-user")
    monkeypatch.setenv("WORKBENCH_PASSWORD", "synthetic-password")
    original_http = httpx.Client
    observed = []
    reject = False

    def handler(request):
        observed.append(request.url.path)
        assert request.headers["origin"] == "https://workbench.example"
        if request.url.path == "/api/auth/login":
            assert json.loads(request.content) == {"username": "synthetic-user", "password": "synthetic-password"}
            if reject:
                return httpx.Response(401, json={"detail": "Incorrect username or password"}, request=request)
            return httpx.Response(200, json={"ok": True}, headers={"set-cookie": "dt_token=synthetic-session; Path=/; HttpOnly; Secure"}, request=request)
        assert request.url.path == "/api/auth/logout"
        assert request.headers["cookie"] == "dt_token=synthetic-session"
        return httpx.Response(200, json={"ok": True}, request=request)

    def client_factory(**kwargs):
        return original_http(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(workbench_auth.httpx, "Client", client_factory)
    monkeypatch.setattr(sys, "argv", ["workbench_auth.py", "login", "--url", "https://workbench.example"])
    workbench_auth.main()
    saved = json.loads(private.read_text(encoding="utf-8"))
    assert saved == {"origin": "https://workbench.example", "cookies": {"dt_token": "synthetic-session"}}
    reject = True
    with pytest.raises(ValueError, match="HTTP 401"):
        workbench_auth.main()
    assert json.loads(private.read_text(encoding="utf-8")) == saved
    monkeypatch.setattr(sys, "argv", ["workbench_auth.py", "logout", "--url", "https://workbench.example"])
    workbench_auth.main()
    assert not private.exists()
    assert observed == ["/api/auth/login", "/api/auth/login", "/api/auth/logout"]
    captured = capsys.readouterr()
    assert "synthetic-password" not in captured.out + captured.err
    assert "synthetic-session" not in captured.out + captured.err


@pytest.mark.asyncio
async def test_session_file_and_bearer_precedence(tmp_path, monkeypatch):
    private = tmp_path / "private.json"
    monkeypatch.setenv("WORKBENCH_SESSION_FILE", str(private))
    monkeypatch.delenv("WORKBENCH_TOKEN", raising=False)
    assert session_path() == private
    with pytest.raises(ValueError, match="sign-in required"):
        WorkbenchClient("https://workbench.example")._http()
    private.write_text(json.dumps({"origin": "https://other.example", "cookies": {"test-session": "synthetic"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="different Workbench origin"):
        WorkbenchClient("https://workbench.example")._http()
    private.write_text(json.dumps({"origin": "https://workbench.example", "cookies": ["synthetic"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid private session file"):
        WorkbenchClient("https://workbench.example")._http()
    private.write_text(json.dumps({"origin": "https://workbench.example", "cookies": {"test-session": "synthetic"}}), encoding="utf-8-sig")
    client = WorkbenchClient("https://workbench.example")
    try:
        assert client._http().cookies.get("test-session") == "synthetic"
        assert client._http().follow_redirects is False
        assert client._http().trust_env is False
    finally:
        await client.close()
    monkeypatch.setenv("WORKBENCH_TOKEN", "synthetic-bearer")
    private.write_text("not-json", encoding="utf-8")
    client = WorkbenchClient("https://workbench.example")
    try:
        assert client._http().headers["authorization"] == "Bearer synthetic-bearer"
        assert not client._http().cookies
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_json_text_svg_binary_transforms(tmp_path, monkeypatch):
    output = tmp_path / "requested outputs"
    monkeypatch.setenv("WORKBENCH_OUTPUT_DIR", str(output))
    cases = {
        "/json": ("application/json", b'{"state":"pending","job_id":"job-independent"}'),
        "/text": ("text/plain; charset=utf-8", "source text \u6d4b\u8bd5".encode("utf-8")),
        "/svg": ("image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
        "/binary": ("application/pdf", b"%PDF-independent-test\x00\xff"),
    }
    def handler(request):
        kind, body = cases[request.url.path]
        return httpx.Response(200, headers={"content-type": kind}, content=body, request=request)
    client = mock_client(handler)
    try:
        assert await client.request("GET", "/json") == {"state": "pending", "job_id": "job-independent"}
        assert await client.request("GET", "/text") == "source text \u6d4b\u8bd5"
        assert (await client.request("GET", "/svg")).startswith("<svg")
        first = await client.request("GET", "/binary")
        second = await client.request("GET", "/binary")
        assert first["path"] != second["path"]
        for artifact in (first, second):
            path = Path(artifact["path"])
            assert path.is_absolute() and path.is_relative_to(output)
            assert path.read_bytes() == cases["/binary"][1]
            assert artifact["bytes"] == len(cases["/binary"][1])
            assert artifact["source_url"] == "https://workbench.example/binary"
        explicit = output / "selected source.txt"
        descriptor = await client.download("/text", str(explicit))
        assert Path(descriptor["path"]) == explicit
        assert explicit.read_bytes() == cases["/text"][1]
        assert not list(output.glob("*.part"))
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_descriptive_pdf_destination_within_windows_path_limit(tmp_path, monkeypatch):
    """A legal descriptive output must not gain its full name again in a temp file."""
    destination_length = 248
    filename_length = destination_length - len(str(tmp_path.resolve())) - 1
    assert 60 <= filename_length <= 255
    description = "literature-preview-Fourier-neural-operator-parametric-partial-differential-equations-"
    filename = (description * 4)[:filename_length - 4] + ".pdf"
    output = tmp_path / filename
    old_temporary = output.with_name("." + output.name + "." + "f" * 32 + ".part")
    assert len(str(output)) == destination_length < 260 < len(str(old_temporary))
    payloads = [b"%PDF-independent-descriptive-preview\x00\xff", b"%PDF-independent-replacement-preview\x01\xfe"]
    writes = []
    original_write = Path.write_bytes

    def bounded_windows_write(path, data):
        # Exercise actual filesystem I/O and retain the former Windows path bound,
        # even on a host where extended-path support has since been enabled.
        assert len(str(path)) < 260
        writes.append(path)
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", bounded_windows_write)
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=payloads.pop(0), request=request)
    client = mock_client(handler)
    try:
        for expected in (b"%PDF-independent-descriptive-preview\x00\xff", b"%PDF-independent-replacement-preview\x01\xfe"):
            descriptor = await client.download("/literature/preview.pdf", str(output))
            assert descriptor["path"] == str(output)
            assert descriptor["bytes"] == len(expected)
            assert output.read_bytes() == expected
        assert len(writes) == 2 and writes[0] != writes[1]
        assert all(path.parent == output.parent and path != output for path in writes)
        assert list(tmp_path.iterdir()) == [output]
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 403, 404, 409, 500])
async def test_errors_never_create_download(tmp_path, status):
    def handler(request):
        return httpx.Response(status, json={"detail": "independent upstream rejection"}, request=request)
    client = mock_client(handler)
    output = tmp_path / "must-not-exist.bin"
    try:
        with pytest.raises(ValueError, match=f"HTTP {status}"):
            await client.request("GET", "/error")
        with pytest.raises(ValueError, match=f"HTTP {status}"):
            await client.download("/error", str(output))
        assert not output.exists()
        with pytest.raises(ValueError, match="must be absolute"):
            await client.download("/error", "relative.bin")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_native_scope_comes_from_owned_project():
    observed = []
    def handler(request):
        observed.append(request)
        if request.url.path == "/research/api/projects":
            return httpx.Response(200, json={"projects": [{"id": "owned", "native_id": "actual-native-workspace"}]}, request=request)
        assert request.url.params["dt_workspace"] == "actual-native-workspace"
        assert request.url.params["q"] == "retained"
        return httpx.Response(200, json={"scope": "actual-native-workspace"}, request=request)
    client = mock_client(handler)
    try:
        result = await client.native_request("GET", "/api/knowledge-bases", "owned", params={"dt_workspace": "substituted", "q": "retained"})
        assert result == {"scope": "actual-native-workspace"}
        count = len(observed)
        with pytest.raises(ValueError, match="unavailable"):
            await client.native_request("POST", "/api/knowledge-bases", "unowned", json={"name": "must-not-create"})
        assert len(observed) == count + 1
        assert observed[-1].url.path == "/research/api/projects"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_missing_native_binding_never_sent():
    observed = []
    def handler(request):
        observed.append(request)
        assert request.url.path == "/research/api/projects"
        return httpx.Response(200, json={"projects": [{"id": "owned"}]}, request=request)
    client = mock_client(handler)
    try:
        with pytest.raises(ValueError, match="no native workspace binding"):
            await client.native_request("GET", "/api/knowledge-bases", "owned")
        assert len(observed) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_actual_mounted_inventory_and_live_read_only(monkeypatch):
    monkeypatch.setenv("WORKBENCH_SESSION_FILE", "C:/Users/DEVELOPER/.codex/research-workbench-mcp-session.json")
    monkeypatch.delenv("WORKBENCH_TOKEN", raising=False)
    monkeypatch.delenv("WORKBENCH_URL", raising=False)
    import project_mcp
    expected = json.loads((PACKAGE / "reports/expected-mcp-tools.json").read_text(encoding="utf-8-sig"))
    try:
        async with Client(project_mcp.mcp) as client:
            actual = await client.list_tools()
            assert len(actual) == 37
            assert sorted(tool.name for tool in actual) == sorted(expected)
            account = await client.call_tool("workbench_account", {})
            rules = await client.call_tool("workbench_rules", {})
            assert not account.is_error and not rules.is_error
            account_payload = account.data
            rules_payload = rules.data
            assert isinstance(account_payload["data"], dict) and account_payload["data"].get("username")
            assert isinstance(rules_payload["data"], dict) and rules_payload["data"]
            assert account_payload["artifacts"] == rules_payload["artifacts"] == []
            assert account_payload["reference"] == "https://tutor.example.invalid/research/api/me"
    finally:
        await project_mcp.client.close()
