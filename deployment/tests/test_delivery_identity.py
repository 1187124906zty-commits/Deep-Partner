"""Optional native links retain causal identity through Dify delivery."""
import json
import time

import pytest
from fastapi import HTTPException

from test_delivery import setup,payload,AUTH


@pytest.mark.asyncio
async def test_delivery_forwards_validated_session_turn_and_operation(setup):
    service,backend=setup
    value=await service.deliver(AUTH,payload(turn_id='turn-a'))
    assert value['status']=='saved' and value['turn_id']=='turn-a'
    receipt=backend.receipts[0]
    assert receipt['session_id']=='session-a' and receipt['turn_id']=='turn-a'
    assert receipt['operation_id']==value['run_id']


@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[{'session_id':'foreign-session'}, {'turn_id':'foreign-turn'},
                                  {'session_id':'','turn_id':'turn-a'}])
async def test_invalid_native_identity_stops_before_artifact_write(setup,changes):
    service,backend=setup
    value=await service.deliver(AUTH,payload(**changes))
    assert value['status']=='failed' and backend.writes==0 and backend.receipts==[]


@pytest.mark.asyncio
async def test_history_verification_rejects_changed_optional_turn(setup):
    service,backend=setup
    value=await service.deliver(AUTH,payload(turn_id='turn-a'))
    run_id=value['run_id'];service.tickets[run_id]={'secret':'test-only-ticket','auth':AUTH,'expires':time.time()+60}
    # Artifact contents still match. Only the causal turn in immutable history differs.
    backend.history[-1]['payload']['turn_id']='different-turn'
    with pytest.raises(HTTPException) as error:await service.verify_delivery(run_id,'test-only-ticket')
    assert error.value.status_code==409


@pytest.mark.asyncio
async def test_old_saved_payload_without_optional_turn_remains_idempotent(setup):
    service,backend=setup
    body=payload(session_id='')
    value=await service.deliver(AUTH,body)
    old=json.loads(service.row(value['run_id'])['payload']);old.pop('turn_id')
    with service.db() as db:db.execute('UPDATE deliveries SET payload=? WHERE id=?',
                                     (json.dumps(old),value['run_id']))
    repeated=await service.deliver(AUTH,body)
    assert repeated['run_id']==value['run_id'] and backend.writes==backend.workflow_runs==1
    assert 'session_id' not in backend.receipts[0] and 'turn_id' not in backend.receipts[0]
