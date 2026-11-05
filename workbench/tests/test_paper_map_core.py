from copy import deepcopy
import json
import os

import pytest

from server import paper_map_core as core


TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>
<fileDesc><titleStmt><title>Transport under coupled attack</title></titleStmt></fileDesc>
<profileDesc><abstract><p coords="1,10,20,300,20">The original first abstract sentence, including its precise condition.</p>
<p coords="1,10,42,300,20">The entire final abstract sentence must remain here.</p></abstract></profileDesc>
</teiHeader><text><body>
<div type="introduction"><head coords="1,10,100,200,12">1 Introduction</head>
<p xml:id="original-p1" coords="1,10,120,300,50">Connected pores control transport. Prior work assumes a fixed topology.</p>
<p coords="1,10,175,300,50;2,10,20,300,15">The topology evolves during attack. This motivates a coupled model.</p></div>
<div type="methods"><head coords="2,10,50,200,12">2 Model</head>
<div><head coords="2,10,70,200,12">2.1 Geometry</head><p coords="2,10,90,300,40">The specimen contains a connected pore network.</p>
<div><head coords="2,10,135,200,12">2.1.1 Boundary conditions</head><p coords="2,10,150,300,40">A prescribed concentration is used at the exposed surface.</p></div></div></div>
<div type="results"><head coords="3,10,20,200,12">3 Comparison</head><p coords="3,10,40,300,40">The coupled model reduces error relative to the fixed topology baseline.</p>
<figure><head>Figure 1</head><figDesc coords="3,10,100,300,30">Figure 1. Error at equal elapsed time.</figDesc></figure></div>
<div type="discussion"><head coords="3,10,140,200,12">4 Interpretation</head><p coords="3,10,160,300,40">The comparison supports the role of connectivity within the tested range.</p></div>
<div type="conclusion"><head coords="3,10,210,200,12">5 Conclusions</head><list><item coords="3,10,230,300,40">Coupling is useful within the tested range.</item></list></div>
</body><back><div type="references"><head>References</head><listBibl><biblStruct><analytic><title>Not body prose</title></analytic></biblStruct></listBibl></div></back></text></TEI>"""


def package():
    return core.parse_tei(TEI, "reading/paper.pdf", {"doi": "10.0000/example"},
                          signature={"bytes": 10, "modified_ns": 20})


def node(ident, parent, kind, section_type, ids, **extra):
    return {"id": ident, "parent_id": parent, "kind": kind, "section_type": section_type,
            "label": "连通孔隙对传输的作用", "content": "在原文给定条件下，连接性影响传输。",
            "keywords": ["孔隙连接性", "传输"], "source_ids": ids, **extra}


def full_output(source):
    nodes = [node("paper", None, "paper", "other", [])]
    paragraphs = []
    for section in source["sections"]:
        role = section["role"] or "methods"
        ident = "sec." + section["id"]
        parent = "sec." + section["parent_id"] if section["parent_id"] else "paper"
        ids = section["unit_ids"]
        nodes.append(node(ident, parent, "section", role, ids, source_section_id=section["id"]))
        for unit in source["units"]:
            if unit["section_id"] != section["id"] or unit["kind"] not in {"paragraph", "list_item"}:
                continue
            kind = {"results": "comparison", "discussion": "discussion", "conclusion": "conclusion"}.get(role, "paragraph")
            item_id = "para." + unit["id"]
            nodes.append(node(item_id, ident, kind, role, [unit["id"]]))
            if role == "introduction":
                nodes.append(node("element." + unit["id"], item_id, "element", role, [unit["id"]]))
                paragraphs.append((item_id, unit["id"]))
    edges = [{"id": "transition", "from": paragraphs[0][0], "to": paragraphs[1][0],
              "relation": "提出限制", "explanation": "前段固定拓扑的假设被后段演化现象限定，进而引出耦合需求。",
              "source_ids": [p[1] for p in paragraphs], "basis": "inferred"}]
    evidence_nodes = [n["id"] for n in nodes if n["kind"] != "section" and n["section_type"] in {"methods", "results", "conclusion"}]
    evidence_sources = list(dict.fromkeys(u for n in nodes if n["id"] in evidence_nodes for u in n["source_ids"]))
    originals = {u['id']: u['text'] for u in source['units']}
    for item in nodes:
        if item['kind'] not in {'paper','section'}:
            item['source_quotes'] = [{'source_id': ident, 'quote': originals[ident]} for ident in item['source_ids']]
    return {"keywords": ["反应传输", "连通性"], "nodes": nodes, "edges": edges,
            "story": {"author_question": "拓扑演化怎样影响传输？", "main_claim": "所测范围内需要考虑连接性演化。",
                      "organization_summary": "固定拓扑限制引出耦合方法，再通过相同时间条件下的比较限定结论。",
                      "means_ends": [{"means": "耦合模型", "end": "考察演化", "explanation": "通过耦合处理演化。",
                                      "node_ids": [paragraphs[0][0]], "source_ids": [paragraphs[0][1]]}],
                      "promise_evidence": [{"question": "演化影响", "method": "耦合模型", "evidence": "基线比较",
                                            "conclusion": "在所测范围内有用", "node_ids": [paragraphs[0][0], *evidence_nodes],
                                            "source_ids": [paragraphs[0][1], *evidence_sources], "status": "supported"}],
                      "learning_points": [{"text": "用前人的具体假设解释为何需要处理演化。", "node_ids": [paragraphs[0][0]],
                                           "source_ids": [paragraphs[0][1]]}]}}


def write_pdf(path, text="Abstract\nFull original abstract sentence.\n"):
    fitz = pytest.importorskip("fitz")
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
        page.insert_text((72, 160), "1 Introduction")
        page.insert_text((72, 190), "The source body concerns transport through pores.")
        page.insert_text((72, 260), "Figure 1. This is a caption, not a paragraph.")
        pdf.save(path)


def test_tei_keeps_full_abstract_real_nested_paragraphs_and_locators():
    source = package()
    assert source["abstract"]["text"] == (
        "The original first abstract sentence, including its precise condition. "
        "The entire final abstract sentence must remain here.")
    assert source["abstract"]["complete"] is True
    sections = {s["title"]: s for s in source["sections"]}
    assert sections["2.1.1 Boundary conditions"]["parent_id"] == sections["2.1 Geometry"]["id"]
    assert sections["2.1 Geometry"]["parent_id"] == sections["2 Model"]["id"]
    first = next(u for u in source["units"] if u.get("original_id") == "original-p1")
    assert first["text"].endswith("fixed topology.")
    assert first["page"] == 1 and first["bounds"]["unit"] == "pt"
    split = next(u for u in source["units"] if u["text"].startswith("The topology"))
    assert len(split["locations"]) == 2
    assert {p["page"] for p in split["locations"]} == {1, 2}
    assert not any("Not body prose" in u["text"] for u in source["units"])
    assert next(u for u in source["units"] if "Figure 1." in u["text"])["kind"] == "caption"


def test_missing_tei_coordinates_are_null_not_invented_pages():
    source = core.parse_tei('<TEI><text><body><div><head>Essay</head><p>A real paragraph.</p></div></body></text></TEI>', "essay.pdf")
    assert all(u["page"] is None and u["bounds"] is None for u in source["units"])
    assert source["abstract"]["status"] == "missing"
    assert source["sections"][0]["title"] == "Essay"


def test_minified_structured_abstract_keeps_labels_all_sentences_and_spacing():
    xml = '<TEI><teiHeader><profileDesc><abstract><div><head>Background</head><p>One sentence.</p></div><div><head>Results</head><p>Another sentence with <ref>one</ref> inline reference.</p></div></abstract></profileDesc></teiHeader><text><body><p>First real paragraph.</p><p>Second real paragraph.</p></body></text></TEI>'
    source = core.parse_tei(xml, "article.pdf")
    assert source["abstract"]["text"] == "Background One sentence. Results Another sentence with one inline reference."
    abstract_units = [u for u in source["units"] if u["id"] in source["abstract"]["source_ids"]]
    assert len(abstract_units) == 4
    body_units = [u for u in source["units"] if u["section_id"] != "s-abstract"]
    assert len(body_units) == 2
    assert body_units[0]["section_id"] == body_units[1]["section_id"]


def test_model_cannot_replace_or_shorten_original_abstract_and_coverage():
    source = package()
    output = full_output(source)
    output.update(abstract={"text": "A model rewrite"}, coverage={"status": "ready", "total_units": 1})
    result = core.normalize_map(source, output)
    assert result["abstract"] == source["abstract"]
    assert result["source_units"] == source["units"]
    assert result["coverage"]["total_units"] == len(source["units"])
    assert result["coverage"]["status"] == "ready"
    assert result["coverage"]["scientific_validation"] == "not_performed"
    assert result["nodes"][-1]["depth"] > 0


def test_navigation_section_can_use_its_real_title_without_a_model_abstract_rewrite():
    source=package();output=full_output(source)
    abstract=next(n for n in output['nodes'] if n.get('source_section_id')=='s-abstract' and n['kind']=='section')
    abstract['content']=''
    result=core.normalize_map(source,output)
    assert next(n for n in result['nodes'] if n['id']==abstract['id'])['content']=='Abstract'
    assert result['abstract']==source['abstract']


def test_clicked_node_quotes_are_exact_source_text_and_paraphrases_are_not_displayed():
    source = package(); output = full_output(source)
    original = next(u for u in source['units'] if u.get('original_id') == 'original-p1')
    target = next(n for n in output['nodes'] if n['kind'] == 'element' and n['source_ids'] == [original['id']])
    target['source_quotes'] = [
        {'source_id': original['id'], 'quote': 'Connected pores\n control transport.'},
        {'source_id': original['id'], 'quote': 'Connected pores always accelerate transport.'},
    ]
    result = core.normalize_map(source, output)
    actual = next(n for n in result['nodes'] if n['id'] == target['id'])
    assert [q['quote'] for q in actual['source_quotes']] == ['Connected pores control transport.']
    assert actual['source_quotes'][0]['start_char'] == 0
    assert any('未与原文逐字匹配' in r for r in result['coverage']['needs_review'])


def test_quote_from_another_paragraph_cannot_be_presented_as_node_source_sentence():
    source = package(); output = full_output(source)
    target = next(n for n in output['nodes'] if n['kind'] == 'element')
    other = next(u for u in source['units'] if u['id'] not in target['source_ids'])
    target['source_quotes'] = [{'source_id': other['id'], 'quote': other['text']}]
    with pytest.raises(ValueError, match='未绑定本节点'):
        core.normalize_map(source, output)


def test_source_sentence_selection_preserves_scientific_abbreviations_and_chinese_text():
    text='Sarkar et al. [20] described diffusion. Fig. 2 shows expansion. 温度改变扩散率。钙溶出改变孔隙。'
    sentences=core.source_sentences({'id':'u1','text':text})
    assert [s['text'] for s in sentences]==['Sarkar et al. [20] described diffusion.','Fig. 2 shows expansion.','温度改变扩散率。','钙溶出改变孔隙。']
    assert ' '.join(s['text'] for s in sentences).replace('。 ','。')==text


def test_model_selects_original_sentences_by_id_without_rewriting_them():
    source=package();output=full_output(source)
    target=next(n for n in output['nodes'] if n['kind']=='element')
    original=next(u for u in source['units'] if u['id']==target['source_ids'][0])
    selected=core.source_sentences(original)[1]
    target.pop('source_quotes');target['sentence_ids']=[selected['id']]
    result=core.normalize_map(source,output)
    actual=next(n for n in result['nodes'] if n['id']==target['id'])
    assert actual['source_quotes'][0]['quote']=='Prior work assumes a fixed topology.'
    _,payload=core.build_prompt(source)
    packet=json.loads(payload);unit=next(u for u in packet['units'] if u['id']==original['id'])
    assert 'text' not in unit and ' '.join(s['text'] for s in unit['sentences'])==original['text']
    target['sentence_ids']=['invented-sentence']
    with pytest.raises(ValueError,match='原句'):
        core.normalize_map(source,output)


def test_content_score_uses_the_saved_rule_maxima_and_does_not_invent_visual_or_author_acceptance():
    source=package();graph=core.normalize_map(source,full_output(source))
    criteria=core.map_rules()['scoring']['items'][:7]
    review={'items':[{'id':item['id'],'score':item['max']-1,'reason':'The cited fixed-topology paragraph establishes the comparison baseline.','node_ids':[graph['nodes'][0]['id']],'edge_ids':[]} for item in criteria], 'issues':[], 'summary':'Actual content review fixture.'}
    result=core.normalize_review(graph,review)
    assert result['content_score']==58 and result['content_max']==65
    assert result['visual_score'] is None and result['interaction_score'] is None
    assert result['author_acceptance']=='pending'
    review['items'][0]['score']=13
    with pytest.raises(ValueError,match='范围'):core.normalize_review(graph,review)
    review['items'][0]['score']=10;review['items'][0]['node_ids']=['invented-node']
    with pytest.raises(ValueError,match='不存在'):core.normalize_review(graph,review)


def test_argument_roles_and_optional_relation_labels_survive_source_validation():
    source=package();output=full_output(source)
    output['nodes'][0]['argument_role']='question'
    output['edges'][0]['show_label']=False
    result=core.normalize_map(source,output)
    assert result['nodes'][0]['argument_role']=='question'
    assert result['edges'][0]['show_label'] is False
    assert result['edges'][0]['relation'] and result['edges'][0]['explanation']


def test_gap_nodes_need_a_purpose_choice_and_evidence_link_instead_of_an_isolated_deficiency_list():
    source=package();output=full_output(source)
    target=next(n for n in output['nodes'] if n['kind']=='element')
    target['argument_role']='gap'
    result=core.normalize_map(source,output)
    assert any('细节罗列' in reason for reason in result['coverage']['needs_review'])
    output['story']['purpose_routes']=[{'gap_node_id':target['id'],'purpose':'Identify whether changing pore topology changes transport predictions.',
                                      'choice_node_ids':[next(n['id'] for n in output['nodes'] if n['section_type']=='methods')],
                                      'evidence_node_ids':[next(n['id'] for n in output['nodes'] if n['section_type']=='results')],
                                      'source_ids':target['source_ids']}]
    result=core.normalize_map(source,output)
    assert not any('细节罗列' in reason for reason in result['coverage']['needs_review'])


@pytest.mark.parametrize("target", ["node", "edge", "story_source", "story_node", "endpoint", "section"])
def test_fabricated_source_or_graph_references_are_rejected(target):
    source = package()
    output = full_output(source)
    if target == "node":
        output["nodes"][1]["source_ids"] = ["invented-source"]
    elif target == "edge":
        output["edges"][0]["source_ids"].append("invented-source")
    elif target == "story_source":
        output["story"]["learning_points"][0]["source_ids"] = ["invented-source"]
    elif target == "story_node":
        output["story"]["means_ends"][0]["node_ids"] = ["invented-node"]
    elif target == "endpoint":
        output["edges"][0]["to"] = "invented-node"
    else:
        output["nodes"][1]["source_section_id"] = "invented-section"
    with pytest.raises(ValueError):
        core.normalize_map(source, output)


def test_real_introduction_granularity_and_adjacent_content_links_are_checked():
    source = package()
    output = full_output(source)
    output["edges"] = []
    output["nodes"] = [n for n in output["nodes"] if n["kind"] != "element"]
    result = core.normalize_map(source, output)
    assert result["coverage"]["status"] == "needs_review"
    assert any("段内内容要素" in r for r in result["coverage"]["needs_review"])
    assert any("承接关系" in r for r in result["coverage"]["needs_review"])
    assert result["coverage"]["introduction_relations"][0]["covered"] is False


def test_cyclic_or_dangling_parent_relationship_is_rejected():
    source = package()
    output = full_output(source)
    output["nodes"][1]["parent_id"] = output["nodes"][2]["id"]
    with pytest.raises(ValueError, match="循环"):
        core.normalize_map(source, output)
    output = full_output(source)
    output["nodes"][-1]["parent_id"] = "unknown"
    with pytest.raises(ValueError, match="parent_id"):
        core.normalize_map(source, output)


def test_pdf_fallback_keeps_locations_and_does_not_claim_real_paragraphs(tmp_path, monkeypatch):
    path = tmp_path / "literature/reading/paper.pdf"
    write_pdf(path)
    monkeypatch.setattr(core, "_fetch_tei", lambda path: (_ for _ in ()).throw(ValueError("GROBID unavailable")))
    source = core.extract_source(tmp_path, "reading/paper.pdf", {"title": "Local source"})
    assert source["coverage"]["paragraph_boundary_status"] == "needs_review"
    assert source["coverage"]["extraction_complete"] is False
    assert source["abstract"]["complete"] is False
    assert source["abstract"]["text"] == "Full original abstract sentence."
    assert not any(u["kind"] == "paragraph" for u in source["units"])
    assert all(u["page"] == 1 and u["bounds"] for u in source["units"])
    caption = next(u for u in source["units"] if u["text"].startswith("Figure"))
    assert caption["kind"] == "caption"
    assert source["source"]["signature"] == core.source_signature(path)


def test_current_source_cache_is_reused_and_same_size_replacement_invalidates_it(tmp_path, monkeypatch):
    path = tmp_path / "literature/paper.pdf"
    write_pdf(path)
    calls = []
    def fetch(path):
        calls.append(path)
        return TEI
    monkeypatch.setattr(core, "_fetch_tei", fetch)
    first = core.extract_source(tmp_path, "paper.pdf", {})
    assert core.extract_source(tmp_path, "paper.pdf", {}) == first
    assert len(calls) == 1
    stat = path.stat()
    # Same bytes, different modification nanoseconds is a different source
    # version; no whole-PDF content hash is needed to invalidate the cache.
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000))
    third = core.extract_source(tmp_path, "paper.pdf", {})
    assert len(calls) == 2
    assert third["source"]["signature"] != first["source"]["signature"]


def test_existing_flat_writing_cache_is_not_misrepresented_as_full_structure(tmp_path, monkeypatch):
    path = tmp_path / "literature/paper.pdf"
    write_pdf(path)
    cache = tmp_path / ".workbench/writing/structure-cache/paper.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"signature": {"source": "literature/paper.pdf", **core.source_signature(path)},
        "result": {"engine": "GROBID", "headings": ["Introduction"], "paragraphs": [{"text": "Flattened"}]}}), encoding="utf8")
    monkeypatch.setattr(core, "_fetch_tei", lambda path: (_ for _ in ()).throw(ValueError("unavailable")))
    result = core.extract_source(tmp_path, "paper.pdf", {})
    assert result["source"]["parser"].startswith("PyMuPDF")
    assert result["abstract"]["complete"] is False
    assert not any(u["text"] == "Flattened" for u in result["units"])


def test_existing_version_matched_raw_tei_cache_can_be_reused(tmp_path, monkeypatch):
    path = tmp_path / "literature/paper.pdf"
    write_pdf(path)
    cache = tmp_path / ".workbench/writing/structure-cache/paper.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"signature": {"source": "literature/paper.pdf", **core.source_signature(path)},
                                "result": {"tei_xml": TEI}}), encoding="utf8")
    monkeypatch.setattr(core, "_fetch_tei", lambda path: pytest.fail("should reuse original TEI"))
    result = core.extract_source(tmp_path, "paper.pdf", {})
    assert result["source"]["parser"] == "GROBID TEI"
    assert result["abstract"]["complete"] is True


def test_current_reader_layout_is_reused_with_source_revision_and_size(tmp_path, monkeypatch):
    path = tmp_path / "literature/paper.pdf"
    write_pdf(path)
    signature = core.source_signature(path)
    document_id = "a" * 32
    reader = tmp_path / ".workbench/neoread"
    (reader / "papers").mkdir(parents=True)
    (reader / "papers" / (document_id + ".pdf")).write_bytes(path.read_bytes())
    mapping = tmp_path / ".workbench/neoread-map.json"
    mapping.write_text(json.dumps({"literature:workspace/paper.pdf": {"document_id": document_id,
                       "revision": str(signature["modified_ns"])}}), encoding="utf8")
    analysis = reader / "cache" / document_id / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "manifest.json").write_text(json.dumps({"pages": 1, "blocks": [
        {"id": "p1-b1", "page": 1, "label": "paragraph_title", "text": "Abstract", "bounds": {"x": .1, "y": .1, "width": .8, "height": .1}},
        {"id": "p1-b2", "page": 1, "label": "text", "text": "The complete candidate as preserved by the reader.", "bounds": {"x": .1, "y": .2, "width": .8, "height": .1}},
        {"id": "p1-b3", "page": 1, "label": "paragraph_title", "text": "Introduction", "bounds": {"x": .1, "y": .3, "width": .8, "height": .1}},
        {"id": "p1-b4", "page": 1, "label": "text", "text": "Reader preserved body.", "bounds": {"x": .1, "y": .4, "width": .8, "height": .1}}]}), encoding="utf8")
    monkeypatch.setattr(core, "_fetch_tei", lambda path: (_ for _ in ()).throw(ValueError("unavailable")))
    monkeypatch.setattr(core, "_pdf_layout", lambda path: pytest.fail("must reuse current layout"))
    result = core.extract_source(tmp_path, "paper.pdf", {})
    assert result["source"]["parser"].startswith("NeoRead")
    assert result["abstract"]["text"] == "The complete candidate as preserved by the reader."
    assert result["abstract"]["complete"] is False
    assert any(u["text"] == "Reader preserved body." for u in result["units"])


def test_stale_reader_revision_is_not_accepted(tmp_path):
    mapping = tmp_path / ".workbench/neoread-map.json"
    mapping.parent.mkdir(parents=True)
    mapping.write_text(json.dumps({"literature:workspace/paper.pdf": {"document_id": "a" * 32, "revision": "10"}}), encoding="utf8")
    assert core._reader_layout(tmp_path, "paper.pdf", "workspace", {"bytes": 20, "modified_ns": 11}) is None


def test_exact_section_batch_has_full_outline_context_and_no_unselected_prose():
    source = package()
    section = next(s for s in source["sections"] if s["title"] == "2.1 Geometry")
    prompt, raw = core.build_prompt(source, {"section_ids": [section["id"]], "unit_ids": section["unit_ids"]})
    payload = json.loads(raw)
    assert [s["id"] for s in payload["sections"]] == [section["id"]]
    assert {u["id"] for u in payload["units"]} == set(section["unit_ids"])
    assert len(payload["section_outline"]) == len(source["sections"])
    assert payload["abstract"] == source["abstract"]
    assert "只输出本批nodes/edges" in prompt
    assert "The coupled model reduces error" not in raw
    assert "不得改写摘要" in prompt
    with pytest.raises(ValueError):
        core.build_prompt(source, {"section_ids": [section["id"]], "unit_ids": [source["units"][0]["id"]]})


def test_synthesis_prompt_requests_only_story_and_cross_section_edges():
    source = package()
    output = full_output(source)
    prompt, raw = core.build_prompt(source, {"mode": "synthesis", "nodes": output["nodes"]})
    assert "只返回story和跨章节edges" in prompt
    assert json.loads(raw)["completed_nodes"] == output["nodes"]


def test_partial_evidence_is_not_upgraded_to_a_complete_promise():
    source = package()
    output = full_output(source)
    output["story"]["promise_evidence"][0]["evidence"] = ""
    result = core.normalize_map(source, output)
    assert result["story"]["promise_evidence"][0]["status"] == "partial"
    assert result["coverage"]["status"] == "needs_review"
    assert output["story"]["promise_evidence"][0]["status"] == "supported"


def test_omitted_sections_stay_visible_as_missing_coverage():
    source = package()
    output = full_output(source)
    section = next(s for s in source["sections"] if s["title"] == "2.1.1 Boundary conditions")
    remove = {n["id"] for n in output["nodes"] if n.get("source_section_id") == section["id"] or n["parent_id"] == "sec." + section["id"]}
    output["nodes"] = [n for n in output["nodes"] if n["id"] not in remove]
    output["story"]["promise_evidence"][0]["node_ids"] = [ident for ident in output["story"]["promise_evidence"][0]["node_ids"] if ident not in remove]
    result = core.normalize_map(source, output)
    assert section["id"] in result["coverage"]["missing_section_ids"]
    assert result["coverage"]["status"] == "needs_review"


def test_question_reference_alone_does_not_prove_a_complete_evidence_chain():
    source = package()
    output = full_output(source)
    promise = output["story"]["promise_evidence"][0]
    promise["node_ids"] = [n["id"] for n in output["nodes"] if n["kind"] == "paragraph" and n["section_type"] == "introduction"][:1]
    result = core.normalize_map(source, output)
    assert result["story"]["promise_evidence"][0]["status"] == "partial"
    assert any("兑现缺少" in item for item in result["coverage"]["needs_review"])
