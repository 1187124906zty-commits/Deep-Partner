"""Policy behavior through the public stage-review interface; no model calls."""
from copy import deepcopy
import json
import math

import pytest

from server.stage_reviews import evaluate_review, list_reviews, rubric, save_review
from server.storage import Conflict, Store


STAGES = ('idea', 'landscape', 'concept', 'evidence', 'writing', 'review', 'code', 'figure',
          'translation', 'slides-plan', 'slides-export', 'ingestion', 'delivery')
PURPOSES = ('group', 'conference', 'project', 'proposal', 'defense', 'literature')


def request(stage='writing', purpose='', operation='op-1', version=1):
    return {'operation_id': operation, 'stage': stage, 'purpose': purpose,
            'bindings': {'stage_version': '1', 'source_version': 'source:1',
                         'rule_version': rubric(stage, purpose)['version'],
                         'artifacts': [{'path': 'project/results/report.json', 'revision': version}]}}


def model_result(stage='writing', purpose='', score=3):
    return {'dimensions': [
        {'id': d['id'], 'score': score, 'reason': 'This draft ties the stated claim to the located evidence.',
         'evidence_refs': [{'path': 'project/results/report.json', 'locator': {'section_id': 's1'}}]}
        for d in rubric(stage, purpose)['dimensions']], 'issues': [], 'limitations': []}


def checks(stage='writing', purpose='', status='passed'):
    return [{'id': check['id'], 'status': status, 'source': 'tool',
             'performed_by': 'synthetic_test_measurement', 'evidence': {'synthetic': True, 'measurement': 0.0}}
            for check in rubric(stage, purpose)['required_hard_checks']]


@pytest.fixture
def project(tmp_path):
    store = Store(tmp_path)
    owner = 'test-owner'
    pid = store.create(owner, 'Synthetic stage review')['id']
    root = store.path(owner, pid)
    artifact = root / 'project/results/report.json'
    artifact.write_text(json.dumps({'revision': 1, 'sections': [{'id': 's1', 'content': 'Evidence and scope.'}]}), encoding='utf8')
    return store, owner, pid, artifact


@pytest.mark.parametrize('stage', STAGES)
def test_each_stage_contract_has_core_scoring_and_required_real_artifact_check(stage):
    rules = rubric(stage, 'group' if stage.startswith('slides-') else '')
    assert rules['minimum'] == 0 and rules['maximum'] == 4 and rules['core_minimum'] == 3
    assert any(d['core'] for d in rules['dimensions'])
    assert len({d['id'] for d in rules['dimensions']}) == len(rules['dimensions'])
    assert rules['required_hard_checks'][0]['id'] == 'artifact_current'
    assert all(d['anchors']['3'] for d in rules['dimensions'])


@pytest.mark.parametrize('purpose', PURPOSES)
def test_ppt_purposes_read_shared_rule_card(purpose):
    from server.presentation_catalog import purpose_rule
    rules = rubric('slides-plan', purpose)
    assert rules['purpose_guidance'] == purpose_rule(purpose)
    shared = {d['id']: d['core'] for d in purpose_rule(purpose)['evaluation_dimensions']}
    actual = {d['id']: d['core'] for d in rules['dimensions']}
    assert all(actual[key] == value for key, value in shared.items())
    assert ':ppt-' in rules['version']


def test_unknown_stage_or_purpose_cannot_silently_use_another_rubric():
    with pytest.raises(ValueError):
        rubric('new-stage')
    with pytest.raises(ValueError):
        rubric('slides-plan', 'invented-purpose')


@pytest.mark.parametrize('score', [True, False, float('nan'), float('inf'), -1, 4.1, '4', None])
def test_invalid_scores_are_unscored_and_block_core_progression(score):
    raw = model_result(score=4)
    raw['dimensions'][0]['score'] = score
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['dimensions'][0]['score'] is None
    assert result['coverage']['core_scored'] == 3
    assert result['overall'] == 4
    assert result['missing_core_dimensions'] == [raw['dimensions'][0]['id']]
    assert not result['quality_passed'] and not result['passed'] and not result['can_proceed']


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'no_reason', 'no_evidence', 'unknown_path', 'no_locator', 'invalid_page'])
def test_core_judgments_require_one_score_reason_and_located_bound_evidence(damage):
    raw = model_result(score=4)
    dimension = raw['dimensions'][0]
    if damage == 'missing':
        raw['dimensions'].pop(0)
    elif damage == 'duplicate':
        raw['dimensions'].append(deepcopy(dimension))
    elif damage == 'no_reason':
        dimension['reason'] = ' '
    elif damage == 'no_evidence':
        dimension['evidence_refs'] = []
    elif damage == 'unknown_path':
        dimension['evidence_refs'][0]['path'] = 'project/results/unbound.json'
    elif damage == 'no_locator':
        dimension['evidence_refs'][0]['locator'] = {}
    elif damage == 'invalid_page':
        dimension['evidence_refs'][0]['locator'] = {'page': True}
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['dimensions'][0]['score'] is None
    assert not result['passed']


def test_core_each_must_reach_three_even_when_mean_is_high():
    raw = model_result(score=4)
    raw['dimensions'][0]['score'] = 2
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['overall'] == 3.5 and result['coverage']['ratio'] == 1
    assert result['decision'] == 'needs_revision'
    assert not result['can_proceed']


def test_noncore_missing_is_disclosed_without_replacing_a_core_gate():
    raw = model_result('slides-plan', 'group', score=3)
    noncore = next(d['id'] for d in rubric('slides-plan', 'group')['dimensions'] if not d['core'])
    raw['dimensions'] = [d for d in raw['dimensions'] if d['id'] != noncore]
    result = evaluate_review(request('slides-plan', 'group'), raw, hard_checks=checks('slides-plan', 'group'))
    assert result['passed'] and result['overall'] == 3
    assert result['coverage']['ratio'] < 1 and result['missing_dimensions'] == [noncore]


def test_high_scores_do_not_cancel_verified_hard_failure():
    real_checks = checks()
    real_checks[0]['status'] = 'failed'
    result = evaluate_review(request(), model_result(score=4), hard_checks=real_checks)
    assert result['overall'] == 4 and result['quality_passed']
    assert result['hard_checks'][0]['verified']
    assert result['decision'] == 'blocked' and not result['passed']


def test_model_claims_cannot_inject_verified_checks_decision_or_override():
    raw = model_result(score=4)
    raw.update(hard_checks=checks(), decision='passed', overall=4, author_override={'confirmed': True})
    result = evaluate_review(request(), raw)
    assert result['hard_checks'][0]['status'] == 'unknown'
    assert not result['hard_checks'][0]['verified']
    assert result['decision'] == 'blocked' and not result['can_proceed']
    assert 'author_override' not in result


@pytest.mark.parametrize('damage', ['reported', 'missing_performer', 'missing_evidence'])
def test_check_attestations_require_actual_tool_or_server_provenance(damage):
    attestation = checks()
    if damage == 'reported':
        attestation[0]['source'] = 'reported'
    elif damage == 'missing_performer':
        attestation[0].pop('performed_by')
    else:
        attestation[0]['evidence'] = None
    result = evaluate_review(request(), model_result(), hard_checks=attestation)
    assert result['hard_checks'][0]['status'] == 'unknown'
    assert not result['can_proceed']


def test_not_applicable_requires_explanation_and_trusted_evidence():
    attestation = checks()
    attestation[0].update(status='N/A', reason='The fixture is a proposed plan; no execution is claimed.')
    result = evaluate_review(request(), model_result(), hard_checks=attestation)
    assert result['hard_checks'][0]['status'] == 'not_applicable' and result['passed']
    attestation[0].pop('reason')
    assert not evaluate_review(request(), model_result(), hard_checks=attestation)['passed']


@pytest.mark.parametrize('raw', ['not json', '[]', '{"dimensions":NaN}', None])
def test_unparseable_or_missing_judgment_never_gets_a_default_score(raw):
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['overall'] is None and result['coverage']['scored'] == 0
    assert not result['can_proceed']


def test_saved_review_is_idempotent_but_payload_reuse_conflicts(project):
    store, owner, pid, _ = project
    first = save_review(store, owner, pid, request(), model_result(), hard_checks=checks())
    again = save_review(store, owner, pid, request(), model_result(), hard_checks=checks())
    assert first == again and first['passed']
    index = list_reviews(store, owner, pid, current_bindings=request()['bindings'])
    assert len(index['items']) == 1 and index['can_proceed']
    assert index['current']['review_id'] == first['review_id']
    with pytest.raises(Conflict, match='operation_id'):
        save_review(store, owner, pid, request(), model_result(score=4), hard_checks=checks())


@pytest.mark.parametrize('changed', ['stage_version', 'source_version', 'rule_version', 'artifact'])
def test_any_binding_change_makes_old_review_ineligible(project, changed):
    store, owner, pid, _ = project
    saved = save_review(store, owner, pid, request(), model_result(), hard_checks=checks())
    binding = deepcopy(saved['bindings'])
    if changed == 'artifact':
        binding['artifacts'][0]['revision'] += 1
    else:
        binding[changed] = 'changed'
    history = list_reviews(store, owner, pid, current_bindings=binding)
    assert history['latest']['stale'] and not history['latest']['can_proceed']
    assert history['current'] is None and history['decision'] == 'stale'
    assert not history['can_proceed']


def test_history_without_current_state_does_not_authorize_progression(project):
    store, owner, pid, _ = project
    save_review(store, owner, pid, request(), model_result(), hard_checks=checks())
    history = list_reviews(store, owner, pid)
    assert not history['can_proceed'] and not history['latest']['automatic_flow']
    assert history['decision'] == 'binding_unverified'


def test_saved_locations_must_refer_to_an_existing_section(project):
    store, owner, pid, _ = project
    raw = model_result(score=4)
    raw['dimensions'][0]['evidence_refs'][0]['locator']['section_id'] = 'invented-section'
    result = save_review(store, owner, pid, request(), raw, hard_checks=checks())
    assert result['dimensions'][0]['score'] is None
    assert not result['passed']


def test_bound_input_sources_can_support_scores(project):
    store, owner, pid, artifact = project
    source = artifact.parent / 'original.txt'
    source.write_text('Original measurement.', encoding='utf8')
    req = request()
    req['input_refs'] = [{'path': 'project/results/original.txt'}]
    raw = model_result()
    raw['dimensions'][0]['evidence_refs'] = [{'path': 'project/results/original.txt', 'locator': {'line': 1}, 'quote': 'Original measurement.'}]
    result = save_review(store, owner, pid, req, raw, hard_checks=checks())
    assert result['passed']


def test_override_preserves_failure_and_records_real_author(project):
    store, owner, pid, _ = project
    blocked = checks()
    blocked[0]['status'] = 'failed'
    original = save_review(store, owner, pid, request(), model_result(score=4), hard_checks=blocked)
    req = request(operation='author-continues')
    req['override'] = {'review_id': original['review_id'], 'confirmed': True,
                       'reason': 'I accept this known limitation for the discussion draft.'}
    continued = save_review(store, owner, pid, req, None, actor={'id': owner, 'role': 'author'})
    assert continued['can_proceed'] and not continued['automatic_flow']
    assert continued['decision'] == 'author_override' and continued['base_decision'] == 'blocked'
    assert continued['passed'] is False and continued['hard_checks'] == original['hard_checks']
    assert continued['author_override']['author_id'] == owner
    assert continued['round'] == original['round']


@pytest.mark.parametrize('damage', ['no_actor', 'not_author', 'different_owner', 'unconfirmed', 'no_reason', 'different_version', 'fake_review'])
def test_override_cannot_be_forged_or_reused_for_a_new_version(project, damage):
    store, owner, pid, _ = project
    original = save_review(store, owner, pid, request(), model_result(score=2), hard_checks=checks())
    req = request(operation='override')
    req['override'] = {'review_id': original['review_id'], 'confirmed': True, 'reason': 'Explicit author choice.'}
    actor = {'id': owner, 'role': 'author'}
    if damage == 'no_actor':
        actor = None
    elif damage == 'not_author':
        actor['role'] = 'model'
    elif damage == 'different_owner':
        actor['id'] = 'another-owner'
    elif damage == 'unconfirmed':
        req['override']['confirmed'] = 1
    elif damage == 'no_reason':
        req['override']['reason'] = ' '
    elif damage == 'different_version':
        req['bindings']['artifacts'][0]['revision'] = 2
    else:
        req['override']['review_id'] = 'f' * 32
    with pytest.raises((ValueError, Conflict, KeyError)):
        save_review(store, owner, pid, req, None, actor=actor)


def test_two_targeted_revisions_then_author_decision_and_no_third_round(project):
    store, owner, pid, _ = project
    previous = save_review(store, owner, pid, request(), model_result(score=2), hard_checks=checks())
    snapshots = [previous]
    for round_number in (1, 2):
        req = request(operation='revision-' + str(round_number), version=round_number + 1)
        req['parent_review_id'] = previous['review_id']
        previous = save_review(store, owner, pid, req, model_result(score=2), hard_checks=checks())
        assert previous['round'] == round_number
        snapshots.append(previous)
    assert previous['decision'] == 'needs_author' and previous['stop_reason'] == 'revision_limit'
    assert previous['revision_allowed'] is False
    req = request(operation='revision-3', version=4)
    req['parent_review_id'] = previous['review_id']
    with pytest.raises(Conflict):
        save_review(store, owner, pid, req, model_result(score=2), hard_checks=checks())
    history = list_reviews(store, owner, pid, current_bindings=previous['bindings'])
    assert len(history['items']) == 3
    assert len({item['root_review_id'] for item in history['items']}) == 1
    assert not history['can_proceed']


def test_revision_requires_a_real_parent_new_artifact_and_same_question_inputs(project):
    store, owner, pid, _ = project
    original = save_review(store, owner, pid, request(), model_result(score=2), hard_checks=checks())
    same = request(operation='no-change')
    same['parent_review_id'] = original['review_id']
    with pytest.raises(Conflict, match='新的产物版本'):
        save_review(store, owner, pid, same, model_result(), hard_checks=checks())
    changed_input = request(operation='new-source', version=2)
    changed_input['parent_review_id'] = original['review_id']
    changed_input['bindings']['source_version'] = 'different-source'
    with pytest.raises(Conflict, match='新的评审链'):
        save_review(store, owner, pid, changed_input, model_result(), hard_checks=checks())


def test_immutable_prior_review_survives_new_failures_and_foreign_owner_is_denied(project):
    store, owner, pid, _ = project
    first = save_review(store, owner, pid, request(), model_result(), hard_checks=checks())
    path = store.path(owner, pid) / '.workbench/stage-reviews' / (first['review_id'] + '.json')
    before = path.read_text(encoding='utf8')
    save_review(store, owner, pid, request(operation='second'), model_result(score=1), hard_checks=checks())
    assert path.read_text(encoding='utf8') == before
    with pytest.raises(KeyError):
        list_reviews(store, 'other-owner', pid)
    current = list_reviews(store, owner, pid, current_bindings=first['bindings'])
    assert current['latest']['overall'] == 1 and not current['can_proceed']


def test_nonfinite_model_score_is_saved_as_unscored_valid_json(project):
    store, owner, pid, _ = project
    raw = model_result()
    raw['dimensions'][0]['score'] = math.nan
    review = save_review(store, owner, pid, request(), raw, hard_checks=checks())
    assert review['dimensions'][0]['score'] is None
    path = store.path(owner, pid) / '.workbench/stage-reviews' / (review['review_id'] + '.json')
    json.loads(path.read_text(encoding='utf8'), parse_constant=lambda value: pytest.fail(value))


def test_prompt_issue_shape_preserves_located_repair_scope():
    raw = model_result(score=2)
    raw['issues'] = [{'id': 'shorten-title', 'severity': 'major', 'path': 'project/results/report.json',
                      'locator': {'section_id': 's1'}, 'reason': 'The title does not identify the result.',
                      'requested_change': 'Use a result-bearing title without changing its claim.', 'scope': 'wording'}]
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['issues_are_model_reported'] is True
    assert result['issues'][0]['scope'] == 'wording'
    assert result['issues'][0]['severity'] == 'major'
    assert result['issues'][0]['evidence_refs'] == [{'path': 'project/results/report.json', 'locator': {'section_id': 's1'}}]
    assert result['issues'][0]['reported_by'] == 'model'
    assert result['decision'] == 'needs_revision'


@pytest.mark.parametrize('severity', ['critical', 'blocker', 'major', 'high'])
def test_high_core_scores_with_reported_blocking_issue_require_consistent_revision(severity):
    raw = model_result(score=4)
    raw['issues'] = [{'id': 'contradiction', 'severity': severity, 'path': 'project/results/report.json',
                      'locator': {'section_id': 's1'}, 'reason': 'The reported result contradicts its stated condition.',
                      'requested_change': 'Resolve the stated inconsistency against the source.', 'scope': 'scientific_choice'}]
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['overall'] == 4 and result['quality_passed'] is True
    assert not result['review_consistency_passed']
    assert result['reported_blocking_issues'] == ['contradiction']
    assert not result['automatic_flow'] and not result['can_proceed'] and not result['passed']
    assert result['decision'] == 'needs_revision'
    assert result['hard_blockers'] == []
    assert all(c['status'] == 'passed' for c in result['hard_checks'])


def test_unlocated_issue_is_rejected_and_unknown_scope_cannot_authorize_wording_repair():
    raw = model_result(score=2)
    raw['issues'] = [{'id': 'unlocated', 'severity': 'major', 'path': 'project/results/report.json',
                      'locator': {}, 'reason': 'A problem.', 'requested_change': 'Fix it.', 'scope': 'wording'},
                     {'id': 'untrusted-scope', 'severity': 'medium', 'path': 'project/results/report.json',
                      'locator': {'section_id': 's1'}, 'reason': 'Needs interpretation.',
                      'requested_change': 'Consider the alternative.', 'scope': 'automatic_scientific_decision'}]
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert [i['id'] for i in result['issues']] == ['untrusted-scope']
    assert result['issues'][0]['scope'] == 'unspecified'
    assert result['evaluation_errors']


def test_a_bound_directory_is_not_accepted_as_score_evidence(project):
    store, owner, pid, _ = project
    req = request()
    req['input_refs'] = [{'path': 'project/results'}]
    raw = model_result(score=4)
    raw['dimensions'][0]['evidence_refs'] = [{'path': 'project/results', 'locator': {'kind': 'document'}}]
    result = save_review(store, owner, pid, req, raw, hard_checks=checks())
    assert result['dimensions'][0]['score'] is None and not result['can_proceed']


@pytest.mark.parametrize('path', ['../outside.txt', 'C:/outside.txt', '/outside.txt'])
def test_external_evidence_paths_cannot_become_supported_core_scores(path):
    raw = model_result(score=4)
    raw['dimensions'][0]['evidence_refs'][0]['path'] = path
    result = evaluate_review(request(), raw, hard_checks=checks())
    assert result['dimensions'][0]['score'] is None and not result['can_proceed']
