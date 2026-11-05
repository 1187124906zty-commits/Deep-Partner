"""Write the independent authoring handoff from retained actual check outputs."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

PACKAGE = Path(__file__).resolve().parents[3]
RESULTS = PACKAGE / "tests/results/authoring_api"


def record(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def main():
    implementation = json.loads((PACKAGE / "reports/implementation-authoring_api.json").read_text(encoding="utf8"))
    suite = ET.parse(RESULTS / "pytest.xml").getroot().find("testsuite")
    stdio = json.loads((RESULTS / "stdio-development.json").read_text(encoding="utf8"))
    artifacts = json.loads((RESULTS / "stdio-artifact-comparisons.json").read_text(encoding="utf8"))
    assert suite.attrib["tests"] == "57" and suite.attrib["failures"] == suite.attrib["errors"] == suite.attrib["skipped"] == "0"
    assert stdio["success"] and len(stdio["cases"]) == 34 and all(c["success"] for c in stdio["cases"])
    assert artifacts["success"] and len(artifacts["artifact_comparisons"]) == 7
    tool_checks = {
        "workbench_manuscript": {
            "source": ["server/app.py::manuscript", "server/app.py::save_manuscript", "server/app.py::manuscript_import", "server/app.py::asset_upload"],
            "checks": ["Full live manuscript JSON exact against independent HTTP", "Changed title saves exactly and preserves content/references; stale revision409 does not alter state", "New Markdown import yields the same complete Tiptap tree as direct source; all uploaded PNG bytes agree", "Caller inputs remain unchanged; document content restored"]},
        "workbench_manuscript_templates": {
            "source": ["server/app.py::templates", "server/app.py::manuscript_template_preview", "server/app.py::manuscript_template_source"],
            "checks": ["Every template record and field equals independent catalog", "Changed source/preview and kind selections preserve every original DOCX/PNG byte", "Repeated downloads use disjoint explicit destinations and absolute artifact descriptors", "Missing conditional kind and native404 become MCP errors"]},
        "workbench_manuscript_export": {
            "source": ["server/app.py::manuscript_export", "server/manuscripts.py::export_manuscript", "server/author_profile.py::prepare_preview"],
            "checks": ["Native unmodified job receipt truthfully remains pending until direct polling completes", "Changed columns1/2 and review false/true passed to existing API", "Source language explicitly avoids model/translation calls", "TeX full byte agreement; review ZIP every member byte exact, native source-created preview-date paragraph and full document/comments retained", "Closed format/columns and missing reader selection are MCP errors"]},
        "workbench_export_download": {
            "source": ["server/app.py::download"],
            "checks": ["Full native bytes for manuscript DOCX/PDF and slides PPTX/PDF equal repeated MCP downloads", "DOCX/PPTX ZIP integrity and core members checked; actual deck has three slides", "PDF signatures/EOF checked in addition to full native byte agreement", "Absolute descriptors and byte counts correct; eight repeated downloads isolated", "Missing file404 and closed area validation preserved"]},
        "workbench_references": {
            "source": ["server/app.py::reference_library", "server/app.py::reference_add", "server/app.py::reference_replace", "server/app.py::reference_recommend", "server/related_papers.py::install"],
            "checks": ["Complete records, IDs, DOI metadata and revision equal native library", "Uppercase DOI changed input returns the existing source identity without duplicate addition or revision change", "Missing metadata/stale revision/recommendation identity fail before model use", "Existing source-capture test preserves replacement paragraph, stable ID and expected_text unchanged"]},
        "workbench_journals": {
            "source": ["server/journals.py::install", "server/journals.py::lookup"],
            "checks": ["Full generic catalog and changed en/zh detail records match source after excluding only source-generated checked/metrics_checked timestamps", "No fabricated impact factor/quartile; both remain null", "Year parameter forwarded; short query/missing selection/preview project errors preserved"]},
        "workbench_journal_templates": {
            "source": ["server/template_discovery.py::install", "server/template_discovery.py::discover"],
            "checks": ["Independently fetched official candidate identity/title/URL/source/kind/downloadability retained", "Selected journal and scope exact; fresh guides/search/error provenance retained", "Missing journal, unselected candidate and absent retained file fail as MCP errors"]},
        "workbench_figure": {
            "source": ["server/app.py::figure_read", "server/app.py::figure_preview", "server/app.py::figure_save", "server/figures.py::inspect", "server/reviews.py::image_context"],
            "checks": ["Complete raster state equals direct source, truthfully ready=false", "Changed include_context/start_edit_session composes exact native figure/context results with correct16x16 dimensions", "Unregistered preview/save returns original400; missing revision fails before request", "Source refresh Request/owner defect was corrected by coordinator; actual native two-branch regression inspected"]},
        "workbench_figure_chat": {
            "source": ["server/app.py::figure_chat_history", "server/app.py::figure_chat", "server/app.py::figure_session"],
            "checks": ["Complete native histories exact for existing and changed image keys", "Missing message/session rejected; unassociated session preserves native403", "No model-backed send or external conversation performed"]},
        "workbench_image_review": {
            "source": ["server/app.py::image_review", "server/reviews.py::prepare_review"],
            "checks": ["Fresh corrected native send:false reference captured before MCP invocation", "Both changed image inputs/instructions/crops/annotations pass unchanged, proven by actual safe outbound JSON hook", "Prepared prompt exact against direct source and latest native source-context instruction correct", "Unique IDs/timestamps treated as native call identities, not hardcoded equality", "Blank instruction/missing local image are MCP errors", "Source no-model draft correction and actual two-branch regression inspected"]},
        "workbench_raster": {
            "source": ["server/app.py::save_raster"],
            "checks": ["Both synthetic image inputs yield every pixel equal to caller image and every native normalized output byte equal to direct source", "All16x16x3 RGB bytes decoded with all native PNG filters supported", "Native modified timestamp exact; stale timestamp409 preserves file; original pixels restored", "Missing project image preserves native error"]},
        "workbench_slide_templates": {
            "source": ["server/app.py::slide_templates", "server/app.py::upload_template", "server/app.py::prepare_slide_template", "server/app.py::choose_template", "server/app.py::template_roles"],
            "checks": ["Full catalog/manifests/profiles/layout equals independent live source", "Changed beamer-default/metropolis selection exact and original selection restored", "No implicit confirmation; missing upload source, fixed builtin roles and unknown template preserve errors"]},
        "workbench_slides": {
            "source": ["server/app.py::slides_get", "server/app.py::slides_save", "server/app.py::confirm_presentation", "server/app.py::generate_plan", "server/app.py::slides_export", "server/app.py::slide_preview"],
            "checks": ["Complete native plan exact; changed caller title/section saves verbatim then original plan restored", "Changed real deck page1/page2 and source-template page preserve every PNG byte", "Unconfirmed export/planning rejected before model use; malformed sections/page0 fail as native errors", "No new slides generated or model call started"]},
    }
    counts = Counter()
    errors = Counter()
    direct_count = 0
    for events_path in (RESULTS / "inprocess").glob("*/events.json"):
        for event in json.loads(events_path.read_text(encoding="utf8")):
            if event["source"] == "fastmcp_client":
                (errors if event.get("is_error") else counts)[event["tool"]] += 1
            elif event["source"] == "independent_direct_http":
                direct_count += 1
    sources = ["server/app.py", "server/manuscripts.py", "server/author_profile.py", "server/references.py", "server/journals.py",
               "server/template_discovery.py", "server/reviews.py", "server/figures.py", "server/presentation_catalog.py", "server/slides.py",
               "tests/image_review_draft_acceptance.py", "tests/figure_refresh_acceptance.py"]
    owned_tests = sorted((PACKAGE / "tests/code/authoring_api").glob("*.py"))
    report = {
        "module": "authoring_api", "agent_id": "/root/mcp_verify_authoring", "role": "fresh_independent_verifier",
        "implementation_run_id": "implement_authoring_api", "implementer_agent_id": implementation["agent_id"],
        "started_utc": "2026-11-01T13:10:59.749844Z", "started_utc_basis": "Exact host spawn/assignment UTC supplied by coordinator; task ID returned13:10:59.879345Z, after both implementation gates at13:10:24UTC",
        "ended_utc": datetime.now(timezone.utc).isoformat(), "status": "passed_with_explicit_action_limits",
        "selected_tools": list(tool_checks), "selected_tool_count": len(tool_checks), "verified_tool_count": len(tool_checks),
        "production_files_tested": [record(PACKAGE / "src/tools/authoring_api.py")],
        "tested_files": {str(p.relative_to(PACKAGE)).replace("\\", "/"): record(p)["sha256"] for p in [PACKAGE / "src/tools/authoring_api.py", PACKAGE / "tests/code/test_authoring_api.py", *owned_tests]},
        "test_files": [record(PACKAGE / "tests/code/test_authoring_api.py"), *[record(p) for p in owned_tests]],
        "read_only_shared_dependencies": [record(PACKAGE / name) for name in ["src/client.py", "src/project_mcp.py"]],
        "source_bindings_reviewed": [record(PACKAGE / "repo/research-workbench" / name) for name in sources],
        "source_call_review": tool_checks,
        "source_reuse_judgment": "Every tool traces through its actual _project_call/_upload/_download into the coordinator WorkbenchClient, then the exact original Research Workbench HTTP route and native implementation. No generated numerical/scientific algorithm, copied replacement method, benchmark recomputation, or hardcoded fixture choice exists in production. Wrapper code only adapts fixed action contracts, file handles/PNG encoding, explicit output destinations and the result envelope.",
        "necessary_adaptations": ["Conditional fields validated only when required by native selected action; revision0 and empty changes dictionaries remain admissible", "Multipart files stay open across awaited requests and close afterward", "BinaryPNG bytes encoded only, not recomputed by wrapper", "Explicit caller output destinations atomically saved by shared transport; repeated calls tested with disjoint destinations", "Project/native workspace ownership comes from existing authenticated account inventory; identifiers never fabricated", "Native full result preserved under data; image-context is composed only when caller opts in"],
        "independent_oracles": {"method": "Separate HTTPX client using private existing same-origin session in memory, bypassing generated MCP module for expected values; original source plus stage2 captures separately inspected", "direct_http_evidence_count": direct_count,
                                "per_tool_successful_fastmcp_calls": dict(counts), "per_tool_expected_mcp_errors": dict(errors), "artifact_root": str(RESULTS.resolve())},
        "scientific_comparisons": ["Full JSON structures and metadata/IDs equal direct native values, not merely shape or a few rows", "Only real source clock fields checked/metrics_checked excluded from otherwise complete generic-journal equality", "All downloaded DOCX/PDF/PPTX/PNG bytes equal independent native response bytes", "Every review ZIP member byte equals direct source; ZIP archive container timestamps are intentionally not compared", "Full TeX reviewed document matches source-added date paragraph plus every original manuscript node and complete comments", "All RGB raster pixels equal requested changed inputs, with timestamp-conflict immutability and original pixels restored"],
        "upstream_repairs": json.loads((PACKAGE / "reports/source-amendments.json").read_text(encoding="utf8")).get("followup_amendments", []),
        "upstream_regression_evidence": str((PACKAGE / "reports/source-regression-results.json").resolve()),
        "wrapper_repairs": [], "dependency_changes": [], "exclusions": [],
        "attempts": [
            {"attempt": 1, "scope": "all57 tests", "exit_status": 1, "passed": 48, "failed": 9, "log": "tests/logs/authoring_api/initial-failed-pytest.log", "diagnosis": "Six early upstream500 checks tracked to native auth RemoteProtocolError confirmed in coordinator server logs. Three verifier assumptions/harness issues: Windows evidence path too long; review TeX ZIP container timestamps/native zip suffix; unknown-template is native400. No failed tool was skipped; retry retained assertions and source behavior."},
            {"attempt": 2, "scope": "all57 tests", "exit_status": 1, "passed": 56, "failed": 1, "log": "tests/logs/authoring_api/second-failed-pytest.log", "diagnosis": "All transient500 cases pass. Remaining test expected raw manuscript in review.json; source explicitly prepends prepare_preview metadata. Corrected oracle to exact source-added date paragraph plus every unchanged manuscript block; retained full native ZIP member byte comparison."},
            {"attempt": 3, "scope": "all57 tests after final native corrections", "exit_status": 0, "passed": 57, "failed": 0, "log": "tests/logs/authoring_api/inprocess-pytest.log", "junit": "tests/results/authoring_api/pytest.xml"}],
        "commands": [
            {"command": "research-workbench-env/Scripts/python.exe -m pytest tests/code/test_authoring_api.py tests/code/authoring_api -q --disable-warnings --tb=short --junitxml=tests/results/authoring_api/pytest.xml", "exit_status": 0, "tests": 57, "junit_timestamp": suite.attrib["timestamp"], "duration_seconds": float(suite.attrib["time"])},
            {"command": "research-workbench-env/Scripts/python.exe tests/code/authoring_api/build_acceptance.py --label development", "exit_status": 0, "cases": 34, "positive_tools": 13},
            {"command": "research-workbench-env/Scripts/python.exe tests/code/authoring_api/postcheck_stdio_artifacts.py", "exit_status": 0, "native_byte_equal_artifacts": 7, "raster_rgb_bytes_equal": 768},
            {"command": "research-workbench-env/Scripts/python.exe C:/Users/DEVELOPER/.agents/skills/paper2agent/paper2mcp/scripts/verify_mcp_server.py --server tests/code/authoring_api/stdio_server.py --expected tests/results/authoring_api/expected-tools.json --cases reports/mcp-acceptance-authoring_api.json --require-all-tools --cwd . --report tests/results/authoring_api/stdio-development.json --timeout 60 --call-timeout 180", "exit_status": 0, "cases": len(stdio["cases"]), "passed": len(stdio["cases"])}],
        "stdio_acceptance": {"report": str((RESULTS / "stdio-development.json").resolve()), "cases": str((PACKAGE / "reports/mcp-acceptance-authoring_api.json").resolve()), "artifact_content_comparisons": str((RESULTS / "stdio-artifact-comparisons.json").resolve()), "case_count": 34, "positive_tools": 13, "exact_required_input_schemas": True, "inventory_exact": True, "success": True, "scope": "Real child-process stdio, authoring-only mount of same production module/shared transport; seven actual stdio artifacts compared in full to separate native HTTP and all768 changed raster RGB bytes checked; coordinator must also run merged cases on assembled project_mcp.py and extracted package"},
        "runtime": {"python_executable": sys.executable, "python_version": platform.python_version(), "fastmcp": stdio["fastmcp"], "service": "https://tutor.example.invalid", "private_session": "Existing session path supplied by WORKBENCH_SESSION_FILE; no credential values, headers or cookies persisted", "mutation_scope": "Only exclusively assigned synthetic QA4959b9a67b324c0eb69ab9c67ee897cb; formal05a893386c09449d88366cf6dfdc825f never written"},
        "limitations": ["Positive registered Matplotlib-artist preview/save needs a trusted registry in an exclusive fixture; this verifier tested truthful raster inspection/context and real original unsupported-edit errors. Coordinator native regression covers repaired refresh plumbing; no formal registered plot was mutated.", "No successful model-backed reference recommendation/related generation, figure-chat send/associated agent response, model slide planning, or paid model execution was attempted. Missing-identity/unconfirmed paths fail before those calls.", "Official journal template discovery is live; arbitrary selected-package downloads/positive retained-file retrieval were not repeated. Existing native source and missing-selection/file errors reviewed.", "Builtin slide catalog/selection/actual rendered pages tested; private institutional PPTX upload and role edits were not performed.", "This report is development-module verification. Clean-runtime and assembled/extracted package acceptance belong to coordinator; they are not inferred from imports or this isolated stdio run.", "Original service uses dynamic network/auth providers: initial auth upstream disconnects produced recorded500 responses before recovery; wrapper does not mask or invent successful results.", "Existing pytest-asyncio unset-loop-scope deprecation is nonblocking; no dependency/configuration changes made."],
    }
    target = PACKAGE / "reports/verification-authoring_api.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps({"status": report["status"], "tests": 57, "stdio_cases": len(stdio["cases"]), "report": str(target)}))


if __name__ == "__main__":
    main()
