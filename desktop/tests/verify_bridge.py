"""Exercise the compiled Windows bridge, real browser CDP, and parallel I/O."""
from __future__ import annotations
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    executable = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "target/debug/deep-partner.exe"
    report = {"binary": str(executable), "checks": []}
    with tempfile.TemporaryDirectory(prefix="deeptutor-bridge-",ignore_cleanup_errors=True) as temporary:
        home = Path(temporary)
        workspace = home / "workspace"
        workspace.mkdir()
        (workspace / "sample.txt").write_text("DeepTutor desktop verification\n氯离子扩散 diffusion\n", encoding="utf-8")
        for index in range(40):
            (workspace / f"bulk-{index}.txt").write_text("background I/O\n" * 8000, encoding="utf-8")
        bridge_port, browser_port = port(), port()
        (home / "config.json").write_text(json.dumps({"workspace": str(workspace), "bridge_port": bridge_port, "browser_port": browser_port, "cpu_workers": 2, "cache_mb": 4, "desktop_control":False}), encoding="utf-8")
        environment = dict(os.environ, DEEPTUTOR_DESKTOP_HOME=str(home))
        process = subprocess.Popen([str(executable), "--bridge-only"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{bridge_port}"
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            for _ in range(100):
                try:
                    client.open(base + "/health", timeout=1).read()
                    break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        raise RuntimeError(process.stderr.read().decode(errors="replace"))
                    time.sleep(0.1)
            else:
                raise RuntimeError("Bridge did not start")
            token = (home / "bridge-token").read_text().strip()

            def rpc(method: str, params: dict | None = None, authenticated: bool = True):
                headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
                if authenticated:
                    headers["Authorization"] = "Bearer " + token
                request = urllib.request.Request(base + "/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode(), headers=headers)
                return json.loads(client.open(request, timeout=45).read())["result"]

            def call(name: str, arguments: dict | None = None, error: bool = False):
                result = rpc("tools/call", {"name": name, "arguments": arguments or {}})
                assert bool(result.get("isError", False)) == error, result
                if error:
                    return result
                if result["content"][0]["type"] == "image":
                    return result
                return json.loads(result["content"][0]["text"])

            try:
                rpc("initialize", authenticated=False)
                raise AssertionError("Unauthenticated tool access was accepted")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            assert rpc("initialize", {"protocolVersion": "2025-06-18"})["serverInfo"]["name"] == "deep-partner-desktop"
            assert len(rpc("tools/list")["tools"]) == 17
            report["checks"].append("MCP initialize/list and authentication")
            assert "diffusion" in call("workspace_read", {"path": "sample.txt"})["text"]
            call("workspace_read", {"path": "../config.json"}, error=True)
            call("workspace_write", {"path": "../escape.txt", "text": "no"}, error=True)
            assert call("workspace_write", {"path": "summary.md", "text": "本机输出验证"})["bytes"] > 0
            call("workspace_write", {"path": "summary.md", "text": "overwrite"}, error=True)
            call("desktop_click", {"x": 0, "y": 0}, error=True)
            report["checks"].append("Real file read/write, traversal rejection, no overwrite, desktop off")
            latency = []
            for _ in range(30):
                begin = time.perf_counter()
                call("workspace_read", {"path": "sample.txt"})
                latency.append((time.perf_counter() - begin) * 1000)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                searches = [pool.submit(call, "workspace_search", {"query": "diffusion"}) for _ in range(4)]
                health = []
                for _ in range(15):
                    begin = time.perf_counter()
                    client.open(base + "/health", timeout=2).read()
                    health.append((time.perf_counter() - begin) * 1000)
                for future in searches:
                    assert future.result()["matches"]
            report["local_cached_read_ms"] = {"median": round(statistics.median(latency), 2), "p95": round(sorted(latency)[28], 2)}
            report["health_during_parallel_search_ms"] = {"median": round(statistics.median(health), 2), "max": round(max(health), 2)}
            report["checks"].append("Parallel searches do not block I/O service")
            call("browser_open", {"url": base + "/test-page"})
            snapshot = call("browser_snapshot")
            assert snapshot["title"] == "DeepTutor Browser Test"
            call("browser_type", {"target": "#query", "text": "CPU GPU 异步验证"})
            call("browser_click", {"target": "#search"})
            snapshot = call("browser_snapshot")
            assert "已检索：CPU GPU 异步验证" in snapshot["text"]
            screenshot = call("browser_screenshot")
            assert len(screenshot["content"][0]["data"]) > 1000
            report["checks"].append("Real Edge browser open/snapshot/Unicode input/click/screenshot")
            call("browser_close")
            report["passed"] = True
        finally:
            # This browser has an isolated test profile, not the user's browser.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=10)
    (ROOT / "verification/bridge.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
