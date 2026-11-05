"""Purpose guidance and regression checks for private-template font precedence."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from server.presentation_catalog import (
    PROFILES, catalog, generation_context, profile, purpose_rule, purpose_rules,
)
from server.slide_quality import layout_sections


PURPOSE_IDS={'group','conference','project','proposal','defense','literature'}
LEGACY_FIELDS={'id','name','audience','purpose','structure','sources'}


def manifest(name='private-template',body=18,title=26):
    return {'name':name,'width':12192000,'height':6858000,
            'examples':{'cover':1,'content':1},
            'slides':[{'page':1,'role':'content',
                       'title_box':{'font_pt':title},'body_box':{'font_pt':body}}]}


def plan(template=None):
    result={'sections':[{'id':'evidence','role':'content','title':'Evidence',
                         'content':'A measured result with its conditions.'}]}
    if template is not None:result['visual_template']=template
    return result


def context_parts(value):
    lines=value.splitlines()
    return json.loads(lines[0].split('：',1)[1]),json.loads(lines[1].split('：',1)[1])


def test_six_purpose_cards_keep_legacy_catalog_fields():
    assert {p['id'] for p in PROFILES}==PURPOSE_IDS
    assert all(set(p)==LEGACY_FIELDS for p in PROFILES)
    for identifier in PURPOSE_IDS:
        assert profile(identifier)['id']==identifier
        card=purpose_rule(identifier)
        assert card['necessary_information'] and card['exceptions']
        assert card['evidence_feedback_or_decision']
        dimensions=card['evaluation_dimensions']
        assert dimensions and any(d['core'] for d in dimensions)
        assert all(d['id'].startswith(identifier+'_') and d['question'] for d in dimensions)
        assert len({d['id'] for d in dimensions})==len(dimensions)


def test_source_bindings_resolve_to_scoped_institutional_guidance():
    rules=purpose_rules();sources={s['id']:s for s in rules['sources']}
    for card in rules['profiles']:
        assert card['rule_kind']=='source_informed_product_guidance'
        assert card['source_bindings']
        for binding in card['source_bindings']:
            source=sources[binding['source_id']]
            assert binding['locator'] and source['locators'] and source['access_scope']
            assert source['url'].startswith('https://')
            assert source['url'] in card['sources']
    assert '索引' in sources['S04']['access_scope']


def test_scoring_policy_keeps_hard_checks_independent():
    policy=purpose_rules()['scoring_policy']
    assert (policy['minimum'],policy['maximum'],policy['core_minimum'])==(0,4,3)
    assert policy['hard_checks_independent'] is True
    assert policy['kind']=='product_policy_confirmed_by_user'


@pytest.mark.parametrize('identifier',sorted(PURPOSE_IDS))
def test_context_uses_actual_purpose_card_independently_of_theme(identifier):
    selected=None
    for theme in catalog()['templates']:
        card,visual=context_parts(generation_context(theme['id'],identifier))
        assert card==purpose_rule(identifier)
        assert visual['id']==theme['id']
        assert visual['replaceable'] is True
        if selected is None:selected=card
        assert card==selected
    uploaded,_=context_parts(generation_context('uploaded',identifier))
    assert uploaded==selected


def test_scope_exceptions_do_not_require_fabricated_results_or_a_unified_thesis():
    assert '无结果' in ' '.join(purpose_rule('group')['exceptions'])
    assert '全部结果' in ' '.join(purpose_rule('proposal')['exceptions'])
    assert '独立章节' in ' '.join(purpose_rule('defense')['exceptions'])
    assert '临床' in ' '.join(purpose_rule('literature')['exceptions'])
    assert '论文的统一问题' not in purpose_rule('defense')['structure']


def test_uploaded_parsed_18pt_body_and_26pt_title_are_preserved():
    section=layout_sections(plan('uploaded'),manifest())[0]
    assert section['_font']==18
    assert section['_title_font']==26
    assert section['font_resolution']['body']['origin']=='parsed_template'


def test_uploaded_selection_overrides_a_public_looking_filename():
    section=layout_sections(plan('uploaded'),manifest('beamer-default'))[0]
    assert section['_font']==18 and section['_title_font']==26


def test_private_template_sizes_above_public_maximum_are_preserved():
    section=layout_sections(plan(),manifest(body=30,title=42))[0]
    assert section['_font']==30 and section['_title_font']==42


@pytest.mark.parametrize('template',['beamer-default','beamer-madrid','metropolis'])
def test_public_template_defaults_and_bounds_remain_in_effect(template):
    section=layout_sections(plan(template),manifest(template,body=24,title=32))[0]
    assert section['_font']==24 and section['_title_font']==32
    section=layout_sections(plan(template),manifest(template,body=18,title=26))[0]
    assert section['_font']==20 and section['_title_font']==28


def test_unresolved_uploaded_fonts_have_explicit_product_fallbacks():
    inspected=manifest(body=None,title=None)
    section=layout_sections(plan('uploaded'),inspected)[0]
    assert section['_font']==24 and section['_title_font']==32
    assert all(v['origin']=='product_fallback' for v in section['font_resolution'].values())
    context=generation_context('uploaded','group',inspected)
    _,visual=context_parts(context)
    assert visual['pages'][0]['fonts']==section['font_resolution']
    assert 'product_fallback' in context and '正文20–24pt' not in context
    assert 'layout' not in visual


def test_context_reads_the_uploaded_template_sizes():
    _,visual=context_parts(generation_context('uploaded','defense',manifest()))
    assert visual['pages'][0]['fonts']['body']=={'font_pt':18.0,'origin':'parsed_template'}
    assert visual['pages'][0]['fonts']['title']['font_pt']==26


def test_layout_preserves_source_plan_and_marks_only_the_derived_sections():
    original=plan('uploaded');before=deepcopy(original)
    sections=layout_sections(original,manifest())
    assert original==before
    assert sections[0]['font_resolution']['body']['font_pt']==18


def test_unknown_purpose_and_visual_are_rejected_independently():
    with pytest.raises(ValueError,match='用途'):purpose_rule('unknown')
    with pytest.raises(ValueError,match='用途'):generation_context('metropolis','unknown')
    with pytest.raises(ValueError,match='模板'):generation_context('unknown','group')
