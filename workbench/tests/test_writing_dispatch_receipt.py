import json
import pytest
from server.writing import stage_acceptance


def result(receipt):
    return {'data':{'status':'succeeded','outputs':{'receipt_intent':json.dumps(receipt)}}}


def test_successful_http_node_cannot_hide_rejected_callback():
    with pytest.raises(ValueError,match='请在原会话继续'):
        stage_acceptance(result({'detail':'请在原会话继续该写作任务'}),'run-a','intent')


def test_acknowledgement_is_bound_to_run_and_stage():
    assert stage_acceptance(result({'accepted':True,'run_id':'run-a','stage':'intent'}),'run-a','intent')['accepted']
    with pytest.raises(ValueError,match='不属于当前任务'):
        stage_acceptance(result({'accepted':True,'run_id':'run-b'}),'run-a','intent')
    with pytest.raises(ValueError,match='回执与请求不一致'):
        stage_acceptance(result({'accepted':True,'run_id':'run-a','stage':'review'}),'run-a','intent')


def test_empty_dify_success_is_not_stage_acceptance():
    with pytest.raises(ValueError,match='缺少有效'):
        stage_acceptance({'data':{'status':'succeeded','outputs':{}}},'run-a','intent')
