"""Assemble independent verification evidence without contacting the service."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "tests/code"))
from workspace_api.contracts import CASES, CHANGED, REQUIRED
from workspace_api.support import PID


def read(path):
    return json.loads((PACKAGE / path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256((PACKAGE / path).read_bytes()).hexdigest()


def main():
    result = "tests/results/workspace_api/"
    logs = "tests/logs/workspace_api/"
    impl = read("reports/implementation-workspace_api.json")
    ledger = read("notebooks/workspace_flows/outputs/execution-ledger.json")
    stdio = read(result + "stdio-development-attempt-1.json")
    prep = read(result + "live-preparation.json")
    final = read(result + "live-finalization.json")
    entry = read(result + "full-production-entrypoint.json")
    binary = read(result + "live-artifact-comparisons.json")
    accept = read("reports/mcp-acceptance-workspace_api.json")
    suite = ET.parse(PACKAGE / result / "pytest-junit.xml").getroot().find("testsuite")
    assert int(suite.attrib["tests"]) == 198 and int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
    assert all(x["success"] for x in [stdio, prep, final, entry])
    assert len(stdio["cases"]) == 35 and all(x["success"] for x in stdio["cases"])
    assert set(CASES) == {r["tool"] for r in accept if "error_contains" not in r}
    assert set(CASES) == {x["tool_name"] for x in impl["tool_mappings"]}
    files = []
    for relative in ["src/tools/workspace_api.py", "src/client.py", "src/project_mcp.py", "src/tools/authoring_api.py"]:
        files.append({"path": str(PACKAGE / relative), "relative_path": relative, "sha256": digest(relative),
                      "ownership": "owned module" if relative.endswith("workspace_api.py") else "read-only shared dependency",
                      "coverage": "import/inventory only; authoring behavior belongs to its verifier" if relative.endswith("authoring_api.py") else "actual FastMCP, native HTTP and/or stdio execution"})
    assert files[0]["sha256"] == "77d622ce1ac778c7f236a01b356e84aa198cdb96e9b819687cfb0e984a2f6ce0"
    bindings = {b["path"] for x in impl["tool_mappings"] for b in x["source_bindings"]}
    source_hashes = {name: digest("repo/research-workbench/" + name) for name in sorted(bindings)}
    nonfinite = []
    def scan(x, where):
        if isinstance(x, float) and not math.isfinite(x):
            nonfinite.append(where)
        elif isinstance(x, dict):
            for key, value in x.items():
                scan(value, where + "/" + key)
        elif isinstance(x, list):
            for i, value in enumerate(x):
                scan(value, where + "/" + str(i))
    for row in ledger:
        scan(row["value"], row["label"])
    assert nonfinite == []
    tool_checks = []
    for mapping in impl["tool_mappings"]:
        name = mapping["tool_name"]
        tool_checks.append({"tool": name, "source_bindings_reviewed": mapping["source_bindings"],
                            "reference_cases": [{"label": label, "native_status": next(r["status"] for r in ledger if r["label"] == label)} for label, _ in CASES[name]],
                            "full_reference_equality": True, "required_inputs": REQUIRED[name],
                            "new_changed_contract": name in CHANGED,
                            "other_changed_inputs": "Alternate native actions/queries/defaults when supported; singleton reads instead exercise invalid actions/upstream failures",
                            "missing_invalid_inputs": "FastMCP ToolError for invalid action, missing schema-required inputs, injected HTTP503 and relevant native/action failures",
                            "unchanged_user_inputs_checked": True,
                            "test_file": str(PACKAGE / "tests/code/workspace_api" / ("test_" + name + ".py"))})
    commands = []
    def command(cmd, exit_code, outcome, log, **kw):
        commands.append({"command": cmd, "exit_code": exit_code, "outcome": outcome, "log": str(PACKAGE / logs / log), **kw})
    base_test = "research-workbench-env/Scripts/python.exe -X utf8 -m pytest "
    tail = " -q --tb=short -o asyncio_default_fixture_loop_scope=function"
    command(base_test + "tests/code/workspace_api" + tail, 1, "108 passed, 2 independent test input/oracle mistakes; production unchanged", "pytest-attempt-1.log")
    command(base_test + "tests/code/workspace_api" + tail, 0, "110 passed", "pytest-attempt-2.log")
    command(base_test + "tests/code/workspace_api tests/code/test_workspace_api.py" + tail, 1, "167 passed, 1 shared client Windows staging-path defect", "pytest-attempt-3.log")
    command(base_test + "tests/code/workspace_api tests/code/test_workspace_api.py" + tail, 0, "168 passed after coordinator repair; failing regression unchanged", "pytest-attempt-4.log")
    command(base_test + "tests/code/workspace_api tests/code/test_workspace_api.py" + tail + " --junitxml=tests/results/workspace_api/pytest-junit.xml", 0, "198 passed in 4.79 seconds; 165 independent tests and 33 existing implementation regression checks", "pytest-final.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_verification.py prepare", 0, "13 fresh live comparison groups; QA write/conflict/history/artifact lifecycle verified; 35 cases prepared", "live-preparation-attempt-1.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 C:/Users/DEVELOPER/.agents/skills/paper2agent/paper2mcp/scripts/verify_mcp_server.py --server tests/code/workspace_api/stdio_server.py --expected tests/results/workspace_api/expected-tools.json --cases reports/mcp-acceptance-workspace_api.json --require-all-tools --cwd . --report tests/results/workspace_api/stdio-development-attempt-1.json --call-timeout 90", 0, "35/35 strict real stdio cases passed; all 24 tools have positive assertions", "stdio-development-attempt-1.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_verification.py finalize", 0, "Actual import and translation COMPLETED, exact marker/artifacts verified, QA source manuscript restored", "live-finalization-attempt-1.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_full_entrypoint.py", 0, "Actual src/project_mcp.py stdio: 37 tools, all 24 workspace schemas, 2 fresh live calls passed", "full-production-entrypoint.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_verification.py check --label development --expected-runs 1", 0, "New read-only runtime checkpoint phase found and retained the actual completed import/translation pair", "runtime-jobs-development.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_artifacts.py (first supplemental attempt)", -1, "Owned Python child stopped after more than four minutes without a complete source PDF; failure evidence retained", "live-artifact-comparisons.log")
    command("research-workbench-env/Scripts/python.exe -X utf8 tests/code/workspace_api/live_artifacts.py (bounded supplemental retry)", 0, "PNG passed twice; full native PDF transfers exceeded bound at both endpoints. Comparison report success:false. Script then returned zero despite the false comparison result; its future exit behavior was corrected without relabeling this retained run.", "live-artifact-comparisons-attempt-2.log", comparison_success=False)
    now = datetime.now(timezone.utc).isoformat()
    report = {
        "module": "workspace_api", "verifier": "/root/mcp_verify_workspace", "agent_id": "/root/mcp_verify_workspace",
        "implementation_run_id": "implement_workspace_api", "implementation_agent": "/root/mcp_environment",
        "implementation_ended_utc": impl["ended_utc"], "started_utc": "2026-11-01T13:11:07+00:00", "ended_utc": now,
        "status": "verified_with_explicit_live_transfer_limits", "success": True, "fresh_after_all_implementers": True,
        "scope": "24 decorated workspace tools; native-source fidelity; per-tool tests; actual QA service; strict module stdio; full production stdio entry point",
        "runtime": {"python": str(PACKAGE / "research-workbench-env/Scripts/python.exe"), "python_version": platform.python_version(), "fastmcp": importlib.metadata.version("fastmcp"), "httpx": importlib.metadata.version("httpx")},
        "tested_files": files, "read_only_shared_dependencies": [x for x in files if x["ownership"].startswith("read-only")],
        "source_snapshot_hashes": source_hashes,
        "source_snapshot_note": "Read-only snapshot; coordinator separately records scoped live upstream amendments. Earlier semantic failures remain in the immutable executor ledger. No snapshot or execution oracle edited here.",
        "source_call_review": tool_checks,
        "wrapper_quality": {
            "source_reuse": "Traced each action through actual wrapper HTTP calls to reviewed server/native implementations, reader UI protocol and project-scoped native RAG bridge. Imports/URLs alone were not used as reuse evidence.",
            "scientific_transformations": [], "duplicate_formulas_or_recomputation": False, "example_hardcoding": False,
            "necessary_adaptations": ["Annotated flat inputs and source-backed Literal actions", "Required action fields and native upload caps", "Actual owned project/native workspace resolution", "Bound-KB original read guard", "Open multipart handles during await", "Native provider selection JSON fields", "Fresh UUID artifact children", "Partial settings/profile preservation", "Recent-job missing status without invented completion"],
            "format": "All 24 exact selected tools; per-parameter Annotated descriptions; two-line docstrings; message/reference/artifacts/data returns",
            "parameter_default_fidelity": "Native supported defaults retained. Current masked settings/profile fetched only to preserve unspecified native replacement fields. Pending and failed source states remain pending/failed."
        },
        "scientific_comparisons": {
            "nature": "Application protocol conversion: full native JSON, source text, bytes, IDs and provenance are the preservation contract; no numerical method was invented.",
            "reference_ledger": str(PACKAGE / "notebooks/workspace_flows/outputs/execution-ledger.json"), "reference_cases": 86,
            "comparison": "Full nested values, identifiers, metadata, scores, text and available binary fixtures; no shape-only comparators",
            "floating_tolerance": "Exact native serialization preservation; no recomputation/rounding", "nonfinite_reference_values": nonfinite,
            "changed_inputs": "16 additional independent source-contract properties, alternate native actions/queries, changed project/native scope, live optimistic write/conflict/history composition and 30 action-specific missing inputs",
            "artifact_composition": ["File write/read/trash/diff/restore consumes actual returned revision ID", "Bound-KB original delivery", "Reader options/processing/translations ordered protocol", "Existing/absent recent job filters", "Fresh import exact marker then actual completed tiny translation"],
            "complete_png_live_comparison": binary["comparisons"], "incomplete_live_pdf_comparisons": binary["failures"]
        },
        "tests": {"total": 198, "passed": 198, "failed": 0, "skipped": 0, "independent_tests": 165, "existing_regression_tests": 33, "per_tool_test_files": 24, "junit": str(PACKAGE / result / "pytest-junit.xml"), "final_log": str(PACKAGE / logs / "pytest-final.log")},
        "attempts_and_repairs": {"suite_runs": 5, "maximum_repair_attempts_for_one_tool": 2, "production_edits_in_owned_module": 0, "source_oracle_edits": 0,
            "repairs": [
                {"tools": ["workbench_literature", "workbench_review"], "kind": "Independent test setup", "detail": "literature/file has no library parameter; executor's unused field is explicitly ignored with source attribution. Review chat reference is area=literature, so exact input fixed from default paper. Full native value/byte assertions retained."},
                {"tools": ["workbench_literature", "shared artifact transport"], "kind": "Real bug repaired by coordinator in shared client", "detail": "Windows long preview filename failed because temporary basename duplicated target name plus UUID. Shared _save now uses only .<uuid>.part in same parent; unchanged regression passes."}
            ]},
        "commands": commands,
        "live_service": {"origin": "https://tutor.example.invalid", "project_id": PID,
            "credential_source": "WORKBENCH_SESSION_FILE passed to shared WorkbenchClient only; private session never printed/copied",
            "formal_project_id": "05a893386c09449d88366cf6dfdc825f", "formal_project_writes": 0,
            "allowed_mutations": "Only designated QA project; reversible files/history plus tiny synthetic import/translation",
            "preparation": str(PACKAGE / result / "live-preparation.json"), "terminal_jobs": str(PACKAGE / result / "native-acceptance-jobs.json"), "finalization": str(PACKAGE / result / "live-finalization.json"),
            "cleanup_verified": final["cleanup"],
            "retained_native_effects": "Recoverable trash/history, jobs and import metadata remain in disposable QA. Existing synthetic source DOCX bytes reused. Title/template/content/comments/references/translation restored; revision/time advances remain."
        },
        "runtime_acceptance": {
            "cases": str(PACKAGE / "reports/mcp-acceptance-workspace_api.json"), "case_file_sha256": digest("reports/mcp-acceptance-workspace_api.json"),
            "module_stdio_report": str(PACKAGE / result / "stdio-development-attempt-1.json"), "all_tools_positive": 24, "positive_cases": 28, "expected_errors": 7, "cases_passed": 35, "strict_require_all_tools": True,
            "required_inputs_independently_checked": True, "full_production_entrypoint_report": str(PACKAGE / result / "full-production-entrypoint.json"), "full_production_inventory_count": 37,
            "final_relocated_fresh_installation": "Coordinator-owned, not claimed here",
            "setup_for_final_runtime": "Use the development interpreter: tests/code/workspace_api/live_verification.py prepare --run-dir tests/results/workspace_api/final-integration. It writes an isolated mcp-acceptance-workspace_api.json there and preserves this report, accepted development cases and development result files. Run the same generated cases sequentially in the project, clean and ZIP runtimes.",
            "between_runtimes": "Run live_verification.py check --run-dir tests/results/workspace_api/final-integration --expected-runs N --label project|clean|zip with N=1,2,3 before the next runtime. It verifies native terminal completion and retains all pairs even if /jobs latest20 rolls over.",
            "teardown_for_final_runtime": "Run live_verification.py finalize --run-dir tests/results/workspace_api/final-integration --expected-runs 3 once after three runtimes. Development fixtures were already cleaned; old temporary paths require fresh prepare. Default prepare without --run-dir overwrites development cases/preparation, so final integration must use the isolated flag.",
            "relocation": "Setup resolves PACKAGE from its own location, rebinding local archive/output paths. It needs the small retained notebooks/workspace_flows/data/import-source.docx fixture."
        },
        "exclusions": [], "deferred_tools": [],
        "limits": [
            "Full 2,436,198-byte original PDF body equality did not complete within bounded live trials. Both native endpoints returned HTTP200 and partial bytes; no partial response was represented as a complete original. Saved 1,024-byte PDF prefix establishes only its bounded native fixture.",
            "Complete PNG preview was compared byte-for-byte (86,851 bytes, 490x634) twice; native project/KB text originals were compared fully with unique local artifacts through HTTP/MCP/stdio.",
            "Live calls do not cover every write action/provider. Account setting/profile saves, discovery/download queue mutations, indexing retry/cancel, full reader translation, and model-intensive reviews primarily use saved execution or independent source-contract tests.",
            "Real provider/backend availability remains external. Crossref HTTP500 and earlier semantic failures are retained/propagated. Discovery is not relabeled full-text verification.",
            "Actual completed tiny import/translation jobs establish that QA workflow only; general full-paper translation quality is not claimed.",
            "No dependency changes. Final relocated installation and full 37-tool acceptance remain coordinator-owned."
        ]
    }
    (PACKAGE / "reports/verification-workspace_api.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PACKAGE / result / "source-review-summary.json").write_text(json.dumps({"source_hashes": source_hashes, "tools": tool_checks, "reviewer": report["verifier"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "status": report["status"], "tests": 198, "tools": 24, "stdio_cases": 35, "ended_utc": now, "tested_files": files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
