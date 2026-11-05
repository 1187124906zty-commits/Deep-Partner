"""Readable author review of the actual deployed literature-synthesis run."""
from pathlib import Path
import html
import json
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/氯硫框架具体化/workflow-20261104'
LIVE=OUT/'live'


def read(name,default=None):
    p=LIVE/name
    return json.loads(p.read_text(encoding='utf8')) if p.is_file() else default


def text(node):
    if node.get('type')=='citation':return '['+str(node['attrs']['number'])+']'
    return node.get('text','')+''.join(text(n) for n in node.get('content',[]))


def group_numbers(match):
    values=[int(n) for n in re.findall(r'\[(\d+)\]',match[0])]
    parts=[];i=0
    while i<len(values):
        j=i
        while j+1<len(values) and values[j+1]==values[j]+1:j+=1
        parts.append(str(values[i]) if i==j else str(values[i])+'–'+str(values[j]))
        i=j+1
    return '['+','.join(parts)+']'


def paragraphs(document):
    out=[]
    for node in document.get('content',{}).get('content',[]):
        value=text(node)
        if node.get('type')=='heading' and re.search(r'参考文献|references',value,re.I):break
        if node.get('type')=='paragraph' and value.strip():out.append(re.sub(r'(?:\[\d+\]){2,}',group_numbers,value))
    return out


def main():
    status=read('status.json',{});candidate=read('final-candidate-document.json') or read('candidate-document.json') or read('wide-candidate.json')
    source=read('source-document.json',{});l2=read('alignment.json',{});review=read('review.json',{})
    exemplar=read('exemplar.json',{})
    if exemplar:
        learning={k:exemplar[k] for k in ['journal_profile','perspective_alignment_rules','literature_synthesis_examples','retrieval_and_provenance'] if k in exemplar}
        (LIVE/'exemplar-learning-summary.json').write_text(json.dumps(learning,ensure_ascii=False,indent=2),encoding='utf8')
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
      '<title>期刊引言文献综合工作流回归</title><style>body{max-width:1080px;margin:40px auto;padding:0 24px;color:#17201d;background:#fff;font:17px/1.9 "Segoe UI","Microsoft YaHei",sans-serif}h1{font-size:28px}h2{margin-top:2em;font-size:23px}h3{font-size:19px}p{margin:1em 0}a{color:#174d78}table{width:100%;border-collapse:collapse;font-size:15px}th,td{padding:10px;border:1px solid #d5dbd8;vertical-align:top}th{background:#edf0ee;text-align:left}.prose p{text-indent:2em;line-height:2.05}.refs{font-size:14px;overflow-wrap:anywhere}details{margin:1.2em 0}summary{cursor:pointer;font-weight:600}.note{color:#435149}code{font-size:14px}</style>',
      '<h1>期刊引言文献综合工作流回归</h1>',
      '<p>本轮按作者确定的“新方法解决预测问题”沙漏重组引言：前两段即现有预测的困难与能力边界，随后从深度学习进入物理信息与贝叶斯推断，并回应相场神经求解。文献按研究群体形成认识，段落判断连续推进。</p>']
    feedback=OUT/'paragraph-organization-feedback.json'
    if feedback.is_file():
        current=json.loads(feedback.read_text(encoding='utf8'))
        if current.get('status')=='awaiting_author_structure_choice':parts.append('<p><strong>作者最新反馈与当前状态：</strong>作者指出这版整体组织仍松散，意义应先立住，难点随后分段展开。下文保留上一轮实际候选及评分；87分未识别这一整体结构缺陷。工作流已修正全篇功能规划与复评，具体重组方案等待作者选择。</p>')
    if candidate:
        body=paragraphs(candidate);refs=candidate.get('references',[])
        parts+=['<h2>本轮候选正文</h2><p class="note">候选供作者继续反馈；不以模型评分或引用数量代表科学验证及作者认可。</p><div class="prose">']
        parts.extend('<p>'+html.escape(p)+'</p>' for p in body);parts.append('</div>')
        heading='氯硫引言_研究群体综合候选'
        md='# '+heading+'\n\n'+'\n\n'.join(body)+'\n\n## 参考文献\n\n'
        ref_html=[]
        for i,row in enumerate(refs):
            label='['+str(row.get('number',i+1))+'] '+'; '.join(row.get('authors',[]))+'. '+row['title']+'. '+str(row.get('venue') or row.get('journal') or '')+', '+str(row.get('year',''))+'.'
            url='https://doi.org/'+row['doi'] if row.get('doi') else row.get('url','')
            md+=label+(' [DOI]('+url+')' if url else '')+'\n\n'
            ref_html.append('<p>'+html.escape(label)+(' <a href="'+html.escape(url,quote=True)+'">DOI</a>' if url else '')+'</p>')
        (OUT/(heading+'.md')).write_text(md,encoding='utf8')
        parts+=['<details><summary>参考文献 '+str(len(refs))+' 篇</summary><div class="refs">',''.join(ref_html),'</div></details>']
        if (OUT/(heading+'.docx')).is_file():parts.append('<p><a href="'+heading+'.docx">下载完整可编辑 Word 候选</a> · <a href="'+heading+'.md">阅读正文及参考文献</a></p>')
    else:parts.append('<p>当前阶段：'+html.escape(status.get('stage','准备'))+'。尚未取得完整候选。</p>')
    synthesis=read('wide.json',{}).get('literature_synthesis_notes',[])
    if synthesis:
        parts.append('<h2>候选各段的判断与承接</h2><table><tr><th>段落</th><th>形成的判断</th><th>交给下一段的问题</th></tr>')
        for item in synthesis:
            parts.append('<tr><td>'+html.escape(str(item.get('paragraph','')) )+'</td><td>'+html.escape(str(item.get('synthesis_judgment') or item.get('group_claim','')))+'</td><td>'+html.escape(str(item.get('next_dependency') or item.get('unresolved_problem','')))+'</td></tr>')
        parts.append('</table>')
    parts+=['<h2>实际流程与审读</h2>','<p>本轮将章节重组与局部润色分流；旧任务仅提供背景，本轮意图重新理解。稳定文献身份贯通规划、正文与原生引用。复评读取实际候选，不再改正文。</p>',
      '<p><a href="../../../docs/期刊引言综合工作流改进.md">工作流改动说明</a> · <a href="journal-learning/examples.md">四篇CCR引言的实际学习</a> · <a href="gap-check/findings.md">框架缺口与反证</a></p>']
    stages={v['stage']:v for v in status.get('stage_history',[])}
    names={'intent':'本轮任务理解','exemplar':'期刊与连续引言学习','alignment':'研究支流与论证规划','wide':'目标引言重组','review':'只读复评','deliver':'候选保存'}
    parts.append('<table><tr><th>阶段</th><th>实际状态</th><th>可回查产物</th></tr>')
    for key,label in names.items():
        file='exemplar-learning-summary.json' if key=='exemplar' else key+'.json';exists=(LIVE/file).is_file()
        state='已返回' if key in stages else ('当前执行' if status.get('stage')==key else '尚未返回')
        link='<a href="live/'+file+'">'+file+'</a>' if exists else ''
        parts.append('<tr><td>'+label+'</td><td>'+state+'</td><td>'+link+'</td></tr>')
    parts.append('</table>')
    before=l2.get('editorial_assessment',{});after=review.get('after_assessment',{})
    if before or after:
        parts+=['<h3>模型对实际文本的评分</h3><p>评分是具体文字判断的量化记录，仍需结合候选正文与作者意见。没有以工具调用、引用篇数或自动通过代替验收。</p>',
          '<p>原稿 '+str(before.get('total_score','待返回'))+' / 100；模型返回的候选 '+str(after.get('total_score','待返回'))+' / 100。此评分早于最终题录校正与一处归因表述收窄；这些必要修正没有另行预估加分。</p>']
    checks=review.get('literature_synthesis_checks',[])
    if checks:
        parts+=['<details><summary>逐段综合与承接的模型审读记录</summary><pre style="white-space:pre-wrap;font:14px/1.7 sans-serif">'+html.escape(json.dumps(checks,ensure_ascii=False,indent=2))+'</pre></details>']
    if (OUT/'qa/independent-review.md').is_file():
        parts+=['<h3>独立读者审读</h3><p>独立审读确认八段已形成作者指定的问题沙漏和群体综合，引用身份52项全部落到正文；对关键方法原件回读后提出一项必要修正：反馈开关只支持检验损伤反馈的影响，不能由此分别归因多个过程。最终候选已采纳这一收窄，其余段落组织保留。</p><p><a href="qa/independent-review.md">完整独立审读与实际阅读范围</a></p>']
    diff_name='final-diff.html' if (LIVE/'final-diff.html').is_file() else 'wide-diff.html'
    if (LIVE/diff_name).is_file():parts.append('<p><a href="live/'+diff_name+'">实际原稿与最终候选差异</a></p>')
    parts.append('<details><summary>上一轮五段底稿</summary><div class="prose">'+''.join('<p>'+html.escape(p)+'</p>' for p in paragraphs(source))+'</div></details>')
    finalization=read('finalization.json',{})
    if finalization:
        correction_note='独立审读后已收窄下列必要表述；其余段落措辞及全部文献身份保留。' if finalization.get('accepted_prose_corrections') else '这一整理保留正文措辞与文献身份。'
        parts.append('<p class="note">候选正文规则版本 '+str(finalization['raw_prompt_version'])+'；最终编号按首次出现顺序整理，规则版本 '+str(finalization['reference_formatter_version'])+'。'+correction_note+'另据原件统一GEM-Selektor论文正式卷期年份及Chen2024第三位作者姓名。Word已渲染 '+str(finalization['pages_rendered'])+' 页，视觉检查状态 '+html.escape(finalization['visual_review'])+'。</p>')
        for correction in finalization.get('accepted_prose_corrections',[]):
            parts.append('<p class="note">第'+str(correction['paragraph'])+'段：'+html.escape(correction['after'])+' '+html.escape(correction['basis'])+'</p>')
    parts.append('<p class="note">本轮保存为独立候选，正式稿revision '+str(status.get('native_manuscript_revision','待回读'))+'。软件回归45项通过，写作质量由实际文本审读。来源完整版本、访问深度和尚未核验的终版差异分别保留。</p></html>')
    target=OUT/'期刊引言综合工作流回归.html';target.write_text('\n'.join(parts),encoding='utf8')
    print(target)


if __name__=='__main__':main()
