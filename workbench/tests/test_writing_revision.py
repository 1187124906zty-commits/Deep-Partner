from copy import deepcopy
from server.writing_revision import revision_sections,apply_edits,edit_issue_ids


def manuscript():
    return {'content':{'type':'doc','content':[
        {'type':'paragraph','content':[{'type':'text','text':'Author'}]},
        {'type':'heading','content':[{'type':'text','text':'1 Results'}]},
        {'type':'paragraph','content':[{'type':'text','text':'The error is reduced by 75%.'},{'type':'citation','attrs':{'number':2}}]},
        {'type':'image','attrs':{'src':'original.png'}},
        {'type':'table','content':[{'type':'tableRow','content':[]}]},
        {'type':'paragraph','content':[{'type':'inlineMath','attrs':{'latex':'D(h)'}},{'type':'text','text':' denotes diffusivity.'}]},
        {'type':'heading','content':[{'type':'text','text':'References'}]},
        {'type':'paragraph','content':[{'type':'text','text':'Original reference.'}]}]},'references':[{'id':'ref-2','doi':'10.test/test'}]}


def test_small_edit_preserves_native_figures_tables_math_authors_and_references():
    old=manuscript();prior=deepcopy(old)
    out,report=apply_edits(old,[{'path':[2,0],'before':'The error is reduced by 75%.','after':'The error decreases by 75%.','reason':'clearer verb'}])
    assert len(report['accepted'])==1 and not report['rejected']
    assert old==prior
    for i in [0,3,4,5,6,7]:assert old['content']['content'][i]==out['content']['content'][i]
    assert out['references']==old['references']
    assert out['content']['content'][2]['content'][1]==old['content']['content'][2]['content'][1]


def test_changed_numbers_stale_source_and_reference_edits_are_returned_for_review():
    old=manuscript()
    out,r=apply_edits(old,[
        {'path':[2,0],'before':'The error is reduced by 75%.','after':'The error is reduced by 80%.'},
        {'path':[2,0],'before':'A stale sentence.','after':'Revised stale sentence.'},
        {'path':[7,0],'before':'Original reference.','after':'New reference.'}])
    assert out==old and len(r['rejected'])==3


def test_sections_retain_the_context_around_editable_fragments():
    parts=revision_sections(manuscript())
    assert len(parts)==1 and len(parts[0]['paragraphs'])==2
    assert '[CITE:2]' in parts[0]['paragraphs'][0]['context']
    assert '[MATH:D(h)]' in parts[0]['paragraphs'][1]['context']


def test_grouped_necessary_issue_ids_are_understood():
    assert edit_issue_ids({'issue_id':'E01,E02，E03'})==['E01','E02','E03']
    assert edit_issue_ids({'issue_ids':['E01','E02','E01']})==['E01','E02']
    assert edit_issue_ids({})==[]


def test_regrouped_citations_keep_identities_and_scientific_numbers():
    old=manuscript();old['references']=[{'id':'ref-'+str(n),'number':n} for n in range(15,19)]
    original='The effect is 75% [15–18].';old['content']['content'][2]['content'][0]['text']=original
    revised='The effect is 75% [15]; the models are described in [16–18].'
    _,report=apply_edits(old,[{'path':[2,0],'before':original,'after':revised}])
    assert len(report['accepted'])==1
    for changed in [revised.replace('75%','80%'),revised.replace('16–18','16–17')]:
        out,report=apply_edits(old,[{'path':[2,0],'before':original,'after':changed}])
        assert out==old and len(report['rejected'])==1
