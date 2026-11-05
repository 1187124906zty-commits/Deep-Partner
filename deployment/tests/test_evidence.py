"""Evidence contract tests with real branch execution and injected upstream faults.

The Dify transport invokes EvidenceService.branch just as the installed workflow
does. Its final output is deliberately untrusted: coverage must come from the
recorded provider calls, including when the workflow fails midway through.
"""
import asyncio
from collections import Counter
import copy
import json
from pathlib import Path
import sys
import time

import httpx
from fastapi import HTTPException
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from delivery import DeliveryService
from evidence import EvidenceRequest, EvidenceService
from test_delivery import AUTH, PID, Backend


QUERY = "chloride sulfate transport"
RAG = {
    "source": "DeepTutor native RAG",
    "result": {"sources": [
        {"evidence_text": "Passage on competitive chloride binding.",
         "page_label": "12", "source": "reports/transport.pdf",
         "document_key": "document-native-42", "title": "Transport report", "score": 0.92},
        {"evidence_text": "A different passage on sulfate precipitation.",
         "page_label": "13", "source": "reports/transport.pdf",
         "document_key": "document-native-42", "title": "Transport report", "score": 0.88},
    ]},
}
WEB = {"status": "ok", "source": "public-web", "items": [
    {"title": "Public transport study", "url": "https://public.example/study",
     "snippet": "Public page search excerpt", "provider": "web-fixture"}
]}
PAPERS = {"status": "ok", "source": "Crossref", "items": [
    {"title": "Coupled transport", "doi": "10.1234/transport",
     "url": "https://doi.org/10.1234/transport", "abstract": "Paper metadata abstract",
     "authors": ["A. Researcher"], "year": 2024}
]}


def request(**changes):
    return EvidenceRequest.model_validate({"project_id": PID, "workspace_id": "ws-a",
                                           "query": QUERY, **changes})


def coverage(result):
    return {entry["branch"]: entry for entry in result["coverage"]}


class EvidenceBackend(Backend):
    """Only network boundaries are mocked; branch parsing and storage are real."""

    def __init__(self):
        super().__init__()
        self.bound = ["library-a"]
        self.responses = {"knowledge": copy.deepcopy(RAG), "web": copy.deepcopy(WEB),
                          "papers": copy.deepcopy(PAPERS)}
        self.faults = {}
        self.calls = []
        self.workflow_mode = "complete"
        self.workflow_entered = asyncio.Event()
        self.workflow_release = asyncio.Event()
        self.hold_workflows = False
        self.hold_providers = set()
        self.provider_release = asyncio.Event()
        self.provider_entered = {name: asyncio.Event() for name in self.responses}
        self.two_provider_calls = asyncio.Event()
        self.active = Counter()
        self.peak = Counter()
        self.workflow_ids = []

    async def handle(self, req):
        path = req.url.path
        owner = req.headers.get("authorization", "").removeprefix("Bearer ")
        if req.url.host == "dify":
            self.workflow_runs += 1
            body = json.loads(req.content)
            run_id = body["inputs"]["run_id"]
            self.workflow_ids.append(run_id)
            self.workflow_entered.set()
            assert req.headers["authorization"] == "Bearer evidence-test-key"
            assert body["user"] == "deeptutor-owner-a"
            if self.hold_workflows:
                await self.workflow_release.wait()
            if self.workflow_mode == "forged":
                output = {"status": "ready", "items": [{"title": "Fabricated evidence"}]}
            else:
                names = ("web",) if self.workflow_mode in {"fail_after_web", "timeout_after_web", "missing_branch"} else ("knowledge", "web", "papers")
                await asyncio.gather(*(self.service.evidence.branch(run_id, name) for name in names))
                if self.workflow_mode == "fail_after_web":
                    return httpx.Response(503, json={"detail": "Dify stopped after the web branch"})
                if self.workflow_mode == "timeout_after_web":
                    raise httpx.ReadTimeout("Dify reply timed out", request=req)
                if self.workflow_mode == "failed_terminal":
                    return httpx.Response(200, json={"data": {"status": "failed", "outputs": {}}})
                if self.workflow_mode == "invalid_terminal_json":
                    return httpx.Response(200, json={"data": {"status": "succeeded", "outputs": {"evidence": "invalid JSON"}}})
                if self.workflow_mode == "missing_terminal_data":
                    return httpx.Response(200, json={"data": None})
                output = {}  # The provider receipts, rather than this model output, are authoritative.
            return httpx.Response(200, json={"workflow_run_id": "evidence-workflow-" + run_id,
                "data": {"status": "succeeded", "outputs": {"evidence": json.dumps(output)}}})
        if path == "/research/api/projects":
            return httpx.Response(200, json={"projects": [{"id": PID, "native_id": "ws-a",
                "name": "Study", "config": {"knowledge_bases": self.bound}}] if owner == "owner-a" else []})
        name = ("knowledge" if path.endswith("/knowledge/search") else
                "papers" if path.endswith("/literature/search") else
                "web" if path == "/research/api/search/web" else None)
        if name is None:
            return await super().handle(req)
        body = json.loads(req.content) if req.content else None
        library = body.get("knowledge_base") if body else None
        self.calls.append({"branch": name, "body": body, "params": dict(req.url.params),
                           "auth": req.headers.get("authorization"), "path": path})
        self.active[name] += 1
        self.peak[name] = max(self.peak[name], self.active[name])
        self.provider_entered[name].set()
        if self.active[name] >= 2:
            self.two_provider_calls.set()
        try:
            if name in self.hold_providers:
                await self.provider_release.wait()
            fault = self.faults.get(library, self.faults.get(name))
            if isinstance(fault, int):
                return httpx.Response(fault, json={"detail": "Injected upstream status " + str(fault)})
            if fault == "timeout":
                raise httpx.ReadTimeout("Injected provider timeout", request=req)
            if fault == "disconnect":
                raise httpx.ConnectError("Injected transport disconnect", request=req)
            if fault == "invalid_json":
                return httpx.Response(200, text="not JSON")
            return httpx.Response(200, json=self.responses[name])
        finally:
            self.active[name] -= 1


@pytest.fixture
def evidence_setup(tmp_path):
    backend = EvidenceBackend()
    key = tmp_path / "workflow-key"
    key.write_text("delivery-test-key")
    (tmp_path / "evidence-key").write_text("evidence-test-key")
    service = DeliveryService(tmp_path / "state.sqlite3", workbench_url="http://workbench",
        native_url="http://native", dify_url="http://dify", dify_key=key,
        origin="https://tutor.example", transport=httpx.MockTransport(backend.handle))
    backend.service = service
    return service, backend


@pytest.mark.asyncio
async def test_three_sources_execute_concurrently_and_preserve_evidence_identity(evidence_setup):
    service, backend = evidence_setup
    backend.hold_providers = {"knowledge", "web", "papers"}
    task = asyncio.create_task(service.evidence.search(AUTH, request()))
    try:
        # Each provider must enter before any is released: this detects serial execution.
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in backend.provider_entered.values())), 1)
        assert not task.done()
    finally:
        backend.provider_release.set()
    result = await task
    assert result["status"] == "ready" and result["missing_sources"] == []
    assert {entry["status"] for entry in result["coverage"]} == {"ok"}
    assert {item["branch"] for item in result["items"]} == {"knowledge", "web", "papers"}
    rag = [item for item in result["items"] if item["branch"] == "knowledge"]
    assert [(item["document_id"], item["locator"], item["excerpt"]) for item in rag] == [
        ("document-native-42", "12", RAG["result"]["sources"][0]["evidence_text"]),
        ("document-native-42", "13", RAG["result"]["sources"][1]["evidence_text"])]
    assert all(item["source"] == "DeepTutor native RAG" and item["knowledge_base"] == "library-a" for item in rag)
    assert all(item["evidence_kind"] == "indexed-source-excerpt" for item in rag)
    for name, expected in [("web", WEB["items"][0]), ("papers", PAPERS["items"][0])]:
        item = next(item for item in result["items"] if item["branch"] == name)
        assert item["raw"] == expected and item["query"] == QUERY
        assert item["url"] == expected["url"] and item["title"] == expected["title"]
        assert item["evidence_kind"] == "metadata-and-search-snippet"
    paper = next(item for item in result["items"] if item["branch"] == "papers")
    assert paper["doi"] == "10.1234/transport" and paper["source"] == "Crossref"
    assert all(call["auth"] == "Bearer owner-a" for call in backend.calls)
    assert result["workflow_run_id"].startswith("evidence-workflow-")


@pytest.mark.asyncio
async def test_query_limit_paper_provider_and_project_are_forwarded(evidence_setup):
    service, backend = evidence_setup
    await service.evidence.search(AUTH, request(limit=2, paper_source="crossref"))
    calls = {call["branch"]: call for call in backend.calls}
    assert calls["knowledge"]["body"] == {"query": QUERY, "mode": "semantic", "knowledge_base": "library-a", "limit": 2}
    assert calls["web"]["params"]["q"] == QUERY
    assert calls["papers"]["params"] == {"q": QUERY, "source": "crossref", "page": "1", "limit": "2"}
    assert PID in calls["papers"]["path"] and PID in calls["knowledge"]["path"]


@pytest.mark.asyncio
async def test_no_hits_is_empty_with_complete_coverage(evidence_setup):
    service, backend = evidence_setup
    backend.responses = {"knowledge": {"result": {"sources": []}}, "web": {"items": []}, "papers": {"items": []}}
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "empty" and result["items"] == [] and result["missing_sources"] == []
    assert {entry["status"] for entry in result["coverage"]} == {"empty"}


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", ["knowledge", "web", "papers"])
@pytest.mark.parametrize("fault", ["timeout", "disconnect", "invalid_json"])
async def test_single_provider_failure_retains_other_sources(evidence_setup, branch, fault):
    service, backend = evidence_setup
    backend.faults[branch] = fault
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "partial" and result["missing_sources"] == [branch]
    assert {item["branch"] for item in result["items"]} == {"knowledge", "web", "papers"} - {branch}
    assert coverage(result)[branch]["status"] == ("timed_out" if fault == "timeout" else "failed")
    assert all(entry["status"] == "ok" for name, entry in coverage(result).items() if name != branch)


@pytest.mark.asyncio
async def test_unbound_project_marks_knowledge_unavailable_but_keeps_other_sources(evidence_setup):
    service, backend = evidence_setup
    backend.bound = []
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "partial" and result["missing_sources"] == ["knowledge"]
    assert coverage(result)["knowledge"]["status"] == "not_configured"
    assert coverage(result)["knowledge"]["error"]["code"] == "knowledge_base_unbound"
    assert {call["branch"] for call in backend.calls} == {"web", "papers"}


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", ["knowledge", "web", "papers"])
@pytest.mark.parametrize("status,retryable", [(401, False), (403, False), (429, True), (500, True), (502, True), (503, True), (504, True)])
async def test_http_failures_keep_actionable_status_and_retry_semantics(evidence_setup, branch, status, retryable):
    service, backend = evidence_setup
    backend.faults[branch] = status
    result = await service.evidence.search(AUTH, request(sources=[branch]))
    entry = coverage(result)[branch]
    assert result["status"] == "unavailable" and result["missing_sources"] == [branch]
    assert entry["status"] == "failed"
    errors = [entry.get("error")] + entry.get("warnings", [])
    actual = next((error for error in errors if error and error.get("code") == "http_" + str(status)), None)
    assert actual is not None, f"HTTP {status} was lost in {entry}"
    assert actual["retryable"] is retryable


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", ["web", "papers"])
async def test_structured_provider_failure_is_not_reported_as_empty(evidence_setup, branch):
    service, backend = evidence_setup
    backend.responses[branch] = {"status": "unavailable", "items": [], "source": "external-provider",
        "error": {"code": "verification_required", "retryable": False, "message": "Complete access verification"}}
    result = await service.evidence.search(AUTH, request(sources=[branch]))
    assert result["status"] == "unavailable" and result["missing_sources"] == [branch]
    assert coverage(result)[branch]["error"] == backend.responses[branch]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [
    {"result": {"error_type": "needs_reindex", "error": "Rebuild the knowledge index", "sources": []}},
    {"result": {"needs_reindex": True, "sources": []}},
    {"result": {"status": "failed", "error": "Embedding provider unavailable", "sources": []}},
])
async def test_native_rag_error_inside_http_200_is_not_a_successful_empty_search(evidence_setup, raw):
    service, backend = evidence_setup
    backend.responses["knowledge"] = raw
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "partial" and result["missing_sources"] == ["knowledge"]
    entry = coverage(result)["knowledge"]
    assert entry["status"] == "failed" and entry["error"]
    assert {item["branch"] for item in result["items"]} == {"web", "papers"}


@pytest.mark.asyncio
@pytest.mark.parametrize("branch,raw", [
    ("web", []),
    ("papers", {"items": [None]}),
    ("web", {"items": "not a result list"}),
    ("knowledge", {"result": {"sources": "not a source list"}}),
    ("knowledge", {"result": {"sources": [{"node": "not an evidence object"}]}}),
])
async def test_malformed_provider_contract_fails_only_that_branch(evidence_setup, branch, raw):
    service, backend = evidence_setup
    backend.responses[branch] = raw
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "partial" and result["missing_sources"] == [branch]
    assert coverage(result)[branch]["status"] == "failed"
    assert coverage(result)[branch]["error"]["code"] == "invalid_upstream_result"
    assert {item["branch"] for item in result["items"]} == {"knowledge", "web", "papers"} - {branch}


@pytest.mark.asyncio
@pytest.mark.parametrize("sources", [["web"], ["papers"], ["knowledge"], ["web", "papers"]])
async def test_selected_source_set_does_not_fetch_or_mark_unrequested_sources_missing(evidence_setup, sources):
    service, backend = evidence_setup
    result = await service.evidence.search(AUTH, request(sources=sources))
    assert result["status"] == "ready" and result["missing_sources"] == []
    assert {call["branch"] for call in backend.calls} == set(sources)
    assert {item["branch"] for item in result["items"]} == set(sources)
    assert all(entry["status"] == "not_requested" for name, entry in coverage(result).items() if name not in sources)


@pytest.mark.parametrize("sources", [[], ["web", "web"], ["unknown"], ["web", "papers", "knowledge", "web"]])
def test_invalid_source_sets_are_rejected(sources):
    with pytest.raises(ValidationError):
        request(sources=sources)


@pytest.mark.asyncio
@pytest.mark.parametrize("auth,changes", [
    ({"Authorization": "Bearer invalid"}, {}),
    ({"Authorization": "Bearer owner-b"}, {}),
    (AUTH, {"workspace_id": "other-workspace"}),
    (AUTH, {"knowledge_base": "unbound-private-library"}),
])
async def test_identity_workspace_and_library_checks_precede_any_provider_calls(evidence_setup, auth, changes):
    service, backend = evidence_setup
    with pytest.raises(HTTPException):
        await service.evidence.search(auth, request(**changes))
    assert backend.workflow_runs == 0 and backend.calls == []


@pytest.mark.asyncio
async def test_results_are_owner_scoped_and_persist_across_service_restart(evidence_setup):
    service, backend = evidence_setup
    result = await service.evidence.search(AUTH, request())
    restarted = DeliveryService(service.state, workbench_url=service.workbench_url, native_url=service.native_url,
        dify_url=service.dify_url, dify_key=service.dify_key, origin=service.origin, transport=service.transport)
    assert await restarted.evidence.status(AUTH, result["run_id"]) == result
    with pytest.raises(HTTPException) as error:
        await restarted.evidence.status({"Authorization": "Bearer owner-b"}, result["run_id"])
    assert error.value.status_code == 404
    assert backend.workflow_runs == 1


@pytest.mark.asyncio
async def test_unknown_and_finished_run_ids_cannot_trigger_fresh_provider_queries(evidence_setup):
    service, backend = evidence_setup
    for run_id in ["unknown-run", (await service.evidence.search(AUTH, request()))["run_id"]]:
        before = len(backend.calls)
        with pytest.raises(HTTPException) as error:
            await service.evidence.branch(run_id, "web")
        assert error.value.status_code == 404 and len(backend.calls) == before


@pytest.mark.asyncio
async def test_expired_active_run_id_is_refused_before_provider_access(evidence_setup):
    service, backend = evidence_setup
    backend.hold_workflows = True
    task = asyncio.create_task(service.evidence.search(AUTH, request()))
    await asyncio.wait_for(backend.workflow_entered.wait(), 1)
    run_id = backend.workflow_ids[0]
    service.evidence.tickets[run_id]["expires"] = time.time() - 1
    try:
        with pytest.raises(HTTPException) as error:
            await service.evidence.branch(run_id, "web")
        assert error.value.status_code == 404 and backend.calls == []
    finally:
        backend.workflow_release.set()
        result = await task
    assert result["status"] == "unavailable"


@pytest.mark.asyncio
async def test_duplicate_hit_is_removed_but_distinct_passages_of_same_document_survive(evidence_setup):
    service, backend = evidence_setup
    nodes = backend.responses["knowledge"]["result"]["sources"]
    nodes.append(copy.deepcopy(nodes[0]))
    nodes.append({**nodes[0], "evidence_text": "A separate paragraph located on the same page."})
    result = await service.evidence.search(AUTH, request(sources=["knowledge"]))
    assert len(result["items"]) == 3
    assert {item["excerpt"] for item in result["items"]} == {node["evidence_text"] for node in nodes}
    assert {item["document_id"] for item in result["items"]} == {"document-native-42"}


@pytest.mark.asyncio
async def test_same_prefix_does_not_erase_distinct_passages(evidence_setup):
    service, backend = evidence_setup
    prefix = "Shared lead-in about coupled chloride sulfate transport. " * 3
    backend.responses["knowledge"]["result"]["sources"] = [
        {"document_key": "same-document", "page_label": "7", "evidence_text": prefix + "Binding increases."},
        {"document_key": "same-document", "page_label": "7", "evidence_text": prefix + "Binding decreases."},
    ]
    result = await service.evidence.search(AUTH, request(sources=["knowledge"]))
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_same_url_and_excerpt_keep_both_web_and_literature_provenance(evidence_setup):
    service, backend = evidence_setup
    common = {"title": "Shared publication page", "url": "https://publisher.example/study", "snippet": "Same upstream excerpt"}
    backend.responses["web"]["items"] = [copy.deepcopy(common)]
    backend.responses["papers"]["items"] = [copy.deepcopy(common)]
    result = await service.evidence.search(AUTH, request(sources=["web", "papers"]))
    provenance = {(item["branch"], item["source"]) for item in result["items"]}
    provenance.update((origin["branch"], origin["source"]) for item in result["items"]
                      for origin in item.get("provenance", []))
    assert provenance == {("web", "public-web"), ("papers", "Crossref")}


@pytest.mark.asyncio
async def test_native_source_path_is_retained_when_document_key_is_absent(evidence_setup):
    service, backend = evidence_setup
    node = {"evidence_text": "Source path only passage", "page_label": "iv", "source": "native/source.pdf"}
    backend.responses["knowledge"] = {"result": {"sources": [node]}}
    result = await service.evidence.search(AUTH, request(sources=["knowledge"]))
    item, = result["items"]
    assert item["document_id"] == "native/source.pdf"
    assert item["locator"] == "iv" and item["excerpt"] == node["evidence_text"]
    assert item["raw"] == node


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fail_after_web", "timeout_after_web", "missing_branch"])
async def test_workflow_failure_retains_already_completed_provider_evidence(evidence_setup, mode):
    service, backend = evidence_setup
    backend.workflow_mode = mode
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "partial"
    assert set(result["missing_sources"]) == {"knowledge", "papers"}
    assert coverage(result)["web"]["status"] == "ok"
    assert len(result["items"]) == 1 and result["items"][0]["url"] == WEB["items"][0]["url"]
    assert "workflow_error" in result
    assert await service.evidence.status(AUTH, result["run_id"]) == result


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["failed_terminal", "invalid_terminal_json", "missing_terminal_data"])
async def test_invalid_dify_terminal_response_preserves_all_completed_provider_receipts(evidence_setup, mode):
    service, backend = evidence_setup
    backend.workflow_mode = mode
    result = await service.evidence.search(AUTH, request())
    assert {item["branch"] for item in result["items"]} == {"knowledge", "web", "papers"}
    assert all(entry["status"] == "ok" for entry in result["coverage"])
    assert result.get("workflow_error")
    assert await service.evidence.status(AUTH, result["run_id"]) == result


@pytest.mark.asyncio
async def test_unpublished_workflow_returns_explicit_unavailability_without_upstream_searches(evidence_setup):
    service, backend = evidence_setup
    (service.dify_key.parent / "evidence-key").unlink()
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "unavailable" and result["items"] == []
    assert set(result["missing_sources"]) == {"knowledge", "web", "papers"}
    assert result.get("workflow_error")
    assert backend.calls == [] and backend.workflow_runs == 0
    assert await service.evidence.status(AUTH, result["run_id"]) == result


@pytest.mark.asyncio
async def test_dify_generated_evidence_without_actual_branch_receipts_is_rejected(evidence_setup):
    service, backend = evidence_setup
    backend.workflow_mode = "forged"
    result = await service.evidence.search(AUTH, request())
    assert result["status"] == "unavailable" and result["items"] == []
    assert set(result["missing_sources"]) == {"knowledge", "web", "papers"}
    assert backend.calls == []


@pytest.mark.asyncio
async def test_partial_failure_between_bound_libraries_keeps_successful_library(evidence_setup):
    service, backend = evidence_setup
    backend.bound = ["library-a", "library-b"]
    backend.faults["library-b"] = 503
    result = await service.evidence.search(AUTH, request(sources=["knowledge"]))
    assert result["status"] == "partial" and result["missing_sources"] == ["knowledge"]
    assert coverage(result)["knowledge"]["status"] == "partial"
    assert all(item["knowledge_base"] == "library-a" for item in result["items"])
    assert coverage(result)["knowledge"]["warnings"][0]["knowledge_base"] == "library-b"


@pytest.mark.asyncio
async def test_provider_queue_deadline_includes_capacity_wait_without_blocking_completed_runs(evidence_setup):
    service, backend = evidence_setup
    backend.hold_providers = {"web"}
    service.evidence.deadlines["web"] = 2
    first = asyncio.create_task(service.evidence.search(AUTH, request(sources=["web"])))
    second = asyncio.create_task(service.evidence.search(AUTH, request(sources=["web"])))
    try:
        await asyncio.wait_for(backend.two_provider_calls.wait(), 1)
        service.evidence.deadlines["web"] = 0.05
        third = await service.evidence.search(AUTH, request(sources=["web"]))
        assert third["status"] == "unavailable"
        assert coverage(third)["web"]["status"] == "timed_out"
        assert backend.peak["web"] == 2 and len(backend.calls) == 2
    finally:
        backend.provider_release.set()
        earlier = await asyncio.gather(first, second)
    assert all(result["status"] == "ready" for result in earlier)
    recovered = await service.evidence.search(AUTH, request(sources=["web"]))
    assert recovered["status"] == "ready"


@pytest.mark.asyncio
async def test_whole_workflow_budget_rejects_excess_and_recovers_after_release(evidence_setup):
    service, backend = evidence_setup
    backend.hold_workflows = True
    active = [asyncio.create_task(service.evidence.search(AUTH, request(sources=["web"]))) for _ in range(3)]
    try:
        async def all_started():
            while backend.workflow_runs < 3:
                await asyncio.sleep(0)
        await asyncio.wait_for(all_started(), 1)
        with pytest.raises(HTTPException) as error:
            await service.evidence.search(AUTH, request(sources=["web"]))
        assert error.value.status_code == 429 and backend.workflow_runs == 3
    finally:
        backend.workflow_release.set()
        results = await asyncio.gather(*active)
    assert all(result["status"] == "ready" for result in results)
    assert (await service.evidence.search(AUTH, request(sources=["web"])))["status"] == "ready"
