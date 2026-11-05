from copy import deepcopy
import pytest
from server.storage import Store,atomic_json,Conflict
from server.research_outline import validate_outline,task_progress,read_state,location,accept


@pytest.mark.asyncio
async def test_retrieval_uses_unique_body_passages_not_bibliography(tmp_path,monkeypatch):
    import httpx
    from server.research_outline import retrieve
    store=Store(tmp_path);pid=store.create('alice','Study')['id']
    store.update('alice',pid,native_id='ws-study',config={'knowledge_bases':['kb-study']})
    body={'title':'method.pdf','page':'4','evidence_text':'The coupled transport equation uses a measured reaction rate.'}
    async def semantic(*args):return {'sources':[{'title':'method.pdf','page':'12','evidence_text':'[18] Q. Liu, Reactive transport, Journal (2024).'},body,deepcopy(body)],'provider':'test'}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,*args,**kwargs):return httpx.Response(200)
    monkeypatch.setattr('server.knowledge_search.semantic',semantic)
    monkeypatch.setattr('server.research_outline.httpx.AsyncClient',Client)
    sources,reports=await retrieve(store,{'id':'alice'},pid,{},['reaction rate'],{'sources':[]})
    assert len(sources)==1 and sources[0]['page']=='4'
    assert reports[0]['source_count']==1 and reports[0]['retrieved_count']==3
    assert reports[0]['excluded'][0]['page']=='12'


def proposal():
    return {'mainline':{'title':'Extend the existing transport model','previous_work':'Published baseline','opportunity':'A bounded gap','scope':'Saturated case','source_ids':['s']},
        'outline':[{'id':'comparison','title':'Understand the missing coupling','purpose':'Establish the scope of the change','source_ids':['s'],
            'tasks':[{'id':'read-model','title':'Compare the baseline assumptions','kind':'read','source_ids':['s'],'job_ids':['j'],'record_ids':['f']}]}],
        'change_summary':'Connect prior work to the current question','author_decisions':[],'limitations':[]}


def test_outline_requires_sources_and_owned_execution_ids():
    sources=[{'id':'s'}]
    assert validate_outline(proposal(),sources,{'j'},{'f'})['outline'][0]['tasks'][0]['job_ids']==['j']
    value=proposal();value['mainline']['source_ids']=['invented']
    with pytest.raises(ValueError,match='未读取'):validate_outline(value,sources,{'j'},{'f'})
    value=proposal();value['outline'][0]['tasks'][0]['job_ids']=['foreign-job']
    with pytest.raises(ValueError,match='job_ids'):validate_outline(value,sources,{'j'},{'f'})


def test_execution_completion_is_not_scientific_completion():
    task={'job_ids':['j'],'record_ids':['f']}
    assert task_progress(task,{'j':{'id':'j','status':'completed','stage':'Done'}},{'f':{}})['state']=='results'
    assert task_progress(task,{'j':{'id':'j','status':'waiting_input','stage':'Awaiting author'}},{'f':{}})['state']=='attention'
    assert task_progress({'record_ids':['f']},{},{'f':{}})['state']=='recorded'
    assert task_progress({}, {}, {})['state']=='planned'


def test_only_explicit_versioned_adoption_changes_mainline(tmp_path):
    store=Store(tmp_path);pid=store.create('alice','Research')['id'];root=store.path('alice',pid)
    document=validate_outline(proposal(),[{'id':'s'}],{'j'},{'f'})
    document.update(id='draft-1',status='proposal',sources=[{'id':'s','refs':[{'path':'docs/source.md'}]}],graph_revision=0)
    atomic_json(location(store,'alice',pid),{'revision':1,'active':None,'draft':document,'generation_job_id':None})
    assert read_state(store,'alice',pid)['active'] is None
    with pytest.raises(Conflict):accept(store,'alice',pid,0,'draft-1')
    with pytest.raises(KeyError):accept(store,'bob',pid,1,'draft-1')
    state=accept(store,'alice',pid,1,'draft-1')
    assert state['active']['status']=='confirmed' and state['draft'] is None and state['revision']==2
    assert not state['active']['new_records']
