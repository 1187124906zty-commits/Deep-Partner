"""Source-bound section reorganisation and journal-facing literature synthesis."""
from copy import deepcopy
import re
import uuid


SYNTHESIS_GUIDE = '''【期刊引言与文献综合】
先确定本文是用新方法解决哪一个领域问题，以及目标期刊读者需要获得什么认识。引言以这一问题收窄，技术能力解释为什么现在能够回答它。
先规划全篇引言的功能层次，再规划段落：领域意义说明问题值得解决的具体后果，难点展开结合已有认识说明预测为何仍困难，研究回应说明本文怎样推进。按作者确认的组织分配这些功能，不能把方法递进表或研究支流清单直接变成一类方法一段。
意义段要建立研究对象、科学或工程后果及需要获得的预测能力；复杂相态机制、软件、算法定义和详细局限放到随后难点展开中。难点可用数段逐步展开，同一个难点也可在一段内比较多类方法；每段增加的认识由当前预测困难决定。
写作范例提供论述和表达经验；领域文献提供科学证据。连读范例的完整引言和相邻段落，记录作者怎样把已有认识推向未解问题，而不从单篇范例复制研究路线。
多篇领域文献先按共同研究对象、已经建立的认识及其适用条件形成研究支流。分类服务当前论证，同一支流内的机制、尺度或假设差异需要解释，不能只按方法名堆成几个篮子。
正文以材料过程、预测任务或一类方法的已知能力为主语，综合叙述该支流建立了什么、哪些条件改变判断、由此还有哪个问题未解决，随后在对应命题后挂引多篇来源。
作者名可在辨认特定原始方法、真正不同的结果或必要优先权时使用；普通现状由群体认识推进。删去作者名、把多篇题名连在一起，或将列举改成“已有研究”，均不等于完成综合。
历史演进解释认识怎样改变：前一阶段能预测什么，后续研究为何引入新的物理关系或求解方式，新增能力留下什么具体困难。年代顺序只在这种变化有作用时参与组织。
每段按其功能发展一个与本文相关的判断。展开难点与现状的段落由证据形成后果，明确下一段接续的对象或能力；意义段收束到核心预测目标，本文工作段回应前述困难，不强迫这两类段落再造文献缺口。问题可用陈述句提出，不要求问号、固定“然而”或段段重复同一结尾句型。
方法论文可在前段同时介绍已有模型的物理优势和预测不足，再逐步进入数据学习、物理约束及适合当前任务的具体推断/求解方法。按作者已选沙漏链安排，不把化学、损伤、算法拆成彼此独立的说明书。
研究立场来自有证据的比较与后果：肯定前人解决的对象，指出仍未闭合的科学关系、适用范围或计算能力。结尾先综合各支流共同留下的具体问题，再说明本文的核心变化及领域价值。
“研究不多”“缺少统一框架”和“首次”各需相应检索或直接比较；检索未命中不能代替不存在的证据。组成方法已有而整合能力仍待建立时，说明尚需同时实现和检验的能力。
引言具体到读者理解科学理由所需的层次；求解器名称、接口、训练参数和验证清单按论证需要保留，其余进入方法。面向材料期刊时，计算设计持续落回材料响应、结构—性质关系或可检验预测。
复评先逆向概括实际各段功能及整篇推进，判断意义是否先立住、难点是否逐步收窄、方法是否回应困难、研究回应是否重复前文或展开成实施清单。即使相邻段都有转折和回指，若整篇仍按学科或技术模块平行铺陈，也不能判为组织紧凑。段数与作者名数量不代替这一判断。
研究回应与拟开展比较相互对应：一次整体反馈开关可检验该反馈通路的影响，不能据此承诺分别归因多个相互耦合过程的相对贡献。检验支持多强的判断，正文就写到多强。
作者给定50—60篇等引用范围时，先为论断分配独立来源，再按来源的支撑范围组织挂引；保留原始身份和访问深度。篇数是覆盖要求，不是质量分数，不以连续大段引用代替分析。
复评读实际候选的段首、证据、判断、段尾及下一段入口，并核对正文命题与引用群是否相符。仅工具调用、更多引文、无作者名或模型高分均不构成论证已经改善的证据。'''


def editorial_scope(value=None, *, fallback='full_draft'):
    value = deepcopy(value or {})
    mode = value.get('mode', fallback)
    if mode not in ('local_edit', 'section_restructure', 'full_draft'):
        raise ValueError('编辑范围需要区分局部润色、指定章节重组或初稿')
    sections = value.get('sections', [])
    if not isinstance(sections, list) or any(not isinstance(s, str) or not s.strip() for s in sections):
        raise ValueError('编辑范围的章节需要名称列表')
    if mode == 'section_restructure' and not sections:
        raise ValueError('章节重组需要指定目标章节')
    return {**value, 'mode': mode, 'sections': sections}


def reference_manifest(document, library=None, supplied=None):
    """Keep registered identities while making the current project's sources available."""
    rows = []
    by_identity = {}
    used_ids = set()
    for source in [document.get('references', []), supplied or [], list((library or {}).values())]:
        for row in source:
            identity = (row.get('doi') or row.get('arxiv') or row.get('id') or '').strip().lower()
            if not identity or not row.get('title'):
                continue
            if identity in by_identity:
                existing = by_identity[identity]
                for key, value in row.items():
                    if value and not existing.get(key):
                        existing[key] = deepcopy(value)
                continue
            item = deepcopy(row)
            ident = item.get('id') or 'ref-writing-' + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex[:16]
            if ident in used_ids:
                ident = 'ref-writing-' + uuid.uuid5(uuid.NAMESPACE_URL, identity).hex[:16]
            item['id'] = ident
            if not item.get('venue') and item.get('journal'):
                item['venue'] = item['journal']
            rows.append(item)
            by_identity[identity] = item
            used_ids.add(ident)
    return rows


def reference_policy(value=None):
    policy = deepcopy(value or {})
    for key in ('min_unique', 'max_unique'):
        if key in policy and (isinstance(policy[key], bool) or not isinstance(policy[key], int) or policy[key] < 0):
            raise ValueError('引用范围需要非负整数')
    if policy.get('max_unique', 1000) < policy.get('min_unique', 0):
        raise ValueError('引用范围上下限不一致')
    return policy


def manifest_for_model(rows):
    keys = ('id', 'title', 'authors', 'year', 'venue', 'doi', 'arxiv', 'source_path',
            'attachment', 'access_scope', 'evidence_excerpt', 'evidence_locations', 'read_version')
    return [{key: row[key] for key in keys if row.get(key)} for row in rows]


def _section_key(value):
    value = re.sub(r'^\s*\d+(?:\.\d+)*[.、\s]*', '', value).strip().casefold()
    return {'引言': 'introduction', '绪论': 'introduction', '参考文献': 'references'}.get(value, value)


def _section_bounds(document, title):
    from .writing_revision import text
    blocks = document['content']['content']
    target = _section_key(title)
    headings = [(i, n, _section_key(text(n))) for i, n in enumerate(blocks) if n.get('type') == 'heading']
    match = next(((i, n) for i, n, key in headings if key == target), None)
    if match:
        i, node = match
        level = node.get('attrs', {}).get('level', 1)
        end = next((j for j, n, _ in headings if j > i and n.get('attrs', {}).get('level', 1) <= level), len(blocks))
        return i + 1, end
    if target == 'introduction' and (not headings or headings[0][2] == 'references'):
        return 0, headings[0][0] if headings else len(blocks)
    raise ValueError('原稿没有目标章节：' + title)


def _inline_text(value, entries):
    output = []
    cited = []
    last = 0
    for match in re.finditer(r'\[REF:([\w-]+)\]', value):
        ident = match[1]
        if ident not in entries:
            raise ValueError('候选引用未在当前来源清单中登记：' + ident)
        if match.start() > last:
            output.append({'type': 'text', 'text': value[last:match.start()]})
        output.append({'type': 'citation', 'attrs': {'refId': ident, 'number': entries[ident]['number']}})
        cited.append(ident)
        last = match.end()
    if last < len(value):
        output.append({'type': 'text', 'text': value[last:]})
    return output, cited


def apply_section_restructure(document, sections, allowed_sections, manifest, policy=None):
    """Replace explicitly selected prose sections, retaining other native objects."""
    from .references import prepare
    from .writing_revision import text
    if not sections:
        raise ValueError('章节重组没有返回实际正文')
    output = deepcopy(document)
    known = reference_manifest(document, supplied=manifest)
    for i, row in enumerate(known):
        row['number'] = i + 1
    entries = {row['id']: row for row in known}
    allowed = {_section_key(s) for s in allowed_sections}
    replacements = []
    used = []
    seen = set()
    for section in sections:
        title = section.get('title') or section.get('id') or ''
        key = _section_key(title)
        if key not in allowed or key in seen:
            raise ValueError('章节重组超出本轮范围或重复返回章节：' + title)
        seen.add(key)
        start, end = _section_bounds(document, title)
        # This operation owns prose reorganisation; formulas/tables/images retain their existing path.
        def prose(node):
            return node.get('type') in ('paragraph', 'text', 'citation', 'hardBreak') and all(prose(n) for n in node.get('content', []))
        if any(not prose(node) for node in document['content']['content'][start:end]):
            raise ValueError('目标节含公式、图表或子标题，请保留这些原生对象并另行指定可重组正文范围')
        nodes = []
        for paragraph in section.get('paragraphs', []):
            value = paragraph if isinstance(paragraph, str) else paragraph.get('text', '')
            if not isinstance(value, str) or not value.strip():
                raise ValueError('章节重组段落不能为空')
            inline, ids = _inline_text(value, entries)
            nodes.append({'type': 'paragraph', 'content': inline})
            used.extend(ids)
        if not nodes:
            raise ValueError('章节重组必须包含正文段落')
        replacements.append((start, end, nodes, title))
    unique = list(dict.fromkeys(used))
    policy = reference_policy(policy)
    if len(unique) < policy.get('min_unique', 0) or len(unique) > policy.get('max_unique', 1000):
        raise ValueError(f"候选实际引用{len(unique)}篇，未达到本轮来源覆盖范围；需要补足对应命题证据后继续")
    for start, end, nodes, _ in sorted(replacements, reverse=True):
        output['content']['content'][start:end] = nodes
    body = output['content']['content']
    bibliography = next((i for i, node in enumerate(body) if node.get('type') == 'heading' and _section_key(text(node)) in ('references', 'bibliography')), len(body))
    # Rebuild the bibliography from identities cited anywhere in the retained manuscript body.
    all_used = []
    def walk(node):
        if node.get('type') == 'citation':
            all_used.append(node['attrs']['refId'])
        for child in node.get('content', []):
            walk(child)
    for node in body[:bibliography]:
        walk(node)
    order = list(dict.fromkeys(all_used))
    output['references'] = [entries[ident] for ident in order]
    output = prepare(output)
    return output, {'sections': [v[3] for v in replacements], 'paragraphs': sum(len(v[2]) for v in replacements),
                    'unique_cited': len(unique), 'cited_reference_ids': unique,
                    'reference_policy': policy, 'source_identity_bound': True,
                    'quality_scope': '身份和覆盖范围已核对；群体综合、论断支撑及段间逻辑由实际正文审读'}


RESTRUCTURE_NOTE = '''本轮为作者已指定的章节重组，保留科学主线、事实和结果，允许目标节内合段、拆段、重排及重新组织引用。
只写editorial_scope.sections中的章节，其他章节保持原生内容；author_round控制本轮评分与作者验收，不限制为原段数或逐字小改。
按L2的研究支流与论证链写连续正文。每段的未解对象由下一段接续；不将规划表、分类标签或编辑说明写入正文。
引用使用source_manifest中稳定id，格式[REF:ref-id]，可连续组合；不自造身份、不自行编数字编号、不在正文列出作者题录。
reference_policy给出本轮独立来源覆盖范围；每项挂引都支持所在命题，访问深度不足的强主张需先读取来源。
只返回JSON：{"sections":[{"id":"Introduction","title":"Introduction","paragraphs":["实际连续正文，内含[REF:来源id]"]}],
"literature_synthesis_notes":[{"paragraph":1,"group_claim":"实际群体认识","source_ids":[],"synthesis_judgment":"本段判断","unresolved_problem":"余下问题","next_dependency":"下一段怎样接续"}],"author_notes":[]}。'''

STRUCTURE_ASSESSMENT_NOTE = '''本轮采用作者指定的章节重组，保留已确定的研究问题和科学承诺，允许改变目标节内的段数、次序及引用分配。
返回editorial_assessment，按payload.rubric对原稿评分，各项给原文位置、实际例句与理由，不给尚未写出的候选预估分。
使用editorial_assessment.scores数组，每项含id、score、reason和locations；reason总结该维度的具体评分依据，locations保留原文位置、例句和各处理由。
issues区分necessary、potential、author_decision；作者已要求的结构与群体综合属于本轮任务，新的科学主张或证据不足才需另作作者判断。
先形成literature_streams和introduction_argument，再用已有来源把每段的认识、判断与下一段依赖写清；不能用逐篇提要替代论证计划。
关注当前正文如何回答领域预测问题，指出实际的列举、主次失衡或段间失联；不因引用多、作者名少或软件专业而加分。
这是单轮候选规划，之后写作、只读复评并交作者验收，不自动进入下一轮。'''
