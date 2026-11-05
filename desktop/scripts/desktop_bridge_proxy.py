"""MCP stdio adapter inside DeepTutor. HTTP travels over an SSH Unix socket."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

SYSTEM = Path("/app/data/system")


def main() -> None:
    token = (SYSTEM / "desktop-bridge-token").read_text().strip()
    transport = httpx.HTTPTransport(uds=str(SYSTEM / "desktop-bridge.sock"))
    with httpx.Client(
        transport=transport,
        base_url="http://localhost",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"},
        timeout=90,
    ) as client:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if "id" not in request:
                    continue
                response = client.post("/mcp", json=request)
                response.raise_for_status()
                result = response.json()
            except Exception as error:
                request = locals().get("request", {})
                if "id" not in request:
                    continue
                result = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "error": {"code": -32000, "message": "Desktop is unavailable: " + type(error).__name__},
                }
            print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
