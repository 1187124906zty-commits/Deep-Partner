import pytest
from server.storage import Store
from server.project_progress import snapshot


def test_project_view_preserves_attention_and_actual_review_state(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Research')['id']
    waiting=store.job('alice',pid,'research-flow',{'subject':'Review the method'})
    store.set_job(waiting,status='waiting_input')
    reviewed=store.job('alice',pid,'manuscript-export',{'subject':'Draft'})
    store.set_job(reviewed,status='completed',result={'quality':{'can_proceed':False,'reason':'Evidence gap'}})
    active=store.job('alice',pid,'simulation');store.set_job(active,status='waiting_service')
    value=snapshot(store,'alice',pid)
    assert value['counts']=={'attention':2,'active':1,'done':0,'closed':0}
    rows={r['id']:r for r in value['jobs']}
    assert rows[reviewed]['status']=='completed' and rows[reviewed]['group']=='attention'
    assert rows[waiting]['status']=='waiting_input'
    assert value['jobs'][0]['id']==active
    code=next(r for r in value['routes'] if r['id']=='code')
    assert [s['id'] for s in code['steps']]==['dispatch','archive']
    with pytest.raises(KeyError):snapshot(store,'other-owner',pid)


def test_author_decision_cannot_be_buried_by_recent_completed_jobs(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Research')['id']
    waiting=store.job('alice',pid,'research-flow');store.set_job(waiting,status='paused')
    for _ in range(201):
        jid=store.job('alice',pid,'material-import');store.set_job(jid,status='completed')
    jobs=snapshot(store,'alice',pid)['jobs']
    assert len(jobs)==200 and jobs[0]['id']==waiting
