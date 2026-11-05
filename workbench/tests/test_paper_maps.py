from pathlib import Path
from unittest.mock import patch
import asyncio
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.storage import Store
from server.native import actor
from server.paper_maps import PaperMaps,install,source_key


@pytest.fixture
def project(tmp_path):
    store=Store(tmp_path/'store');p=store.create('owner','Content map test');root=store.path('owner',p['id'])
    path=root/'literature/reading/source.pdf';path.parent.mkdir(parents=True);path.write_bytes(b'%PDF immutable sample')
    return store,p,root,path


def test_ingestion_queue_is_idempotent_and_does_not_need_open_reader(project):
    store,p,root,_=project;service=PaperMaps(store)
    first=service.enqueue('owner',p['id'],'reading/source.pdf',metadata={'title':'Original paper'})
    second=service.enqueue('owner',p['id'],'reading/source.pdf',metadata={'title':'Verified title'})
    assert first['job_id']==second['job_id'] and second['title']=='Verified title'
    with store.db() as db:rows=db.execute("SELECT * FROM jobs WHERE kind='paper-content-map'").fetchall()
    assert len(rows)==1 and rows[0]['status']=='queued'
    assert not (root/'.workbench/neoread-map.json').exists()


def test_read_status_never_generates_and_original_changes_are_stale(project):
    store,p,root,path=project;service=PaperMaps(store)
    assert service.status('owner',p['id'],'reading/source.pdf')['status']=='missing'
    with store.db() as db:assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0
    entry=service.enqueue('owner',p['id'],'reading/source.pdf');state=json.loads(service.job_path('owner',p['id'],entry['job_id']).read_text())
    service.update(state,'ready','Saved')
    path.write_bytes(path.read_bytes()+b' new version')
    assert service.status('owner',p['id'],'reading/source.pdf')['status']=='stale'


def test_capability_is_private_and_bound_to_exact_running_job(project):
    store,p,_,_=project;app=FastAPI();service=install(app,store)
    app.dependency_overrides[actor]=lambda:{'id':'owner'}
    entry=service.enqueue('owner',p['id'],'reading/source.pdf');state=json.loads(service.job_path('owner',p['id'],entry['job_id']).read_text())
    client=TestClient(app)
    assert client.get('/internal/paper-map-jobs/'+entry['job_id']).status_code==403
    assert client.get('/internal/paper-map-jobs/'+entry['job_id'],headers={'x-paper-map-capability':state['capability']}).status_code==403
    service.update(state,'running','Generating')
    response=client.get('/internal/paper-map-jobs/'+entry['job_id'],headers={'x-paper-map-capability':state['capability']})
    assert response.status_code==200 and response.json()['owner']=='owner'
    response=client.get('/research/api/projects/'+p['id']+'/literature/content-map',params={'asset':'reading/source.pdf'})
    assert 'capability' not in response.text and 'source_path' not in response.json()


def test_sources_cannot_leave_owned_project_or_use_unbound_knowledge_base(project):
    store,p,_,_=project;service=PaperMaps(store)
    with pytest.raises(ValueError):service.enqueue('owner',p['id'],'../../secret.pdf')
    with pytest.raises(Exception):service.source_path('other',p['id'],'reading/source.pdf')
    with pytest.raises(Exception):service.source_path('owner',p['id'],'source.pdf','unbound-kb')
    assert source_key('a/source.pdf')!=source_key('b/source.pdf')


def test_failed_job_can_resume_without_deleting_saved_parts(project):
    store,p,_,_=project;service=PaperMaps(store)
    entry=service.enqueue('owner',p['id'],'reading/source.pdf');state=json.loads(service.job_path('owner',p['id'],entry['job_id']).read_text())
    part=service.folder('owner',p['id'])/'jobs'/entry['job_id']/'part-0.json';part.parent.mkdir(parents=True);part.write_text('{"nodes":[]}')
    service.update(state,'interrupted','Stopped')
    next_job=service.enqueue('owner',p['id'],'reading/source.pdf')
    assert next_job['job_id']==entry['job_id'] and part.is_file()
    assert next_job['status']=='queued'


def test_full_build_saves_source_bound_map_and_reuses_completed_model_parts(project,monkeypatch):
    from server import paper_map_core as core
    store,p,root,path=project;service=PaperMaps(store)
    source=core.parse_tei('<TEI><teiHeader><profileDesc><abstract><p>The original abstract stays complete.</p></abstract></profileDesc></teiHeader><text><body><div type="introduction"><head>Introduction</head><p>Connected pores control ion transport.</p></div></body></text></TEI>', 'reading/source.pdf', {'title':'Ion transport through connected pores'},signature=service.signature(path))
    unit=next(u for u in source['units'] if u['kind']=='paragraph' and u['section_id']!='s-abstract')
    section=unit['section_id'];uid=unit['id'];calls=[]
    def node(ident,parent,kind):
        return {'id':ident,'parent_id':parent,'kind':kind,'section_type':'introduction','source_section_id':section,'label':'连通孔隙','content':'孔隙连通性影响离子传输。','keywords':['连通孔隙','离子传输'],'source_ids':[uid],'source_quotes':[{'source_id':uid,'quote':unit['text']}]}
    nodes=[node('sec.'+section,'paper','section'),node('para.'+uid,'sec.'+section,'paragraph'),node('element.'+uid,'para.'+uid,'element')]
    async def model(state,prompt,payload,part):
        calls.append(part)
        if part=='quality-review':return {'items':[{'id':item['id'],'score':item['max'],'reason':'The fixture source supports the referenced transport relation.','node_ids':['para.'+uid],'edge_ids':[]} for item in core.map_rules()['scoring']['items'][:7]],'issues':[],'summary':'Fixture review.'}
        if part!='whole-paper':return {'nodes':nodes,'edges':[]}
        return {'keywords':['连通孔隙','离子传输'],'edges':[],'story':{'author_question':'孔隙连通性怎样影响离子传输？','main_claim':'连通孔隙控制所考察的离子传输。','organization_summary':'材料结构连接到离子传输问题。','means_ends':[],'promise_evidence':[],'learning_points':[]}}
    monkeypatch.setattr(core,'extract_source',lambda *args,**kwargs:source)
    service.call_model=model
    entry=service.enqueue('owner',p['id'],'reading/source.pdf')
    with store.db() as db:row=dict(db.execute('SELECT * FROM jobs WHERE id=?',(entry['job_id'],)).fetchone())
    asyncio.run(service.build(row))
    value=service.status('owner',p['id'],'reading/source.pdf')
    assert value['status']=='needs_review' and value['map']['abstract']['text']=='The original abstract stays complete.'
    assert next(n for n in value['map']['nodes'] if n['kind']=='paper')['content']=='连通孔隙控制所考察的离子传输。'
    assert calls==['section-1','whole-paper','quality-review']
    assert value['map']['evaluation']['content_score']==65 and value['map']['evaluation']['visual_score'] is None
    asyncio.run(service.build(row))
    assert calls==['section-1','whole-paper','quality-review']
