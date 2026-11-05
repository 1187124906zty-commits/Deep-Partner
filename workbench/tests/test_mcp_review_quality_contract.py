"""Offline HTTP contracts for the existing MCP review tool and authenticated transport."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys

import httpx
import pytest

PACKAGE = Path(__file__).resolve().parents[1] / 'mcp-package/src'
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from client import WorkbenchClient
from tools import workspace_api


PID = 'a' * 32
TOKEN = 'synthetic-owner-session-only'


def invoke(arguments, handler, tool='workbench_review'):
    async def run():
        transport = WorkbenchClient('https://workbench.test')
        transport._session = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                               headers={'Authorization': 'Bearer ' + TOKEN}, trust_env=False)
        workspace_api.configure_client(transport)
        try:
            return await getattr(workspace_api, tool)(**arguments)
        finally:
            await transport.close()
            workspace_api.configure_client(None)
    return asyncio.run(run())


@pytest.mark.parametrize('arguments,method,route,body,params', [
    ({'action': 'receipt', 'purpose': 'group', 'operation_id': 'ignored-without-stage'}, 'POST',
     f'/research/api/projects/{PID}/agent-receipt',
     {'question_ids': [], 'artifacts': [], 'validation': [], 'limitations': [], 'resolved': False}, {}),
    ({'action': 'receipt', 'stage': 'writing', 'purpose': '', 'operation_id': 'write-1',
      'question_ids': ['q1'], 'artifacts': [{'path': 'manuscript/main.json'}],
      'validation': [{'check': 'readback', 'result': 'passed'}], 'limitations': ['Fixture'], 'resolved': True},
     'POST', f'/research/api/projects/{PID}/agent-receipt',
     {'question_ids': ['q1'], 'artifacts': [{'path': 'manuscript/main.json'}],
      'validation': [{'check': 'readback', 'result': 'passed'}], 'limitations': ['Fixture'], 'resolved': True,
      'stage': 'writing', 'purpose': '', 'operation_id': 'write-1'}, {}),
    ({'action': 'quality_rubric', 'stage': 'slides-plan', 'purpose': 'group'}, 'GET',
     '/research/api/quality/rubric', None, {'stage': 'slides-plan', 'purpose': 'group'}),
    ({'action': 'quality_submit', 'stage': 'slides-plan', 'purpose': 'proposal', 'operation_id': 'quality-1',
      'artifact_paths': ['slides/plan.json'], 'source_paths': ['manuscript/main.json'], 'intended_use': 'Discuss feasibility'},
     'POST', f'/research/api/projects/{PID}/quality/reviews',
     {'stage': 'slides-plan', 'purpose': 'proposal', 'operation_id': 'quality-1',
      'artifact_paths': ['slides/plan.json'], 'source_paths': ['manuscript/main.json'], 'intended_use': 'Discuss feasibility'}, {}),
    ({'action': 'quality_submit', 'stage': 'writing', 'operation_id': 'quality-defaults'}, 'POST',
     f'/research/api/projects/{PID}/quality/reviews',
     {'stage': 'writing', 'purpose': '', 'operation_id': 'quality-defaults',
      'artifact_paths': [], 'source_paths': [], 'intended_use': ''}, {}),
    ({'action': 'quality_list', 'stage': 'evidence'}, 'GET',
     f'/research/api/projects/{PID}/quality/reviews', None, {'stage': 'evidence', 'purpose': ''}),
    ({'action': 'quality_gate', 'stage': 'writing'}, 'GET',
     f'/research/api/projects/{PID}/quality/gate', None, {'stage': 'writing', 'purpose': '', 'artifact_path': ''}),
    ({'action': 'quality_gate', 'stage': 'slides-export', 'purpose': 'defense',
      'artifact_paths': ['slides/exports/研究汇报.pptx']}, 'GET',
     f'/research/api/projects/{PID}/quality/gate', None,
     {'stage': 'slides-export', 'purpose': 'defense', 'artifact_path': 'slides/exports/研究汇报.pptx'}),
])
def test_http_route_payload_and_legacy_compatibility(arguments, method, route, body, params):
    original = deepcopy(arguments)
    observed = []
    native = {'status': 'synthetic-native-result', 'job_id': 'job-fixture',
              'can_proceed': False, 'nested': {'scores': [0, 3, None], 'hard_checks': ['unknown']}}

    def handler(request):
        observed.append(request)
        assert request.method == method and request.url.path == route
        assert dict(request.url.params) == params
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        assert not any(key in request.url.params for key in ('owner', 'owner_id', 'user_id'))
        if body is not None:
            assert json.loads(request.content) == body
            assert not any(key in body for key in ('owner', 'owner_id', 'user_id', 'hard_checks', 'passed'))
        return httpx.Response(200, json=native)

    result = invoke({'project_id': PID, **arguments}, handler)
    assert result['data'] == native
    assert result['reference'] == 'https://workbench.test' + route
    assert result['artifacts'] == [] and len(observed) == 1
    assert arguments == original


def test_missing_quality_input_and_multi_artifact_gate_fail_before_http():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    for arguments in [
        {'action': 'quality_submit', 'stage': 'writing'},
        {'action': 'quality_submit', 'operation_id': 'missing-stage'},
        {'action': 'quality_rubric'},
        {'action': 'quality_gate', 'stage': 'writing', 'artifact_paths': ['a', 'b']},
    ]:
        with pytest.raises(ValueError):
            invoke({'project_id': PID, **arguments}, handler)
    assert not calls


def test_owner_auth_failure_is_not_converted_to_a_successful_quality_result():
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        return httpx.Response(403, json={'detail': 'Owned project only'})

    with pytest.raises(ValueError, match='HTTP 403'):
        invoke({'project_id': PID, 'action': 'quality_list'}, handler)


def test_saving_other_settings_preserves_custom_reviewer_without_replaying_secret():
    current = {'base_url': 'https://author.test/v1', 'model': 'author-model', 'translation_prompt': '',
               'literature_provider': 'auto', 'reviewer_mode': 'custom',
               'reviewer_base_url': 'https://review.test/v1', 'reviewer_model': 'saved-reviewer',
               'reviewer_supports_vision': True, 'reviewer_configured': True,
               'reviewer_api_key': 'masked-old-value-must-never-be-sent'}
    calls = []

    def handler(request):
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        assert request.url.path == '/research/api/api-settings'
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(200, json=current)
        body = json.loads(request.content)
        assert body == {'base_url': current['base_url'], 'model': current['model'],
                        'translation_prompt': 'Updated translation prompt', 'literature_provider': 'auto',
                        'reviewer_mode': 'custom', 'reviewer_base_url': current['reviewer_base_url'],
                        'reviewer_model': 'saved-reviewer', 'reviewer_supports_vision': True}
        assert 'reviewer_api_key' not in body and 'reviewer_configured' not in body
        return httpx.Response(200, json={'saved': True})

    result = invoke({'action': 'save', 'translation_prompt': 'Updated translation prompt'}, handler,
                    tool='workbench_settings')
    assert result['data'] == {'saved': True} and calls == ['GET', 'PUT']


def test_explicit_reviewer_selection_update_and_vision_keep_legacy_service_compatible():
    cases = [({}, {'action': 'save', 'model': 'new-author'},
              {'base_url': '', 'model': 'new-author', 'translation_prompt': '', 'literature_provider': 'auto'}),
             ({}, {'action': 'save', 'reviewer_mode': 'custom', 'reviewer_base_url': 'https://review.test/v1',
                   'reviewer_model': 'visual-reviewer', 'reviewer_api_key': 'explicit-new-fixture-key',
                   'reviewer_supports_vision': True},
              {'base_url': '', 'model': '', 'translation_prompt': '', 'literature_provider': 'auto',
               'reviewer_mode': 'custom', 'reviewer_base_url': 'https://review.test/v1',
               'reviewer_model': 'visual-reviewer', 'reviewer_api_key': 'explicit-new-fixture-key',
               'reviewer_supports_vision': True}),
             ({'reviewer_mode': 'custom', 'reviewer_model': 'kept-model', 'reviewer_base_url': 'https://kept.test/v1',
               'reviewer_supports_vision': True}, {'action': 'save', 'reviewer_mode': 'inherit',
                                                  'reviewer_supports_vision': False, 'reviewer_api_key': ''},
              {'base_url': '', 'model': '', 'translation_prompt': '', 'literature_provider': 'auto',
               'reviewer_mode': 'inherit', 'reviewer_base_url': 'https://kept.test/v1',
               'reviewer_model': 'kept-model', 'reviewer_supports_vision': False, 'reviewer_api_key': ''})]
    for current, arguments, expected in cases:
        observed = []

        def handler(request):
            assert request.headers['Authorization'] == 'Bearer ' + TOKEN
            observed.append(request.method)
            if request.method == 'GET':
                return httpx.Response(200, json=current)
            assert json.loads(request.content) == expected
            return httpx.Response(200, json={'saved': True})

        assert invoke(arguments, handler, tool='workbench_settings')['data']['saved'] is True
        assert observed == ['GET', 'PUT']
