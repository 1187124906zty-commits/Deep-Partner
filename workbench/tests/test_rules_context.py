from server import standards
from server.storage import Store


def test_ordinary_code_does_not_default_to_the_paper_reproduction_pipeline():
    from server.research_flow import RunInput
    assert RunInput(kind='code',instruction='Fix the requested function').code_engine=='agent'
    assert RunInput(kind='code',code_engine='paper2code',instruction='Reproduce the supplied paper').code_engine=='paper2code'


def test_native_workspace_points_to_current_rules_without_a_stale_copy():
    text=standards.workspace_instructions('project-a')
    assert '/projects/project-a/agent-context' in text
    assert 'when_to_use' in text and '独立评审' in text
    assert 'standard_version' in text
    assert standards.contract() not in text


def test_task_context_exposes_applicable_rules_and_preserves_artifact_review(tmp_path):
    store=Store(tmp_path);pid=store.create('owner','research')['id']
    value=standards.context(store,'owner',pid,'code')
    assert value['quality']['policy']==standards.quality_policy()
    assert '独立评审' in value['quality']['policy']
    assert '不取消产物独立评审' in value['quality']['policy']
    assert '最多两轮' in value['quality']['policy']
    assert all(s['when_to_use'] and s['url'] for s in value['skills'])
    assert all('content' not in s for s in value['skills'])
    assert 'mattpocock/diagnosing-bugs' in [s['id'] for s in value['rule_sources']['selected_skills']]
    assert value['rule_sources']['standard']['version']==value['standard_version']
