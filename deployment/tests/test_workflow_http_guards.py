import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ops'))
from workflow_guards import HTTP_GUARD, STAGE_GUARD


def run(source, **args):
    scope = {};exec(source, scope)
    return scope['main'](**args)


def test_real_prepare_failure_stops_with_original_reason():
    with pytest.raises(ValueError, match='HTTP 409: 当前任务的技能原文不完整'):
        run(HTTP_GUARD, status_code=409, body=json.dumps({'detail':'当前任务的技能原文不完整，请重新载入项目上下文'}))


def test_http_success_without_business_acceptance_is_not_success():
    with pytest.raises(ValueError, match='未被接受'):
        run(STAGE_GUARD, status_code=200, body='{}', run_id='task-a', stage='intent')


def test_bound_stage_accepted_and_duplicate_advance():
    for value in [{'accepted':True,'run_id':'task-a','stage':'intent'},
                  {'accepted':True,'run_id':'task-a','stage':'review','status':'already_advanced'}]:
        assert json.loads(run(STAGE_GUARD,status_code=200,body=json.dumps(value),run_id='task-a',stage='intent')['receipt'])==value


def test_wrong_run_and_invalid_json_cannot_advance():
    with pytest.raises(ValueError, match='当前任务'):
        run(STAGE_GUARD,status_code=200,body='{"accepted":true,"run_id":"other"}',run_id='task-a',stage='intent')
    with pytest.raises(ValueError, match='结构化回执'):
        run(HTTP_GUARD,status_code=200,body='<html>sign in</html>')
