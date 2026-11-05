"""Dify coordinates delivery; the existing workbench owns projects and revisions."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path, PurePosixPath
import secrets
import sqlite3
import time
from typing import Literal
from urllib.parse import quote
from urllib.parse import urlsplit
import ipaddress
import uuid

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from workbench_mcp.client import request_with_read_retry
from automation import DeliveryAutomation
from evidence import EvidenceService


def workflow_receipt(saved: dict, run: dict) -> dict:
    """Keep native save evidence distinct from the terminal Dify verification."""
    workflow = run.get("data")
    if not isinstance(workflow, dict):
        workflow = {}
    result = {**saved, "workflow_run_id": run.get("workflow_run_id") or workflow.get("id"),
              "workflow_status": workflow.get("status") or "unknown"}
    if result["workflow_status"] == "succeeded":
        outputs = workflow.get("outputs")
        final = outputs.get("receipt") if isinstance(outputs, dict) else None
        try:
            final = json.loads(final) if isinstance(final, str) else final
        except (TypeError, ValueError):
            final = None
        if (isinstance(final, dict) and final.get("run_id") == saved["run_id"]
                and final.get("project_id") == saved["project_id"]
                and final.get("artifact") == saved["artifact"]
                and final.get("processing_history_verified") is True and final.get("history_event_id")):
            result.update(processing_history_verified=True, history_event_id=final["history_event_id"])
        else:
            result.update(workflow_status="unverified", workflow_error="Dify ended without a matching verified processing history")
    else:
        result["workflow_error"] = str(workflow.get("error") or "Dify terminal result is unavailable")[:1000]
    return result


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["file", "manuscript", "existing"]
    path: str = ""
    content: str | None = Field(default=None, max_length=2_000_000)
    document: dict | None = None
    expected_modified: float | None = None
    summary: str = Field(min_length=1, max_length=1000)
    source_paths: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def check(self):
        if self.type == "manuscript":
            if not isinstance(self.document, dict) or "revision" not in self.document:
                raise ValueError("稿件需要包含当前 revision 的工作台文档结构")
            self.path = "manuscript/main.json"
        else:
            path = PurePosixPath(self.path)
            if (not self.path or "\\" in self.path or path.is_absolute()
                    or any(p in {"..", ".trash", ".workbench", ".git"} for p in path.parts)
                    or any(p.startswith(".") for p in path.parts)):
                raise ValueError("成果路径必须位于当前项目的可见文件目录")
            if self.type == "file" and self.content is None:
                raise ValueError("文本成果需要 content；已有二进制成果使用 existing")
            self.path = str(path)
        return self


class Delivery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    project_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    task: Literal["code", "code-review", "test", "paper", "translation", "literature", "slides", "review", "figure"]
    standard_version: str = Field(min_length=1, max_length=100)
    workspace_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    artifact: Artifact
    question_ids: list[str] = Field(default_factory=list, max_length=30)
    validation: list[dict] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)


class DeliveryService:
    def __init__(self, state: Path, *, workbench_url: str, native_url: str,
                 dify_url: str, dify_key: Path, origin: str, transport=None):
        self.state = state
        state.parent.mkdir(parents=True, exist_ok=True)
        self.workbench_url, self.native_url = workbench_url, native_url
        self.dify_url, self.dify_key, self.origin = dify_url, dify_key, origin
        self.transport = transport
        self.tickets: dict[str, dict] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_id TEXT NOT NULL,
              project_id TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
              context TEXT, written TEXT, receipt TEXT, error TEXT,
              workflow_run_id TEXT, created REAL NOT NULL, updated REAL NOT NULL,
              UNIQUE(owner,request_id))""")
            db.execute("UPDATE deliveries SET state='interrupted',error='交付服务重新启动，请查询状态后重试' "
                       "WHERE state IN ('pending','prepared','written')")
        self.automation = DeliveryAutomation(self, dify_key.parent / 'automation-config.json')
        self.evidence = EvidenceService(self)

    @contextmanager
    def db(self):
        with sqlite3.connect(self.state, timeout=15) as db:
            db.row_factory = sqlite3.Row
            yield db

    def row(self, run_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM deliveries WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "交付任务不存在")
        return dict(row)

    def update(self, run_id, **fields):
        allowed = {"state", "context", "written", "receipt", "error", "workflow_run_id"}
        if not fields.keys() <= allowed:
            raise ValueError("Invalid delivery field")
        fields["updated"] = time.time()
        with self.db() as db:
            db.execute("UPDATE deliveries SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                       (*fields.values(), run_id))

    async def request(self, base, method, path, auth=None, **kwargs):
        headers = {"Origin": self.origin, **(auth or {})}
        async with httpx.AsyncClient(timeout=120, trust_env=False, transport=self.transport) as client:
            response = await request_with_read_retry(client, method, base + path, headers=headers, **kwargs)
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.json().get("message", "请求失败"))
            except ValueError:
                detail = "上游服务返回 HTTP " + str(response.status_code)
            raise HTTPException(response.status_code, detail)
        return response

    async def profile(self, auth):
        result = (await self.request(self.native_url, "GET", "/api/auth/profile", auth)).json()
        if not result.get("id"):
            raise HTTPException(401, "请使用当前 DeepTutor 账户登录")
        return result

    async def projects(self, auth):
        return (await self.request(self.workbench_url, "GET", "/research/api/projects", auth)).json()["projects"]

    async def read_webpage(self, auth, url):
        """Use Dify's installed reader without forwarding Workbench credentials."""
        profile=await self.profile(auth)
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or len(url)>2000:
            raise HTTPException(400,'请输入公开网页的 HTTPS 链接')
        if parsed.hostname in {'localhost','localhost.localdomain'}:
            raise HTTPException(400,'网页读取仅接受公开来源')
        try:
            if not ipaddress.ip_address(parsed.hostname).is_global:
                raise HTTPException(400,'网页读取仅接受公开来源')
        except ValueError:pass
        key_path=self.dify_key.parent/'web-reader-key'
        if not key_path.is_file():raise HTTPException(503,'网页证据读取模块尚未配置')
        # Stop on access challenges before invoking the built-in reader.
        try:
            async with httpx.AsyncClient(timeout=12,trust_env=False,transport=self.transport) as client:
                response=await client.head(url,follow_redirects=True)
        except httpx.HTTPError as error:
            return {'status':'unavailable','source_url':url,'error':{'code':'timeout' if isinstance(error,httpx.TimeoutException) else 'connection_error',
                'message':'网页访问检查未完成','retryable':True,'next_action':'稍后重试或选择其他公开来源'}}
        if response.status_code in {401,403,429}:
            return {'status':'unavailable','source_url':url,'error':{'code':'access_required' if response.status_code!=429 else 'rate_limited',
                'message':'该网页要求访问验证或暂时限制请求','retryable':False,'next_action':'在原站确认访问条件或选择其他公开来源'}}
        result=(await self.request(self.dify_url,'POST','/v1/workflows/run',
            {'Authorization':'Bearer '+key_path.read_text().strip()},json={'inputs':{'url':url},
             'response_mode':'blocking','user':'deeptutor-'+profile['id']})).json()
        run=result.get('data',{})
        if run.get('status')!='succeeded':
            return {'status':'unavailable','source_url':url,'workflow_run_id':result.get('workflow_run_id'),
                'error':{'code':'page_read_failed','message':'网页正文读取未完成','retryable':True,'next_action':'检查原网页是否可读，或使用其他原文来源'}}
        try:
            value=json.loads(run['outputs']['evidence'])
        except (KeyError,TypeError,ValueError):raise HTTPException(502,'网页读取没有返回有效证据') from None
        if value.get('source_url')!=url or value.get('status')!='ready' or not value.get('content'):
            raise HTTPException(502,'网页证据与本次请求不一致')
        return {**value,'workflow_run_id':result.get('workflow_run_id') or run.get('id')}

    async def project(self, auth, project_id="", workspace_id=""):
        projects = await self.projects(auth)
        selected = [p for p in projects if p["id"] == project_id] if project_id else [
            p for p in projects if workspace_id and p.get("native_id") == workspace_id]
        if len(selected) != 1:
            raise HTTPException(409, "先选择当前账户的研究项目；可以用 projects 列出项目")
        project = selected[0]
        if workspace_id and project.get("native_id") != workspace_id:
            raise HTTPException(409, "目标项目与当前 DeepTutor 工作区不一致")
        return project

    async def context(self, auth, project_id, task, workspace_id=""):
        project = await self.project(auth, project_id, workspace_id)
        prefix = "/research/api/projects/" + project["id"]
        context = (await self.request(self.workbench_url, "GET", prefix + "/agent-context", auth,
                                      params={"task": task})).json()
        context["native_workspace_id"] = project["native_id"]
        context["manuscript"] = (await self.request(self.workbench_url, "GET", prefix + "/manuscript", auth)).json()
        context["delivery"] = {
            "types": ["file", "manuscript", "existing"],
            "file_paths": "Relative to project/. Existing files require expected_modified from files metadata.",
            "manuscript": "Use the current manuscript structure and revision; the native template and history remain authoritative.",
            "existing": "Record an artifact already generated in project/; no binary data in model prompts.",
        }
        return context

    async def native_identity(self,auth,delivery):
        if not delivery.session_id:
            if delivery.turn_id:raise HTTPException(400,'执行编号需要对应的会话编号')
            return {}
        identity=(await self.request(self.workbench_url,'GET',
            '/research/api/projects/'+delivery.project_id+'/native-session',auth,
            params={'session_id':delivery.session_id,'turn_id':delivery.turn_id})).json()
        if (identity.get('session_id')!=delivery.session_id
            or delivery.turn_id and identity.get('turn_id')!=delivery.turn_id
            or delivery.workspace_id and identity.get('native_workspace_id')!=delivery.workspace_id):
            raise HTTPException(409,'交付与原生项目会话不一致')
        return {key:identity[key] for key in ('session_id','turn_id') if identity.get(key)}

    def ticket(self, run_id, secret):
        value = self.tickets.get(run_id)
        if not value or time.time() > value["expires"] or not secrets.compare_digest(value["secret"], secret):
            raise HTTPException(401, "交付票据已失效；从当前会话查询任务状态后重试")
        return value

    async def metadata(self, auth, project_id, path):
        parent = str(PurePosixPath(path).parent)
        if parent == ".":
            parent = ""
        try:
            result = (await self.request(self.workbench_url, "GET", "/research/api/projects/" + project_id + "/files",
                                         auth, params={"path": parent})).json()
        except HTTPException as exc:
            if exc.status_code == 404:
                return None
            raise
        return next((x for x in result["items"] if x["path"] == path), None)

    async def prepare(self, run_id, secret, workflow_run_id=''):
        ticket = self.ticket(run_id, secret)
        if workflow_run_id:
            try:uuid.UUID(workflow_run_id)
            except ValueError:raise HTTPException(400,'Dify 运行编号无效') from None
            if ticket.get('workflow_run_id') not in (None,workflow_run_id):raise HTTPException(409,'同一次交付的 Dify 运行编号发生变化')
            ticket['workflow_run_id']=workflow_run_id
            self.update(run_id,workflow_run_id=workflow_run_id)
        row = self.row(run_id)
        delivery = Delivery.model_validate_json(row["payload"])
        context = await self.context(ticket["auth"], delivery.project_id, delivery.task, delivery.workspace_id)
        await self.native_identity(ticket['auth'],delivery)
        if context["standard_version"] != delivery.standard_version:
            raise HTTPException(409, "工作台技能规范已更新，请重新读取 context 后交付")
        if context.get('project',{}).get('id') != delivery.project_id or not context.get('instructions'):
            raise HTTPException(409, '项目上下文与交付目标不一致，或项目规范缺失')
        # The workbench catalog is lazy: a canonical reference is its current
        # contract. Full skill bodies are read by the executor when needed.
        def has_skill_source(skill):
            if not isinstance(skill,dict) or not skill.get('id'):return False
            if isinstance(skill.get('content'),str) and skill['content'].strip():return True
            identifier=skill['id']
            return (isinstance(identifier,str) and all(part not in ('','..','.') for part in identifier.split('/'))
                    and skill.get('url')=='/research/api/standards/skills/'+identifier)
        if not context.get('skills') or not all(has_skill_source(skill) for skill in context['skills']):
            raise HTTPException(409, '当前任务缺少有效的技能原文或读取入口，请重新载入项目上下文')
        if delivery.question_ids:
            notes = (await self.request(self.workbench_url, "GET", "/research/api/projects/" + delivery.project_id + "/annotations",
                                         ticket["auth"])).json()["items"]
            if set(delivery.question_ids) - {x["id"] for x in notes}:
                raise HTTPException(400, "问题标识不属于当前项目")
        value = {"standard_version": context["standard_version"], "project_id": delivery.project_id,
                 "task": delivery.task, "skills": [s["id"] for s in context["skills"]]}
        self.update(run_id, context=json.dumps(value, ensure_ascii=False), state="prepared")
        return value

    async def verify_delivery(self, run_id, secret):
        """One business check shared by Dify: saved content, identity and history."""
        ticket = self.ticket(run_id, secret)
        row = self.row(run_id)
        if not row['receipt']:
            raise HTTPException(409, '成果尚未取得保存回执；查询同一交付任务')
        saved = json.loads(row['receipt'])
        delivery = Delivery.model_validate_json(row['payload'])
        project = await self.project(ticket['auth'], delivery.project_id, delivery.workspace_id)
        profile = await self.profile(ticket['auth'])
        if profile['id'] != row['owner']:
            raise HTTPException(403, '交付记录与当前账户不一致')
        prefix = '/research/api/projects/' + delivery.project_id
        if delivery.artifact.type == 'file':
            current = await self.request(self.workbench_url, 'GET', prefix + '/file', ticket['auth'],
                params={'path':delivery.artifact.path})
            if current.text != delivery.artifact.content:
                raise HTTPException(409, '已保存文件在交付后发生变化，请保留当前版本并刷新状态')
        elif delivery.artifact.type == 'manuscript':
            current = (await self.request(self.workbench_url, 'GET', prefix + '/manuscript', ticket['auth'])).json()
            if current.get('revision') != saved['artifact']['revision']:
                raise HTTPException(409, '稿件版本在交付后发生变化，请刷新状态')
        else:
            meta = await self.metadata(ticket['auth'], delivery.project_id, delivery.artifact.path)
            if not meta or meta.get('modified') != saved['artifact'].get('modified'):
                raise HTTPException(409, '成果文件元数据已变化，请刷新状态')
        history = (await self.request(self.workbench_url, 'GET', prefix + '/review-history', ticket['auth'])).json()
        receipt = saved['receipt']
        match_keys=['created','artifacts','validation']+[key for key in ('session_id','turn_id','operation_id') if key in receipt]
        matching = next((event for event in history.get('events',[]) if event.get('kind') == 'agent.receipt'
            and event.get('owner') == row['owner'] and event.get('project') == delivery.project_id
            and all(event.get('payload',{}).get(key) == receipt.get(key) for key in match_keys)), None)
        if matching is None:
            raise HTTPException(409, '原生处理记录中尚未找到当前成果回执')
        return {**saved, 'processing_history_verified':True, 'history_event_id':matching['id'],
            'delivery_summary':{'project':project['name'], 'artifact':saved['artifact']['path'],
                'task':delivery.task, 'validation_scope':'成果保存、版本和处理记录；科研有效性见项目验证证据'}}

    async def commit(self, run_id, secret):
        ticket = self.ticket(run_id, secret)
        async with self.locks.setdefault(run_id, asyncio.Lock()):
            row = self.row(run_id)
            if row["receipt"]:
                return json.loads(row["receipt"])
            if not row["context"]:
                raise HTTPException(409, "先完成工作台规范与项目核对")
            delivery = Delivery.model_validate_json(row["payload"])
            artifact, auth = delivery.artifact, ticket["auth"]
            await self.project(auth, delivery.project_id, delivery.workspace_id)
            identity=await self.native_identity(auth,delivery)
            prefix = "/research/api/projects/" + delivery.project_id
            written = json.loads(row["written"]) if row["written"] else None
            if artifact.type == "manuscript":
                current = (await self.request(self.workbench_url, "GET", prefix + "/manuscript", auth)).json()
                document = artifact.document
                # Recover a successful native write if the HTTP reply was interrupted.
                same = current.get("revision") == document["revision"] + 1 and all(
                    current.get(k) == document[k] for k in ("content", "title", "template") if k in document)
                if not written and not same:
                    current = (await self.request(self.workbench_url, "PUT", prefix + "/manuscript", auth,
                                                   json={**document, "reason": artifact.summary})).json()
                if any(current.get(k) != document[k] for k in ("content", "title", "template") if k in document):
                    raise HTTPException(409, "稿件写入后已变化，保留当前稿，交付尚未确认")
                written = {"path": "manuscript/main.json", "revision": current["revision"]}
            else:
                meta = await self.metadata(auth, delivery.project_id, artifact.path)
                if artifact.type == "existing":
                    if not meta or meta["kind"] != "file":
                        raise HTTPException(404, "回执指向的成果文件尚不存在")
                else:
                    same = False
                    if meta and meta["kind"] == "file":
                        old = await self.request(self.workbench_url, "GET", prefix + "/file", auth,
                                                  params={"path": artifact.path})
                        same = old.text == artifact.content
                    if not same and not written:
                        if meta and artifact.expected_modified is None:
                            raise HTTPException(409, "替换现有文件需要当前 expected_modified，旧文件已保留")
                        await self.request(self.workbench_url, "PUT", prefix + "/file", auth,
                            json={"path": artifact.path, "content": artifact.content,
                                  "expected_modified": artifact.expected_modified, "reason": artifact.summary})
                    check = await self.request(self.workbench_url, "GET", prefix + "/file", auth,
                                                 params={"path": artifact.path})
                    if check.text != artifact.content:
                        raise HTTPException(409, "成果写入后已变化，尚未确认交付")
                    meta = await self.metadata(auth, delivery.project_id, artifact.path)
                written = {"path": "project/" + artifact.path, "modified": meta["modified"], "size": meta["size"]}
            self.update(run_id, written=json.dumps(written), state="written")
            checks = [{"check": "workbench_readback", "result": "passed", "evidence": written["path"]}]
            checks += [{**check, "reported_by": "agent"} for check in delivery.validation]
            stage = {"paper": "writing", "literature": "landscape", "code-review": "review", "test": "code", "slides": "slides-plan"}.get(delivery.task, delivery.task)
            purpose = ""
            if stage == "slides-plan":
                project_info = await self.project(auth, delivery.project_id, delivery.workspace_id)
                purpose = project_info.get("config", {}).get("slides_confirmation", {}).get("profile", "")
            receipt_body = {
                "stage": stage, "purpose": purpose, "operation_id": run_id,
                **identity,
                "question_ids": delivery.question_ids,
                "artifacts": [{"path": written["path"], "summary": artifact.summary,
                               "source_paths": artifact.source_paths}],
                "validation": checks, "limitations": delivery.limitations,
            }
            receipt = (await self.request(self.workbench_url, "POST", prefix + "/agent-receipt", auth, json=receipt_body)).json()
            result = {"status": "saved", "run_id": run_id, "request_id": delivery.request_id,
                      "project_id": delivery.project_id, "session_id": delivery.session_id,
                      **({'turn_id':delivery.turn_id} if delivery.turn_id else {}),
                      "standard_version": delivery.standard_version, "artifact": written,
                      "url": self.origin + "/research", "receipt": receipt}
            self.update(run_id, state="saved", receipt=json.dumps(result, ensure_ascii=False))
            return result

    async def status(self, auth, run_id):
        owner = (await self.profile(auth))["id"]
        row = self.row(run_id)
        if row["owner"] != owner:
            raise HTTPException(404, "交付任务不存在")
        if row["receipt"]:
            return {**json.loads(row["receipt"]), "workflow_run_id": row["workflow_run_id"],
                    "automation": self.automation.summary(run_id)}
        return {"run_id": run_id, "status": row["state"], "error": row["error"],
                "workflow_run_id": row["workflow_run_id"], "automation": self.automation.summary(run_id)}

    async def deliver(self, auth, delivery: Delivery):
        owner = (await self.profile(auth))["id"]
        await self.project(auth, delivery.project_id, delivery.workspace_id)
        serialized = delivery.model_dump_json()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM deliveries WHERE owner=? AND request_id=?",
                               (owner, delivery.request_id)).fetchone()
            if prior:
                if Delivery.model_validate_json(prior['payload']).model_dump()!=delivery.model_dump():
                    raise HTTPException(409, "同一 request_id 的内容发生变化，请使用新编号")
                if prior["receipt"]:
                    return {**json.loads(prior["receipt"]), "workflow_run_id": prior["workflow_run_id"]}
                if prior["state"] not in {"failed", "interrupted"}:
                    return {"run_id": prior["id"], "status": prior["state"], "message": "查询同一任务，避免重复提交"}
                run_id = prior["id"]
                db.execute("UPDATE deliveries SET state='pending',error=NULL,updated=? WHERE id=?", (time.time(), run_id))
            else:
                run_id = uuid.uuid4().hex
                db.execute("INSERT INTO deliveries(id,owner,request_id,project_id,payload,state,created,updated) VALUES(?,?,?,?,?,'pending',?,?)",
                           (run_id, owner, delivery.request_id, delivery.project_id, serialized, time.time(), time.time()))
        secret = secrets.token_urlsafe(32)
        self.tickets[run_id] = {"secret": secret, "auth": auth, "expires": time.time() + 600}
        try:
            key = self.dify_key.read_text().strip()
            response = await self.request(self.dify_url, "POST", "/v1/workflows/run",
                {"Authorization": "Bearer " + key}, json={"inputs": {"run_id": run_id, "ticket": secret},
                "response_mode": "blocking", "user": "deeptutor-" + owner})
            run = response.json()
            if not isinstance(run,dict) or not isinstance(run.get('data'),dict):raise ValueError('Dify 未返回结构化运行终态')
            workflow_id = run.get("workflow_run_id") or run.get("data", {}).get("id")
            self.update(run_id, workflow_run_id=workflow_id)
            row = self.row(run_id)
            if row["receipt"]:
                result = workflow_receipt(json.loads(row["receipt"]), run)
                self.update(run_id, receipt=json.dumps(result, ensure_ascii=False))
                return result
            error = run.get("data", {}).get("error") or "Dify 未返回成功的工作台回执"
            self.update(run_id, state="failed", error=str(error)[:1000])
            return await self.status(auth, run_id)
        except (httpx.HTTPError, OSError, HTTPException, ValueError, TimeoutError) as exc:
            # A native save can succeed even if the workflow response is lost.
            row = self.row(run_id)
            if row["receipt"]:
                result = {**json.loads(row["receipt"]), "workflow_status": "unknown",
                          "workflow_run_id": row['workflow_run_id'],
                          "workflow_error": "Native save verified; Dify terminal response was interrupted"}
                self.update(run_id, receipt=json.dumps(result, ensure_ascii=False))
                return result
            error = str(exc.detail) if isinstance(exc, HTTPException) else type(exc).__name__
            self.update(run_id, state="failed", error=error[:1000])
            return {"run_id": run_id, "status": "failed", "error": error}
        finally:
            self.tickets.pop(run_id, None)
            self.automation.enqueue(run_id)

