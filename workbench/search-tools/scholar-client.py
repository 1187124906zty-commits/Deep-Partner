"""One-shot local-agent bridge to the unmodified Scholar MCP stdio server."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE = Path(__file__).resolve().parent


async def run(args: argparse.Namespace) -> int:
    server = StdioServerParameters(
        command=str(BASE / "scholar-env/Scripts/python.exe"),
        args=["-m", "scholar_mcp.server"],
        cwd=str(BASE / "scholar-mcp"),
        env={
            "PYTHONUNBUFFERED": "1",
            "SCHOLAR_TIMEOUT": "20",
            "SCHOLAR_MAX_RETRIES": "0",
        },
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if args.list_tools:
                result = await session.list_tools()
                print(result.model_dump_json(by_alias=True))
                return 0
            request = {"query": args.query, "page_size": args.limit}
            for option in ("cursor", "year_min", "year_max"):
                value = getattr(args, option)
                if value is not None:
                    request[option] = value
            result = await session.call_tool("search_papers_by_topic", request)
            payload = result.structuredContent
            if payload is None:
                texts = [item.text for item in result.content if item.type == "text"]
                payload = json.loads(texts[0]) if texts else {"ok": False, "error": {"code": "empty_mcp_response"}}
            print(json.dumps(payload, ensure_ascii=False))
            return 2 if result.isError or payload.get("ok") is False else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--list-tools", action="store_true")
    operation.add_argument("--query")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=5)
    parser.add_argument("--cursor")
    parser.add_argument("--year-min", type=int)
    parser.add_argument("--year-max", type=int)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "mcp_transport_error", "message": str(exc)}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
