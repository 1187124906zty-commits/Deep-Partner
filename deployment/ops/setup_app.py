"""One-time Dify setup, official DSL import, publication, and app-scoped API key."""
import base64
import http.cookiejar
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.request


ROOT = Path("/srv/dify-research")
BASE = "http://127.0.0.1:8088/console/api"
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None):
    headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1:8088"}
    csrf = next((c.value for c in jar if "csrf" in c.name), None)
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(BASE + path, method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with client.open(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.load(exc)
        except ValueError:
            error = {"message": "HTTP " + str(exc.code)}
        raise RuntimeError(json.dumps({"path": path, "status": exc.code, "error": error}, ensure_ascii=False)) from None


def main():
    private = ROOT / "private"
    credentials = private / "admin-login.json"
    if credentials.exists():
        account = json.loads(credentials.read_text())
    else:
        account = {"email": "admin@zty123.me", "name": "科研工作台", "password": "Dify-" + secrets.token_urlsafe(22), "language": "zh-Hans"}
        credentials.write_text(json.dumps(account, ensure_ascii=False, indent=2))
        credentials.chmod(0o600)
    status = call("GET", "/setup")
    if status["step"] == "not_started":
        call("POST", "/setup", account)
    login = call("POST", "/login", {"email": account["email"], "password": base64.b64encode(account["password"].encode()).decode(), "remember_me": True})
    if login.get("result") != "success":
        raise RuntimeError("Dify login not established")
    app_path = ROOT / "app.json"
    if app_path.exists():
        print(json.dumps({"retained_existing_app": json.loads(app_path.read_text())}))
        return
    dsl = (ROOT / "research-delivery.dsl.json").read_text()
    result = call("POST", "/apps/imports", {"mode": "yaml-content", "yaml_content": dsl})
    if result.get("status") == "pending":
        result = call("POST", "/apps/imports/" + result["id"] + "/confirm", {})
    app_id = result.get("app_id")
    if not app_id:
        raise RuntimeError("DSL import did not return app_id: " + json.dumps(result))
    call("POST", "/apps/" + app_id + "/workflows/publish", {"marked_name": "当前工作台接入", "marked_comment": "Native DeepTutor turn and standard workbench delivery"})
    keys = call("POST", "/apps/" + app_id + "/api-keys", {})
    token = keys.get("token") or keys.get("api_key")
    if not token:
        raise RuntimeError("App API key creation did not return a token; response field names: " + str(list(keys)))
    key_file = private / "workflow-key"
    key_file.write_text(token + "\n")
    key_file.chmod(0o600)
    metadata = {"app_id": app_id, "name": "研究工作台 · 技能成果交付", "mode": "workflow", "version": "1.18.0"}
    app_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
