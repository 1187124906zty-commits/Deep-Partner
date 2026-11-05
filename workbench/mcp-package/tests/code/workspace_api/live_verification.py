"""Fresh direct-service oracles, in-process MCP checks, and real stdio acceptance.

Only the coordinator-designated disposable project is mutated. Authentication
is loaded solely by WorkbenchClient; no session contents enter evidence.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4
import zipfile

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "src"))
sys.path.insert(0, str(PACKAGE / "tests/code"))
from fastmcp import Client
from fastmcp.exceptions import ToolError
from client import WorkbenchClient
from tools import workspace_api as workspace
from workspace_api.contracts import REQUIRED, CASES
from workspace_api.support import PID, KB, DOC, ASSET, EVIDENCE

RESULTS = PACKAGE / "tests/results/workspace_api"
LOGS = PACKAGE / "tests/logs/workspace_api"
CASES_PATH = PACKAGE / "reports/mcp-acceptance-workspace_api.json"
EXPECTED_RUNS = 1
RESULTS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)
os.environ["WORKBENCH_SESSION_FILE"] = "C:/Users/DEVELOPER/.codex/research-workbench-mcp-session.json"
os.environ["WORKBENCH_OUTPUT_DIR"] = str(RESULTS / "artifacts")
API = "/research/api/projects/" + PID


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(name, value):
    path = RESULTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


async def request(t, method, route, **kw):
    # A path assertion prevents accidental mutation outside the disposable QA.
    if method not in {"GET", "HEAD"}:
        assert route.startswith(API + "/"), route
    return await t.request(method, route, **kw)


async def prepare():
    record = {"started_utc": utc(), "project_id": PID, "checks": [], "mutations": [], "failures": []}
    direct, transport = WorkbenchClient(), WorkbenchClient()
    workspace.configure_client(transport)
    run = uuid4().hex[:10]
    folder = "docs/mcp-independent-" + run
    path = folder + "/value.txt"
    value = "Independent native value 17\n变量=3.5\n"
    record.update(folder=folder, file=path, text=value, import_marker="docs/mcp-stdio-import-" + run + ".txt")
    try:
        projects = await direct.request("GET", "/research/api/projects")
        qa = next(p for p in projects["projects"] if p["id"] == PID)
        assert KB in qa["config"]["knowledge_bases"]
        before = await request(direct, "GET", API + "/manuscript")
        write("before-manuscript.json", before)
        before_trash = await request(direct, "GET", API + "/trash")
        record["preexisting_trash_ids"] = [r["id"] for r in before_trash["items"]]
        await request(direct, "POST", API + "/folders", json={"path": folder})
        first = await request(direct, "PUT", API + "/file", json={"path": path, "content": value, "reason": "Independent MCP verification"})
        record["mutations"].append({"action": "created_temporary_QA_file", "path": path})
        async with Client(workspace.workspace_api_mcp) as c:
            schema = {s.name: s.input_schema for s in await c.list_tools()}
            assert set(schema) == set(CASES)
            for name, required in REQUIRED.items():
                assert set(schema[name].get("required", [])) == set(required)

            # Each comparison calls the original API directly before invoking MCP.
            stable = [
                ("workbench_account", {"action": "status"}, "/api/auth/status", {}, None),
                ("workbench_rules", {}, "/research/api/standards", {}, None),
                ("workbench_search_sources", {}, "/research/api/search/sources", {}, None),
                ("workbench_settings", {}, "/research/api/api-settings", {}, None),
                ("workbench_author_profile", {}, "/research/api/author-profile", {}, None),
                ("workbench_files", {"project_id": PID, "action": "read", "path": path}, API + "/file", {"path": path}, None),
                ("workbench_literature", {"project_id": PID}, API + "/literature/items", {}, None),
                ("workbench_literature_organization", {"project_id": PID}, API + "/literature/folders", {}, None),
                ("workbench_annotations", {"project_id": PID, "area": "code", "asset": path}, API + "/annotations", {"area": "code", "asset": path}, None),
                ("workbench_reader", {"project_id": PID, "action": "content", "document_id": DOC}, f"/research/reader/{PID}/api/documents/{DOC}/blocks", {}, None),
            ]
            for name, args, route, params, _ in stable:
                expected = await direct.request("GET", route, params=params)
                got = (await c.call_tool(name, args)).data
                assert got["data"] == expected
                record["checks"].append({"tool": name, "comparison": "Full fresh native response equality", "passed": True})

            kbfiles = await direct.native_request("GET", "/api/knowledge-bases/" + KB + "/files", PID)
            actual = (await c.call_tool("workbench_knowledge_files", {"project_id": PID, "knowledge_base": KB})).data["data"]
            assert actual == kbfiles
            kbname = next(f["name"] for f in kbfiles["files"] if f.get("type") == "file" and f["name"].endswith("knowledge-fixture.txt"))
            kbraw = await direct.native_request("GET", "/api/knowledge-bases/" + KB + "/files/" + kbname, PID)
            assert "QA_KB_7B3C9" in kbraw
            record["kb_filename"] = kbname
            record["checks"].append({"tool": "workbench_knowledge_files", "comparison": "Full current native list and original QA marker", "passed": True})

            # Optimistic writes, recoverable revisions and repeated artifacts are composed.
            args = {"project_id": PID, "action": "write", "path": path, "content": value + "changed=23\n", "expected_modified": first["modified"], "reason": "Changed independent input"}
            (await c.call_tool("workbench_files", args)).data
            with_error = False
            try:
                await c.call_tool("workbench_files", {**args, "expected_modified": 0, "content": "must not replace"})
            except ToolError as exc:
                assert "409" in str(exc)
                with_error = True
            assert with_error
            changed = await request(direct, "GET", API + "/file", params={"path": path})
            assert changed == value + "changed=23\n"
            trashed = (await c.call_tool("workbench_files", {"project_id": PID, "action": "trash", "path": path})).data["data"]
            revision = trashed["trash_id"]
            diff = (await c.call_tool("workbench_revisions", {"project_id": PID, "action": "inspect", "revision_id": revision})).data["data"]
            assert diff["kind"] == "text" and diff["before_count"] == 3 and diff["after_count"] == 0
            restored = (await c.call_tool("workbench_revisions", {"project_id": PID, "action": "restore", "revision_id": revision})).data["data"]
            assert restored["restored"] == "project/" + path
            assert await request(direct, "GET", API + "/file", params={"path": path}) == changed
            record["text"] = changed
            outputs = []
            for _ in range(2):
                data = (await c.call_tool("workbench_files", {"project_id": PID, "action": "read", "path": path, "output_dir": str(RESULTS / "artifacts")})).data
                artifact = Path(data["artifacts"][0]["path"])
                assert artifact.read_bytes() == changed.encode("utf-8")
                outputs.append(str(artifact))
            assert outputs[0] != outputs[1]
            record["checks"].append({"tool": "workbench_files/workbench_revisions", "comparison": "Live changed text, 409, trash/diff/restore and two exact unique artifacts", "passed": True, "artifacts": outputs})
            query = "QA_KB_7B3C9"
            retrieval = (await c.call_tool("workbench_knowledge_search", {"project_id": PID, "query": query, "knowledge_base": KB, "limit": 3})).data["data"]
            assert retrieval["query"] == query and retrieval["mode"] == "fulltext-keyword"
            assert any(query in x["excerpt"] for x in retrieval["items"])
            record["checks"].append({"tool": "workbench_knowledge_search", "comparison": "Fresh live source marker appears in project-bound retrieval", "passed": True})

        # Fresh archive preserves the original QA DOCX bytes while adding a fresh
        # disposable project marker; the imported editable document is restored.
        bundle = RESULTS / "inputs/stdio-qa-import.zip"
        bundle.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("workbench-import.json", json.dumps({"title": "Independent MCP runtime QA", "manuscript": "manuscript/source.docx", "source": "Fresh synthetic independent verifier fixture"}))
            archive.writestr("manuscript/source.docx", (EVIDENCE / "data/import-source.docx").read_bytes())
            archive.writestr("project/" + record["import_marker"], "Independent runtime import marker " + run + "\n")
        record["import_archive"] = str(bundle.resolve())
        record["import_marker_text"] = "Independent runtime import marker " + run + "\n"
        record["fresh_archive_members"] = zipfile.ZipFile(bundle).namelist()
        cases = []
        def case(name, tool, arguments, expected, **extras):
            cases.append({"name": name, "tool": tool, "arguments": arguments, "required_inputs": REQUIRED[tool], "expected_subset": expected, **extras})
        def error(name, tool, args, fragment):
            cases.append({"name": name, "tool": tool, "arguments": args, "required_inputs": REQUIRED[tool], "error_contains": fragment})
        p = {"project_id": PID}
        case("account-authenticated", "workbench_account", {"action": "status"}, {"data": {"authenticated": True}})
        case("project-list-owned", "workbench_projects", {}, {"reference": direct.origin + "/research/api/projects", "artifacts": []})
        case("read-current-file", "workbench_files", {**p, "action": "read", "path": path}, {"data": record["text"]})
        case("revisions-list", "workbench_revisions", p, {"reference": direct.origin + API + "/trash", "artifacts": []})
        case("rules-standard-version", "workbench_rules", {}, {"data": {"version": "2026-11-01"}})
        case("storage-native-quota", "workbench_storage", {}, {"data": {"quota": 2147483648}})
        case("knowledge-native-details", "workbench_knowledge_bases", {**p, "action": "details", "knowledge_base": KB}, {"data": {"id": KB, "name": "MCP-Execution-Fixture"}})
        case("knowledge-original-text", "workbench_knowledge_files", {**p, "knowledge_base": KB, "action": "read", "view": "original", "filename": kbname}, {"data": kbraw})
        case("knowledge-index-readiness", "workbench_knowledge_index", {**p, "knowledge_base": KB}, {"data": {"ready": True}})
        case("discovery-source-status", "workbench_search_sources", {}, {"data": {"web": {"configured": True}, "institutions": {"name": "ROR", "configured": True}}})
        case("live-web-discovery", "workbench_web_search", {"q": "Fourier neural operator ICLR 2021"}, {"reference": direct.origin + "/research/api/search/web", "artifacts": []})
        case("live-paper-discovery", "workbench_paper_search", {**p, "q": '"Fourier Neural Operator"', "source": "scholar_mcp", "limit": 2}, {"data": {"query": '"Fourier Neural Operator"', "provider": "scholar_mcp", "limit": 2, "page": 1}})
        case("literature-native-list", "workbench_literature", p, {"reference": direct.origin + API + "/literature/items", "artifacts": []})
        case("literature-folder-assignments", "workbench_literature_organization", p, {"data": {"assignments": {}}})
        case("download-worker-native-pipeline", "workbench_paper_downloads", {}, {"data": {"pipeline": ["local-scansci", "research-cluster-xh5", "user-workspace"]}})
        case("reader-source-options", "workbench_reader", {**p, "action": "content", "document_id": DOC, "view": "options"}, {"data": {"formulaPolicy": "original-vector", "parserVersion": 3}})
        case("annotations-empty-new-source", "workbench_annotations", {**p, "area": "code", "asset": path}, {"data": {"items": []}})
        case("review-source-chat", "workbench_review", {**p, "action": "chat_history", "area": "paper"}, {"reference": direct.origin + API + "/review-chat", "artifacts": []})
        case("absent-job-preserved", "workbench_jobs", {**p, "job_id": "independent-no-such-job"}, {"data": {"status": "not_found_in_recent_jobs", "job_id": "independent-no-such-job"}})
        case("settings-native-availability", "workbench_settings", {}, {"data": {"native_available": True}})
        profile = await direct.request("GET", "/research/api/author-profile")
        case("author-native-profile", "workbench_author_profile", {}, {"data": {"purpose": profile["purpose"]}})
        case("knowledge-project-marker", "workbench_knowledge_search", {**p, "query": query, "knowledge_base": KB, "limit": 3}, {"data": {"query": query, "mode": "fulltext-keyword"}})
        # Positive asynchronous assertions are supplemented by final native jobs
        # and exact imported file/document checks, rather than equating queued to completed.
        case("fresh-synthetic-import", "workbench_project_import", {**p, "file_path": str(bundle.resolve())}, {"reference": direct.origin + API + "/import", "message": "Native Workbench result", "artifacts": []})
        case("tiny-native-translation", "workbench_translation", {**p, "target": "en"}, {"reference": direct.origin + API + "/manuscript/translate", "message": "Native Workbench result", "artifacts": []})
        for i in range(2):
            case("unique-file-artifact-" + str(i), "workbench_files", {**p, "action": "read", "path": path, "output_dir": str(RESULTS / "artifacts")}, {"data": {"bytes": len(record["text"].encode("utf-8"))}}, min_artifacts=1, artifact_root=str(RESULTS / "artifacts"), unique_artifacts=True)
        for i in range(2):
            case("unique-kb-artifact-" + str(i), "workbench_knowledge_files", {**p, "knowledge_base": KB, "action": "read", "view": "original", "filename": kbname, "output_dir": str(RESULTS / "artifacts")}, {"data": {"bytes": len(kbraw.encode("utf-8"))}}, min_artifacts=1, artifact_root=str(RESULTS / "artifacts"), unique_artifacts=True)
        error("required-project-input", "workbench_files", {}, "project_id")
        error("invalid-action-enum", "workbench_account", {"action": "sign-in"}, "action")
        error("invalid-web-query", "workbench_web_search", {"q": "x"}, "400")
        error("missing-project-file", "workbench_files", {**p, "action": "read", "path": folder + "/absent.txt"}, "404")
        error("native-stale-write", "workbench_files", {**p, "action": "write", "path": path, "content": "must not replace", "expected_modified": 0}, "409")
        error("native-unbound-knowledge", "workbench_knowledge_search", {**p, "query": "Fourier", "knowledge_base": "not-project-bound"}, "403")
        error("unavailable-project-scope", "workbench_files", {"project_id": "independent-nonexistent-project", "action": "list"}, "404")
        # Import has a real asynchronous prerequisite. Put it before the read-only
        # cases; translation is last, then finalize verifies both terminal jobs.
        import_case = next(x for x in cases if x["tool"] == "workbench_project_import")
        translation_case = next(x for x in cases if x["tool"] == "workbench_translation")
        cases = [import_case] + [x for x in cases if x not in (import_case, translation_case)] + [translation_case]
        CASES_PATH.parent.mkdir(parents=True, exist_ok=True)
        CASES_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write("expected-tools.json", sorted(CASES))
        record["ended_utc"] = utc()
        record["success"] = True
        write("live-preparation.json", record)
        print(json.dumps({"success": True, "live_checks": len(record["checks"]), "acceptance_cases": len(cases), "run": run, "cases": str(CASES_PATH)}))
    except Exception as exc:
        record["failures"].append({"type": type(exc).__name__, "message": str(exc)[:700]})
        record["ended_utc"] = utc()
        write("live-preparation-failed.json", record)
        raise
    finally:
        await direct.close()
        await transport.close()


async def check_jobs(label="current"):
    """Retain completed job checkpoints between sequential runtime validations."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", label):
        raise ValueError("label must contain only letters, numbers, underscores or hyphens")
    prep = json.loads((RESULTS / "live-preparation.json").read_text(encoding="utf-8"))
    kinds = {"material-import", "manuscript-translate"}
    collected = {}
    # Native /jobs exposes only 20 recent records. Preserve already-checked
    # earlier runtime jobs if the full integration creates additional jobs.
    for path in RESULTS.glob("runtime-jobs-*.json"):
        saved = json.loads(path.read_text(encoding="utf-8"))
        for job in saved.get("jobs", []):
            if job.get("created", "") >= prep["ended_utc"]:
                collected[job["id"]] = job
    t = WorkbenchClient()
    try:
        for _ in range(35):
            rows = (await request(t, "GET", API + "/jobs"))["jobs"]
            for job in rows:
                if job.get("created", "") >= prep["ended_utc"] and job["kind"] in kinds:
                    collected[job["id"]] = job
            counts = {kind: sum(x["kind"] == kind for x in collected.values()) for kind in kinds}
            if all(counts[kind] >= EXPECTED_RUNS for kind in kinds) and all(x["status"] in {"completed", "failed", "interrupted"} for x in collected.values()):
                break
            await asyncio.sleep(2)
        outcome = {"checked_utc": utc(), "expected_runs": EXPECTED_RUNS, "counts": counts, "jobs": list(collected.values())}
        outcome["success"] = all(counts[kind] >= EXPECTED_RUNS for kind in kinds) and all(x["status"] == "completed" for x in collected.values())
        write("runtime-jobs-" + label + ".json", outcome)
        assert outcome["success"], "At least one runtime import/translation has not completed successfully; retained job checkpoint identifies it"
        return outcome
    finally:
        await t.close()


async def finalize():
    r = json.loads((RESULTS / "live-preparation.json").read_text(encoding="utf-8"))
    out = {"started_utc": utc(), "checks": [], "cleanup": [], "success": False}
    t = WorkbenchClient()
    try:
        # Retain actual async terminal states and bound result evidence.
        checked = await check_jobs("final")
        jobs = sorted(checked["jobs"], key=lambda x: x["created"], reverse=True)
        import_job = next((j for j in jobs if j["kind"] == "material-import"), None)
        translation_job = next((j for j in jobs if j["kind"] == "manuscript-translate"), None)
        write("native-acceptance-jobs.json", {"import": import_job, "translation": translation_job, "all_runs": checked})
        assert import_job and import_job["status"] == "completed", import_job
        assert translation_job and translation_job["status"] == "completed", translation_job
        marker = await request(t, "GET", API + "/file", params={"path": r["import_marker"]})
        assert marker == r["import_marker_text"]
        imported = await request(t, "GET", API + "/manuscript")
        assert imported["title"] == "Independent MCP runtime QA"
        assert imported.get("translation", {}).get("content")
        write("imported-manuscript-result.json", imported)
        out["checks"].append({"check": "All checked runtime imports and tiny translations completed; exact final marker and editable translated content exist", "passed": True, "completed_job_counts": checked["counts"]})
        artifacts = list((RESULTS / "artifacts").rglob("value.txt"))
        assert len(artifacts) >= 4
        assert all(p.read_bytes() == r["text"].encode("utf-8") for p in artifacts)
        kbf = list((RESULTS / "artifacts").rglob("knowledge-fixture.txt"))
        assert len(kbf) >= 2
        expected = (EVIDENCE / "outputs/execution-ledger.json").read_text(encoding="utf-8")
        expected = next(x["value"] for x in json.loads(expected) if x["label"] == "kb_fixture_raw").encode("utf-8")
        assert all(p.read_bytes() == expected for p in kbf)
        out["checks"].append({"check": "Every live and stdio file/KB artifact equals complete original bytes", "passed": True, "file_artifacts": len(artifacts), "kb_artifacts": len(kbf)})
        out["success"] = True
    finally:
        before = json.loads((RESULTS / "before-manuscript.json").read_text(encoding="utf-8"))
        current = await request(t, "GET", API + "/manuscript")
        await request(t, "PUT", API + "/manuscript", json={**before, "revision": current["revision"], "reason": "Restore QA source after independent runtime acceptance"})
        restored = await request(t, "GET", API + "/manuscript")
        fields = ["title", "template", "content", "comments", "references", "translation"]
        assert {k: restored.get(k) for k in fields} == {k: before.get(k) for k in fields}
        out["cleanup"].append({"action": "restored original QA manuscript fields", "passed": True})
        for name in [r["folder"], r["import_marker"]]:
            result = await request(t, "DELETE", API + "/file", params={"path": name})
            out["cleanup"].append({"action": "moved temporary QA input to native recoverable trash", "path": name, "trash_id": result["trash_id"]})
        out["ended_utc"] = utc()
        write("live-finalization.json", out)
        await t.close()
    print(json.dumps({"success": out["success"], "checks": len(out["checks"]), "cleanup": len(out["cleanup"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "check", "finalize"])
    parser.add_argument("--run-dir", type=Path, help="Isolated integration evidence directory; default retains development paths")
    parser.add_argument("--expected-runs", type=int, default=1, help="Cumulative import/translation pairs expected for check/finalize")
    parser.add_argument("--label", default="current", help="Checkpoint label for check, such as project, clean or zip")
    args = parser.parse_args()
    if args.expected_runs < 1:
        parser.error("--expected-runs must be positive")
    EXPECTED_RUNS = args.expected_runs
    if args.run_dir is not None:
        RESULTS = args.run_dir.expanduser().resolve()
        RESULTS.mkdir(parents=True, exist_ok=True)
        CASES_PATH = RESULTS / "mcp-acceptance-workspace_api.json"
        os.environ["WORKBENCH_OUTPUT_DIR"] = str(RESULTS / "artifacts")
    if args.phase == "prepare":
        asyncio.run(prepare())
    elif args.phase == "finalize":
        asyncio.run(finalize())
    else:
        checked = asyncio.run(check_jobs(args.label))
        print(json.dumps({"success": checked["success"], "counts": checked["counts"], "label": args.label}))
