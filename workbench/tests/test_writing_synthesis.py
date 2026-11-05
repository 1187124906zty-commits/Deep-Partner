from copy import deepcopy
import pytest
from server.writing_synthesis import apply_section_restructure,reference_manifest,editorial_scope


def source():
    return {'title':'Existing paper','content':{'type':'doc','content':[
        {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'1 Introduction'}]},
        {'type':'paragraph','content':[{'type':'text','text':'First literature paragraph.'}]},
        {'type':'paragraph','content':[{'type':'text','text':'Second literature paragraph.'}]},
        {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'2 Results'}]},
        {'type':'paragraph','content':[{'type':'text','text':'The original result remains 75%.'}]},
        {'type':'image','attrs':{'src':'original.png'}},
        {'type':'paragraph','content':[{'type':'inlineMath','attrs':{'latex':'D(h)'}}]},
        {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'References'}]}]},
        'references':[{'id':'old-source','number':1,'title':'Original research','authors':[],'doi':'10.test/old'}]}


def test_section_reorganisation_changes_paragraphs_and_binds_grouped_sources():
    old=source();snapshot=deepcopy(old)
    refs=reference_manifest(old,supplied=[{'id':'new-source','title':'New research','doi':'10.test/new'}])
    sections=[{'title':'Introduction','paragraphs':[
        'One synthesis replaces both old paragraphs.[REF:old-source][REF:new-source]',
        'This unresolved prediction problem motivates the next comparison.',
        'A separate closing paragraph states the method contribution.' ]}]
    out,receipt=apply_section_restructure(old,sections,['引言'],refs,{'min_unique':2,'max_unique':3})
    assert old==snapshot
    assert receipt['paragraphs']==3 and receipt['unique_cited']==2
    assert [n['attrs']['refId'] for n in out['content']['content'][1]['content'] if n['type']=='citation']==['old-source','new-source']
    # All subsequent native results and media survive the paragraph-count change.
    assert out['content']['content'][4:8]==old['content']['content'][3:7]
    assert {r['id'] for r in out['references']}=={'old-source','new-source'}


def test_reference_shortfall_unknown_identity_and_unselected_section_are_not_saved():
    old=source();refs=reference_manifest(old)
    with pytest.raises(ValueError,match='来源覆盖范围'):
        apply_section_restructure(old,[{'title':'Introduction','paragraphs':['No evidence cited.']}],['Introduction'],refs,{'min_unique':1})
    with pytest.raises(ValueError,match='未在当前来源清单'):
        apply_section_restructure(old,[{'title':'Introduction','paragraphs':['Claim.[REF:invented]']}],['Introduction'],refs)
    with pytest.raises(ValueError,match='超出本轮范围'):
        apply_section_restructure(old,[{'title':'Results','paragraphs':['Replacement.']}],['Introduction'],refs)
    assert old==source()


def test_explicit_structural_scope_keeps_target_sections_and_deduplicates_doi():
    scope=editorial_scope({'mode':'section_restructure','sections':['Introduction']})
    assert scope['mode']=='section_restructure'
    with pytest.raises(ValueError,match='指定目标章节'):
        editorial_scope({'mode':'section_restructure'})
    rows=reference_manifest(source(),supplied=[{'id':'other-id','title':'Same original','doi':'10.TEST/OLD','source_path':'literature/original.pdf'}])
    assert len(rows)==1 and rows[0]['id']=='old-source'
    assert rows[0]['source_path']=='literature/original.pdf'


def test_reorganised_reference_numbers_follow_first_appearance_without_changing_ids():
    old=source()
    refs=reference_manifest(old,supplied=[{'id':'new-source','title':'New research','doi':'10.test/new'}])
    out,_=apply_section_restructure(old,[{'title':'Introduction','paragraphs':[
        'First claim.[REF:new-source] Then the earlier source.[REF:old-source]']}],['Introduction'],refs)
    assert [(r['id'],r['number']) for r in out['references']]==[('new-source',1),('old-source',2)]
    assert [(n['attrs']['refId'],n['attrs']['number']) for n in out['content']['content'][1]['content'] if n['type']=='citation']==[('new-source',1),('old-source',2)]


def test_structural_prose_edit_does_not_silently_discard_equations():
    old=source();old['content']['content'][1]['content'].append({'type':'inlineMath','attrs':{'latex':'c(x,t)'}})
    with pytest.raises(ValueError,match='含公式'):
        apply_section_restructure(old,[{'title':'Introduction','paragraphs':['New prose.']}],['Introduction'],reference_manifest(old))
