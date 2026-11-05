import json
from pathlib import Path
import sys

import httpx
from fastapi import HTTPException
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from delivery import Artifact, Delivery, DeliveryService


PID = "a" * 32
AUTH = {"Authorization": "Bearer owner-a"}


class Backend:
    def __init__(self):
        self.files = {}
        self.writes = 0
        self.workflow_runs = 0
        self.receipts = []
        self.version = "2026-11-01"
        self.manuscript = {"revision": 0, "title": "Study", "template": "chinese", "content": {"type": "doc", "content": []}}
        self.fail_receipt = False
        self.history = []
        self.page_status = 200
        self.skills = [{"id": "review", "content": "Preserve source evidence"}]

    async def handle(self, request):
        path = request.url.path
        if request.url.host == "dify":
            self.workflow_runs += 1
            value = json.loads(request.content)
            if 'url' in value['inputs']:
                evidence={'status':'ready','source_url':value['inputs']['url'],'content':'Actual public page text',
                    'source':'Dify WebScraper','truncated':False}
                return httpx.Response(200,json={'workflow_run_id':'reader-test-run',
                    'data':{'status':'succeeded','outputs':{'evidence':json.dumps(evidence)}}})
            run_id, ticket = value["inputs"]["run_id"], value["inputs"]["ticket"]
            await self.service.prepare(run_id, ticket)
            result = await self.service.commit(run_id, ticket)
            return httpx.Response(200, json={"workflow_run_id": "real-test-workflow-id", "data": {"status": "succeeded", "outputs": {"receipt": json.dumps(result)}}})
        if request.url.host=='public.example':
            assert request.method=='HEAD' and not request.headers.get('authorization')
            return httpx.Response(self.page_status)
        owner = request.headers.get("authorization", "").removeprefix("Bearer ")
        if path == "/api/auth/profile":
            return httpx.Response(200, json={"id": owner}) if owner in {"owner-a", "owner-b"} else httpx.Response(401, json={"detail": "Unauthorized"})
        if path == "/research/api/projects":
            return httpx.Response(200, json={"projects": [{"id": PID, "native_id": "ws-a", "name": "Study"}] if owner == "owner-a" else []})
        if path.endswith("/agent-context"):
            return httpx.Response(200, json={"standard_version": self.version, "project": {"id": PID},
                "instructions":"Read project sources before editing", "skills": self.skills})
        if path.endswith('/review-history'):
            return httpx.Response(200, json={'events':self.history})
        if path.endswith('/native-session'):
            session_id=request.url.params.get('session_id')
            turn_id=request.url.params.get('turn_id','')
            if session_id!='session-a' or turn_id not in ('','turn-a'):
                return httpx.Response(404,json={'detail':'Session or turn not in project workspace'})
            return httpx.Response(200,json={'session_id':session_id,'native_workspace_id':'ws-a',
                **({'turn_id':turn_id} if turn_id else {})})
        if path.endswith("/annotations"):
            return httpx.Response(200, json={"items": [{"id": "question-a"}]})
        if path.endswith("/manuscript"):
            if request.method == "PUT":
                value = json.loads(request.content)
                if value["revision"] != self.manuscript["revision"]:
                    return httpx.Response(409, json={"detail": "stale revision"})
                self.manuscript = {**value, "revision": value["revision"] + 1}
                self.writes += 1
            return httpx.Response(200, json=self.manuscript)
        if path.endswith("/files"):
            parent = request.url.params.get("path", "")
            items = [{"path": p, "kind": "file", "modified": m, "size": len(text.encode())}
                     for p, (text, m) in self.files.items() if str(Path(p).parent).replace(".", "") == parent]
            return httpx.Response(200, json={"items": items})
        if path.endswith("/file"):
            if request.method == "PUT":
                value = json.loads(request.content)
                old = self.files.get(value["path"])
                if old and old[1] != value.get("expected_modified"):
                    return httpx.Response(409, json={"detail": "stale file"})
                self.writes += 1
                self.files[value["path"]] = (value["content"], float(self.writes))
                return httpx.Response(200, json={"saved": True})
            value = self.files.get(request.url.params["path"])
            return httpx.Response(200, text=value[0]) if value else httpx.Response(404, json={"detail": "missing"})
        if path.endswith("/agent-receipt"):
            if self.fail_receipt:
                return httpx.Response(503, json={"detail": "receipt service unavailable"})
            value = json.loads(request.content)
            self.receipts.append(value)
            record={"recorded":True, "created":"2026-11-01T00:00:00Z", **value}
            self.history.append({'id':len(self.history)+1, 'kind':'agent.receipt', 'owner':owner, 'project':PID,'payload':record})
            return httpx.Response(200, json=record)
        raise AssertionError(str(request.url))


@pytest.fixture
def setup(tmp_path):
    backend = Backend()
    key = tmp_path / "workflow-key"
    key.write_text("app-test")
    service = DeliveryService(tmp_path / "state.sqlite3", workbench_url="http://workbench", native_url="http://native",
        dify_url="http://dify", dify_key=key, origin="https://tutor.example", transport=httpx.MockTransport(backend.handle))
    backend.service = service
    return service, backend


def payload(**changes):
    value = {"request_id": "request-one", "project_id": PID, "task": "review", "workspace_id": "ws-a",
             "session_id": "session-a", "standard_version": "2026-11-01",
             "artifact": {"type": "file", "path": "docs/result.md", "content": "有来源范围的研究解释。", "summary": "保存本轮解释"}}
    value.update(changes)
    return Delivery.model_validate(value)


@pytest.mark.asyncio
async def test_workflow_saves_and_readbacks_one_native_artifact(setup):
    service, backend = setup
    result = await service.deliver(AUTH, payload())
    assert result["status"] == "saved" and result["workflow_run_id"] == "real-test-workflow-id"
    assert backend.writes == backend.workflow_runs == 1
    assert result["artifact"]["path"] == "project/docs/result.md"
    assert backend.receipts[0]["validation"][0]["check"] == "workbench_readback"


@pytest.mark.asyncio
async def test_repeating_same_delivery_does_not_run_workflow_or_write_again(setup):
    service, backend = setup
    first = await service.deliver(AUTH, payload())
    second = await service.deliver(AUTH, payload())
    assert first == second and backend.writes == backend.workflow_runs == len(backend.receipts) == 1
    with pytest.raises(HTTPException) as error:
        await service.deliver(AUTH, payload(artifact={"type": "file", "path": "docs/other.md", "content": "changed", "summary": "changed"}))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_other_account_and_other_workspace_cannot_target_project(setup):
    service, backend = setup
    for auth, body in [({"Authorization": "Bearer owner-b"}, payload()), (AUTH, payload(workspace_id="other-workspace"))]:
        with pytest.raises(HTTPException):
            await service.deliver(auth, body)
    assert backend.writes == backend.workflow_runs == 0


@pytest.mark.asyncio
async def test_existing_file_requires_current_revision(setup):
    service, backend = setup
    backend.files["docs/result.md"] = ("作者的新内容", 17.0)
    result = await service.deliver(AUTH, payload())
    assert result["status"] == "failed" and backend.files["docs/result.md"][0] == "作者的新内容"
    assert backend.writes == 0
    result = await service.deliver(AUTH, payload(request_id="request-two", artifact={
        "type": "file", "path": "docs/result.md", "content": "修改后", "summary": "修订", "expected_modified": 17.0}))
    assert result["status"] == "saved" and backend.writes == 1


@pytest.mark.asyncio
async def test_updated_skill_contract_blocks_old_delivery(setup):
    service, backend = setup
    backend.version = "new-version"
    result = await service.deliver(AUTH, payload())
    assert result["status"] == "failed" and backend.writes == 0


@pytest.mark.asyncio
async def test_current_lazy_skill_catalog_can_deliver_without_eager_fulltext(setup):
    service, backend = setup
    backend.skills = [{'id':'review','name':'review','description':'Review the actual evidence',
                       'url':'/research/api/standards/skills/review'}]
    result = await service.deliver(AUTH, payload())
    assert result['status']=='saved', result
    assert backend.writes==1


@pytest.mark.asyncio
async def test_missing_skill_content_and_reference_is_not_accepted(setup):
    service, backend = setup
    backend.skills = [{'id':'review','description':'incomplete'}]
    result = await service.deliver(AUTH, payload())
    assert result['status']=='failed'
    assert backend.writes==0


@pytest.mark.asyncio
async def test_manuscript_uses_native_document_revision(setup):
    service, backend = setup
    document = {**backend.manuscript, "content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "实际稿件"}]}]}}
    result = await service.deliver(AUTH, payload(task="paper", artifact={"type": "manuscript", "document": document, "summary": "写入实际稿件"}))
    assert result["status"] == "saved" and result["artifact"]["revision"] == 1
    assert backend.manuscript["template"] == "chinese" and backend.writes == 1
    different = {**document, "title": "stale document"}
    result = await service.deliver(AUTH, payload(request_id="request-stale", task="paper", artifact={"type": "manuscript", "document": different, "summary": "旧稿"}))
    assert result["status"] == "failed" and backend.writes == 1


@pytest.mark.asyncio
async def test_retry_after_receipt_failure_preserves_saved_file(setup):
    service, backend = setup
    backend.fail_receipt = True
    first = await service.deliver(AUTH, payload())
    assert first["status"] == "failed" and backend.writes == 1
    backend.fail_receipt = False
    second = await service.deliver(AUTH, payload())
    assert second["status"] == "saved" and backend.writes == 1


@pytest.mark.asyncio
async def test_status_is_account_scoped(setup):
    service, backend = setup
    result = await service.deliver(AUTH, payload())
    with pytest.raises(HTTPException) as error:
        await service.status({"Authorization": "Bearer owner-b"}, result["run_id"])
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_delivery_verify_requires_current_artifact_and_matching_history(setup):
    import time
    service, backend = setup
    result = await service.deliver(AUTH, payload())
    service.tickets[result['run_id']]={'auth':AUTH,'secret':'test-ticket','expires':time.time()+60}
    verified = await service.verify_delivery(result['run_id'],'test-ticket')
    assert verified['processing_history_verified'] is True
    assert verified['history_event_id'] == 1
    backend.files['docs/result.md']=('User changed this after delivery',999.0)
    with pytest.raises(HTTPException) as caught:
        await service.verify_delivery(result['run_id'],'test-ticket')
    assert caught.value.status_code == 409
    assert backend.writes == 1


@pytest.mark.asyncio
async def test_missing_native_history_cannot_become_verified(setup):
    import time
    service, backend = setup
    result = await service.deliver(AUTH, payload())
    service.tickets[result['run_id']]={'auth':AUTH,'secret':'test-ticket','expires':time.time()+60}
    backend.history.clear()
    with pytest.raises(HTTPException):
        await service.verify_delivery(result['run_id'],'test-ticket')


@pytest.mark.asyncio
async def test_public_page_uses_installed_dify_reader_with_source_identity(setup):
    service,backend=setup
    (service.dify_key.parent/'web-reader-key').write_text('reader-test-key')
    result=await service.read_webpage(AUTH,'https://public.example/page')
    assert result['status']=='ready' and result['source']=='Dify WebScraper'
    assert result['source_url']=='https://public.example/page' and result['workflow_run_id']=='reader-test-run'
    assert backend.workflow_runs==1 and backend.writes==0


@pytest.mark.asyncio
async def test_page_access_challenge_does_not_invoke_reader(setup):
    service,backend=setup
    (service.dify_key.parent/'web-reader-key').write_text('reader-test-key')
    backend.page_status=403
    result=await service.read_webpage(AUTH,'https://public.example/page')
    assert result['error']['code']=='access_required'
    assert backend.workflow_runs==0


@pytest.mark.parametrize("path", ["../outside.md", "/etc/file", ".env", "docs/.secret", "docs\\outside.md"])
def test_artifact_path_stays_in_visible_project_directory(path):
    with pytest.raises(ValidationError):
        Artifact(type="file", path=path, content="test", summary="test")
