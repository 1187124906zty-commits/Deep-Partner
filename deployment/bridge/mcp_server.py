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
from fastmcp.exceptions import ToolError
from fastapi import HTTPException

from workbench_mcp.client import WorkbenchClient
from workbench_mcp.tools import authoring_api, workspace_api


_current: ContextVar[WorkbenchClient] = ContextVar("dify_workbench_transport")
TOOL_TITLES = {
    'workbench_account':'账户与访问状态', 'workbench_projects':'研究项目', 'workbench_rules':'项目规范与任务技能',
    'workbench_search_sources':'检索来源配置', 'workbench_web_search':'公开网页检索',
    'workbench_paper_search':'论文题录检索', 'workbench_knowledge_search':'项目知识库检索',
    'workbench_knowledge_bases':'项目知识库管理', 'workbench_knowledge_files':'知识库源文件',
    'workbench_knowledge_index':'知识库索引状态', 'workbench_literature':'文献附件与原文',
    'workbench_literature_organization':'文献分类与用途', 'workbench_references':'稿件引文与参考文献',
    'workbench_paper_downloads':'论文下载任务', 'workbench_files':'项目文件', 'workbench_jobs':'后台任务状态',
    'workbench_review':'审阅与处理记录', 'workbench_annotations':'项目批注', 'workbench_revisions':'版本历史',
    'workbench_manuscript':'当前稿件', 'workbench_manuscript_templates':'稿件模板',
    'workbench_manuscript_export':'稿件导出', 'workbench_reader':'文献阅读与定位', 'workbench_translation':'文献翻译',
    'workbench_figure':'科研图表', 'workbench_figure_chat':'图表修改任务', 'workbench_image_review':'图像审阅',
    'workbench_raster':'位图处理', 'workbench_slides':'研究汇报', 'workbench_slide_templates':'汇报模板',
    'workbench_journals':'期刊信息', 'workbench_journal_templates':'期刊官方模板',
    'workbench_author_profile':'作者资料', 'workbench_storage':'存储使用情况', 'workbench_settings':'账户设置',
    'workbench_project_import':'研究材料导入', 'workbench_export_download':'导出成果下载',
    'workbench_delivery_verify':'成果保存与处理记录核验',
}


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
            except ToolError:
                raise
            except HTTPException as error:
                code = {401:'authentication_required',403:'access_denied',409:'version_conflict',429:'rate_limited'}.get(error.status_code,'upstream_error')
                raise ToolError(json.dumps({'error':{'code':code,'message':str(error.detail)[:1000],
                    'retryable':error.status_code>=500 or error.status_code==429,
                    'next_action':'刷新项目版本后重试' if error.status_code==409 else '检查当前账户或服务状态'}},ensure_ascii=False)) from None
            except httpx.HTTPError as error:
                raise ToolError(json.dumps({'error':{'code':'timeout' if isinstance(error,httpx.TimeoutException) else 'connection_error',
                    'message':'工作台请求未完成','retryable':True,'next_action':'先查询原任务状态；读取请求可稍后重试'}},ensure_ascii=False)) from None
            finally:
                if audit_id is not None:
                    with service.db() as db:
                        db.execute("UPDATE mcp_calls SET finished=?,state=? WHERE id=?", (time.time(), state, audit_id))
                _current.reset(token)
                await client.close()

        invoke.__signature__ = inspect.Signature(parameters=parameters, return_annotation=dict)
        invoke.__annotations__ = {"run_id": Annotated[str, "Active delivery run_id"], **hints}
        server.tool(name=name, title=TOOL_TITLES.get(name),
            annotations={'readOnlyHint':True,'destructiveHint':False} if name in {
                'workbench_delivery_verify','workbench_search_sources','workbench_web_search','workbench_paper_search'} else None)(invoke)

    for name in names:
        module = workspace_api if hasattr(workspace_api, name) else authoring_api
        expose(getattr(module, name), name)

    async def workbench_delivery_verify() -> dict:
        """核验本轮已保存成果：账户与项目、当前文件或稿件版本，以及原生处理记录。
        仅用于成果交付的最后一步；不运行研究、不检索文献、不替代科学验证。run_id 来自当前工作流。
        """
        client = _current.get()
        ticket = service.tickets[client.run_id]
        value = await service.verify_delivery(client.run_id, ticket['secret'])
        return {'message':'成果版本与处理记录核验完成', 'data':value,
            'reference':service.origin + '/research/dify/api/runs/' + client.run_id, 'artifacts':[]}

    expose(workbench_delivery_verify, 'workbench_delivery_verify')

    @server.tool(name='workbench_delivery_event', title='交付事件核对与分支回执')
    async def workbench_delivery_event(event_id: str, event_token: str, action: str = 'inspect', route: str = '') -> dict:
        """Dify Webhook 专用。凭事件编号及凭证读取服务端真实状态，或登记对应分支。
        只处理交付事件元数据，不读取用户授权、不重复保存成果。action=inspect/settle。
        """
        try:
            if action == 'inspect':
                value = service.automation.inspect(event_id, event_token)
            elif action == 'settle':
                value = service.automation.settle(event_id, event_token, route)
            else:
                raise HTTPException(400, '未知事件操作')
            return {'data': value}
        except HTTPException as exc:
            raise ToolError(str(exc.detail)) from None

    @server.tool(name='workbench_delivery_reconcile', title='交付状态与服务定时核对')
    async def workbench_delivery_reconcile() -> dict:
        """Dify 定时触发专用。读取状态不明的既有交付与服务健康，登记需处理事项。
        不提交新研究任务、不重复写入文件、不启动网络文献搜索。
        """
        return {'data': await service.automation.reconcile()}

    @server.tool(name='workbench_evidence_search', title='项目联合检索的独立来源分支', annotations={'readOnlyHint':True,'destructiveHint':False})
    async def workbench_evidence_search(run_id: str, branch: str, workflow_run_id: str = '') -> dict:
        """Dify 联合检索流程专用。branch=knowledge/web/papers。
        run_id 由当前账户创建并绑定项目，不接受模型传入的账户或授权。
        无匹配、未配置、超时和失败分别返回；单路失败保留其他来源。
        """
        try:
            return {'data': await service.evidence.branch(run_id,branch,workflow_run_id)}
        except HTTPException as exc:
            raise ToolError(str(exc.detail)) from None
    return server
