"""Finite real Dify-to-workbench tests in an explicitly named verification project."""
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid

ROOT = Path("/srv/dify-research")
ORIGIN = "https://tutor.example.invalid"
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
cookie = ""


def call(base, method, path, body=None, *, auth=True, expected=200):
    headers = {"Content-Type": "application/json", "Origin": ORIGIN}
    if auth:
        headers["Cookie"] = cookie
    request = urllib.request.Request(base + path, method=method, headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    try:
        response = client.open(request, timeout=150)
    except urllib.error.HTTPError as response:
        if response.code != expected:
            raise RuntimeError(f"{method} {path}: HTTP {response.code}: " + response.read().decode()[:700]) from None
        return response.code
    if response.status != expected:
        raise RuntimeError(f"{path}: unexpected HTTP {response.status}")
    raw = response.read()
    return json.loads(raw) if "json" in response.headers.get("content-type", "") else raw.decode()


def main():
    global cookie
    account = json.loads(Path("/srv/deeptutor/migration/admin-login.json").read_text())
    call("http://127.0.0.1:8008", "POST", "/api/auth/login", account, auth=False)
    cookie = "; ".join(c.name + "=" + c.value for c in jar)
    projects = call("http://127.0.0.1:47900", "GET", "/research/api/projects")["projects"]
    project = next((p for p in projects if p["name"] == "Dify 部署与交付验证"), None)
    if project is None:
        project = call("http://127.0.0.1:47900", "POST", "/research/api/projects", {"name": "Dify 部署与交付验证"})
    pid = project["id"]
    bridge = ORIGIN + "/research/dify"
    context = call(bridge, "GET", "/api/context?project_id=" + pid + "&task=review&workspace_id=" + project["native_id"])
    report = {"project_id": pid, "native_workspace_id": project["native_id"], "checks": {}}
    report["checks"]["unauthenticated_rejected"] = call(bridge, "GET", "/api/projects", auth=False, expected=401) == 401
    identifier = "live-" + uuid.uuid4().hex
    text = "# Dify 成果交付验证\n\n这份文件通过真实 Dify Workflow 写入当前研究工作台，并由工作台接口回读。\n"
    body = {"request_id": identifier, "project_id": pid, "workspace_id": project["native_id"],
            "session_id": "deployment-verification", "task": "review", "standard_version": context["standard_version"],
            "artifact": {"type": "file", "path": "docs/dify-integration.md", "content": text, "summary": "实际 Dify 写回与回执验证"},
            "validation": [], "limitations": ["这是软件部署验证，不是科学结果或论文质量验证。"]}
    # Re-running this finite verifier is allowed to reuse the same contents.
    saved = call(bridge, "POST", "/api/deliver", body)
    assert saved["status"] == "saved", saved
    repeated = call(bridge, "POST", "/api/deliver", body)
    assert repeated["run_id"] == saved["run_id"] and repeated["artifact"] == saved["artifact"]
    report["checks"]["idempotent_delivery"] = True
    original = call("http://127.0.0.1:47900", "GET", "/research/api/projects/" + pid + "/file?path=docs/dify-integration.md")
    assert original == text
    report["checks"]["file_readback"] = True
    bad = {**body, "request_id": "wrong-" + uuid.uuid4().hex, "workspace_id": "unrelated-workspace"}
    report["checks"]["workspace_mismatch_rejected"] = call(bridge, "POST", "/api/deliver", bad, expected=409) == 409
    conflict = {**body, "request_id": "stale-" + uuid.uuid4().hex,
                "artifact": {**body["artifact"], "content": "stale overwrite attempt", "expected_modified": 0}}
    rejected = call(bridge, "POST", "/api/deliver", conflict)
    assert rejected["status"] == "failed" and call("http://127.0.0.1:47900", "GET", "/research/api/projects/" + pid + "/file?path=docs/dify-integration.md") == text
    report["checks"]["stale_file_preserved"] = True
    document = call("http://127.0.0.1:47900", "GET", "/research/api/projects/" + pid + "/manuscript")
    prior_revision, template = document["revision"], document["template"]
    document["content"] = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "本段用于验证 Agent 成果经 Dify 写回工作台的可编辑稿件。未开展新的科学研究或实验。"}]}]}
    manuscript = call(bridge, "POST", "/api/deliver", {**body, "request_id": "paper-" + uuid.uuid4().hex, "task": "paper",
        "artifact": {"type": "manuscript", "document": document, "summary": "验证当前稿件结构、模板及版本保留"}})
    assert manuscript["status"] == "saved", manuscript
    current = call("http://127.0.0.1:47900", "GET", "/research/api/projects/" + pid + "/manuscript")
    assert current["content"] == document["content"] and current["revision"] == prior_revision + 1 and current["template"] == template
    report["checks"]["editable_manuscript_and_template"] = True
    key = (ROOT / "private/workflow-key").read_text().strip()
    req = urllib.request.Request("http://127.0.0.1:8088/v1/workflows/run/" + saved["workflow_run_id"], headers={"Authorization": "Bearer " + key})
    run = json.load(urllib.request.urlopen(req, timeout=30))
    assert run["status"] == "succeeded", run
    report["checks"]["real_dify_workflow_succeeded"] = True
    report.update(workflow_run_id=saved["workflow_run_id"], manuscript_revision=current["revision"],
                  file_path=saved["artifact"]["path"], standard_version=context["standard_version"],
                  project_url=ORIGIN + "/research")
    (ROOT / "live-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
