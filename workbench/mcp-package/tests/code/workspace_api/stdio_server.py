"""Isolated stdio mount of the production workspace module for strict 24-tool acceptance."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from client import WorkbenchClient
from tools.workspace_api import workspace_api_mcp, configure_client

configure_client(WorkbenchClient())
if __name__ == "__main__":
    workspace_api_mcp.run(transport="stdio", show_banner=False)
