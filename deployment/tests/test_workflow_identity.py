"""Dify records its own identity before saving; lost replies remain recoverable."""
import json

import httpx
import pytest

from test_delivery import setup, payload, AUTH

DIFY_ID='90c581fa-3763-4b2c-a9bb-8de3ded7d16c'


@pytest.mark.asyncio
async def test_workflow_callback_identity_survives_lost_terminal_response_and_reconciles(setup):
    service,backend=setup
    state={}
    async def handle(request):
        if request.url.host=='dify' and request.method=='POST':
            body=json.loads(request.content);run_id,ticket=body['inputs']['run_id'],body['inputs']['ticket']
            await service.prepare(run_id,ticket,DIFY_ID)
            assert service.row(run_id)['workflow_run_id']==DIFY_ID and backend.writes==0
            await service.commit(run_id,ticket)
            verified=await service.verify_delivery(run_id,ticket)
            state['terminal']={'id':DIFY_ID,'status':'succeeded','outputs':{'receipt':json.dumps(verified)}}
            backend.workflow_runs+=1
            raise httpx.ReadError('Injected final reply loss',request=request)
        if request.url.host=='dify' and request.url.path.startswith('/v1/workflows/run/'):
            assert request.url.path.endswith(DIFY_ID)
            return httpx.Response(200,json=state['terminal'])
        if request.url.path in {'/health','/health/ready','/console/api/ping'}:
            return httpx.Response(200,json={'ok':True})
        return await backend.handle(request)
    service.transport=httpx.MockTransport(handle)
    result=await service.deliver(AUTH,payload())
    assert result['status']=='saved' and result['workflow_status']=='unknown' and result['workflow_run_id']==DIFY_ID
    await service.automation.reconcile()
    restored=await service.status(AUTH,result['run_id'])
    assert restored['workflow_status']=='succeeded' and restored['processing_history_verified']
    assert backend.writes==backend.workflow_runs==len(backend.receipts)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('identifier',['not-a-workflow-id','{{#sys.workflow_run_id#}}'])
async def test_invalid_workflow_identity_fails_before_native_write(setup,identifier):
    service,backend=setup
    async def handle(request):
        if request.url.host=='dify':
            body=json.loads(request.content)
            await service.prepare(body['inputs']['run_id'],body['inputs']['ticket'],identifier)
        return await backend.handle(request)
    service.transport=httpx.MockTransport(handle)
    result=await service.deliver(AUTH,payload())
    assert result['status']=='failed' and backend.writes==0
    assert service.row(result['run_id'])['workflow_run_id'] is None
