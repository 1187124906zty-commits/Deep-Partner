"""Bounded PPT repair through actual review persistence and files, mocked model only."""
from copy import deepcopy
import json
import os
from types import SimpleNamespace

import pytest

from server import quality_api, review_transport
from server.stage_reviews import list_reviews
from server.storage import Conflict, Store, atomic_json


@pytest.fixture
def revision(tmp_path_factory, monkeypatch):
    directory = tmp_path_factory.mktemp('qr')
    store = Store(directory / 's')
    owner = 'revision-owner'
    pid = store.create(owner, 'Synthetic bounded repair')['id']
    store.update(owner, pid, native_id='revision-native-workspace')
    root = store.path(owner, pid)
    target = root / 'slides/plan.json'
    source = root / 'manuscript/main.json'
    plan = {'title': 'Synthetic report', 'planner': 'fixture', 'confirmation_id': 'confirmed-fixture',
            'audience_profile': 'group', 'visual_template': 'metropolis',
            'source_figures': [], 'source_tables': [],
            'sections': [
                {'id': 's1', 'role': 'content', 'title': 'Measured result',
                 'content': 'The measured error is 0.25 and does not establish improvement.',
                 'notes': 'The measurement uses 8 samples.', 'figures': [], 'tables': []},
                {'id': 's2', 'role': 'content', 'title': 'Separate evidence',
                 'content': 'This page remains an independent observation.',
                 'notes': 'Limits remain explicit.', 'figures': [], 'tables': []}]}
    atomic_json(target, plan)
    atomic_json(source, {'revision': 1, 'content': {'type': 'doc', 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Original source and its limitations.'}]}]}})
    payload = {'operation_id': 'repair-flow', 'stage': 'slides-plan', 'purpose': 'group',
               'artifact_paths': ['slides/plan.json'], 'source_paths': ['manuscript/main.json'],
               'intended_use': 'Synthetic discussion draft', 'parent_review_id': ''}
    provider = SimpleNamespace(scores=[2, 3], reviews=[], repairs=[], scope='wording',
                               issue_locator={'section_id': 's1'}, issue_path='slides/plan.json',
                               repair_change=None, during_review=None, during_repair=None)

    def complete(settings, native_headers, native_id, prompt, content, base, **kwargs):
        assert native_id == 'revision-native-workspace'
        packet = json.loads(content)
        identity = {'kind': 'model', 'selection': 'synthetic-no-network'}
        if 'rubric' in packet:
            provider.reviews.append(deepcopy(packet))
            index = min(len(provider.reviews) - 1, len(provider.scores) - 1)
            score = provider.scores[index]
            answer = {'dimensions': [
                {'id': dimension['id'], 'score': score, 'reason': 'Located fixture judgment under its stated conditions.',
                 'evidence_refs': [{'path': 'slides/plan.json', 'locator': {'section_id': 's1'}}]}
                for dimension in packet['rubric']['dimensions']],
                'issues': [] if score >= 3 else [
                    {'id': 'title-wording', 'severity': 'major', 'path': provider.issue_path,
                     'locator': deepcopy(provider.issue_locator), 'scope': provider.scope,
                     'reason': 'The located title needs clearer wording.',
                     'requested_change': 'Clarify this title while preserving its scientific meaning.'}],
                'limitations': ['Synthetic model output only.']}
            if provider.during_review:
                provider.during_review()
            return json.dumps(answer), identity
        assert 'plan' in packet and 'issues' in packet
        provider.repairs.append(deepcopy(packet))
        answer = deepcopy(packet['plan'])
        if provider.repair_change:
            provider.repair_change(answer)
        else:
            answer['sections'][0]['title'] += ' clarified'
        if provider.during_repair:
            provider.during_repair()
        return json.dumps(answer), identity

    monkeypatch.setattr(review_transport, 'complete_review', complete)
    settings = lambda _owner: directory / 'unused-settings.json'

    def run():
        return quality_api.review_and_revise_plan(store, settings, owner, pid, payload, {})

    def history():
        return list_reviews(store, owner, pid, stage='slides-plan', purpose='group')['items']

    def replace_outside_revision(path, value):
        previous = path.stat()
        atomic_json(path, value)
        os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))

    return SimpleNamespace(store=store, owner=owner, pid=pid, root=root, target=target, source=source,
                           original=plan, payload=payload, provider=provider, settings=settings,
                           run=run, history=history, change=replace_outside_revision)


def test_real_review_save_targeted_change_and_reassessment_preserve_other_page(revision):
    result = revision.run()
    actual = json.loads(revision.target.read_text(encoding='utf8'))
    assert actual['sections'][0]['title'] == 'Measured result clarified'
    assert actual['sections'][0]['content'] == revision.original['sections'][0]['content']
    assert actual['sections'][1] == revision.original['sections'][1]
    assert all(actual[k] == v for k, v in revision.original.items() if k != 'sections')
    assert len(revision.provider.reviews) == 2 and len(revision.provider.repairs) == 1
    records = revision.history()
    assert [record['round'] for record in records] == [1, 0]
    assert records[0]['parent_review_id'] == records[1]['review_id']
    assert records[0]['bindings']['artifacts'] != records[1]['bindings']['artifacts']
    assert records[0]['bindings']['source_version'] == records[1]['bindings']['source_version']
    assert result['passed'] and result['can_proceed']
    assert result['review_history'] == [records[1]['review_id'], records[0]['review_id']]
    versions = revision.store.trash(revision.owner, revision.pid)
    assert len([item for item in versions if item['original'] == 'slides/plan.json']) == 1


def test_two_actual_repairs_maximum_and_three_saved_review_rounds(revision):
    revision.provider.scores = [2]
    result = revision.run()
    assert len(revision.provider.repairs) == 2
    assert len(revision.provider.reviews) == 3
    assert [item['round'] for item in revision.history()] == [2, 1, 0]
    assert result['stop_reason'] == 'revision_limit'
    assert not result['revision_allowed'] and not result['can_proceed']
    assert json.loads(revision.target.read_text(encoding='utf8'))['sections'][0]['title'].endswith('clarified clarified')


def test_no_artifact_change_is_not_recounted_as_a_revision_or_new_review(revision):
    revision.provider.repair_change = lambda plan: None
    result = revision.run()
    assert result['stop_reason'] == 'no_artifact_change'
    assert len(revision.provider.reviews) == 1 and len(revision.provider.repairs) == 1
    assert [item['round'] for item in revision.history()] == [0]
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original


def test_cached_old_opinion_is_not_applied_to_user_new_version(revision):
    first_payload = {**revision.payload, 'operation_id': revision.payload['operation_id'] + '-r0'}
    original_review = quality_api.run_review(revision.store, revision.settings, revision.owner,
                                            revision.pid, first_payload, {})
    changed = deepcopy(revision.original)
    changed['sections'][0]['title'] = 'User-owned revision'
    revision.change(revision.target, changed)
    with pytest.raises(Conflict):
        revision.run()
    assert json.loads(revision.target.read_text(encoding='utf8')) == changed
    assert not revision.provider.repairs
    assert [record['review_id'] for record in revision.history()] == [original_review['review_id']]


def test_user_plan_change_during_model_repair_is_preserved(revision):
    changed = deepcopy(revision.original)
    changed['sections'][1]['notes'] = 'Concurrent user edit that must survive.'
    revision.provider.during_repair = lambda: revision.change(revision.target, changed)
    with pytest.raises(Conflict):
        revision.run()
    assert json.loads(revision.target.read_text(encoding='utf8')) == changed
    assert len(revision.history()) == 1


def test_source_change_during_model_repair_prevents_plan_write(revision):
    changed_source = {'revision': 2, 'content': {'type': 'doc', 'content': []}}
    revision.provider.during_repair = lambda: revision.change(revision.source, changed_source)
    with pytest.raises(Conflict):
        revision.run()
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original
    assert json.loads(revision.source.read_text(encoding='utf8')) == changed_source
    assert len(revision.history()) == 1
    assert not revision.store.trash(revision.owner, revision.pid)


@pytest.mark.parametrize('change', ['number', 'remove_negation', 'change_uncertainty'])
def test_numerical_negation_or_uncertainty_change_requires_author(revision, change):
    def repair(plan):
        if change == 'number':
            plan['sections'][0]['content'] = plan['sections'][0]['content'].replace('0.25', '0.75')
        elif change == 'remove_negation':
            plan['sections'][0]['content'] = plan['sections'][0]['content'].replace('not ', '')
        else:
            plan['sections'][0]['notes'] += ' This might generalize.'
    revision.provider.repair_change = repair
    result = revision.run()
    assert result['stop_reason'] == 'repair_requires_scientific_choice'
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original
    assert len(revision.history()) == 1


@pytest.mark.parametrize('where', ['plan', 'section'])
def test_automatic_repair_cannot_add_structural_fields(revision, where):
    def repair(plan):
        (plan if where == 'plan' else plan['sections'][0])['new_structure'] = 'not authorized'
    revision.provider.repair_change = repair
    with pytest.raises(ValueError):
        revision.run()
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original
    assert len(revision.history()) == 1


def test_automatic_repair_cannot_change_an_unlocated_page(revision):
    def repair(plan):
        plan['sections'][0]['title'] += ' clarified'
        plan['sections'][1]['title'] += ' unauthorized'
    revision.provider.repair_change = repair
    with pytest.raises(ValueError, match='未定位'):
        revision.run()
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original


def test_scientific_choice_issue_goes_to_author_without_repair_call(revision):
    revision.provider.scope = 'scientific_choice'
    result = revision.run()
    assert result['stop_reason'] == 'author_or_executor_required'
    assert not revision.provider.repairs
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original


def test_source_only_issue_does_not_authorize_changing_plan_pages(revision):
    revision.provider.issue_path = 'manuscript/main.json'
    revision.provider.issue_locator = {'paragraph': 1}
    result = revision.run()
    assert result['stop_reason'] == 'repair_needs_section_locator'
    assert not revision.provider.repairs
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original


def test_changed_slide_count_is_rejected_without_overwriting_plan(revision):
    revision.provider.repair_change = lambda plan: plan['sections'].pop()
    result = revision.run()
    assert result['stop_reason'] == 'repair_contract_not_met'
    assert json.loads(revision.target.read_text(encoding='utf8')) == revision.original
    assert len(revision.history()) == 1
