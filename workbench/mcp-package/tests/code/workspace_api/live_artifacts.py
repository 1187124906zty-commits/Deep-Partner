"""Compare complete source PDF/preview/reader bytes through the actual service."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct
import sys

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "src"))
sys.path.insert(0, str(PACKAGE / "tests/code"))
from client import WorkbenchClient
from fastmcp import Client
from tools import workspace_api as workspace
from workspace_api.support import PID, DOC, ASSET


async def main():
    os.environ["WORKBENCH_SESSION_FILE"] = "C:/Users/DEVELOPER/.codex/research-workbench-mcp-session.json"
    root = PACKAGE / "tests/results/workspace_api/artifacts"
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "comparisons": [], "failures": [], "success": False}
    direct, t = WorkbenchClient(), WorkbenchClient()
    workspace.configure_client(t)
    try:
        async with Client(workspace.workspace_api_mcp) as c:
            native_pdf = None
            for tool, args, route, params, signature in [
                ("workbench_literature", {"project_id": PID, "action": "preview", "asset": ASSET}, f"/research/api/projects/{PID}/literature/preview", {"asset": ASSET, "library": "workspace"}, b"\x89PNG\r\n\x1a\n"),
                ("workbench_literature", {"project_id": PID, "action": "read", "asset": ASSET}, f"/research/api/projects/{PID}/literature/file", {"asset": ASSET}, b"%PDF-"),
                ("workbench_reader", {"project_id": PID, "action": "content", "document_id": DOC, "view": "source"}, f"/research/reader/{PID}/pub/workbench/{DOC}/original.pdf", None, b"%PDF-"),
            ]:
                progress = {"tool": tool, "route": route, "bytes_received": 0}
                async def fetch():
                    chunks = []
                    async with direct._http().stream("GET", direct.url(route), params=params) as response:
                        direct.check(response)
                        progress.update(status=response.status_code, content_length=response.headers.get("content-length"))
                        async for chunk in response.aiter_bytes():
                            chunks.append(chunk)
                            progress["bytes_received"] += len(chunk)
                    return b"".join(chunks)
                try:
                    expected = await asyncio.wait_for(fetch(), timeout=45)
                except TimeoutError:
                    report["failures"].append({**progress, "reason": "Fresh complete native transfer exceeded the independent 45-second bound"})
                    print(json.dumps(report["failures"][-1]), flush=True)
                    continue
                assert expected.startswith(signature)
                if signature == b"%PDF-":
                    assert len(expected) > 1024 and b"%%EOF" in expected[-2000:]
                    if native_pdf is None:
                        native_pdf = expected
                    else:
                        assert native_pdf == expected
                rows = [(await asyncio.wait_for(c.call_tool(tool, {**args, "output_dir": str(root)}), timeout=60)).data for _ in range(2)]
                paths = [Path(x["artifacts"][0]["path"]) for x in rows]
                assert paths[0] != paths[1]
                for path, row in zip(paths, rows):
                    assert path.is_absolute() and path.is_relative_to(root)
                    assert path.read_bytes() == expected
                    assert row["data"]["bytes"] == len(expected)
                item = {"tool": tool, "action": args["action"], "view": args.get("view"), "bytes": len(expected), "artifacts": [str(p) for p in paths], "comparison": "Every byte equals a fresh complete original native HTTP response", "passed": True}
                if signature.startswith(b"\x89PNG"):
                    item["width"], item["height"] = struct.unpack(">II", expected[16:24])
                    assert item["width"] > 100 and item["height"] > 100
                report["comparisons"].append(item)
                print(json.dumps({"tool": tool, "action": args["action"], "bytes": len(expected), "passed": True}), flush=True)
        report["success"] = not report["failures"]
    finally:
        report["ended_utc"] = datetime.now(timezone.utc).isoformat()
        (PACKAGE / "tests/results/workspace_api/live-artifact-comparisons.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        await direct.close()
        await t.close()
    print(json.dumps({"success": report["success"], "complete_binary_comparisons": len(report["comparisons"])}))
    return report["success"]


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
