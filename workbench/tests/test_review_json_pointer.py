"""RFC6901 evidence references through real Store/save_review, without model calls."""
from copy import deepcopy
import json

import pytest

from server.stage_reviews import list_reviews, rubric, save_review
from server.storage import Store, atomic_json


@pytest.fixture
def evidence(tmp_path_factory):
    store = Store(tmp_path_factory.mktemp('jp'))
    owner = 'pointer-owner'
    pid = store.create(owner, 'JSON pointer evidence')['id']
    root = store.path(owner, pid)
    target = root / 'project/results/receipt.json'
    document = {'selected_sources': [{'id': 'paper-1'}],
                'retrieval_checks': [{'response': {'result': 'first'}}, {'response': {'result': 'located evidence'}}],
                '': 0, 'a/b': {'m~n': False}, '~1': 'literal tilde one',
                'values': [None, False, 0, ''], 'é': 'exact Unicode key'}
    atomic_json(target, document)
    counter = 0

    def save(pointer, *, path='project/results/receipt.json', operation=None, legacy=None):
        nonlocal counter
        counter += 1
        rules = rubric('ingestion')
        req = {'operation_id': operation or 'pointer-' + str(counter), 'stage': 'ingestion',
               'bindings': {'stage_version': '1', 'source_version': 'source1', 'rule_version': rules['version'],
                            'artifacts': [{'path': path, 'version': 1}]}}
        locator = deepcopy(legacy) if legacy is not None else {'json_pointer': pointer}
        answer = {'dimensions': [{'id': d['id'], 'score': 3, 'reason': 'The referenced JSON value supports this scope.',
                                  'evidence_refs': [{'path': path, 'locator': locator}]}
                                 for d in rules['dimensions']]}
        checks = [{'id': 'artifact_current', 'status': 'passed', 'source': 'server',
                   'performed_by': 'fixture.file_presence', 'evidence': {'path': path}}]
        return save_review(store, owner, pid, req, answer, hard_checks=checks)

    return store, owner, pid, root, target, document, save


def assert_not_scored(review):
    assert review['overall'] is None and review['coverage']['scored'] == 0
    assert not review['can_proceed'] and not review['automatic_flow']
    assert all(d['score'] is None for d in review['dimensions'])


def test_real_ingestion_references_resolve_object_keys_and_nested_array(evidence):
    *_, save = evidence
    for pointer in ('/selected_sources', '/selected_sources/0/id', '/retrieval_checks/1/response/result'):
        review = save(pointer)
        assert review['passed'] and review['coverage']['core_scored'] == 4
        assert all(d['evidence_refs'][0]['locator'] == {'json_pointer': pointer} for d in review['dimensions'])


def test_empty_pointer_means_whole_valid_json_and_falsey_values_still_exist(evidence):
    *_, save = evidence
    for pointer in ('', '/', '/values/0', '/values/1', '/values/2', '/values/3'):
        assert save(pointer)['passed']


def test_rfc_escapes_decode_in_order_and_unicode_keys_are_exact(evidence):
    *_, save = evidence
    for pointer in ('/a~1b/m~0n', '/~01', '/é'):
        assert save(pointer)['passed']
    # RFC6901 performs no Unicode normalization or URI percent-decoding.
    for pointer in ('/e\u0301', '/%C3%A9'):
        assert_not_scored(save(pointer))


def test_invalid_pointer_syntax_or_nonstring_does_not_support_scores(evidence):
    *_, save = evidence
    for pointer in ('selected_sources', '#/selected_sources', '/a~', '/a~2b', '/~~0', None, True, 1):
        assert_not_scored(save(pointer))


def test_missing_members_invalid_indices_and_scalar_traversal_fail(evidence):
    *_, save = evidence
    for pointer in ('/missing', '/retrieval_checks/2', '/retrieval_checks/-', '/retrieval_checks/01',
                    '/retrieval_checks/-1', '/retrieval_checks/+1', '/retrieval_checks/١',
                    '/retrieval_checks/' + '9' * 1000, '/selected_sources/0/id/child'):
        assert_not_scored(save(pointer))


def test_pointer_requires_json_file_and_unambiguous_valid_json(evidence):
    _, _, _, root, target, _, save = evidence
    text = root / 'project/results/not-json.txt'
    text.write_text('{"selected_sources": []}', encoding='utf8')
    assert_not_scored(save('/selected_sources', path='project/results/not-json.txt'))
    for bad_json in ('not JSON', '{"selected_sources":NaN}', '{"selected_sources":[],"selected_sources":42}'):
        target.write_text(bad_json, encoding='utf8')
        assert_not_scored(save(''))


def test_existing_locator_still_works_and_saved_unscored_review_is_not_upgraded(evidence):
    store, owner, pid, _, target, document, save = evidence
    assert save(None, legacy={'line': 1})['passed']
    original = save('/future_value', operation='saved-before-value-exists')
    assert_not_scored(original)
    document['future_value'] = 'added later'
    atomic_json(target, document)
    replay = save('/future_value', operation='saved-before-value-exists')
    assert replay == original
    assert_not_scored(replay)
    assert save('/future_value', operation='new-reviewed-operation')['passed']
    history = list_reviews(store, owner, pid)['items']
    assert next(r for r in history if r['review_id'] == original['review_id'])['overall'] is None


def test_null_root_json_exists_but_cannot_be_traversed(evidence):
    _, _, _, _, target, _, save = evidence
    target.write_text('null', encoding='utf8')
    assert save('')['passed']
    assert_not_scored(save('/anything'))
