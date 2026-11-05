"""Register this owner's Windows desktop tool bridge without exposing a TCP port."""
from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import sys
import urllib.request
import urllib.error
import http.cookiejar
import subprocess
import hmac
import http.client
from pathlib import Path

ROOT = Path("/srv/deeptutor")
SYSTEM = ROOT / "data/system"
MCP = ROOT / "data/user/settings/mcp.json"


class BridgeConflict(RuntimeError):
    pass


def verify_existing_bridge(uds: Path, token: str) -> None:
    """Reuse only the same credential and a live, authenticated tool endpoint."""
    secret = SYSTEM / "desktop-bridge-token"
    if not secret.is_file() or not hmac.compare_digest(secret.read_text().strip(), token):
        raise BridgeConflict("另一台设备已连接电脑工具，请先在原设备断开后再连接。")
    connection = http.client.HTTPConnection("localhost", timeout=4)
    try:
        stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stream.settimeout(4)
        stream.connect(str(uds))
        connection.sock = stream
        connection.request("POST", "/mcp", json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/list"}),
            {"Authorization":"Bearer " + token,"Content-Type":"application/json"})
        response = connection.getresponse()
        body = json.loads(response.read(4 * 1024 * 1024))
        if response.status != 200 or body.get("error"):
            raise BridgeConflict("已有电脑通道未通过身份核验，请关闭旧桌面程序后重新连接。")
        tools = body.get("result", {}).get("tools", [])
        if not any(tool.get("name") == "project_import" for tool in tools):
            raise BridgeConflict("已有电脑通道需要更新，请关闭旧桌面程序并打开当前版本。")
    except (OSError, ValueError, http.client.HTTPException) as error:
        raise BridgeConflict("已有电脑通道暂时无法使用，请关闭旧桌面程序后重新连接。") from error
    finally:
        connection.close()


def atomic_json(path: Path, value: dict) -> None:
    previous = path.stat() if path.exists() else None
    temp = path.with_suffix(path.suffix + ".desktop-tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(temp, 0o600)
    if previous and os.geteuid() == 0:
        os.chown(temp, previous.st_uid, previous.st_gid)
    os.replace(temp, path)


def enroll() -> None:
    request = json.load(sys.stdin)
    token = request.get("token", "")
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        raise ValueError("Invalid desktop token")
    SYSTEM.mkdir(exist_ok=True)
    uds = SYSTEM / "desktop-bridge.sock"
    if uds.exists():
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(1)
        try:
            probe.connect(str(uds))
        except OSError:
            uds.unlink()
        else:
            verify_existing_bridge(uds, token)
            print(json.dumps({"registered":True,"reused":True,"transport":"ssh-unix-socket"}))
            return
        finally:
            probe.close()
    secret = SYSTEM / "desktop-bridge-token"
    secret.write_text(token, encoding="utf-8")
    os.chmod(secret, 0o600)
    config = json.loads(MCP.read_text(encoding="utf-8")) if MCP.exists() else {"servers": {}}
    config.setdefault("servers", {})["windows-desktop"] = {
        "type": "stdio", "command": "/usr/local/bin/python",
        "args": ["/migration/desktop_bridge_proxy.py"], "tool_timeout": 90,
        "enabled_tools": ["*"], "enabled": True,
    }
    atomic_json(MCP, config)
    # Existing workspace selections are explicit. Add only this deployment resource.
    changed = []
    for path in (ROOT / "data/user").rglob("workspaces.sqlite3"):
        with sqlite3.connect(path, timeout=10) as db:
            for identity, payload in db.execute("SELECT id,payload FROM workspaces").fetchall():
                row = json.loads(payload)
                resources = row.get("resources") or {}
                selected = resources.get("mcp")
                if isinstance(selected, list) and "deployment:windows-desktop" not in selected:
                    selected.append("deployment:windows-desktop")
                    resources["mcp"] = selected
                    row["resources"] = resources
                    db.execute("UPDATE workspaces SET payload=? WHERE id=?", (json.dumps(row, ensure_ascii=False), identity))
                    changed.append(identity)
    print(json.dumps({"registered": True, "transport": "ssh-unix-socket", "workspaces_updated": changed}))


def login():
    credentials = json.loads(subprocess.check_output(["sudo", "-n", "cat", str(ROOT / "migration/admin-login.json")]))
    base = "http://127.0.0.1:8008"
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    login = urllib.request.Request(base + "/api/auth/login", data=json.dumps({"username": credentials["username"], "password": credentials["password"]}).encode(), headers={"Content-Type": "application/json"})
    user = json.loads(client.open(login, timeout=15).read())
    cookie = "; ".join(cookie.name + "=" + cookie.value for cookie in cookies)
    return base, client, cookie, user


def activate() -> None:
    base, client, cookie, user = login()
    config = json.loads(MCP.read_text())
    definition = config["servers"]["windows-desktop"]
    # A previous failed connection remains cached in the running manager.
    # Remove only this tool connection before reopening it on the live tunnel.
    disabled = {**definition, "enabled": False}
    reset = urllib.request.Request(base + "/api/settings/mcp/servers/windows-desktop", method="PUT", data=json.dumps(disabled).encode(), headers={"Content-Type": "application/json", "Cookie": cookie})
    client.open(reset, timeout=30).read()
    # Deployment cookies are Secure for the public HTTPS origin. This request
    # stays on server loopback, so explicitly attach the freshly issued cookie.
    request = urllib.request.Request(base + "/api/settings/mcp/servers/windows-desktop", method="PUT", data=json.dumps(config["servers"]["windows-desktop"]).encode(), headers={"Content-Type": "application/json", "Cookie": cookie})
    result = json.loads(client.open(request, timeout=60).read())
    # Return connection state only. Never echo other servers or their credentials.
    rows = result.get("status", [])
    if isinstance(rows, dict):
        rows = rows.get("servers", list(rows.values()))
    desktop = [row for row in rows if isinstance(row, dict) and (row.get("name") == "windows-desktop" or row.get("server") == "windows-desktop")]
    if not desktop or desktop[0].get("status") != "connected":
        raise RuntimeError("Desktop tool registration did not connect")
    print(json.dumps({"activated": True, "desktop": desktop}))


def session() -> None:
    _, _, cookie, user = login()
    # Consumed only by the local Rust process over SSH; never log this output.
    print(json.dumps({"cookie": cookie, "user": user}))


if __name__ == "__main__":
    if sys.argv[1:] == ["enroll"]:
        try:
            enroll()
        except BridgeConflict as error:
            print(json.dumps({"error":"bridge_conflict","message":str(error)}, ensure_ascii=False))
            raise SystemExit(1)
    elif sys.argv[1:] == ["activate"]:
        activate()
    elif sys.argv[1:] == ["session"]:
        session()
    else:
        raise SystemExit("Usage: desktop_bridge_ctl.py enroll|activate")
