"""Independent synthetic checks of exact delivery helper and Dify code-node bodies.

No production module import, credential access, network request, or mutation.
AST compilation retains the original function and embedded code verbatim.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DELIVERY = ROOT / "integrations/dify-bridge/delivery.py"
CONFIGURE = ROOT / "integrations/dify-bridge/configure_workflow.py"
DELIVERY_TREE = ast.parse(DELIVERY.read_text(encoding="utf8"))
CONFIGURE_TREE = ast.parse(CONFIGURE.read_text(encoding="utf8"))
PROJECT = "a" * 32
RUN = "synthetic-native-run"
OWNER = "synthetic-current-owner"


def helper():
    original = next(node for node in DELIVERY_TREE.body if isinstance(node, ast.FunctionDef) and node.name == "workflow_receipt")
    scope = {"json": json}
    exec(compile(ast.Module(body=[deepcopy(original)], type_ignores=[]), str(DELIVERY), "exec"), scope)
    return scope["workflow_receipt"]


def gate(name):
    original = next(node for node in ast.walk(CONFIGURE_TREE) if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))
    source = ast.literal_eval(original.value)
    scope = {}
    exec(compile(source, f"{CONFIGURE}::{name}", "exec"), scope)
    return scope["main"]


def fixture():
    record = {"recorded": True, "created": "2026-11-01T00:00:00Z",
              "artifacts": [{"path": "project/docs/synthetic.txt", "summary": "Synthetic"}],
              "validation": [{"check": "workbench_readback", "result": "passed", "evidence": "project/docs/synthetic.txt"}]}
    saved = {"status": "saved", "run_id": RUN, "request_id": "synthetic-request", "project_id": PROJECT,
             "standard_version": "current-standards", "artifact": {"path": "project/docs/synthetic.txt", "modified": 0, "size": 7},
             "receipt": record}
    final = {**deepcopy(saved), "processing_history_verified": True, "history_event_id": 41}
    run = {"workflow_run_id": "synthetic-dify-run", "data": {"id": "fallback-run", "status": "succeeded", "outputs": {"receipt": json.dumps(final)}}}
    account = [{"data": {"id": OWNER, "username": "synthetic"}}]
    rules = [{"reference": f"https://workbench.example/research/api/projects/{PROJECT}/agent-context",
              "data": {"project": {"id": PROJECT}, "standard_version": "current-standards", "instructions": "Exact current contract",
                       "skills": [{"id": "synthetic-skill", "content": "Actual original skill content"}]}}]
    history = [{"reference": f"https://workbench.example/research/api/projects/{PROJECT}/review-history",
                "data": {"events": [{"id": 41, "kind": "agent.receipt", "project": PROJECT, "owner": OWNER,
                                      "payload": deepcopy(record)}]}}]
    return saved, final, run, account, rules, history


@pytest.mark.parametrize("as_json", [False, True], ids=["object-output", "json-output"])
def test_exact_helper_success_requires_matching_verified_terminal(as_json):
    saved, final, run, *_ = fixture()
    run["data"]["outputs"]["receipt"] = json.dumps(final) if as_json else final
    original_saved, original_run = deepcopy(saved), deepcopy(run)
    result = helper()(saved, run)
    assert result == {**saved, "workflow_run_id": "synthetic-dify-run", "workflow_status": "succeeded",
                      "processing_history_verified": True, "history_event_id": 41}
    assert saved == original_saved and run == original_run


@pytest.mark.parametrize("status", ["failed", "stopped", "running", "unknown", None])
def test_exact_helper_failure_after_native_save_preserves_saved_status(status):
    saved, _, run, *_ = fixture()
    run["data"]["status"] = status
    run["data"]["error"] = "Synthetic Dify failure after native save"
    result = helper()(saved, run)
    assert result["status"] == "saved" and result["artifact"] == saved["artifact"]
    assert result["workflow_status"] == (status or "unknown")
    assert result["workflow_error"] == "Synthetic Dify failure after native save"
    assert "processing_history_verified" not in result


def test_exact_helper_missing_terminal_data_and_fallback_id():
    saved, _, run, *_ = fixture()
    result = helper()(saved, {})
    assert result["status"] == "saved" and result["workflow_status"] == "unknown"
    assert result["workflow_run_id"] is None and result["workflow_error"]
    del run["workflow_run_id"]
    assert helper()(saved, run)["workflow_run_id"] == "fallback-run"


@pytest.mark.parametrize("value", [None, "", "not JSON", "{}", "[]", [], {}, {"run_id": RUN}],
                         ids=["null", "empty-string", "invalid-json", "empty-object-json", "array-json", "array", "empty-object", "missing-fields"])
def test_exact_helper_invalid_final_output_cannot_report_success(value):
    saved, _, run, *_ = fixture()
    run["data"]["outputs"]["receipt"] = value
    result = helper()(saved, run)
    assert result["status"] == "saved" and result["workflow_status"] == "unverified"
    assert "matching verified processing history" in result["workflow_error"]
    assert "processing_history_verified" not in result


@pytest.mark.parametrize("key,value", [("run_id", "old-run"), ("project_id", "b" * 32),
                                       ("artifact", {"path": "project/other.txt", "modified": 0, "size": 7}),
                                       ("artifact", {"path": "project/docs/synthetic.txt", "modified": 1, "size": 7}),
                                       ("processing_history_verified", False), ("processing_history_verified", 1),
                                       ("history_event_id", ""), ("history_event_id", None)])
def test_exact_helper_mismatched_final_identity_or_history_cannot_pass(key, value):
    saved, final, run, *_ = fixture()
    final[key] = value
    run["data"]["outputs"]["receipt"] = json.dumps(final)
    result = helper()(saved, run)
    assert result["status"] == "saved" and result["workflow_status"] == "unverified"
    assert "processing_history_verified" not in result


@pytest.mark.parametrize("outputs", [None, [], "invalid-output-container"])
def test_exact_helper_invalid_output_container_remains_unverified(outputs):
    saved, _, run, *_ = fixture()
    run["data"]["outputs"] = outputs
    result = helper()(saved, run)
    assert result["status"] == "saved" and result["workflow_status"] == "unverified"


def test_exact_code_nodes_compose_current_native_save_and_history():
    saved, _, run, account, rules, history = fixture()
    context = gate("check_context_source")(account, rules, PROJECT, "current-standards")
    assert context == {"account_id": OWNER, "verified": True}
    native = gate("receipt_source")(json.dumps(saved), 200, PROJECT, RUN, "current-standards")
    verified = gate("check_history_source")(history, native["receipt"], PROJECT, context["account_id"])
    run["data"]["outputs"] = verified
    result = helper()(saved, run)
    assert result["workflow_status"] == "succeeded" and result["processing_history_verified"] is True
    assert result["history_event_id"] == 41


@pytest.mark.parametrize("malformed", [[], [{}], [{"data": {}}], [{"data": []}], [{"isError": True, "data": {}}],
                                      [{"error": "MCP error despite Dify node success", "data": {}}]])
def test_dify_node_success_with_mcp_error_or_empty_result_fails_both_gates(malformed):
    saved, _, _, account, _, _ = fixture()
    with pytest.raises(ValueError):
        gate("check_context_source")(account, malformed, PROJECT, "current-standards")
    with pytest.raises(ValueError):
        gate("check_history_source")(malformed, json.dumps(saved), PROJECT, OWNER)


@pytest.mark.parametrize("field,value", [("owner", "other-owner"), ("project", "b" * 32),
                                        ("kind", "old.kind"), ("created", "old-history-time"),
                                        ("artifacts", [{"path": "project/old.txt"}]),
                                        ("validation", [{"check": "workbench_readback", "result": "failed"}])])
def test_processing_gate_rejects_wrong_owner_project_or_old_receipt(field, value):
    saved, _, _, _, _, history = fixture()
    event = history[0]["data"]["events"][0]
    if field in {"created", "artifacts", "validation"}:
        event["payload"][field] = value
    else:
        event[field] = value
    with pytest.raises(ValueError, match="absent from MCP history"):
        gate("check_history_source")(history, json.dumps(saved), PROJECT, OWNER)


def test_context_gate_rejects_stale_rules_and_wrong_source_project():
    _, _, _, account, rules, _ = fixture()
    for key, value in [("standard_version", "old"), ("project", {"id": "b" * 32}),
                       ("skills", [{"id": "summary-with-no-original"}]), ("instructions", "")]:
        changed = deepcopy(rules)
        changed[0]["data"][key] = value
        with pytest.raises(ValueError):
            gate("check_context_source")(account, changed, PROJECT, "current-standards")
    rules[0]["reference"] = f"https://workbench.example/research/api/projects/{'b' * 32}/agent-context"
    with pytest.raises(ValueError, match="reference differs"):
        gate("check_context_source")(account, rules, PROJECT, "current-standards")


def test_deliver_exact_ast_binds_helper_and_persists_terminal_or_interrupted_receipt():
    service = next(node for node in DELIVERY_TREE.body if isinstance(node, ast.ClassDef) and node.name == "DeliveryService")
    deliver = next(node for node in service.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "deliver")
    calls = [node for node in ast.walk(deliver) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "workflow_receipt"]
    assert len(calls) == 1
    assert ast.unparse(calls[0]) == "workflow_receipt(json.loads(row['receipt']), run)"
    attempt = next(node for node in deliver.body if isinstance(node, ast.Try))
    normal = next(node for node in attempt.body if isinstance(node, ast.If) and ast.unparse(node.test) == "row['receipt']")
    assert [ast.unparse(node) for node in normal.body] == [
        "result = workflow_receipt(json.loads(row['receipt']), run)",
        "self.update(run_id, receipt=json.dumps(result, ensure_ascii=False))", "return result"]
    interrupted = next(node for node in attempt.handlers[0].body if isinstance(node, ast.If) and ast.unparse(node.test) == "row['receipt']")
    original = deepcopy(interrupted.body[0])
    scope = {"json": json, "row": {"receipt": json.dumps(fixture()[0])}}
    exec(compile(ast.Module(body=[original], type_ignores=[]), str(DELIVERY), "exec"), scope)
    assert scope["result"]["status"] == "saved" and scope["result"]["workflow_status"] == "unknown"
    assert "interrupted" in scope["result"]["workflow_error"]
    assert [ast.unparse(node) for node in interrupted.body[1:]] == [
        "self.update(run_id, receipt=json.dumps(result, ensure_ascii=False))", "return result"]
