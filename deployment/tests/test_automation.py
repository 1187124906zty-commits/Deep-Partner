"""Failure injection at the durable event and Dify callback boundaries."""
import asyncio
import json
from pathlib import Path
import time

from fastapi import HTTPException
import httpx
import pytest

from test_delivery import setup, payload, AUTH
from delivery import DeliveryService


def queued(service):
    with service.db() as db:
        return dict(db.execute('SELECT * FROM automation_events ORDER BY created DESC LIMIT 1').fetchone())


@pytest.mark.asyncio
async def test_events_created_once_for_repeated_delivery(setup):
    service, backend = setup
    first = await service.deliver(AUTH, payload())
    await service.deliver(AUTH, payload())
    with service.db() as db:
        assert db.execute('SELECT count(*) FROM automation_events').fetchone()[0] == 1
    assert queued(service)['run_id'] == first['run_id']
    assert backend.writes == 1


@pytest.mark.asyncio
async def test_forged_event_and_wrong_branch_cannot_settle(setup):
    service, _ = setup
    await service.deliver(AUTH, payload())
    event = queued(service)
    with pytest.raises(HTTPException):
        service.automation.inspect(event['id'], 'forged')
    # Fixture deliberately omits the final processing-history verification.
    assert service.automation.inspect(event['id'], event['token'])['outcome'] == 'attention_required'
    with pytest.raises(HTTPException):
        service.automation.settle(event['id'], event['token'], 'success')
    assert queued(service)['state'] == 'queued'


@pytest.mark.asyncio
async def test_duplicate_callback_is_idempotent_and_never_writes_artifacts(setup):
    service, backend = setup
    await service.deliver(AUTH, payload())
    event = queued(service)
    results = [service.automation.settle(event['id'], event['token'], 'attention') for _ in range(25)]
    assert all(r == results[0] for r in results)
    assert queued(service)['state'] == 'completed'
    assert backend.writes == backend.workflow_runs == len(backend.receipts) == 1


@pytest.mark.asyncio
async def test_old_failed_event_is_superseded_after_same_run_recovers(setup):
    service, backend = setup
    backend.fail_receipt = True
    result = await service.deliver(AUTH, payload())
    event = queued(service)
    backend.fail_receipt = False
    recovered = await service.deliver(AUTH, payload())
    assert recovered['run_id'] == result['run_id'] and recovered['status'] == 'saved'
    assert service.automation.inspect(event['id'], event['token'])['outcome'] == 'superseded'
    assert backend.writes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout', 'disconnect', 429, 503])
async def test_callback_failures_keep_saved_content_and_queue_for_retry(setup, failure):
    service, backend = setup
    result = await service.deliver(AUTH, payload())
    service.automation.config.write_text(json.dumps({'webhook_url':'http://events/hook'}))
    async def handle(request):
        if failure == 'timeout':raise httpx.ReadTimeout('injected',request=request)
        if failure == 'disconnect':raise httpx.ConnectError('injected',request=request)
        return httpx.Response(failure)
    service.transport = httpx.MockTransport(handle)
    await service.automation.dispatch()
    event = queued(service)
    assert event['state'] == 'queued' and event['attempts'] == 1 and event['next_attempt'] > time.time()
    assert service.row(result['run_id'])['state'] == 'saved' and backend.writes == 1


@pytest.mark.asyncio
async def test_webhook_acceptance_is_not_completion_and_ack_race_does_not_regress(setup):
    service, _ = setup
    await service.deliver(AUTH, payload())
    service.automation.config.write_text(json.dumps({'webhook_url':'http://events/hook'}))
    async def accepted(request):return httpx.Response(202,json={'accepted':True})
    service.transport = httpx.MockTransport(accepted)
    await service.automation.dispatch()
    assert queued(service)['state'] == 'dispatched'
    with service.db() as db:db.execute('UPDATE automation_events SET next_attempt=0')
    async def ack_before_response(request):
        value=json.loads(request.content)
        service.automation.settle(value['event_id'],value['event_token'],'attention')
        return httpx.Response(202,json={'accepted':True})
    service.transport = httpx.MockTransport(ack_before_response)
    await service.automation.dispatch()
    assert queued(service)['state'] == 'completed'


@pytest.mark.asyncio
async def test_service_restart_preserves_pending_events_without_credentials(setup):
    service, _ = setup
    result=await service.deliver(AUTH,payload())
    event=queued(service)
    restarted=DeliveryService(service.state,workbench_url=service.workbench_url,native_url=service.native_url,
        dify_url=service.dify_url,dify_key=service.dify_key,origin=service.origin,transport=service.transport)
    assert restarted.automation.event(event['id'],event['token'])['state']=='queued'
    assert restarted.row(result['run_id'])['state']=='saved' and not restarted.tickets
    assert 'owner-a' not in event['fingerprint']


@pytest.mark.asyncio
async def test_retry_budget_exhaustion_surfaces_action_required(setup):
    service,_=setup
    await service.deliver(AUTH,payload())
    service.automation.config.write_text(json.dumps({'webhook_url':'http://events/hook'}))
    with service.db() as db:db.execute('UPDATE automation_events SET attempts=5,next_attempt=0')
    await service.automation.dispatch()
    assert queued(service)['state']=='attention_required'


@pytest.mark.asyncio
async def test_timed_reconciliation_marks_only_stale_incomplete_run_and_probes_services(setup):
    service,backend=setup
    backend.fail_receipt=True
    result=await service.deliver(AUTH,payload())
    with service.db() as db:
        db.execute("UPDATE deliveries SET state='written',updated=? WHERE id=?",(time.time()-650,result['run_id']))
    async def healthy(request):return httpx.Response(200,json={'ok':True})
    service.transport=httpx.MockTransport(healthy)
    report=await service.automation.reconcile()
    assert report['interrupted']==1 and report['needs_attention']
    assert service.row(result['run_id'])['state']=='interrupted' and backend.writes==1


@pytest.mark.asyncio
async def test_project_activity_is_owner_scoped(setup):
    service,_=setup
    await service.deliver(AUTH,payload())
    activity=await service.automation.activity(AUTH,'a'*32,'ws-a')
    assert len(activity['deliveries'])==1
    with pytest.raises(HTTPException):
        await service.automation.activity({'Authorization':'Bearer owner-b'},'a'*32)


@pytest.mark.asyncio
async def test_acknowledgement_preserves_failure_and_rejects_another_owner(setup):
    service,_=setup
    result=await service.deliver(AUTH,payload())
    event=queued(service)
    service.automation.settle(event['id'],event['token'],'attention')
    with pytest.raises(HTTPException):
        await service.automation.acknowledge({'Authorization':'Bearer owner-b'},result['run_id'],'Cannot acknowledge another owner')
    await service.automation.acknowledge(AUTH,result['run_id'],'Expected injected verification failure, no research content changed')
    summary=service.automation.summary(result['run_id'])
    assert summary['acknowledged'] and summary['result']['outcome']=='attention_required'


@pytest.mark.asyncio
async def test_schedule_recovers_save_to_queue_crash_window_without_rewriting(setup):
    service,backend=setup
    result=await service.deliver(AUTH,payload())
    with service.db() as db:db.execute('DELETE FROM automation_events')
    async def healthy(request):return httpx.Response(200,json={'ok':True})
    service.transport=httpx.MockTransport(healthy)
    await service.automation.reconcile()
    assert queued(service)['run_id']==result['run_id'] and queued(service)['state']=='queued'
    assert backend.writes==backend.workflow_runs==1


@pytest.mark.asyncio
async def test_concurrent_duplicate_submissions_share_operation_without_duplicate_writes(setup):
    service,backend=setup
    results=await asyncio.gather(*(service.deliver(AUTH,payload()) for _ in range(30)))
    assert len({r['run_id'] for r in results})==1
    assert backend.writes==backend.workflow_runs==len(backend.receipts)==1
    assert service.row(results[0]['run_id'])['state']=='saved'
