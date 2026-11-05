"""Source-checked selection of the Chen paper's consequential argument."""
from pathlib import Path
from copy import deepcopy
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/Chen2025论文内容解析'
sys.path.insert(0, 'D:/Development/research-workbench')
from server.paper_map_core import normalize_map, source_sentences

source = json.loads((OUT / 'run-details/source.json').read_text(encoding='utf8'))
units = {u['id']: u for u in source['units']}
review_locators = {'u00117': (12, '原段跨10–12页'), 'u00127': (15, '原段跨14–15页')}
for uid, (page, span) in review_locators.items():
    unit = deepcopy(units[uid])
    unit.update(id=uid + '.review-p' + str(page), page=page, bounds=None,
        section_title=unit['section_title'] + '（所选句第' + str(page) + '页；' + span + '）',
        original_unit_id=uid, locator_scope='selected source sentences, checked against original PDF')
    unit['locations'] = [v for v in unit.get('locations', []) if v['page'] == page]
    source['units'].append(unit)
    units[unit['id']] = unit


def quote(uid, phrase):
    if uid in review_locators:
        uid += '.review-p' + str(review_locators[uid][0])
    text = next(s['text'] for s in source_sentences(units[uid]) if phrase in s['text'])
    return {'source_id': uid, 'quote': text}


nodes = []


def node(ident, parent, role, label, content, quotes, section):
    nodes.append({'id': ident, 'parent_id': parent, 'kind': 'paper' if ident == 'paper' else 'analysis',
        'section_type': section, 'label': label, 'content': content, 'keywords': [label],
        'source_ids': list(dict.fromkeys(q['source_id'] for q in quotes)), 'source_quotes': quotes,
        'argument_role': role, 'key_point': ident != 'paper', 'order': len(nodes)})


node('paper', None, 'question', '水压下钙溶出如何改变氯传输与结合',
    '作者要解释的是水压服役条件下钙溶出与氯传输的耦合作用，尤其是氯结合为什么随深度改变。引言先建立孔结构、氯结合和多离子化学三层相互影响，再把问题收窄到环境代表性与模型反应描述两项不足。主图是解析后依据原文复核的精选论证，完整自动结果另存。',
    [quote('u00010', 'experiments and numerical simulations')], 'introduction')
node('chen.gap_env', 'paper', 'gap', '化学加速溶出试验难以代表水压下的服役过程',
    '这项不足决定为什么不能仅沿用已有加速溶出试验。作者关心桥梁、隧道等水压环境中的共同作用，因此设置真实水压驱动的盐水渗流—溶出试验，并与无压接触条件对照。这里的代表性是相对于原评述中的化学加速方式，并不表示10% NaCl试验完整复现了海水服役环境。',
    [quote('u00009', 'first limitation'), quote('u00009', 'widely employed chemical')], 'introduction')
node('chen.gap_curve', 'paper', 'gap', '水压改变传输与反应的时间关系，经验平衡曲线适用性存疑',
    '作者用水压下的时间尺度变化质疑现有钙固液平衡曲线。因此后文转向显式矿相反应、氯化学结合与表面络合的反应传输描述。此处忠实保留作者提出的理由；它并不预先证明后文已消除全部局部平衡假设。',
    [quote('u00009', 'second limitation'), quote('u00009', 'However, under hydraulic pressure')], 'introduction')
node('chen.choice_env', 'chen.gap_env', 'approach', '比较0与0.3 MPa下72天的氯浓度、pH及固相和孔隙变化',
    '72天的无压盐水接触与0.3 MPa盐水渗流形成环境对照。氯浓度用于观察传输与结合响应，pH追踪酸碱环境，XRD/TG与SEM-EDS追踪水化相变化，MIP追踪传输通道。多种测试分别对应引言中的作用路径，不能只列成测试技术清单。试验使用10% NaCl，溶液每6天更新。',
    [quote('u00017', '72 d saltwater'), quote('u00017', '0.3 MPa'), quote('u00017', 'subsequent tests')], 'methods')
node('chen.choice_model', 'chen.gap_curve', 'approach', '耦合多离子传输与矿相反应，更新氯结合及孔隙率',
    'COMSOL处理Darcy渗流、Nernst–Planck多离子传输和电中性；PHREEQC处理矿物溶出、氯化学/物理结合及表面络合。两模块交换离子浓度与孔隙率。它把引言中的多离子、固相与传输通道联系落实为计算过程；反应模块仍采用每步热力学平衡。',
    [quote('u00110', 'two modules'), quote('u00111', 'Nernst-Planck'), quote('u00111', 'law of mass action'), quote('u00112', 'COMSOL')], 'methods')
node('chen.answer_env', 'chen.choice_env', 'evidence', '水压试件氯浓度升高，近表层氯结合降低且沿深度变化',
    'Fig.4给出有压/无压自由氯和结合氯差异；Fig.5给出相应pH分布；Fig.6—10从固相、孔结构和Ca/Si比补充钙溶出及微环境变化的证据。因此试验不仅证明“水压会加快侵入”，也形成需要模型解释的空间差异。不能把实验中相对结合氯浓度的局部增加直接替换成对所有机制的独立因果验证。',
    [quote('u00027', 'approximately two'), quote('u00027', 'not uniform across'), quote('u00027', 'markedly decreases'), quote('u00029', 'presents an initial increase')], 'results')
node('chen.answer_model', 'chen.choice_model', 'finding', '模型预测钙离子和氢氧根富集可使氯结合在局部增强',
    '参数分析先看多离子分布，再看水化相，再看孔隙率，最后回到自由氯及结合氯。近表层溶出使pH降低、结合减弱；较深处Ca²⁺和OH⁻富集被用于解释Friedel盐形成和C-S-H吸附增强。这是模型支持的机理解释。Fig.12的直接验证主要针对氯浓度，并未逐项直接验证全部离子富集与反应路径。',
    [quote('u00127', 'fleeting increase'), quote('u00127', 'aligns closely'), quote('u00127', 'Therefore, one may infer'), quote('u00130', 'transient rise')], 'results')
node('chen.limit_env', 'chen.answer_env', 'scope', '模型对照主要验证氯浓度，长期多离子机制仍需另行检验',
    '作者在4.5节用72天自由氯/总氯剖面对照本试验，并比较另外两组文献氯浓度数据。由此不能直接把一年孔隙率、离子富集和所有矿相演化都报告为实验已验证。这个边界是本次解析依据验证范围作出的判断，原文结论没有专门列出这条后续验证任务。',
    [quote('u00114', '72 d'), quote('u00114', 'free and total chloride'), quote('u00114', 'absence of experimental data')], 'discussion')
node('chen.limit_model', 'chen.answer_model', 'scope', '反应仍视为每步瞬时平衡，水压致孔隙损伤仅作为初值',
    '作者明确保留每步反应时间忽略不计的假设，且将水压引起的孔结构退化作为初值。故对引言“经验固液曲线适用性”的回应应评价为改进了反应组成描述；原文没有与经验曲线/有限速率反应直接比较，不能解释为时间尺度争议已解决。作者在5.1节提及继续考虑水压与溶出共同作用的潜力；结论未针对这些模型假设专门展开局限与展望。',
    [quote('u00112', 'duration of the thermodynamic reactions'), quote('u00117', 'initial value'), quote('u00117', 'further enhancement')], 'discussion')

edges = []


def edge(a, b, relation, explanation):
    ids = list(dict.fromkeys(i for n in nodes if n['id'] in (a, b) for i in n['source_ids']))
    edges.append({'id': 'chen.edge.' + str(len(edges) + 1), 'from': a, 'to': b,
        'relation': relation, 'explanation': explanation, 'source_ids': ids, 'basis': 'inferred', 'show_label': False})


edge('paper', 'chen.gap_env', '目标要求环境对应', '既然问题是水压服役条件下的耦合作用，试验代表性就成为必须回答的不足。')
edge('paper', 'chen.gap_curve', '目标要求化学与传输对应', '既然氯结合和钙溶出相互改变，固定固液曲线能否描述该环境就需要检查。')
edge('chen.gap_env', 'chen.choice_env', '不足决定试验选择', '用有压/无压对照和对应机制的测试，把环境不足转为可观察的差异。')
edge('chen.gap_curve', 'chen.choice_model', '不足决定模型选择', '显式计算多离子和矿相反应，取代单一固液关系，但仍保留局部瞬时平衡。')
edge('chen.choice_env', 'chen.answer_env', '对照产生需解释的空间响应', '同一盐水环境比较压力条件，获得氯、pH与微结构沿深度变化的证据。')
edge('chen.choice_model', 'chen.answer_model', '从中间过程回到氯结合', '离子富集和固相变化用于解释为什么近表层结合降低、内部局部增强。')
edge('chen.answer_env', 'chen.limit_env', '证据回答的范围', '氯剖面的符合支持模型描述该响应，但不自动完成所有机制与长期预测的验证。')
edge('chen.answer_model', 'chen.limit_model', '回查尚未解除的假设', '反应描述得到细化，但保留的平衡假设与损伤初值限定了对引言不足的回应。')

story = {'author_question': nodes[0]['label'],
    'main_claim': '水压加快传输并改变溶出和孔溶液化学；氯结合因此具有空间差异，不能只用统一降低的描述概括。',
    'organization_summary': '服役环境与双向耦合关系→两项有关不足→水压对照与反应传输模型→氯结合的空间差异→验证范围及保留假设。',
    'key_node_ids': [n['id'] for n in nodes[1:]], 'means_ends': [], 'promise_evidence': [],
    'purpose_routes': [
        {'gap_node_id': 'chen.gap_env', 'purpose': '为水压服役条件取得可与模型对照的传输和微环境证据。', 'choice_node_ids': ['chen.choice_env'], 'evidence_node_ids': ['chen.answer_env'], 'limit_node_ids': ['chen.limit_env'], 'source_ids': ['u00009','u00017','u00027','u00114']},
        {'gap_node_id': 'chen.gap_curve', 'purpose': '用多离子与显式矿相反应解释氯结合的空间差异，同时检查回应的边界。', 'choice_node_ids': ['chen.choice_model'], 'evidence_node_ids': ['chen.answer_model'], 'limit_node_ids': ['chen.limit_model'], 'source_ids': ['u00009','u00110','u00111','u00112','u00117','u00127']}],
    'learning_points': [{'text': '先建立相互影响的具体路径，才能说明后文为什么既需要多种试验，也需要化学—传输耦合。', 'node_ids': ['chen.gap_env','chen.gap_curve','chen.choice_env','chen.choice_model'], 'source_ids': ['u00004','u00005','u00006','u00009','u00010']}]
}
graph = normalize_map(source, {'nodes': nodes, 'edges': edges, 'story': story, 'keywords': ['水压','钙溶出','氯结合','多离子传输']})
graph['rule_version'] = 'paper-content-map-20261104.3'
graph['source_units'] = source['units']
graph['review_status'] = 'source_checked_selection_pending_author_feedback'
graph['provenance'] = {'automatic_job_id': '4b9f981e8eea44c08f097d2c3d070afc', 'selection': 'current assistant source-based review', 'scope': 'selected argument; full automatic output retained separately'}
if (OUT / 'reviewed-map-evaluation.json').is_file():
    graph['evaluation'] = json.loads((OUT / 'reviewed-map-evaluation.json').read_text(encoding='utf8'))
(OUT / 'reviewed-key-map.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf8')
base_path = OUT / ('automatic-map.json' if (OUT / 'automatic-map.json').is_file() else 'section-map.json')
if base_path.is_file():
    auto = json.loads(base_path.read_text(encoding='utf8'))
    merged_story = {**auto.get('story', {}), **{k: v for k, v in story.items() if v not in ([], {})}}
    merged_story['learning_points'] = auto.get('story', {}).get('learning_points', []) + story['learning_points']
    reviewed_nodes = [dict(n) for n in graph['nodes']]
    for n in reviewed_nodes:
        if n['id'] != 'paper' and n.get('parent_id') == 'paper':
            n['parent_id'] = 'chen.reviewed_argument'
    review_section = {'id': 'chen.reviewed_argument', 'parent_id': 'paper', 'kind': 'section',
        'label': '核心论证与研究边界（回读）', 'content': '解析后结合原文提炼的主线，非原论文章节。',
        'section_type': 'other', 'source_ids': ['u00009','u00010'], 'source_quotes': [], 'order': -1}
    full = {**auto, 'rule_version': graph['rule_version'], 'nodes': [n for n in auto['nodes'] if n['id'] != 'paper'] + [review_section] + reviewed_nodes, 'edges': auto['edges'] + graph['edges'], 'source_units': source['units'], 'story': merged_story, 'provenance': graph['provenance']}
    full['evaluation'] = graph.get('evaluation', {})
    (OUT / 'reviewed-full-map.json').write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'nodes': len(nodes), 'edges': len(edges), 'quotes': sum(len(n['source_quotes']) for n in graph['nodes']), 'full_base': str(base_path) if base_path.is_file() else None, 'full_automatic_merged': (OUT / 'automatic-map.json').is_file()}, ensure_ascii=False))
