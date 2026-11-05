"""ASGI review integration with actual local files and fully mocked model HTTP."""
from __future__ import annotations

import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from server import quality_api
from server.native import actor
from server.storage import Store,atomic_json


AUTHOR_KEY='sk-author-unit-only-secret'
REVIEWER_KEY='sk-reviewer-unit-only-secret'
REVIEWER_MODEL='independent-review-model'


def create_materials(root):
    """Generate valid UTF-8, two-page PDF and editable PPTX fixture files."""
    import fitz
    from pptx import Presentation
    from pptx.util import Inches

    (root/'project/docs/draft.md').write_text('# Draft\n\n实际条件与证据保持对应。\n',encoding='utf8')
    atomic_json(root/'manuscript/main.json',{'title':'Fixture manuscript','content':{'type':'doc','content':[
        {'type':'paragraph','content':[{'type':'text','text':'A measured result under declared conditions.'}]}]}})
    (root/'project/data/source.txt').write_text('原始来源：条件、单位和限制。\n',encoding='utf8')
    document=fitz.open()
    for text in ['PDF EVIDENCE FIRST PAGE','PDF EVIDENCE SECOND PAGE']:
        page=document.new_page();page.insert_text((72,72),text)
    document.save(root/'project/data/source.pdf');document.close()
    presentation=Presentation()
    for text in ['PPTX EVIDENCE FIRST SLIDE','PPTX EVIDENCE SECOND SLIDE']:
        slide=presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1),Inches(1),Inches(8),Inches(2)).text=text
    presentation.save(root/'slides/exports/研究汇报.pptx')
    atomic_json(root/'slides/plan.json',{'sections':[{'id':'s1','title':'A supported result',
                                                   'content':'A result with its scope.'}]})


@pytest.fixture
def api(tmp_path_factory,monkeypatch):
    # Keep UUID-bearing review paths below Windows' legacy path-length limit.
    tmp_path=tmp_path_factory.mktemp('qa')
    # Reuse the real settings handlers without activating the full app lifespan.
    monkeypatch.setenv('WORKBENCH_DATA',str(tmp_path/'import-state'))
    module=importlib.import_module('server.app')
    monkeypatch.setattr(module,'DATA',tmp_path/'settings')
    store=Store(tmp_path/'projects')
    project=store.create('owner-a','Quality API fixture')
    store.update('owner-a',project['id'],native_id='native-workspace-a')
    project=store.get('owner-a',project['id']);root=store.path('owner-a',project['id'])
    create_materials(root)
    current_user={'id':'owner-a','username':'QA'}
    calls=[]
    provider=SimpleNamespace(reference_source=False,forge_checks=False,score=3)
    real_client=httpx.Client

    def mock_model(request):
        body=json.loads(request.content)
        native=request.url.path.endswith('/api/documents/actions/edit')
        packet=json.loads(body['text'] if native else body['messages'][-1]['content'])
        calls.append({'url':str(request.url),'headers':dict(request.headers),'body':body,'packet':packet})
        refs=packet['sources'] if provider.reference_source else packet['artifacts']
        reference=refs[0]['binding']['path']
        answer={'dimensions':[{'id':d['id'],'score':provider.score,
                               'reason':'The supplied fixture supports this judgment.',
                               'evidence_refs':[{'path':reference,'locator':{'paragraph':1}}]}
                              for d in packet['rubric']['dimensions']],
                'issues':[],'limitations':[]}
        if provider.forge_checks:
            answer.update(overall=4,passed=True,can_proceed=True,automatic_flow=True,
                          hard_checks=[{'id':'render_validation','status':'passed','source':'server',
                                        'performed_by':'invented-renderer','evidence':{'claim':'forged'}}])
        encoded=json.dumps(answer,ensure_ascii=False)
        if native:return httpx.Response(200,json={'edited_text':encoded})
        assert request.url.path.endswith('/chat/completions')
        return httpx.Response(200,json={'choices':[{'message':{'content':encoded}}]})

    transport=httpx.MockTransport(mock_model)
    def model_client(*args,**kwargs):
        kwargs['transport']=transport
        return real_client(*args,**kwargs)
    monkeypatch.setattr(httpx,'Client',model_client)

    async def native_options(request,method,path,**kwargs):
        assert method=='GET' and path=='/api/settings/llm-options'
        return {'options':[{'id':'assigned-tutor-model'}]}
    monkeypatch.setattr(module,'call',native_options)

    def run_job(jid,callback):
        store.set_job(jid,status='running')
        try:store.set_job(jid,status='completed',result=callback())
        except Exception as error:store.set_job(jid,status='failed',error=str(error))

    application=FastAPI()
    application.add_exception_handler(KeyError,module.missing)
    application.add_exception_handler(ValueError,module.invalid)
    application.dependency_overrides[actor]=lambda:current_user
    application.add_api_route('/research/api/api-settings',module.api_settings,methods=['GET'])
    application.add_api_route('/research/api/api-settings',module.api_settings_save,methods=['PUT'])
    quality_api.install(application,store,module.api_path,run_job)

    def request(method,path,**kwargs):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application,raise_app_exceptions=False),
                                         base_url='http://quality.test',
                                         headers={'Authorization':'Bearer account-session-fixture'}) as client:
                return await client.request(method,path,**kwargs)
        return asyncio.run(send())

    def submit(payload,pid=None):
        target=pid or project['id']
        response=request('POST',f'/research/api/projects/{target}/quality/reviews',json=payload)
        if response.status_code!=200:return response,None
        jid=response.json()['job_id']
        job=next(x for x in store.jobs(current_user['id'],target) if x['id']==jid)
        return response,job

    return SimpleNamespace(request=request,submit=submit,store=store,project=project,root=root,
                           user=current_user,calls=calls,provider=provider,settings_path=module.api_path,
                           route=f'/research/api/projects/{project["id"]}/quality')


def writing_payload(operation='review-1',**changes):
    return {'operation_id':operation,'stage':'writing',
            'artifact_paths':['manuscript/main.json'],**changes}


def successful_job(job):
    assert job['status']=='completed',job.get('error')
    return job['result']


def update_version(path):
    before=path.stat()
    path.write_text(path.read_text(encoding='utf8')+'\n',encoding='utf8')
    os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1_000_000_000))


def test_default_reviewer_inherits_tutor_even_when_author_api_exists(api):
    atomic_json(api.settings_path('owner-a'),{'base_url':'https://author.invalid/v1',
                                           'model':'author-model','api_key':AUTHOR_KEY})
    settings=api.request('GET','/research/api/api-settings')
    assert settings.status_code==200 and settings.json()['reviewer_mode']=='inherit'
    assert AUTHOR_KEY not in settings.text
    _,job=api.submit(writing_payload())
    review=successful_job(job)
    call=api.calls[0]
    assert '/api/documents/actions/edit?' in call['url']
    assert 'dt_workspace=native-workspace-a' in call['url']
    assert call['headers']['authorization']=='Bearer account-session-fixture'
    assert AUTHOR_KEY not in json.dumps(call)
    assert review['evaluator']['selection']=='tutor_account_model'
    assert review['evaluator']['independent_context'] is True
    assert review['can_proceed'] is True


def test_custom_reviewer_uses_its_own_key_and_model_without_settings_leak(api):
    atomic_json(api.settings_path('owner-a'),{'base_url':'https://author.invalid/v1',
                                           'model':'author-model','api_key':AUTHOR_KEY})
    payload={'base_url':'https://author.invalid/v1','model':'author-model',
             'reviewer_mode':'custom','reviewer_base_url':'https://review.invalid/v1/',
             'reviewer_model':REVIEWER_MODEL,'reviewer_api_key':REVIEWER_KEY}
    saved=api.request('PUT','/research/api/api-settings',json=payload)
    assert saved.status_code==200
    visible=api.request('GET','/research/api/api-settings')
    assert visible.status_code==200 and visible.json()['reviewer_configured'] is True
    assert 'reviewer_api_key' not in visible.json()
    assert AUTHOR_KEY not in visible.text and REVIEWER_KEY not in visible.text
    stored=json.loads(api.settings_path('owner-a').read_text(encoding='utf8'))
    assert stored['api_key']==AUTHOR_KEY and stored['reviewer_api_key']==REVIEWER_KEY
    _,job=api.submit(writing_payload())
    review=successful_job(job);call=api.calls[0]
    assert call['url']=='https://review.invalid/v1/chat/completions'
    assert call['headers']['authorization']=='Bearer '+REVIEWER_KEY
    assert call['body']['model']==REVIEWER_MODEL
    assert review['evaluator']['selection']=='custom'
    assert AUTHOR_KEY not in json.dumps(call)
    assert REVIEWER_KEY not in json.dumps(review)


@pytest.mark.parametrize('configuration',[
    {'reviewer_mode':'unknown'},
    {'reviewer_mode':'custom','reviewer_base_url':'http://review.invalid','reviewer_model':'x','reviewer_api_key':'x'},
    {'reviewer_mode':'custom','reviewer_base_url':'https://review.invalid','reviewer_model':'x'},
    {'reviewer_mode':'custom','reviewer_base_url':'https://review.invalid','reviewer_api_key':'x'},
])
def test_invalid_reviewer_settings_fail_before_model_calls(api,configuration):
    response=api.request('PUT','/research/api/api-settings',json=configuration)
    assert response.status_code==400,response.text
    assert not api.calls
    assert not api.settings_path('owner-a').exists()


def test_settings_and_project_reviews_are_isolated_by_owner(api):
    atomic_json(api.settings_path('owner-a'),{'reviewer_mode':'custom','reviewer_base_url':'https://review.invalid',
                                           'reviewer_model':REVIEWER_MODEL,'reviewer_api_key':REVIEWER_KEY})
    api.user['id']='owner-b'
    settings=api.request('GET','/research/api/api-settings')
    assert settings.status_code==200 and settings.json()['reviewer_mode']=='inherit'
    assert settings.json()['reviewer_configured'] is False
    assert REVIEWER_MODEL not in settings.text and REVIEWER_KEY not in settings.text
    for method,path,kwargs in [
        ('GET',api.route+'/reviews',{}),
        ('GET',api.route+'/gate',{'params':{'stage':'writing'}}),
        ('POST',api.route+'/reviews',{'json':writing_payload()}),
    ]:
        response=api.request(method,path,**kwargs)
        assert response.status_code==404,response.text
    assert not api.calls


def test_operation_replay_deduplicates_job_and_model_call(api):
    payload=writing_payload('replay-id')
    first,job=api.submit(payload);successful_job(job)
    second,replayed=api.submit(payload)
    assert first.json()['job_id']==second.json()['job_id']
    assert first.json()['deduplicated'] is False and second.json()['deduplicated'] is True
    assert job['result']['review_id']==replayed['result']['review_id']
    assert len(api.calls)==1
    changed=api.request('POST',api.route+'/reviews',json={**payload,'intended_use':'A different request'})
    assert changed.status_code==409
    assert len(api.calls)==1


def test_same_owner_projects_do_not_share_reviews_or_operation_ids(api):
    payload=writing_payload('same-operation-different-project')
    first_response,first_job=api.submit(payload)
    first=successful_job(first_job)
    other=api.store.create('owner-a','Independent project')
    other_root=api.store.path('owner-a',other['id']);create_materials(other_root)
    other_route=f'/research/api/projects/{other["id"]}/quality'
    empty=api.request('GET',other_route+'/reviews',params={'stage':'writing'}).json()
    assert empty['items']==[] and empty['can_proceed'] is False
    second_response,second_job=api.submit(payload,pid=other['id'])
    second=successful_job(second_job)
    assert first_response.json()['job_id']!=second_response.json()['job_id']
    assert first['review_id']!=second['review_id']
    assert first['project_id']==api.project['id'] and second['project_id']==other['id']
    assert len(api.calls)==2


def test_changed_artifact_cannot_reuse_an_old_passing_review(api):
    payload=writing_payload('before-change')
    _,job=api.submit(payload);review=successful_job(job)
    assert review['can_proceed'] is True
    before=api.request('GET',api.route+'/gate',params={'stage':'writing'}).json()
    assert before['can_proceed'] is True
    update_version(api.root/'manuscript/main.json')
    after=api.request('GET',api.route+'/gate',params={'stage':'writing'}).json()
    assert after['can_proceed'] is False and after['automatic_flow'] is False
    assert after['current'] is None
    history=api.request('GET',api.route+'/reviews',params={'stage':'writing'}).json()
    assert history['current'] is None
    assert not history['latest']['can_proceed']
    replay,_=api.submit(payload)
    assert replay.json()['deduplicated'] is True and len(api.calls)==1
    assert not api.request('GET',api.route+'/gate',params={'stage':'writing'}).json()['can_proceed']
    override=api.request('POST',api.route+'/reviews/'+review['review_id']+'/override',
                         json={'operation_id':'old-override','confirmed':True,'reason':'Proceed despite review'})
    assert override.status_code==409


def test_source_references_from_actual_inputs_are_accepted(api):
    api.provider.reference_source=True
    _,job=api.submit(writing_payload(source_paths=['project/data/source.txt']))
    review=successful_job(job)
    assert review['can_proceed'] is True
    assert all(d['status']=='scored' for d in review['dimensions'])
    assert all(d['evidence_refs'][0]['path']=='project/data/source.txt' for d in review['dimensions'])
    current=api.request('GET',api.route+'/reviews',params={'stage':'writing'}).json()
    assert current['current']['can_proceed'] is True
    gate=api.request('GET',api.route+'/gate',params={'stage':'writing'}).json()
    assert gate['can_proceed'] is True
    update_version(api.root/'project/data/source.txt')
    changed=api.request('GET',api.route+'/reviews',params={'stage':'writing'}).json()
    assert changed['current'] is None and not changed['latest']['can_proceed']
    override=api.request('POST',api.route+'/reviews/'+review['review_id']+'/override',
                         json={'operation_id':'changed-source-override','confirmed':True,'reason':'Proceed despite source change'})
    assert override.status_code==409


def test_actual_utf8_pdf_pptx_text_reaches_the_reviewer_with_limits_disclosed(api):
    sources=['project/data/source.txt','project/data/source.pdf','slides/exports/研究汇报.pptx']
    _,job=api.submit(writing_payload(artifact_paths=['project/docs/draft.md'],source_paths=sources))
    review=successful_job(job);packet=api.calls[0]['packet']
    assert '实际条件' in packet['artifacts'][0]['content']
    extracted={x['binding']['path']:x for x in packet['sources']}
    assert extracted[sources[0]]['extraction']=='utf8'
    assert '原始来源' in extracted[sources[0]]['content']
    assert extracted[sources[1]]['extraction']=='pdf_text_layer_only'
    assert 'PDF page 2' in extracted[sources[1]]['content']
    assert 'PDF EVIDENCE SECOND PAGE' in extracted[sources[1]]['content']
    assert extracted[sources[2]]['extraction']=='pptx_text_objects_only'
    assert 'Slide 2' in extracted[sources[2]]['content']
    assert 'PPTX EVIDENCE SECOND SLIDE' in extracted[sources[2]]['content']
    assert all(x['truncated'] is False for x in packet['artifacts']+packet['sources'])
    assert review['visual_review_performed'] is False
    assert review['evaluator']['visual_review_performed'] is False
    assert len(review['input_coverage'])==4


def test_long_real_source_is_bounded_and_marked_truncated(api):
    path=api.root/'project/data/long.md';path.write_text('证'*180_050,encoding='utf8')
    _,job=api.submit(writing_payload(source_paths=['project/data/long.md']))
    successful_job(job);source=api.calls[0]['packet']['sources'][0]
    assert len(source['content'])==180_000 and source['truncated'] is True


def test_overlarge_text_fails_without_a_model_call(api):
    path=api.root/'project/data/too-large.txt';path.write_bytes(b'x'*2_000_001)
    _,job=api.submit(writing_payload(source_paths=['project/data/too-large.txt']))
    assert job['status']=='failed' and '过大' in job['error']
    assert not api.calls


def test_model_cannot_forge_a_render_hard_check(api):
    api.provider.forge_checks=True;api.provider.score=4
    _,job=api.submit({'operation_id':'forged-render','stage':'slides-export','purpose':'group'})
    review=successful_job(job)
    checks={x['id']:x for x in review['hard_checks']}
    assert checks['render_validation']['status']=='unknown'
    assert checks['render_validation']['performed_by']!='invented-renderer'
    assert review['quality_passed'] is True
    assert review['can_proceed'] is False and review['passed'] is False


def test_successful_render_report_accepts_false_overlap_flags(api):
    atomic_json(api.root/'slides/verification.json',{'render_validation':{
        'pages':2,'checked_text_blocks':2,'complete_visible_text':True,'page_bounds':True,
        'text_line_overlap':False,'content_text_image_overlap':False,
        'renderer':'fixture report matching slide_quality.verify_rendered schema'}})
    export=api.root/'slides/exports/研究汇报.pptx'
    report=api.root/'slides/verification.json'
    stamp=max(report.stat().st_mtime_ns,export.stat().st_mtime_ns+1_000_000)
    os.utime(report,ns=(stamp,stamp))
    _,job=api.submit({'operation_id':'valid-render','stage':'slides-export','purpose':'group'})
    review=successful_job(job)
    check=next(x for x in review['hard_checks'] if x['id']=='render_validation')
    assert check['status']=='passed' and check['verified'] is True
    assert review['can_proceed'] is True


@pytest.mark.parametrize('payload',[
    writing_payload(stage='unknown'),
    {'operation_id':'unknown-purpose','stage':'slides-plan','purpose':'unknown'},
    writing_payload(artifact_paths=['../outside.md']),
])
def test_invalid_review_inputs_fail_before_job_or_model_call(api,payload):
    response=api.request('POST',api.route+'/reviews',json=payload)
    assert response.status_code==400,response.text
    assert not api.store.jobs('owner-a',api.project['id'])
    assert not api.calls
