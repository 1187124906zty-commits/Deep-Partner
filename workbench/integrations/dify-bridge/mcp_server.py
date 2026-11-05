"""HTTP MCP adapter bound to an active native-to-Dify delivery run."""
from __future__ import annotations

from contextvars import ContextVar
import functools
import inspect
import json
import os
from pathlib import Path
import re
import secrets
import time
from typing import Annotated, get_type_hints
from urllib.parse import unquote, urlsplit

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from workbench_mcp.client import WorkbenchClient
from workbench_mcp.tools import authoring_api, workspace_api


_current: ContextVar[WorkbenchClient] = ContextVar("dify_workbench_transport")


class DifyTokenVerifier(TokenVerifier):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    async def verify_token(self, token: str):
        expected = self.path.read_text().strip()
        if expected and secrets.compare_digest(token, expected):
            return AccessToken(token=token, client_id="dify-workbench", subject="dify-workbench-workflow", scopes=["workbench:delivery"])
        return None


class ScopedProxy:
    def __getattr__(self, name):
        return getattr(_current.get(), name)


class RunClient(WorkbenchClient):
    def __init__(self, service, run_id: str, project: dict, auth: dict):
        super().__init__(service.origin)
        self.run_id, self.selected = run_id, project
        self.output_root = Path(os.environ.get("WORKBENCH_MCP_ARTIFACTS", "/state/mcp-artifacts")) / run_id
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.allowed_roots = [self.output_root.resolve()]
        project_root = project.get("root") or project.get("config", {}).get("project_root")
        if project_root:
            self.allowed_roots.append(Path(project_root).resolve())
        self._session = httpx.AsyncClient(headers={"Origin": service.origin, **auth}, timeout=httpx.Timeout(180, connect=20), follow_redirects=False, trust_env=False)

    def local_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute() or not any(path.resolve().is_relative_to(root) for root in self.allowed_roots):
            raise ValueError("Remote MCP files must remain in this run's project or artifact directory")
        return path.resolve()

    def check_route(self, method: str, path: str):
        route = unquote(urlsplit(self.url(path)).path)
        match = re.match(r"/research/api/projects/([^/]+)", route)
        if match and match[1] != self.selected["id"]:
            raise ValueError("MCP operation belongs to another delivery project")
        if route.rstrip("/") == "/research/api/projects" and method.upper() != "GET":
            raise ValueError("Create projects in the workbench before starting a scoped Dify delivery")

    async def request(self, method, path, **kwargs):
        self.check_route(method, path)
        value = await super().request(method, path, **kwargs)
        if urlsplit(self.url(path)).path == "/research/api/projects":
            return {**value, "projects": [p for p in value.get("projects", []) if p.get("id") == self.selected["id"]]}
        return value

    async def project(self, project_id):
        if project_id != self.selected["id"]:
            raise ValueError("Project differs from the active delivery")
        return self.selected

    async def download(self, path_or_same_origin_url, output_path, *, params=None):
        self.check_route("GET", path_or_same_origin_url)
        output = self.local_path(output_path)
        if not output.is_relative_to(self.output_root.resolve()):
            raise ValueError("Remote downloads use /state/mcp-artifacts/<run_id>; project writes use the native editing tools")
        return await super().download(path_or_same_origin_url, str(output), params=params)

    def _save(self, response, output):
        if not output.resolve().is_relative_to(self.output_root.resolve()):
            output = self.output_root / output.name
        return WorkbenchClient._save(response, output)


def create_mcp(service, secret_path: Path):
    server = FastMCP("Research Workbench · Dify", auth=DifyTokenVerifier(secret_path), instructions="Use the active delivery run_id from this workflow. Every tool retains that run's account and project. Read workbench_rules context before edits; poll asynchronous native results and inspect saved artifacts. Remote files belong to the project's server directory or /state/mcp-artifacts/<run_id>. The run expires when delivery finishes.")
    proxy = ScopedProxy()
    workspace_api.configure_client(proxy)
    authoring_api.configure_client(proxy)
    names = json.loads((Path(__file__).parent / "workbench-tool-names.json").read_text())
    with service.db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS mcp_calls(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, project_id TEXT NOT NULL, tool TEXT NOT NULL, started REAL NOT NULL, finished REAL, state TEXT NOT NULL)")

    def expose(function, name):
        hints = get_type_hints(function, include_extras=True)
        parameters = [inspect.Parameter("run_id", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Annotated[str, "Active delivery run_id received by this Dify workflow"])]
        parameters += [p.replace(annotation=hints.get(p.name, p.annotation)) for p in inspect.signature(function).parameters.values()]

        @functools.wraps(function)
        async def invoke(**arguments):
            run_id = arguments.pop("run_id")
            value = service.tickets.get(run_id)
            if not value:
                raise ValueError("Delivery run is unavailable or expired; start from the authenticated native workbench task")
            ticket = service.ticket(run_id, value["secret"])
            row = service.row(run_id)
            project = await service.project(ticket["auth"], row["project_id"])
            client = RunClient(service, run_id, project, ticket["auth"])
            token = _current.set(client)
            audit_id = None
            state = "failed"
            try:
                for key in ("file_path", "image_path", "output_path", "output_dir"):
                    if arguments.get(key):
                        file = client.local_path(arguments[key])
                        if key.startswith("output_") and not file.is_relative_to(client.output_root.resolve()):
                            raise ValueError("Remote output paths must remain in this delivery's artifact directory")
                for value in arguments.get("file_paths") or []:
                    client.local_path(value)
                if arguments.get("project_id") and arguments["project_id"] != project["id"]:
                    raise ValueError("Tool project_id differs from the active delivery project")
                with service.db() as db:
                    audit_id = db.execute("INSERT INTO mcp_calls(run_id,project_id,tool,started,state) VALUES(?,?,?,?,?)", (run_id, project["id"], name, time.time(), "running")).lastrowid
                result = await function(**arguments)
                state = "completed"
                return result
            finally:
                if audit_id is not None:
                    with service.db() as db:
                        db.execute("UPDATE mcp_calls SET finished=?,state=? WHERE id=?", (time.time(), state, audit_id))
                _current.reset(token)
                await client.close()

        invoke.__signature__ = inspect.Signature(parameters=parameters, return_annotation=dict)
        invoke.__annotations__ = {"run_id": Annotated[str, "Active delivery run_id"], **hints}
        server.tool(name=name)(invoke)

    for name in names:
        module = workspace_api if hasattr(workspace_api, name) else authoring_api
        expose(getattr(module, name), name)
    return server
