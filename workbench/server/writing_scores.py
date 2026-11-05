"""One scored editorial round; the author decides whether another round begins."""
from copy import deepcopy

RUBRIC=[
    {'id':'precision','name':'对象、术语与指代准确性','max':30},
    {'id':'logic','name':'主次、信息顺序与句段联系','max':25},
    {'id':'expression','name':'信息直接性、句法节奏与学术表达','max':20},
    {'id':'journal_fit','name':'研究主题与目标期刊的适配表达','max':15},
    {'id':'consistency','name':'符号、引文及图文表述一致性','max':10},
]


def normalize_score(value,*,use_baseline=False,baseline_assessment=None):
    """Compute totals from explicit rubric subscores, retaining reasons and locations."""
    result=deepcopy(value);scores=result.get('scores',[]);by_id={v['id']:v for v in scores};total=0
    for criterion in RUBRIC:
        row=by_id.get(criterion['id'])
        if row is None:raise ValueError('评分缺少维度：'+criterion['id'])
        if use_baseline and 'baseline_score' in row:
            row.setdefault('projected_score',row['score'])
            row['score']=row['baseline_score']
            row['score_basis']='原稿；模型另给的候选预估分未作为已实现分数'
        score=row.get('score')
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not 0<=score<=criterion['max']:
            raise ValueError('评分超出维度范围：'+criterion['id'])
        if not row.get('reason'):
            reasons=[(str(item.get('location',''))+'：'+item['reason']).lstrip('：')
                     for item in row.get('locations',[]) if isinstance(item,dict) and item.get('reason')]
            if reasons:row['reason']='；'.join(reasons)
        if not row.get('reason'):raise ValueError('评分需要给出依据：'+criterion['id'])
        row['max']=criterion['max'];row['name']=criterion['name'];total+=score
    result['total_score']=total;result['max_score']=100
    if use_baseline:result['score_basis']='original_manuscript'
    previous={item['id']:item for item in (baseline_assessment or {}).get('issues',[])}
    for item in result.get('issues',[]):
        if not item.get('classification') and item.get('id') in previous:
            item['classification']=previous[item['id']].get('classification')
        if item.get('classification') not in ('necessary','potential','author_decision'):
            raise ValueError('修改项需要区分必要修改、潜在优化或作者判断')
    result['author_approval']='pending';return result


ALIGNMENT_NOTE='''本轮采用评分驱动的单轮编辑，结束后等待作者验收与新意见，不自动开始下一轮。
请保留原角色的主题对齐工作，并增加editorial_assessment。评分维度及满分由payload的rubric给出，总分100。
每个维度必须有具体原文位置、扣分理由和实际例句，不能用运行成功、篇幅、工具调用次数或引用数量代替写作质量。
当前尚未实施编辑，score只能给原稿评分。不得把预计修改后分数放入score；如另列预估，使用独立字段且不纳入原稿总分。
issues分为：necessary（违反明确写作规则且可据现有材料修正）、potential（可能更好但原文无明确错误）、
author_decision（尚未由作者确定的科学主张、结构取舍、数值、结果解释或材料不足）。作者已指定的章节重组属于当前执行范围，不能仅因改变段数再交作者重复选择。
necessary列出最不合适的原句、确切问题、引用的规则、建议的小改和issue_id；不为凑数制造问题。
语法虽成立，但首次阅读仍需读者补出主干判断、具体动作或关系的表达问题，也应按实际障碍判断，不能一律当作无需处理的偏好。
对关键位置按expression维度记录key_sentence_review：location、role、before、scientific_statement（原本要说的意思）、reader_obstacle、action（keep|revise|author_decision）、issue_id。
先从当前user_request恢复作者点名的原句，列出author_expression_targets；每句都须有诊断与本轮处理状态，不能被旧意图、语法无误或一般保留原则遗漏。
先看整个段落，保留已经清楚的句子；不能因为位于段首就必须改，或只看单句便增补科学判断。
在必要修改中标出selected_for_this_round，优先处理本轮最影响阅读和准确性的局部问题；不把全文检查变成全文改写。
potential通常保留；作者已明确要求的同义表达改进可以本轮选中，selection_basis设author_request，author_request_quote逐字引自本轮user_request。
这类选择不必改标成事实错误。author_decision始终不自动执行；表达改进不等于变更研究目的、数值、结果解释或科学承诺。
返回原L2字段外，增加editorial_assessment:{"scores":[{"id":"precision","score":25,"reason":"具体依据","locations":[]}],
"issues":[{"id":"E01","classification":"necessary|potential|author_decision","location":"原文位置",
"before":"原句","rule":"适用规则","reason":"为什么需要或可能改","suggested_after":"小改建议","selected_for_this_round":true,
"selection_basis":"necessary|author_request","author_request_quote":"仅作者已指定表达改进时填写原话"}],"key_sentence_review":[]}。
'''
ALIGNMENT_NOTE+='\n引言重组还需诊断群体综合和段间论证：检查实际命题是否由对应来源群支持，本段判断是否产生下一段要解决的对象。logic和journal_fit的扣分要引用当前正文，不把具体软件名、作者名数量或参考文献总数当质量代理。'

EDIT_NOTE='''本轮只实施payload.selected_issue_ids已选择的局部修订，标明对应issue_id。
一个节点涉及多个必要项时，使用issue_ids数组列出各编号。
选中项包括必要修订及作者本轮已明确要求的同义表达改进；未选potential及全部author_decision留给作者判断。
先把原句在当前段落中的科学意思说清，再改句子；保留原稿组织、研究内容和已经清楚的句子。
这是一轮候选稿，完成后提交作者验收；不自动进入第二轮润色。'''

REVIEW_NOTE='''本阶段对本轮候选稿复评，结束后交作者验收，不再次重写正文。
按payload的rubric给出after_assessment，与before_assessment逐项对照并说明已处理、未处理或新增发现的具体事项。
评分必须基于原文与本轮候选的实际差异，不自动加分。潜在优化和作者问题保留为建议，不能直接改稿。
逐项核实当前文本与原稿的实际差异；L2中的修订预估分不是本阶段已实现分数，未实际改变的必要项不能列作已解决。
复核key_sentence_review对应的实际句子：是否直接说出原有科学意思、主干和指代是否顺畅、是否只换了空泛近义词，以及是否靠夸大或削弱科学判断获得语气变化。
增加key_sentence_checks，逐项给出before、after、reader_obstacle_resolved、meaning_preserved、reason。发现未解决项继续记录，不再次改写。
另给author_feedback_coverage，逐项对应作者点名原句、实际改后文字和处理状态；遗漏不能被总分或其他改进抵消。
本阶段不重复输出完整正文；final_text返回空字符串，执行器会从原生候选文件填入全文。正文由候选文件保留，不得改写。
all_assertions_passed置false，author_approval为pending。
增加after_assessment，结构与before_assessment一致；issues逐项保留原classification，另给status说明处理结果。另列resolved_issue_ids、remaining_issue_ids和author_notes。'''
REVIEW_NOTE+='\n引言任务增加literature_synthesis_checks：逐段记录actual_group_claim、supporting_sources、synthesis_instead_of_catalogue、ending_judgment、next_opening_connection、research_question_alignment及具体理由。核对最新作者沙漏顺序，单独报告实际引用覆盖与证据深度；覆盖达标不能抵消正文仍在逐篇列举或段间失联。'
REVIEW_NOTE+='\n先做introduction_architecture_check：从实际正文逆向概括各段功能及整体推进，检查意义段是否被技术现状挤占、难点是否围绕同一预测任务逐步展开、方法名是否机械决定分段、缺口是否重复前段判断、本文工作是否写成实施清单。logic评分需给这一级结构的原句依据；不能仅因逐段有未解问题和过渡就认定全篇紧凑。按段落功能检查，意义段与本文工作段不要求额外抛出新缺口。'
