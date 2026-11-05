import json
import pytest
from server.storage import Store, Conflict
from server.quality_api import receipt_review, latest_gate


def setup(tmp_path):
    store=Store(tmp_path/'s');project=store.create('owner','receipt fixture');pid=project['id']
    root=store.path('owner',pid);target=root/'project/docs/result.md';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('A bounded result with traceable assumptions.',encoding='utf8')
    payload={'stage':'review','operation_id':'receipt-fixture-1','artifacts':[{'path':'project/docs/result.md','summary':'review this result','source_paths':[]} ]}
    return store,pid,payload


def test_receipt_schedules_one_independent_review_job(tmp_path):
    store,pid,payload=setup(tmp_path);scheduled=[]
    run=lambda jid,callback:scheduled.append((jid,callback))
    first=receipt_review(store,lambda owner:tmp_path/'api.json',run,'owner',pid,payload,{'Cookie':'fixture'})
    repeated=receipt_review(store,lambda owner:tmp_path/'api.json',run,'owner',pid,payload,{'Cookie':'fixture'})
    assert first['job_id']==repeated['job_id'] and len(scheduled)==1
    assert first['automatic_flow'] is False and first['status']=='pending'
    assert len(store.jobs('owner',pid))==1
    altered=json.loads(json.dumps(payload));altered['artifacts'][0]['summary']='different task'
    with pytest.raises(Conflict):receipt_review(store,lambda owner:tmp_path/'api.json',run,'owner',pid,altered,{})


def test_unidentified_receipt_never_claims_quality_passed(tmp_path):
    store,pid,payload=setup(tmp_path);payload.pop('stage')
    result=receipt_review(store,lambda owner:tmp_path/'api.json',lambda *a:pytest.fail('unexpected job'),'owner',pid,payload,{})
    assert result['status']=='not_reviewed' and result['required'] is True and result['automatic_flow'] is False
    assert store.jobs('owner',pid)==[]


def test_uncreated_stage_artifact_is_not_an_endpoint_failure(tmp_path):
    store,pid,payload=setup(tmp_path)
    gate=latest_gate(store,'owner',pid,'slides-plan','group')
    assert gate['decision']=='not_reviewed' and gate['can_proceed'] is False
    assert gate['automatic_flow'] is False and 'slides/plan.json' in gate['missing_paths']
