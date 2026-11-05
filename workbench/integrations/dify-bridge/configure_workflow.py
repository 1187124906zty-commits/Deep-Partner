"""Register and wire the source-bound MCP provider in the existing Dify app."""
from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path("/srv/dify-research")
sys.path.insert(0, str(ROOT / "ops"))
import setup_app as api
api.BASE = "https://tutor.example.invalid/dify/console/api"


def login():
    account = json.loads((ROOT / "private/admin-login.json").read_text())
    value = api.call("POST", "/login", {"email": account["email"], "password": base64.b64encode(account["password"].encode()).decode(), "remember_me": True})
    assert value.get("result") == "success", "Dify console authentication failed"


def node(identifier, kind, title, x, y, **fields):
    return {"id": identifier, "type": "custom", "data": {"type": kind, "title": title, "desc": "", "selected": False, **fields}, "position": {"x": x, "y": y}, "positionAbsolute": {"x": x, "y": y}, "sourcePosition": "right", "targetPosition": "left", "width": 260, "height": 102}


def variable(value):
    # Dify's string editor persists templated strings as mixed inputs. A
    # selector-list string binding is normalized to empty by the frontend.
    return {"type": "mixed", "value": "{{#" + ".".join(value) + "#}}"}


def constant(value):
    return {"type": "constant", "value": value}


def tool(provider, identifier, tool_name, title, x, y, parameters):
    return node(identifier, "tool", title, x, y, provider_id=provider["id"], provider_type="mcp", provider_name=provider["server_identifier"], tool_name=tool_name, tool_label=tool_name.replace("_", " ").title(), tool_configurations={}, tool_parameters={"run_id": variable(["start", "run_id"]), **parameters}, tool_node_version="2", is_team_authorization=True)


def code(identifier, title, x, y, source, variables, outputs):
    return node(identifier, "code", title, x, y, code_language="python3", code=source, variables=[{"variable": name, "value_selector": selector} for name, selector in variables.items()], outputs={name: {"type": type_, "children": None} for name, type_ in outputs.items()})


def main():
    login()
    app_id = json.loads((ROOT / "app.json").read_text())["app_id"]
    provider = json.loads((ROOT / "mcp-registration.json").read_text())
    assert provider["count"] == 37 and provider["server_identifier"] == "research-workbench"
    draft = api.call("GET", f"/apps/{app_id}/workflows/draft")
    # Preserve one concrete pre-change revision for rollback and review.
    before = ROOT / "research-delivery-before-mcp.json"
    if not before.is_file():
        before.write_text(json.dumps(draft, ensure_ascii=False, indent=2))
    graph = deepcopy(draft["graph"])
    original = {n["id"]: n for n in graph["nodes"]}
    assert {"start", "prepare", "commit", "end"} <= original.keys()
    start, prepare, commit, end = [original[name] for name in ("start", "prepare", "commit", "end")]
    positions = {"start": (80, 100), "prepare": (410, 100), "commit": (410, 410), "end": (740, 720)}
    for n in (start, prepare, commit, end):
        x, y = positions[n["id"]]
        n.update(position={"x": x, "y": y}, positionAbsolute={"x": x, "y": y})
        n["data"]["selected"] = False
    parse_source = '''import json, re
def main(body: str, status_code: int) -> dict:
    if status_code != 200:
        raise ValueError("Project and standards check failed: HTTP " + str(status_code))
    context = json.loads(body)
    project = context.get("project_id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", project) or not context.get("standard_version") or not context.get("skills"):
        raise ValueError("Current project or task skill context is incomplete")
    return {"project_id": project, "task": context["task"], "standard_version": context["standard_version"]}
'''
    check_context_source = '''
def result(items, label):
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ValueError(label + " MCP result is missing")
    item = items[0]
    if item.get("isError") or item.get("error") or not isinstance(item.get("data"), dict):
        raise ValueError(label + " MCP call failed")
    return item

def main(account: list, rules: list, project_id: str, standard_version: str) -> dict:
    identity = result(account, "Account")["data"]
    policy = result(rules, "Rules")
    value = policy["data"]
    if not identity.get("id") or not identity.get("username"):
        raise ValueError("MCP current account is incomplete")
    if value.get("project", {}).get("id") != project_id or value.get("standard_version") != standard_version:
        raise ValueError("MCP project or current standards do not match this delivery")
    if not value.get("instructions") or not value.get("skills") or any(not s.get("content") for s in value["skills"]):
        raise ValueError("MCP task skill originals are incomplete")
    if not policy.get("reference", "").endswith("/projects/" + project_id + "/agent-context"):
        raise ValueError("MCP policy reference differs from this project")
    return {"account_id": identity["id"], "verified": True}
'''
    check_history_source = '''import json
def main(history: list, receipt: str, project_id: str, account_id: str) -> dict:
    if not isinstance(history, list) or len(history) != 1 or not isinstance(history[0], dict):
        raise ValueError("MCP processing history is missing")
    item = history[0]
    if item.get("isError") or item.get("error") or not isinstance(item.get("data"), dict):
        raise ValueError("MCP processing history call failed")
    if not item.get("reference", "").endswith("/projects/" + project_id + "/review-history"):
        raise ValueError("MCP processing history belongs to another project")
    value = json.loads(receipt)
    record = value["receipt"]
    events = item["data"].get("events", [])
    matching = [event for event in events if event.get("kind") == "agent.receipt"
        and event.get("project") == project_id and event.get("owner") == account_id
        and event.get("payload", {}).get("created") == record.get("created")
        and event.get("payload", {}).get("artifacts") == record.get("artifacts")
        and event.get("payload", {}).get("validation") == record.get("validation")]
    if not matching:
        raise ValueError("Actual native processing receipt is absent from MCP history")
    value["processing_history_verified"] = True
    value["history_event_id"] = matching[0]["id"]
    return {"receipt": json.dumps(value, ensure_ascii=False), "history_event_id": str(matching[0]["id"])}
'''
    receipt_source = '''import json
def main(body: str, status_code: int, project_id: str, run_id: str, standard_version: str) -> dict:
    if status_code != 200:
        raise ValueError("Native artifact delivery failed: HTTP " + str(status_code))
    value = json.loads(body)
    if value.get("status") != "saved" or value.get("project_id") != project_id or value.get("run_id") != run_id:
        raise ValueError("Delivery has no matching saved current artifact")
    if value.get("standard_version") != standard_version or value.get("receipt", {}).get("recorded") is not True:
        raise ValueError("Delivery rules or processing receipt did not verify")
    artifact = value.get("artifact", {})
    if not artifact.get("path") or not ("revision" in artifact or "modified" in artifact):
        raise ValueError("Actual saved artifact metadata is missing")
    return {"receipt": json.dumps(value, ensure_ascii=False), "artifact": artifact["path"], "project_id": project_id}
'''
    parse = code("parse_context", "核验项目与任务参数", 740, 100, parse_source, {"body": ["prepare", "body"], "status_code": ["prepare", "status_code"]}, {"project_id": "string", "task": "string", "standard_version": "string"})
    account = tool(provider, "mcp_account", "workbench_account", "MCP · 核对当前账户", 1070, 100, {"action": constant("current")})
    rules = tool(provider, "mcp_rules", "workbench_rules", "MCP · 读取项目技能原文", 1070, 410, {"action": constant("context"), "project_id": variable(["parse_context", "project_id"]), "task": variable(["parse_context", "task"])})
    check_context = code("check_mcp_context", "核验 MCP 身份与技能内容", 740, 410, check_context_source, {"account": ["mcp_account", "json"], "rules": ["mcp_rules", "json"], "project_id": ["parse_context", "project_id"], "standard_version": ["parse_context", "standard_version"]}, {"account_id": "string", "verified": "boolean"})
    receipt = code("verify_receipt", "核验实际保存与回读回执", 80, 410, receipt_source, {"body": ["commit", "body"], "status_code": ["commit", "status_code"], "project_id": ["parse_context", "project_id"], "run_id": ["start", "run_id"], "standard_version": ["parse_context", "standard_version"]}, {"receipt": "string", "artifact": "string", "project_id": "string"})
    history = tool(provider, "mcp_history", "workbench_review", "MCP · 回查实际处理记录", 80, 720, {"action": constant("history"), "project_id": variable(["parse_context", "project_id"])})
    check_history = code("check_mcp_history", "核验当前成果的处理记录", 410, 720, check_history_source, {"history": ["mcp_history", "json"], "receipt": ["verify_receipt", "receipt"], "project_id": ["parse_context", "project_id"], "account_id": ["check_mcp_context", "account_id"]}, {"receipt": "string", "history_event_id": "string"})
    end["data"]["outputs"] = [{"variable": "receipt", "value_selector": ["check_mcp_history", "receipt"]}, {"variable": "artifact", "value_selector": ["verify_receipt", "artifact"]}, {"variable": "project_id", "value_selector": ["verify_receipt", "project_id"]}, {"variable": "history_event_id", "value_selector": ["check_mcp_history", "history_event_id"]}, {"variable": "mcp_account", "value_selector": ["mcp_account", "json"]}, {"variable": "mcp_rules", "value_selector": ["mcp_rules", "json"]}, {"variable": "mcp_history", "value_selector": ["mcp_history", "json"]}]
    graph["nodes"] = [start, prepare, parse, account, rules, check_context, commit, receipt, history, check_history, end]
    kinds = {n["id"]: n["data"]["type"] for n in graph["nodes"]}
    order = [n["id"] for n in graph["nodes"]]
    graph["edges"] = [{"id": f"{a}-source-{b}-target", "type": "custom", "source": a, "sourceHandle": "source", "target": b, "targetHandle": "target", "data": {"sourceType": kinds[a], "targetType": kinds[b], "isInIteration": False}} for a, b in zip(order, order[1:])]
    graph["viewport"] = {"x": 0, "y": 30, "zoom": 0.68}
    body = {"graph": graph, "features": draft["features"], "hash": draft["hash"], "conversation_variables": draft.get("conversation_variables", [])}
    saved = api.call("POST", f"/apps/{app_id}/workflows/draft", body)
    result = api.call("GET", f"/apps/{app_id}/workflows/draft")
    assert [(n["id"], n["data"]["type"]) for n in result["graph"]["nodes"]] == [(n["id"], n["data"]["type"]) for n in graph["nodes"]]
    (ROOT / "research-delivery-mcp-draft.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"saved": True, "app_id": app_id, "nodes": len(graph["nodes"]), "mcp_nodes": ["mcp_account", "mcp_rules", "mcp_history"], "provider_id": provider["id"], "save_result_keys": list(saved)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
