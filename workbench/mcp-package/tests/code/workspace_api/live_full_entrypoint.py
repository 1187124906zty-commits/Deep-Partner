"""Read-only verification of the actual full production stdio entry point."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE / "src"))
sys.path.insert(0, str(PACKAGE / "tests/code"))
from client import WorkbenchClient
from fastmcp import Client
from workspace_api.contracts import REQUIRED
from workspace_api.support import PID, KB


async def main():
    env = {**os.environ, "WORKBENCH_SESSION_FILE": "C:/Users/DEVELOPER/.codex/research-workbench-mcp-session.json"}
    os.environ["WORKBENCH_SESSION_FILE"] = env["WORKBENCH_SESSION_FILE"]
    record = {"started_utc": datetime.now(timezone.utc).isoformat(), "server": str(PACKAGE / "src/project_mcp.py"), "success": False}
    direct = WorkbenchClient()
    try:
        config = {"mcpServers": {"full-production-entrypoint": {"command": sys.executable, "args": [str(PACKAGE / "src/project_mcp.py")], "cwd": str(PACKAGE), "env": env}}}
        async with Client(config) as c:
            inventory = {s.name: s for s in await c.list_tools()}
            assert set(REQUIRED).issubset(inventory)
            for tool, required in REQUIRED.items():
                assert set(inventory[tool].input_schema.get("required", [])) == set(required)
            status = (await c.call_tool("workbench_account", {"action": "status"})).data["data"]
            assert status["authenticated"] is True
            expected = await direct.native_request("GET", "/api/knowledge-bases/" + KB + "/files", PID)
            actual = (await c.call_tool("workbench_knowledge_files", {"project_id": PID, "knowledge_base": KB})).data["data"]
            assert actual == expected
            record.update(success=True, full_inventory_count=len(inventory), workspace_tools_checked=sorted(REQUIRED), live_calls=["workbench_account:status", "workbench_knowledge_files:list"], native_comparison="Full current native KB file list equality")
    finally:
        await direct.close()
        record["ended_utc"] = datetime.now(timezone.utc).isoformat()
        (PACKAGE / "tests/results/workspace_api/full-production-entrypoint.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": record["success"], "workspace_schemas": len(REQUIRED), "full_inventory_count": record.get("full_inventory_count")}))


if __name__ == "__main__":
    asyncio.run(main())
