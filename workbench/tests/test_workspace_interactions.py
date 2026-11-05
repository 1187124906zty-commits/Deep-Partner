from pathlib import Path
import asyncio,json
import httpx
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from server.storage import Store
from server.bibliography_metadata import resolve,pdf_author_names,more_complete_authors,overlay,key
from server.project_canvas import belongs_to_project,record_retrieval
from server.knowledge_sources import install
from server.native import actor


def test_full_author_names_require_the_actual_written_name():
    assert pdf_author_names(['Liu, D. C.','Nocedal, J.'],'ON THE LIMITED MEMORY BFGS METHOD\nDong C. LIU and Jorge NOCEDAL\nAbstract')==['Dong C. Liu','Jorge Nocedal']
    assert pdf_author_names(['Wang, J.'],'No given name is present.\nAbstract')==['J. Wang']


def test_exact_doi_record_cannot_replace_another_pdf_identity():
    async def run():
        def response(request):return httpx.Response(200,json={'message':{'DOI':'10.1234/exact','title':['A different paper'],'author':[{'given':'Jane','family':'Smith'}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            result=await resolve({'title':'The actual uploaded paper','doi':'10.1234/exact'},'The actual uploaded paper\nAlice Doe\nAbstract',client)
        assert result['metadata_status']=='unconfirmed' and result['title']=='The actual uploaded paper'
    asyncio.run(run())


def test_exact_doi_preserves_all_source_authors_in_order():
    async def run():
        def response(request):return httpx.Response(200,json={'message':{'DOI':'10.1234/exact','title':['A verified paper'],'author':[{'given':'Jane Anne','family':'Smith'},{'given':'Wei','family':'Zhang'}],'published':{'date-parts':[[2025]]}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:result=await resolve({'doi':'10.1234/exact','title':'A verified paper'},client=client)
        assert result['authors']==['Jane Anne Smith','Wei Zhang'] and result['metadata_status']=='verified'
    asyncio.run(run())


def test_cached_initials_cannot_contract_written_given_names():
    entry={'doi':'10.1234/full','authors':['Dong C. Liu','Jorge Nocedal']}
    cache={key(entry):{'record':{'authors':['D. C. Liu','J. Nocedal']}}}
    assert overlay(entry,cache)['authors']==entry['authors']
    assert more_complete_authors(['A. Smith'],['Alice Smith','Bob Jones'])==['Alice Smith','Bob Jones']


def test_graphics_and_code_views_have_distinct_files_and_counts(tmp_path):
    store=Store(tmp_path);project=store.create('alice','Scoped files');root=store.path('alice',project['id'])/'project'
    (root/'src/main.py').write_text('print(1)');(root/'results/chart.png').write_bytes(b'png');(root/'results/values.csv').write_text('x,y\n1,2');(root/'docs/paper.pdf').write_bytes(b'pdf')
    graphics=store.inventory('alice',project['id'],mode='images')['items'];code=store.inventory('alice',project['id'],mode='code')['items']
    assert [(r['name'],r['count']) for r in graphics]==[('results',1)]
    assert 'src' in {r['name'] for r in code} and 'docs' not in {r['name'] for r in code}
    assert store.inventory('alice',project['id'],'results','images')['items'][0]['name']=='chart.png'
    assert {r['name'] for r in store.inventory('alice',project['id'],'results','code')['items']}=={'values.csv'}


def test_account_memory_is_not_silently_attributed_to_a_project():
    project={'native_id':'workspace-a','config':{'knowledge_bases':['workspace:workspace-a:kb:papers']}}
    assert not belongs_to_project({'payload':{'kb_name':'unrelated account KB'}},project,{'session-a'},{'papers'})
    assert not belongs_to_project({'session_id':'session-b','payload':{'kb_name':'papers'}},project,{'session-a'},{'papers'})
    assert not belongs_to_project({'payload':{'workspace_id':'workspace-b','kb_name':'papers'}},project,{'session-a'},{'papers'})
    assert belongs_to_project({'session_id':'session-a','payload':{}},project,{'session-a'},set())
    assert belongs_to_project({'payload':{'kb_name':'papers'}},project,set(),{'papers'})


def test_retrieval_receipts_remain_in_the_owning_project(tmp_path):
    store=Store(tmp_path);first=store.create('alice','First');second=store.create('alice','Second')
    record_retrieval(store,'alice',first['id'],{'query':'diffusion','mode':'fulltext-keyword','items':[{'title':'Actual PDF','asset':'reading/a.pdf','url':'/owned'}]})
    path=store.path('alice',first['id'])/'.workbench/retrieval-events.json'
    assert json.loads(path.read_text())[0]['count']==1
    assert not (store.path('alice',second['id'])/'.workbench/retrieval-events.json').exists()


def test_knowledge_rename_keeps_resource_id_and_other_account_names(tmp_path,monkeypatch):
    store=Store(tmp_path);project=store.create('alice','Project');project=store.update('alice',project['id'],native_id='ws-a')
    app=FastAPI();install(app,store,lambda owner:tmp_path/owner/'api.json');app.dependency_overrides[actor]=lambda:{'id':'alice'}
    async def native_call(*args,**kwargs):return [{'id':'workspace:ws-a:kb:original','name':'Original','read_only':False}]
    monkeypatch.setattr('server.knowledge_sources.call',native_call)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            endpoint='/research/api/projects/'+project['id']+'/knowledge/sources'
            response=await client.patch(endpoint+'/workspace:ws-a:kb:original',json={'name':'Project evidence'});assert response.status_code==200
            row=(await client.get(endpoint)).json()['items'][0]
            assert row['id']=='workspace:ws-a:kb:original' and row['name']=='Project evidence'
    asyncio.run(run());assert not (tmp_path/'bob/knowledge-names.json').exists()


def test_native_template_reference_preserves_column_and_line_number_system(tmp_path):
    from docx import Document
    from docx.oxml.ns import qn
    from server.word_layout import make_reference
    chinese=Document(make_reference(tmp_path,'journal-zh',2));english=Document(make_reference(tmp_path,'journal-en',1))
    assert chinese.sections[0]._sectPr.find(qn('w:cols')).get(qn('w:num'))=='2'
    assert english.sections[0]._sectPr.find(qn('w:lnNumType')) is not None
    assert chinese.styles['Title'].font.size.pt==22
    assert english.styles['Normal'].font.name=='Times New Roman'
    assert chinese.styles['Bibliography'].font.size.pt==7.5
    assert chinese.styles['Title'].element.find('.//'+qn('w:vertAlign')) is None
    assert english.styles['Heading 1'].font.color.type is not None
    assert english.styles['Heading 1'].element.find('.//'+qn('w:color')).get(qn('w:val')) in ('auto','000000')
