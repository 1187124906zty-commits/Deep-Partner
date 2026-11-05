"""MCP entry point for the existing Research Workbench service."""
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from client import WorkbenchClient
from tools import authoring_api, workspace_api


client = WorkbenchClient()
authoring_api.configure_client(client)
workspace_api.configure_client(client)


@asynccontextmanager
async def lifespan(server):
    try:
        yield {}
    finally:
        await client.close()


mcp = FastMCP("Research Workbench", instructions="Start with workbench_account, workbench_rules and workbench_projects. Read project context and relevant skills before editing. All project ownership, revision conflicts and asynchronous job states are enforced by the existing upstream service. Record completed changes using workbench_review receipt with the stage and stable operation_id from current context; follow its quality job and read quality_gate before the next automatic stage. Use explicit output_dir/output_path for intended local downloads and inspect returned absolute paths. Results retain source and artifact paths; pending jobs are not completed results.", lifespan=lifespan)
mcp.mount(authoring_api.authoring_api_mcp)
mcp.mount(workspace_api.workspace_api_mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
