"""Read-only Codex app-server/skill discovery; starts no model turn or download."""

from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def probe(executable: str, cwd: Path) -> dict:
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    version = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, timeout=10,
        encoding="utf-8", creationflags=flags, check=True,
    ).stdout.strip()
    configured = subprocess.run(
        [executable, "mcp", "list", "--json"], capture_output=True, text=True,
        encoding="utf-8", timeout=20, creationflags=flags, check=True,
    )
    mcp = json.loads(configured.stdout)
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "executable": executable,
        "cwd": str(cwd),
        "transport": "stdio",
        "model_turn_started": False,
        "download_started": False,
        "mcp_configuration_only": True,
        "mcp_servers": [
            {"name": row.get("name"), "enabled": row.get("enabled"),
             "transport": row.get("transport", {}).get("type")}
            for row in mcp
        ],
    }
    messages: queue.Queue = queue.Queue()
    proc = subprocess.Popen(
        [executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", cwd=cwd, creationflags=flags,
    )

    def read():
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except json.JSONDecodeError:
                messages.put({"protocol_error": "non_json_stdout"})
        messages.put({"eof": True})

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    serial = 0

    def send(method: str, params: dict, identity=None):
        payload = {"method": method, "params": params}
        if identity is not None:
            payload["id"] = identity
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def rpc(method: str, params: dict):
        nonlocal serial
        serial += 1
        send(method, params, serial)
        deadline = time.monotonic() + 30
        while True:
            msg = messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if msg.get("eof") or msg.get("protocol_error"):
                raise RuntimeError(f"app-server stream ended during {method}")
            if msg.get("id") != serial:
                continue
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg["result"]

    try:
        started = time.monotonic()
        initialized = rpc("initialize", {
            "clientInfo": {"name": "deep_partner_readonly_probe", "version": "0.1.0"},
        })
        send("initialized", {})
        report["initialize_passed"] = True
        report["server_user_agent"] = initialized.get("userAgent")
        result = rpc("skills/list", {"cwds": [str(cwd)], "forceReload": True})
        entries = result.get("data", [])
        skills = [skill for entry in entries for skill in entry.get("skills", [])]
        terms = ("scan", "download", "paper", "pdf", "ppt", "figure", "scientific")
        report["skills_list_passed"] = True
        report["skill_count"] = len(skills)
        report["discovery_errors"] = [err for entry in entries for err in entry.get("errors", [])]
        report["relevant_skills"] = [
            {key: skill.get(key) for key in ("name", "path", "scope", "enabled")}
            for skill in skills if any(term in skill.get("name", "").lower() for term in terms)
        ]
        report["discovery_elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["status"] = "passed"
        return report
    finally:
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
        reader.join(timeout=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    executable = shutil.which("codex")
    if not executable:
        parser.error("codex is not on PATH")
    report = probe(executable, args.cwd.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "version": report["version"],
                      "skills": report["skill_count"], "mcp": report["mcp_servers"],
                      "output": str(args.output.resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
