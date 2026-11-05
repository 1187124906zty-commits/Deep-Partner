"""Real FastMCP calls compared with saved direct-upstream authoring responses."""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys

from fastmcp import Client
import httpx
import pytest

PACKAGE = Path(__file__).resolve().parents[2]
SOURCE = PACKAGE / "src/tools/authoring_api.py"
SPEC = importlib.util.spec_from_file_location("authoring_api_under_test", SOURCE)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
EVIDENCE = PACKAGE / "notebooks/authoring_flows"
REQUESTS = json.loads((EVIDENCE / "requests.json").read_text(encoding="utf8"))
CAPTURES = {row["label"]: row for row in REQUESTS}
PROJECT = json.loads((EVIDENCE / "fixture.json").read_text(encoding="utf8"))["project_id"]
IMAGE = EVIDENCE / "data/synthetic.png"


def native(label):
    record = CAPTURES[label]
    path = Path(record["response_path"])
    return json.loads(path.read_text(encoding="utf8")) if "json" in record["content_type"] else path.read_bytes()


class NativeCaptureAdapter:
    """Test-only transport adapter returning actual retained native responses."""
    origin = "https://tutor.example.invalid"

    def __init__(self, label):
        self.label = label
        self.calls = []
        self.open_uploads = []

    async def project(self, project_id):
        if project_id != PROJECT:
            raise ValueError("Project is not owned by the test account")
        return {"id": project_id, "native_id": "test-only-scope-from-owned-project"}

    async def request(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **copy.deepcopy({k: v for k, v in kwargs.items() if k != "files"})})
        for field, value in (kwargs.get("files") or {}).items():
            name, stream, mime = value
            self.open_uploads.append({"field": field, "name": name, "stream": stream,
                                      "open_during_await": not stream.closed, "bytes": stream.read(), "mime": mime})
        record = CAPTURES[self.label]
        if record["status"] >= 400:
            raise ValueError(f"HTTP {record['status']}: {native(self.label).get('detail', 'native error')}")
        return copy.deepcopy(native(self.label))

    async def native_request(self, method, path, project_id, **kwargs):
        await self.project(project_id)
        value = await self.request(method, path, **kwargs)
        self.calls[-1]["project_id"] = project_id
        return value

    async def download(self, path, output_path, *, params=None):
        self.calls.append({"method": "GET", "path": path, "params": params, "output_path": output_path})
        record = CAPTURES[self.label]
        if record["status"] >= 400:
            raise ValueError(f"HTTP {record['status']}: native download error")
        data = native(self.label)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": str(target), "bytes": len(data), "content_type": record["content_type"], "source_url": self.origin + path}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,label,arguments,expected_method,expected_suffix", [
    ("workbench_manuscript", "replay_manuscript_read", {"project_id": PROJECT}, "GET", "/manuscript"),
    ("workbench_manuscript_templates", "manuscript_template_catalog", {}, "GET", "/manuscript-templates"),
    ("workbench_manuscript_export", "start_manuscript_docx", {"project_id": PROJECT, "format": "docx", "language": "source", "columns": 1}, "POST", "/manuscript/export"),
    ("workbench_export_download", "manuscript_docx_url", {"project_id": PROJECT, "name": "清稿.docx"}, "GET", "/download"),
    ("workbench_references", "reference_library", {"project_id": PROJECT}, "GET", "/references"),
    ("workbench_journals", "journal_generic_details", {"action": "details", "journal_id": "generic-en"}, "GET", "/journals/generic-en"),
    ("workbench_journal_templates", "official_journal_template_search", {"project_id": PROJECT, "journal": "issn-0008-8846"}, "POST", "/journal-templates/search"),
    ("workbench_figure", "inspect_unregistered_fixture_figure", {"project_id": PROJECT, "path": "results/synthetic.png"}, "GET", "/figure"),
    ("workbench_figure_chat", "figure_chat_history", {"project_id": PROJECT, "path": "results/synthetic.png"}, "GET", "/figure/chat"),
    ("workbench_image_review", "prepare_image_review_only", {"project_id": PROJECT, "path": "results/synthetic.png", "image_path": str(IMAGE), "instruction": "Synthetic API review fixture. Record the image; do not change scientific content.", "send": False}, "POST", "/image-review"),
    ("workbench_raster", "save_raster", {"project_id": PROJECT, "path": "results/synthetic.png", "image_path": str(IMAGE)}, "POST", "/image/save"),
    ("workbench_slide_templates", "slide_template_catalog", {"project_id": PROJECT}, "GET", "/slide-templates"),
    ("workbench_slides", "replay_slide_plan", {"project_id": PROJECT}, "GET", "/slides"),
])
async def test_each_task_uses_native_capture(tool, label, arguments, expected_method, expected_suffix, tmp_path):
    adapter = NativeCaptureAdapter(label)
    module.configure_client(adapter)
    if tool == "workbench_export_download":
        arguments = {**arguments, "output_path": str(tmp_path / "captured.docx")}
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool(tool, arguments)).data
    assert set(result) == {"message", "reference", "artifacts", "data"}
    assert adapter.calls[-1]["method"] == expected_method
    assert adapter.calls[-1]["path"].endswith(expected_suffix)
    if "project_id" in arguments and tool != "workbench_export_download":
        assert adapter.calls[-1]["project_id"] == PROJECT
    if tool == "workbench_export_download":
        assert Path(result["artifacts"][0]["path"]).read_bytes() == native(label)
        assert Path(result["artifacts"][0]["path"]).is_absolute()
        assert adapter.calls[-1]["params"] == {"area": "manuscript", "name": "清稿.docx"}
    else:
        assert result["data"] == native(label)
        assert result["artifacts"] == []


@pytest.mark.asyncio
async def test_changed_revision_and_document_are_forwarded_without_recomputation():
    adapter = NativeCaptureAdapter("save_manuscript")
    module.configure_client(adapter)
    document = {"title": "Changed caller title", "content": {"type": "doc", "content": [{"type": "blockMath", "attrs": {"latex": "q=x^2"}}]}, "revision": 8}
    original = copy.deepcopy(document)
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool("workbench_manuscript", {"project_id": PROJECT, "action": "save", "document": document, "revision": 11, "reason": "Caller reason"})).data
    assert document == original
    assert adapter.calls[0]["json"] == {**original, "revision": 11, "reason": "Caller reason"}
    assert result["data"] == native("save_manuscript")
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_native_stale_revision_error_is_not_repaired():
    adapter = NativeCaptureAdapter("reject_stale_manuscript_revision")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        with pytest.raises(Exception, match="HTTP 409"):
            await client.call_tool("workbench_manuscript", {"project_id": PROJECT, "action": "save", "document": {"revision": 0, "content": {"type": "doc"}}})
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_missing_conditional_revision_is_clear_without_network():
    adapter = NativeCaptureAdapter("save_manuscript")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        with pytest.raises(Exception, match="revision"):
            await client.call_tool("workbench_manuscript", {"project_id": PROJECT, "action": "save", "document": {"content": {"type": "doc"}}})
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_multipart_file_stays_open_until_native_call_returns():
    adapter = NativeCaptureAdapter("import_editable_markdown")
    module.configure_client(adapter)
    source = EVIDENCE / "data/synthetic_manuscript.md"
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool("workbench_manuscript", {"project_id": PROJECT, "action": "import", "file_path": str(source)})).data
    assert result["data"] == native("import_editable_markdown")
    upload = adapter.open_uploads[0]
    assert upload["open_during_await"]
    assert upload["stream"].closed
    assert upload["bytes"] == source.read_bytes()
    assert upload["field"] == "file"


@pytest.mark.asyncio
async def test_export_defaults_and_pending_job_are_preserved():
    adapter = NativeCaptureAdapter("start_manuscript_pdf")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool("workbench_manuscript_export", {"project_id": PROJECT, "format": "pdf"})).data
    assert adapter.calls[0]["json"] == {"format": "pdf", "review": False, "language": "auto", "document_id": "", "columns": 2}
    assert result["data"] == native("start_manuscript_pdf")
    assert "job_id" in result["data"]
    assert "completed" not in result["message"].lower()


@pytest.mark.asyncio
async def test_slide_export_does_not_manufacture_confirmation():
    adapter = NativeCaptureAdapter("reject_unconfirmed_slide_export")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        with pytest.raises(Exception, match="HTTP 400"):
            await client.call_tool("workbench_slides", {"project_id": PROJECT, "action": "export"})
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["path"].endswith("/slides/export")


@pytest.mark.asyncio
async def test_explicit_slide_choice_and_changed_planning_settings():
    adapter = NativeCaptureAdapter("confirm_synthetic_slide_settings")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool("workbench_slides", {"project_id": PROJECT, "action": "confirm", "template": "beamer-default", "profile": "group"})).data
    assert adapter.calls[0]["json"] == {"template": "beamer-default", "profile": "group", "action": "generate"}
    assert result["data"] == native("confirm_synthetic_slide_settings")


@pytest.mark.asyncio
async def test_fixed_action_enum_rejects_arbitrary_http_operation():
    adapter = NativeCaptureAdapter("replay_slide_plan")
    module.configure_client(adapter)
    async with Client(module.authoring_api_mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("workbench_slides", {"project_id": PROJECT, "action": "raw_http"})
    assert not adapter.calls


@pytest.mark.asyncio
async def test_reference_replace_preserves_selected_identity_and_expected_text():
    adapter = NativeCaptureAdapter("replace_real_reference_metadata")
    module.configure_client(adapter)
    inputs = {"project_id": PROJECT, "action": "replace", "reference_id": "stable-reference", "revision": 3,
              "entry": {"title": "Selected source", "doi": "10.1234/input-only"}, "paragraph": "Caller text [1].", "expected_text": "Old text [1]."}
    async with Client(module.authoring_api_mcp) as client:
        result = (await client.call_tool("workbench_references", inputs)).data
    assert adapter.calls[0]["json"] == {"id": "stable-reference", "revision": 3, "entry": inputs["entry"], "paragraph": "Caller text [1].", "expected_text": "Old text [1]."}
    assert result["data"] == native("replace_real_reference_metadata")


def test_exact_inventory_and_two_line_annotated_tool_format():
    inventory = json.loads((PACKAGE / "reports/tutorial-scanner.json").read_text(encoding="utf8"))
    expected = {x["tool_name"] for x in inventory["tool_review"] if x["owner_module"] == "authoring_api"}
    tree = ast.parse(SOURCE.read_text(encoding="utf8"))
    selected = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.decorator_list]
    assert {n.name for n in selected} == expected
    assert len(selected) == 13
    for n in selected:
        assert len(ast.get_docstring(n).splitlines()) == 2
        assert all(isinstance(a.annotation, ast.Subscript) and isinstance(a.annotation.value, ast.Name) and a.annotation.value.id == "Annotated" for a in n.args.args)


@pytest.mark.asyncio
@pytest.mark.parametrize("download", [False, True])
async def test_actual_shared_client_scopes_native_reads_and_saves_captured_bytes(monkeypatch, tmp_path, download):
    spec = importlib.util.spec_from_file_location("authoring_shared_client_under_test", PACKAGE / "src/client.py")
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    real_async_client = httpx.AsyncClient
    project = native("create_owned_disposable_project")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-only-fixture-token"
        assert request.headers["Origin"] == "https://tutor.example.invalid"
        if request.url.path == "/research/api/projects":
            return httpx.Response(200, json={"projects": [project]})
        if download:
            assert request.url.path.endswith("/slide-preview")
            assert dict(request.url.params) == {"kind": "deck", "page": "2"}
            return httpx.Response(200, content=native("actual_rendered_slide_preview"), headers={"content-type": "image/png"})
        assert request.url.params["dt_workspace"] == project["native_id"]
        return httpx.Response(200, json=native("replay_manuscript_read"))

    monkeypatch.setenv("WORKBENCH_TOKEN", "test-only-fixture-token")
    monkeypatch.setattr(shared.httpx, "AsyncClient", lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs))
    transport = shared.WorkbenchClient()
    module.configure_client(transport)
    try:
        async with Client(module.authoring_api_mcp) as client:
            if download:
                for name in ["first.png", "second.png"]:
                    target = tmp_path / name
                    result = (await client.call_tool("workbench_slides", {"project_id": PROJECT, "action": "preview", "page": 2, "output_path": str(target)})).data
                    assert result["data"]["path"] == str(target)
                    assert result["artifacts"][0]["path"] == str(target)
                    assert target.read_bytes() == native("actual_rendered_slide_preview")
            else:
                result = (await client.call_tool("workbench_manuscript", {"project_id": PROJECT})).data
                assert result["data"] == native("replay_manuscript_read")
    finally:
        await transport.close()
    assert calls


@pytest.mark.asyncio
async def test_figure_patch_and_edit_session_are_forwarded_unchanged():
    adapter = NativeCaptureAdapter("registered_figure_preview_requires_registry")
    module.configure_client(adapter)
    changes = {"objects": {"actual-line-id": {"line_width": 2.3}}, "figure": {"font_size": 14}}
    async with Client(module.authoring_api_mcp) as client:
        with pytest.raises(Exception, match="HTTP 400"):
            await client.call_tool("workbench_figure", {"project_id": PROJECT, "path": "results/synthetic.png", "action": "preview", "revision": 7, "changes": changes, "edit_session": "existing-session"})
    assert adapter.calls[0]["json"]["changes"] == changes
    assert adapter.calls[0]["json"]["revision"] == 7
    assert adapter.calls[0]["json"]["edit_session"] == "existing-session"
