from copy import deepcopy
import pytest
from server.storage import Store,atomic_json,Conflict
from server.research_flow import save_record,graph
from server.research_outline import location,read_state
from server.research_updates import inspect,apply_update,history


def study(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Hydration comparison')['id'];root=store.path('alice',pid)
    source=root/'project/docs/model.md';source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text('The run resolves crack initiation. The complete post-peak branch has not been established.',encoding='utf8')
    save_record(store,'alice',pid,{'id':'prior','nodes':[{'id':'finding:run','kind':'finding','label':'Initiation response','detail':'Existing run','status':'partial','evidence_refs':[{'path':'docs/model.md'}]}]})
    doc={'id':'accepted','status':'confirmed','mainline':{'title':'Compare fixed geometry'},'outline':[{'id':'compare','tasks':[{'id':'postpeak','title':'Interpret the response','understanding':'Initiation response available','next_step':'Compare results'}]}]}
    atomic_json(location(store,'alice',pid),{'revision':2,'active':doc,'draft':None})
    return store,pid,source


def patch(read):
    return {'inspection_id':read['id'],'reason':'Retain the stated scope of the original report','source_ids':['source-1'],
            'record_updates':[{'id':'finding:run','detail':'Crack initiation was computed; the complete post-peak branch is not established.'}],
            'task_updates':[{'id':'postpeak','understanding':'Initiation only; post-peak remains unverified','next_step':'Read the existing reaction curve before interpreting softening.'}]}


def test_source_backed_update_preserves_mainline_and_before_after(tmp_path):
    store,pid,_=study(tmp_path);before=deepcopy(read_state(store,'alice',pid));read=inspect(store,'alice',pid,{'record_ids':['finding:run']})
    assert 'post-peak' in read['sources'][0]['text'] and read['sources'][0]['status']=='read'
    receipt=apply_update(store,'alice',pid,patch(read));after=read_state(store,'alice',pid)
    assert after['active']['mainline']==before['active']['mainline']
    assert after['active']['outline'][0]['tasks'][0]['next_step'].startswith('Read the existing')
    assert receipt['changes'][0]['before']['detail']=='Existing run'
    assert history(store,'alice',pid)['updates'][0]['id']==receipt['id']
    from server.research_overview import agent_brief
    assert agent_brief(store,'alice',pid)['recent_updates'][0]['changes'][0]['after']['detail'].startswith('Crack initiation')
    with pytest.raises(Conflict):apply_update(store,'alice',pid,patch(read))


@pytest.mark.parametrize('change',[{'scope_change':True},{'conflicts':['Conflicting source']},{'source_ids':['not-read']}, {'task_updates':[{'id':'postpeak','title':'New scientific goal'}]}])
def test_unread_or_scientific_changes_do_not_partially_mutate(tmp_path,change):
    store,pid,_=study(tmp_path);read=inspect(store,'alice',pid,{});before=graph(store,'alice',pid)
    with pytest.raises(ValueError):apply_update(store,'alice',pid,{**patch(read),**change})
    assert graph(store,'alice',pid)==before and history(store,'alice',pid)['updates']==[]


def test_source_changes_and_foreign_inspection_are_rejected(tmp_path):
    store,pid,source=study(tmp_path);read=inspect(store,'alice',pid,{})
    source.write_text('A revised report',encoding='utf8')
    with pytest.raises(Conflict,match='原始材料'):apply_update(store,'alice',pid,patch(read))
    with pytest.raises(KeyError):apply_update(store,'bob',pid,patch(read))
    other=store.create('alice','Other project')['id']
    with pytest.raises(ValueError,match='没有这次'):apply_update(store,'alice',other,patch(read))
