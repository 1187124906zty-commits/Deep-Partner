"""Test-only real stdio server isolating the independently selected authoring inventory."""
from contextlib import asynccontextmanager
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from client import WorkbenchClient
from fastmcp import FastMCP
from tools import authoring_api

client = WorkbenchClient()
authoring_api.configure_client(client)


@asynccontextmanager
async def lifespan(server):
    try:
        yield {}
    finally:
        await client.close()


mcp = FastMCP("Independent authoring acceptance", lifespan=lifespan)
mcp.mount(authoring_api.authoring_api_mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
