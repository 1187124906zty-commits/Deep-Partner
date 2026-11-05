"""Writing mode through task, state and real source-tool interfaces."""
import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from server.storage import Store
from server.writing import WritingService,settings,save_settings,decode_json,ACTIVE
from server.writing_tools import parse_tei,comparative_metric_calculator,intrinsic_scientific_rigor_auditor
from server import writing_prompts as prompts

if Path('/opt/workbench-tools/writing-libs').is_dir():sys.path.insert(0,'/opt/workbench-tools/writing-libs')


@pytest.fixture
def project(tmp_path):
    store=Store(tmp_path);owner='writing-test';p=store.create(owner,'Workflow test');pid=p['id']
    store.update(owner,pid,native_id='ws_writing_test');return store,owner,pid,store.path(owner,pid)


def test_default_conversation_does_not_activate_writing(project):
    _,_,_,root=project
    value=settings(root)
    assert value['mode']=='research' and value['phase']=='auto'
    assert 'confirmation' not in value


@pytest.mark.parametrize('phase',['draft','submission','revision'])
def test_three_phases_persist(project,phase):
    _,_,_,root=project
    save_settings(root,{'phase':phase,'journal':{'id':'issn-0008-8846','name':'Cement and Concrete Research'}})
    assert settings(root)['phase']==phase
    assert settings(root)['journal']['name']=='Cement and Concrete Research'


class ExercisedService(WritingService):
    def __init__(self,store,phase):super().__init__(store);self.calls=[];self.phase=phase
    async def dispatch(self,run,stage):
        self.calls.append(stage)
        await self.perform_stage(run['id'],run['owner'],run['project_id'],stage)
    async def prepare_journal(self,run):return {'journal':{'id':'test','name':'Test Journal'},'pages':[]}
    async def generate(self,run,prompt,payload,structured=True):
        if prompt==prompts.INTENT:return {'phase':self.phase,'goal':'respond to actual request','task_kind':'analysis','sections':['Analysis']}
        if prompt==prompts.EXEMPLAR:return {'journal_profile':{'name':'Test Journal'},'native_expression_bank':{}}
        if prompt==prompts.ALIGNMENT:return {'aligned_core_thesis':{'single_main_thread':'test'},'section_plan':[]}
        if prompt==prompts.NARROW:return {'paragraphs':[{'text':'computed task section'}],'l1_buffer':{'current_section_id':'Analysis'}}
        if prompt==prompts.WIDE:return {'sections':[{'id':'Analysis','paragraphs':['response to requested task']}]}
        return {'final_text':'# Actual task\n\nResponse to the test request.','all_assertions_passed':True}


@pytest.mark.parametrize('phase',['draft','submission','revision'])
def test_full_pipeline_runs_all_roles_and_saves(project,phase):
    store,owner,pid,root=project;s=ExercisedService(store,phase)
    run=asyncio.run(s.start(owner,pid,{'request':'Process the current task','operation_id':'op-one'},{}))
    assert run['status']=='completed',run
    assert run['phase']==phase
    assert s.calls==[x[0] for x in prompts.STAGES]
    assert (root/run['outputs']['path']).read_text().startswith('# Actual task')
    assert (root/'.workbench/writing/L3_Journal_Genome.json').is_file()
    assert (root/'.workbench/writing/L2_Manuscript_Alignment_State.json').is_file()
    assert (root/'.workbench/writing/L1_Paragraph_Flow_Buffer.json').is_file()
    repeated=asyncio.run(s.start(owner,pid,{'request':'Process the current task','operation_id':'op-one'},{}))
    assert repeated['id']==run['id'] and len(s.calls)==7


def test_explicit_phase_wins_over_model_inference(project):
    store,owner,pid,root=project;s=ExercisedService(store,'draft')
    run=asyncio.run(s.start(owner,pid,{'request':'Review response','phase':'revision'},{}))
    assert run['phase']=='revision'


def test_ordinary_mode_does_not_dispatch(project):
    store,owner,pid,_=project;s=ExercisedService(store,'draft')
    run=asyncio.run(s.start(owner,pid,{'request':'hello','mode':'research'},{}))
    assert run['status']=='disabled' and not s.calls


def test_automatic_dispatch_respects_default_and_explicit_mode(project):
    import httpx
    from fastapi import FastAPI
    from server import writing
    from unittest.mock import AsyncMock
    store,owner,pid,root=project
    app=FastAPI();app.dependency_overrides[writing.actor]=lambda:{'id':owner}
    service=writing.install(app,store)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            with patch.object(service,'dispatch',new_callable=AsyncMock) as dispatch:
                ordinary=await client.post('/research/api/writing/dispatch',json={'workspace_id':'ws_writing_test','request':'Discuss results'})
                assert ordinary.json()['status']=='disabled' and dispatch.await_count==0
                explicit=await client.post('/research/api/projects/'+pid+'/writing/start',json={'request':'Revise the draft'})
                assert explicit.status_code==200 and dispatch.await_count==1
                save_settings(root,{'mode':'writing'})
                selected=await client.post('/research/api/writing/dispatch',json={'workspace_id':'ws_writing_test','request':'Continue selected writing mode'})
                assert selected.status_code==200 and dispatch.await_count==2
    asyncio.run(exercise())


def test_grobid_tei_retains_structure_and_citation_locations():
    xml='''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>Paper</title></titleStmt></fileDesc></teiHeader><text><body><div><head>Introduction</head><p>Existing work <ref type="bibr" target="#b1">[1]</ref>.</p><formula>x=1</formula><figure><head>Figure 1</head></figure></div></body><back><listBibl><biblStruct>Reference</biblStruct></listBibl></back></text></TEI>'''
    result=parse_tei(xml,'literature/paper.pdf')
    assert result['headings']==['Introduction','Figure 1']
    assert result['paragraphs'][0]['citation_count']==1
    assert result['paragraphs'][0]['source']=='literature/paper.pdf'
    assert result['formulas']==['x=1'] and result['references']==['Reference']


def test_metrics_are_calculated_from_actual_csv(tmp_path):
    (tmp_path/'data.csv').write_text('pred,reference\n2,1\n4,3\n6,5\n')
    r=comparative_metric_calculator(tmp_path,'data.csv','pred',reference_column='reference')
    assert r['mean']==4 and r['rmse']==1 and r['mae']==1 and r['paired_n']==3
    assert r['confidence_interval_mean_95'][0]<4<r['confidence_interval_mean_95'][1]


def test_units_and_real_evidence_candidates():
    r=intrinsic_scientific_rigor_auditor([{'path':'results/convergence.csv','text':'mesh refinement'}],
        {'quantities':[{'symbol':'D','unit':'m^2/s'}]})
    assert r['unit_checks'][0]['status']=='parsed'
    assert r['evidence_candidates']['LOCK_3_CONVERGENCE_AND_SCALE'][0]['path']=='results/convergence.csv'


def test_task_ticket_does_not_authorize_another_run(project):
    store,owner,pid,_=project;s=ExercisedService(store,'draft')
    run=asyncio.run(s.start(owner,pid,{'request':'task'},{}))
    with pytest.raises(Exception):s.ticket_run(run['id'],'wrong-ticket')


def test_intent_selects_only_needed_roles_and_retains_source_input(project):
    class Focused(ExercisedService):
        async def generate(self,run,prompt,payload,structured=True):
            value=await super().generate(run,prompt,payload,structured)
            if prompt==prompts.INTENT:value['execution_stages']=['review','deliver']
            if prompt==prompts.REVIEW:
                assert payload['current_input']['user_request']=='Polish this paragraph'
                assert 'source_assets' in payload['current_input']
            return value
    store,owner,pid,root=project;s=Focused(store,'draft')
    run=asyncio.run(s.start(owner,pid,{'request':'Polish this paragraph'},{}))
    assert run['status']=='completed',run
    assert s.calls==['intent','review','deliver']
    assert run['stage_plan']==s.calls


def test_model_stage_selection_cannot_omit_deliverable_review(project):
    class SkipsReview(ExercisedService):
        async def generate(self,run,prompt,payload,structured=True):
            value=await super().generate(run,prompt,payload,structured)
            if prompt==prompts.INTENT:value['execution_stages']=['wide','deliver']
            return value
    store,owner,pid,root=project;service=SkipsReview(store,'draft')
    run=asyncio.run(service.start(owner,pid,{'request':'Write the requested section'},{}))
    assert 'review' in service.calls
    assert run['status']=='completed'


def test_reused_run_reinterprets_latest_request_and_preserves_editor_baseline(project):
    store,owner,pid,root=project;parent=ExercisedService(store,'draft')
    old=asyncio.run(parent.start(owner,pid,{'request':'Prior task'},{}))
    doc=store.manuscript(owner,pid)
    doc['content']={'type':'doc','content':[
        {'type':'paragraph','content':[{'type':'text','text':'Editor paragraph 1.'}]},
        {'type':'paragraph','content':[{'type':'text','text':'Editor paragraph 2.'}]},
        {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'参考文献'}]}]}
    store.save_manuscript(owner,pid,doc);original=store.manuscript(owner,pid)
    class StartOnly(WritingService):
        async def dispatch(self,run,stage):self.stage=stage
    service=StartOnly(store)
    run=asyncio.run(service.start(owner,pid,{'request':'One scored round','author_round':True,
        'proposal':True,'baseline_text':'Latest paragraph 1.\n\nLatest paragraph 2.',
        'reuse_run_id':old['id']},{}))
    saved=service.load(owner,pid,run['id'])
    assert service.stage=='intent'
    assert saved['previous_intent']['goal']=='respond to actual request'
    assert saved['request']=='One scored round'
    assert saved['source_document']['content']['content'][0]['content'][0]['text']=='Latest paragraph 1.'
    assert store.manuscript(owner,pid)==original


def test_explicit_section_restructure_uses_wide_and_score_only_native_candidate(project):
    from server.writing_scores import RUBRIC
    from server.writing import document_markdown
    store,owner,pid,root=project
    original=store.manuscript(owner,pid)
    original.update(title='Author paper',content={'type':'doc','content':[
        {'type':'paragraph','content':[{'type':'text','text':'Existing introduction one.'}]},
        {'type':'paragraph','content':[{'type':'text','text':'Existing introduction two.'}]},
        {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'References'}]}]},
        references=[{'id':'source-a','title':'Registered source','doi':'10.test/source','number':1,'authors':[]}])
    store.save_manuscript(owner,pid,original);untouched=store.manuscript(owner,pid)
    class Restructure(ExercisedService):
        async def generate(self,run,prompt,payload,structured=True):
            scores=[{'id':r['id'],'score':r['max']-2,'reason':'Based on the actual input text'} for r in RUBRIC]
            if prompt==prompts.INTENT:
                assert payload['editorial_scope']['mode']=='section_restructure'
                return {'phase':'draft','task_kind':'section','execution_stages':['review','deliver']}
            if prompt.startswith(prompts.ALIGNMENT):return {'editorial_assessment':{'scores':scores,'issues':[]}}
            if prompt.startswith(prompts.WIDE):
                assert payload['source_manifest'][0]['id']=='source-a'
                return {'sections':[{'title':'Introduction','paragraphs':[
                    'A synthesis grounded in the registered source.[REF:source-a]',
                    'The unresolved problem connects to the chosen method.',
                    'The third paragraph states the proposed contribution.' ]}]}
            if prompt.startswith(prompts.REVIEW):
                assert isinstance(payload['Manuscript_Draft'],str)
                assert 'A synthesis grounded' in payload['Manuscript_Draft']
                return {'after_assessment':{'scores':scores,'issues':[]},'final_text':'An unwanted extra rewrite.','all_assertions_passed':True}
            return await super().generate(run,prompt,payload,structured)
    service=Restructure(store,'draft')
    with patch('server.manuscripts.export_manuscript',return_value=(b'docx-test','application/docx','candidate.docx')) as export:
        result=asyncio.run(service.start(owner,pid,{'request':'Reorganise only the introduction','author_round':True,'proposal':True,
            'editorial_scope':{'mode':'section_restructure','sections':['Introduction']},
            'reference_policy':{'min_unique':1,'max_unique':2}},{}))
    exported=export.call_args.args[1]['content']['content']
    assert exported[0]['type']=='heading' and exported[0]['content'][0]['text']=='Introduction'
    assert exported[1]['type']=='paragraph' and 'A synthesis grounded' in exported[1]['content'][0]['text']
    assert result['status']=='completed',result
    assert service.calls==['intent','exemplar','alignment','wide','review','deliver']
    saved=service.load(owner,pid,result['id'])
    assert saved['revision_mode']=='section_restructure'
    assert saved['review']['final_text']==document_markdown(saved['candidate_document'])
    assert saved['review']['author_approval']=='pending'
    assert len(saved['candidate_document']['content']['content'])==5
    assert store.manuscript(owner,pid)==untouched
    assert (root/result['outputs']['path']).read_text().startswith('# Author paper')


def test_scored_review_cannot_rewrite_the_candidate_or_auto_accept_it(project):
    from server.writing_scores import RUBRIC
    from server.writing import document_markdown
    store,owner,pid,root=project
    candidate={'title':'Existing title','content':{'type':'doc','content':[
        {'type':'paragraph','content':[{'type':'text','text':'Keep the existing 75% result.'}]}]}}
    class ScoreOnly(WritingService):
        async def generate(self,run,prompt,payload,structured=True):
            return {'final_text':'An unwanted rewrite with 80%.','all_assertions_passed':True,
                'after_assessment':{'scores':[{'id':r['id'],'score':r['max']-2,'reason':'Original text compared with actual candidate'} for r in RUBRIC]}}
    run={'revision_mode':'incremental','author_round':True,'candidate_document':candidate,
        'l3':{},'l2':{},'intent':{},'phase':'draft','tool_results':{},'asset_index':{'selected_assets':[]}}
    result=asyncio.run(ScoreOnly(store).review_text(run,{},root))
    assert result['final_text']==document_markdown(candidate)
    assert result['all_assertions_passed'] is False
    assert result['author_approval']=='pending'


def test_author_selected_style_patch_reaches_native_candidate(project):
    store,owner,pid,root=project
    doc={'title':'Existing paper','content':{'type':'doc','content':[
        {'type':'heading','content':[{'type':'text','text':'Introduction'}]},
        {'type':'paragraph','content':[{'type':'text','text':'原有科学意思，表达需要改善。'}]}]}}
    class ExpressionEditor(WritingService):
        async def generate(self,run,prompt,payload,structured=True):
            assert payload['selected_issue_ids']==['P1']
            assert payload['key_sentence_context'][0]['paragraph_id']=='p1'
            return {'edits':[{'path':[1,0],'before':'原有科学意思，表达需要改善。',
                'after':'直接表达原有科学意思。','issue_ids':['P1']}],'author_notes':[]}
    run={'id':'c'*32,'owner':owner,'project_id':pid,'request':'保留原意，让关键句更直接。',
        'candidate_document':doc,'author_round':True,'l3':{},'l2':{'editorial_assessment':{'issues':[
            {'id':'P1','classification':'potential','selected_for_this_round':True,
                'selection_basis':'author_request','author_request_quote':'让关键句更直接'}]}}}
    result=asyncio.run(ExpressionEditor(store).revise_native_sections(run,'wide',lambda title:True))
    assert result['edited_fragments']==1 and not result['rejected_edits']
    assert run['candidate_document']['content']['content'][1]['content'][0]['text']=='直接表达原有科学意思。'
    assert doc['content']['content'][1]['content'][0]['text']=='原有科学意思，表达需要改善。'
