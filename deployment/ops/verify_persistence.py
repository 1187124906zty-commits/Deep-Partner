"""Verify saved delivery, native session, and Dify run after process restarts."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.request

ROOT = Path("/srv/dify-research")
parser = argparse.ArgumentParser()
parser.add_argument('--already-restarted', action='store_true')
args = parser.parse_args()
agent = json.loads(Path("/srv/deeptutor/migration/dify-agent-verification.json").read_text())
account = json.loads(Path("/srv/deeptutor/migration/admin-login.json").read_text())
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
req = urllib.request.Request("http://127.0.0.1:8008/api/auth/login", data=json.dumps(account).encode(), headers={"Content-Type": "application/json"})
client.open(req, timeout=15).read()
cookie = "; ".join(c.name + "=" + c.value for c in jar)
with sqlite3.connect(ROOT / "state/deliveries.sqlite3") as db:
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM deliveries WHERE state='saved' AND payload LIKE ? ORDER BY updated DESC LIMIT 1",
                     ("%" + agent["session_id"] + "%",)).fetchone()
    assert row, "Native agent delivery record missing"
    run_id, workflow_id = row["id"], row["workflow_run_id"]
if not args.already_restarted:
    subprocess.run(["docker", "restart", "dify-workbench-bridge", "dify-research-api-1"], check=True, stdout=subprocess.DEVNULL)
for _ in range(45):
    try:
        result = json.load(client.open("http://127.0.0.1:8088/console/api/setup", timeout=3))
        if result.get("step") == "finished":
            break
    except Exception:
        pass
    time.sleep(2)
else:
    raise RuntimeError("Dify API did not recover after restart")


def get(url, auth=None):
    return json.load(client.open(urllib.request.Request(url, headers=auth or {"Cookie": cookie}), timeout=30))


saved = get("http://127.0.0.1:47910/research/dify/api/runs/" + run_id)
assert saved["status"] == "saved" and saved["session_id"] == agent["session_id"]
key = (ROOT / "private/workflow-key").read_text().strip()
run = get("http://127.0.0.1:8088/v1/workflows/run/" + workflow_id, {"Authorization": "Bearer " + key})
assert run["status"] == "succeeded"
session = get("http://127.0.0.1:8008/api/sessions/" + agent["session_id"] + "?dt_workspace=" + agent["workspace_id"])
messages = session.get("messages", [])
assert len(messages) >= 4 and any("saved" in str(m.get("content", "")) for m in messages)
result = {"bridge_restart_retained_receipt": True, "dify_api_restart_retained_workflow_run": True,
          "native_session_messages": len(messages), "native_session_id": agent["session_id"],
          "delivery_run_id": run_id, "workflow_run_id": workflow_id,
          "native_workspace_id": agent["workspace_id"]}
(ROOT / "persistence-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
