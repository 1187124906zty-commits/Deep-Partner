"""Development MCP checks against saved direct-upstream execution responses."""

import ast
import json
from pathlib import Path
import sys
from urllib.parse import unquote

import httpx
import pytest
from fastmcp import Client


PACKAGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE / "src"))
from client import WorkbenchClient
from tools import workspace_api as workspace

EVIDENCE = PACKAGE / "notebooks/workspace_flows"
LEDGER = {row["label"]: row for row in json.loads((EVIDENCE / "outputs/execution-ledger.json").read_text(encoding="utf-8"))}
PID = "15289d1656da4c9f8b408609c83cc331"
KB = "workspace:ws_84fb4958dab24bd3a17ead349ef301c9:kb:MCP-Execution-Fixture"
DOCUMENT = LEDGER["reader_open"]["value"]["document_id"]
NATIVE_WORKSPACE = "ws_84fb4958dab24bd3a17ead349ef301c9"


def native_response(row, request):
    if "json" in row.get("content_type", ""):
        return httpx.Response(row["status"], json=row["value"], request=request)
    content = row["value"].encode("utf-8") if row.get("content_type", "").startswith("text/") else Path(row["output"]).read_bytes()
    return httpx.Response(row["status"], content=content,
                          headers={"content-type": row["content_type"]}, request=request)


def transport_for(label):
    reference = LEDGER[label]
    observed = []

    def handler(request):
        observed.append(request)
        if request.method == "GET" and request.url.path == "/research/api/projects" and reference["route"] != "/research/api/projects":
            return native_response(LEDGER["projects"], request)
        assert request.method == reference["method"]
        assert request.url.path == unquote(reference["route"])
        for key, value in (reference.get("params") or {}).items():
            expected = str(value).lower() if isinstance(value, bool) else str(value)
            assert request.url.params.get(key) == expected
        if reference.get("json") is not None:
            expected_body = dict(reference["json"])
            if reference["tool"] == "workbench_knowledge_search":
                expected_body.setdefault("knowledge_base", "")
            assert json.loads(request.content) == expected_body
        return native_response(reference, request)

    client = WorkbenchClient("https://tutor.example.invalid")
    client._session = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    return client, observed


CASES = [
    ("workbench_account", {}, "account_current"),
    ("workbench_projects", {}, "projects"),
    ("workbench_files", {"project_id": PID}, "files_initial"),
    ("workbench_revisions", {"project_id": PID}, "revisions_list"),
    ("workbench_rules", {}, "standards"),
    ("workbench_storage", {}, "storage"),
    ("workbench_knowledge_bases", {"project_id": PID}, "kb_fixture_list"),
    ("workbench_knowledge_files", {"project_id": PID, "knowledge_base": KB, "action": "read", "filename": "knowledge-fixture.txt", "view": "text"}, "kb_fixture_text"),
    ("workbench_knowledge_index", {"project_id": PID, "knowledge_base": KB, "action": "run"}, "kb_fixture_final_run"),
    ("workbench_search_sources", {}, "health_sources"),
    ("workbench_web_search", {"q": "Fourier neural operator ICLR 2021"}, "web_search"),
    ("workbench_paper_search", {"project_id": PID, "q": '"Fourier Neural Operator"', "source": "scholar_mcp", "limit": 5}, "scholar_papers"),
    ("workbench_literature", {"project_id": PID}, "literature_initial"),
    ("workbench_literature_organization", {"project_id": PID}, "literature_folders"),
    ("workbench_paper_downloads", {}, "download_worker"),
    ("workbench_reader", {"project_id": PID, "action": "content", "document_id": DOCUMENT}, "reader_blocks"),
    ("workbench_translation", {"project_id": PID, "target": "en"}, "translation_submit"),
    ("workbench_annotations", {"project_id": PID}, "annotations_initial"),
    ("workbench_review", {"project_id": PID}, "review_history_initial"),
    ("workbench_jobs", {"project_id": PID}, "jobs_final"),
    ("workbench_settings", {}, "settings_masked"),
    ("workbench_author_profile", {}, "author_profile_initial"),
    ("workbench_project_import", {"project_id": PID, "file_path": str(EVIDENCE / "data/material-import-fixture.zip")}, "material_import_submit"),
    ("workbench_knowledge_search", {"project_id": PID, "query": "Fourier", "limit": 8}, "knowledge_fourier"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,arguments,label", CASES, ids=[case[0] for case in CASES])
async def test_selected_tools_preserve_native_reference(tool_name, arguments, label):
    transport, observed = transport_for(label)
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool(tool_name, arguments)
        assert result.data["data"] == LEDGER[label]["value"]
        assert result.data["message"]
        assert result.data["reference"].startswith(transport.origin)
        assert result.data["artifacts"] == []
        assert observed
        if label.startswith("kb_fixture_"):
            assert observed[-1].url.params["dt_workspace"] == NATIVE_WORKSPACE
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_inventory_schema_and_exact_two_line_descriptions():
    selected = json.loads((PACKAGE / "reports/tutorial-scanner.json").read_text(encoding="utf-8-sig"))["tool_review"]
    expected = {row["tool_name"]: row["action_schema"]["enum"] for row in selected if row["owner_module"] == "workspace_api"}
    async with Client(workspace.workspace_api_mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == set(expected)
        for tool in tools:
            action = tool.input_schema["properties"]["action"]
            assert action.get("enum", [action.get("const")]) == expected[tool.name]
            assert len(tool.description.strip().splitlines()) == 2
        with pytest.raises(Exception, match="literal|Input|input|current"):
            await client.call_tool("workbench_account", {"action": "login"})
    tree = ast.parse(Path(workspace.__file__).read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name in expected]
    assert len(functions) == 24
    assert all(isinstance(argument.annotation, ast.Subscript) and getattr(argument.annotation.value, "id", "") == "Annotated"
               for node in functions for argument in node.args.args)


@pytest.mark.asyncio
@pytest.mark.parametrize("label,query,limit", [("knowledge_changed_query", "generalization", 2), ("knowledge_no_hit", "mcp_execution_absent_7b3c9", 8)])
async def test_changed_retrieval_inputs_keep_native_source_results(label, query, limit):
    transport, _ = transport_for(label)
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool("workbench_knowledge_search", {"project_id": PID, "query": query, "limit": limit})
        assert result.data["data"] == LEDGER[label]["value"]
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_semantic_input_reuses_native_rag_and_preserves_source_chunk():
    label = "kb_fixture_semantic_after_native_roots"
    transport, _ = transport_for(label)
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool("workbench_knowledge_search", {"project_id": PID, "query": "Fourier operator verification", "mode": "semantic", "knowledge_base": KB, "limit": 2})
        assert result.data["data"] == LEDGER[label]["value"]
        assert "QA_KB_7B3C9" in result.data["data"]["result"]["sources"][0]["content"]
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_native_conflict_is_an_mcp_error():
    transport, _ = transport_for("fixture_stale_write")
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            with pytest.raises(Exception, match="409"):
                await client.call_tool("workbench_files", {"project_id": PID, "action": "write", "path": "docs/mcp-execution-fixture/evidence.txt", "content": "must not replace", "expected_modified": 0, "reason": "Expected conflict fixture"})
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_settings_partial_update_keeps_unspecified_native_fields():
    observed = []
    current = LEDGER["settings_masked"]["value"]

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=current)
        body = json.loads(request.content)
        observed.append(body)
        return httpx.Response(200, json={"saved": True, "configured": True})

    transport = WorkbenchClient("https://tutor.example.invalid")
    transport._session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool("workbench_settings", {"action": "save", "model": "fixture-model", "api_key": "synthetic-test-secret"})
        assert observed[0]["model"] == "fixture-model"
        assert observed[0]["base_url"] == current["base_url"]
        assert observed[0]["translation_prompt"] == current["translation_prompt"]
        assert observed[0]["literature_provider"] == current["literature_provider"]
        assert "synthetic-test-secret" not in json.dumps(result.data)
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_upload_stream_stays_open_during_await(tmp_path):
    content = b"Native multipart upload fixture\n"
    path = tmp_path / "upload.txt"
    path.write_bytes(content)
    observed = []

    def handler(request):
        observed.append(request.content)
        return native_response(LEDGER["fixture_upload"], request)

    transport = WorkbenchClient("https://tutor.example.invalid")
    transport._session = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool("workbench_files", {"project_id": PID, "action": "upload", "path": "docs/mcp-execution-fixture", "file_paths": [str(path)]})
        assert content in observed[0]
        assert b'filename="upload.txt"' in observed[0]
        assert result.data["data"] == LEDGER["fixture_upload"]["value"]
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_repeated_downloads_create_distinct_absolute_artifacts(tmp_path):
    transport, _ = transport_for("fixture_read_v1")
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            arguments = {"project_id": PID, "action": "read", "path": "docs/mcp-execution-fixture/evidence.txt", "output_dir": str(tmp_path)}
            first = (await client.call_tool("workbench_files", arguments)).data
            second = (await client.call_tool("workbench_files", arguments)).data
        a, b = Path(first["artifacts"][0]["path"]), Path(second["artifacts"][0]["path"])
        assert a.is_absolute() and b.is_absolute() and a != b
        assert a.read_text() == b.read_text() == LEDGER["fixture_read_v1"]["value"]
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_missing_recent_job_is_not_reported_completed():
    transport, _ = transport_for("jobs_final")
    workspace.configure_client(transport)
    try:
        async with Client(workspace.workspace_api_mcp) as client:
            result = await client.call_tool("workbench_jobs", {"project_id": PID, "job_id": "absent-from-native-recent-jobs"})
        assert result.data["data"]["status"] == "not_found_in_recent_jobs"
    finally:
        await transport.close()
