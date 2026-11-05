"""Reader-facing expression policy and author-scoped editorial selection."""
import re


EXPRESSION_GUIDE='''【关键句表达】
作者要求文字更有力度、更顺、更直接时，首先检查句子是否直接陈述了原有科学意思；不要自行解释为拔高贡献、增加新颖性或扩大结果。
本轮user_request优先于复用的旧意图和编辑意见。作者点名的原句逐项记录为author_expression_targets，保留原话及位置。
即使原句语法成立、段落上下文足以解释其含义，也应回应作者已指出的表达不适；可在原意内改善时，按作者选择的表达项实施，不能仅因不存在事实错误而跳过。
诊断、编辑与复评均逐项交代点名句的处理状态；只有确实需要改变科学意思、缺少必要材料或超出本轮请求时才说明具体原因并留待作者判断。
按首次阅读顺序读完整段落，重点看入口句、承接转折句、段尾判断及摘要收尾。先用一句普通话说清该位置原本要表达的对象、动作或关系，
再把这项科学陈述写进主干。正文保留学科术语与必要限定，长短句依内容安排，不套统一句型。
语法完整不等于表达清楚。主句若只宣布存在某种关系、需要处理某项内容或提供某种支持，而具体科学动作被藏在抽象名词和多层修饰中，
应据当前段落已有信息重组主谓宾，使读者直接读到实际过程、模型计算或求解任务。不能只换近义动词、加程度副词或把句子机械缩短。
以上是结合语境的审读原则，不是短语黑名单：指代清楚且承担真实承接作用的概括、连接词及方法说明应保留。
从原文及邻句能够恢复的信息直接用于表达修订；需要新增事实、确定未知机制或改变结果解释时才列作者问题。
同义局部润色保持原有研究问题、论断强度和时态；不因语言显得有力就补出普遍规律、保证性效果、优先权或已完成的新发现。
摘要末句履行意义收束的职责，说明已建立能力可以支持的科学或工程用途，不自动以未验证、仍需研究一类提醒收尾。
作者要求修正被削弱的表达时，不能只把同一提醒挪到倒数第二句；要判断它是否确实影响结果解释。
先前编辑额外引入的防御性说明不自动视为作者必须保留的科学结论。可据原有能力明确其用途；未验证的扩展不写成已实现成果，也不必单独加入验证提醒。
真正影响结果解释的条件写在相应命题中；其余研究边界在合适位置保留，不能用反复自我削弱替代表达。
诊断及复评都须引用具体句子并说明首次阅读的障碍是否消除；单纯更短、更强的形容词或更多工具调用均不构成表达改善。'''


def selected_issue_ids(assessment,author_request=''):
    """Allow selected corrections and exact author-requested stylistic choices."""
    selected=set()
    for issue in (assessment or {}).get('issues',[]):
        if not issue.get('selected_for_this_round',issue.get('classification')=='necessary'):continue
        kind=issue.get('classification')
        if kind=='necessary':selected.add(issue['id'])
        elif kind=='potential' and issue.get('selection_basis')=='author_request':
            quote=issue.get('author_request_quote','').strip()
            if quote and quote in author_request:selected.add(issue['id'])
    return selected


def key_sentence_windows(sections):
    """Expose paragraph entry/ending positions without assigning language quality."""
    output=[]
    for section in sections:
        for paragraph in section.get('paragraphs',[]):
            value=paragraph.get('context','').strip()
            if not value:continue
            parts=[p.strip() for p in re.split(r'(?<=[。！？!?])\s*|(?<=\.)\s+(?=[A-Z])',value) if p.strip()]
            output.append({'section':section['title'],'paragraph_id':paragraph['id'],
                'opening':parts[0],'ending':parts[-1],
                'instruction':'连同完整段落判断其表达任务；位置本身不说明质量有问题'})
    return output


def expression_feedback_coverage(source,candidate,targets,author_request):
    """Report literal feedback coverage separately from semantic quality."""
    from .writing_revision import text
    before=source['content']['content'];after=candidate['content']['content'];rows=[]
    for target in targets:
        quote=target.get('quote','').strip()
        row={'quote':quote,'location':target.get('location','')}
        if not quote or quote not in author_request:
            row['status']='not_in_current_author_request'
        else:
            matches=[i for i,node in enumerate(before) if quote in text(node)]
            row['source_paragraph_indices']=matches
            if not matches:row['status']='source_not_found'
            else:
                remaining=[i for i in matches if i<len(after) and quote in text(after[i])]
                row['unchanged_paragraph_indices']=remaining
                row['status']='unchanged' if remaining else 'revised'
        row['scope']='仅检查点名文字是否实际改动；语言质量与科学原意另行复评'
        rows.append(row)
    return rows
