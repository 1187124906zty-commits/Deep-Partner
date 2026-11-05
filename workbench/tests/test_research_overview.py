import pytest
from server.storage import Store
from server.research_flow import save_record
from server.research_overview import snapshot, agent_brief


def test_research_view_keeps_evidence_distinct_from_execution(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Damage study')['id']
    root=store.path('alice',pid)
    (root/'project/results/report.md').write_text('Only onset is verified')
    save_record(store,'alice',pid,{'id':'onset','nodes':[
        {'id':'f','kind':'finding','label':'Onset observed','status':'known','evidence_refs':[{'path':'results/report.md'}]},
        {'id':'l','kind':'limitation','label':'Postpeak not checked','status':'partial','evidence_refs':[{'path':'results/missing.md'}]},
        {'id':'m','kind':'method','label':'Conditional history law','status':'proposed'},
        {'id':'d','kind':'decision','label':'GPU allowance','status':'recorded'},
        {'id':'q','kind':'question','label':'When does damage localize?','status':'recorded'}],
        'edges':[{'source':'f','target':'l','relation':'limited_by'}]})
    job=store.job('alice',pid,'simulation');store.set_job(job,status='completed')
    waiting=store.job('alice',pid,'research-flow');store.set_job(waiting,status='waiting_input')
    failed=store.job('alice',pid,'simulation');store.set_job(failed,status='failed')
    view=snapshot(store,'alice',pid)
    groups={s['id']:s for s in view['sections']}
    assert groups['findings']['count']==1
    assert groups['approaches']['items'][0]['id']=='m'
    assert groups['findings']['items'][0]['sources'][0]['available']
    assert 'results%2Freport.md' in groups['findings']['items'][0]['sources'][0]['url']
    assert not groups['open_questions']['items'][0]['sources'][0]['available']
    assert view['edges'][0]['relation']=='limited_by'
    assert [j['id'] for j in view['attention']]==[waiting,failed]
    assert agent_brief(store,'alice',pid)['sections'][0]['items'][0]['label']=='When does damage localize?'
    with pytest.raises(KeyError):snapshot(store,'bob',pid)


def test_empty_project_does_not_invent_question_or_results(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Transport')['id']
    job=store.job('alice',pid,'simulation');store.set_job(job,status='completed')
    view=snapshot(store,'alice',pid)
    assert all(not s['items'] for s in view['sections'])
    assert not view['edges'] and not view['attention']
