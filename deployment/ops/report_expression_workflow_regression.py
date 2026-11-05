"""Present actual output and contextual checks for author review."""
from pathlib import Path
import copy
import html
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE))
from server.writing_revision import text,apply_edits,edit_issue_ids

OUT=ROOT/'reports/关键句工作流回归'


def load(path):return json.loads(path.read_text(encoding='utf8'))
def esc(value):return html.escape(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2))
def opener(node):return re.split(r'(?<=[。！？!?])\s*',text(node).strip())[0]
def structure(value):
    if isinstance(value,list):return [structure(x) for x in value]
    if isinstance(value,dict):return {k:('TEXT' if k=='text' and value.get('type')=='text' else structure(v)) for k,v in value.items()}
    return value


def main():
    sys.stdout.reconfigure(encoding='utf8');sections=[];summary=[]
    named=OUT/'named-feedback';abstract=OUT/'abstract-feedback'
    assert (named/'status.json').is_file() and (abstract/'status.json').is_file(),'Focused follow-up tests are not complete'
    focused='<section><h2>当前规则下的作者反馈回归</h2><p>这里的候选由实际模型按通用规则生成，输入包含作者指出的原句，没有提供指定改写答案。</p>'
    focused_results=[]
    for folder,title in [(named,'作者点名的三个入口句'),(abstract,'摘要收尾')]:
        status=load(folder/'status.json');assert status['status']=='completed'
        report=load(folder/'applied-edits.json');base=load(folder/'baseline.json');candidate=load(folder/'candidate.json')
        reconstructed,check=apply_edits(base,report['accepted']);assert reconstructed==candidate and not check['rejected']
        focused+='<h3>'+title+'</h3>'
        for edit in report['accepted']:
            if folder==named:
                before=edit['before'].split('。',1)[0]+'。';after=edit['after'].split('。',1)[0]+'。'
                assert edit['before'].split('。',1)[1]==edit['after'].split('。',1)[1]
            else:
                before=edit['before'].split('此外，')[-1];after=edit['after'].split('此外，')[-1]
            focused+='<article><p><b>修改前：</b>'+esc(before)+'</p><p><b>实际输出：</b>'+esc(after)+'</p><p>'+esc(edit.get('reason',''))+'</p></article>'
        focused+='<p><a href="'+folder.name+'/changes.html">查看完整差异与上下文</a></p>'
        focused_results.append(status)
    focused+='</section>'
    for label,name in [('chloride','氯硫引言'),('moisture','水分扩散摘要与未指定段落')]:
        folder=OUT/label;status=load(folder/'status.json');assert status['status']=='completed',status
        base=load(folder/'baseline.json');candidate=load(folder/'candidate.json')
        before=load(folder/'before-assessment.json');after=load(folder/'after-assessment.json')
        report=load(folder/'applied-edits.json');review=load(folder/'review.json')
        rebuilt,check=apply_edits(base,report['accepted'])
        assert rebuilt==candidate and not check['rejected']
        assert structure(base)==structure(candidate)
        changed={e['path'][0] for e in report['accepted']}
        evidence={'case':label,'workflow_version':status['prompt_version'],
            'actual_edits':len(report['accepted']),'edited_paragraph_indices':sorted(changed),
            'rejected_edits':len(report['rejected']),'unselected_edits':len(report.get('not_selected',[])),
            'structure_and_nontext_unchanged':True,'candidate_reconstructed_from_recorded_edits':True,
            'author_approval':'pending','score_scope':'仅本回归输入段落，不能与上一轮全篇分数直接比较',
            'expression_before':next(s['score'] for s in before['scores'] if s['id']=='expression'),
            'expression_after':next(s['score'] for s in after['scores'] if s['id']=='expression')}
        indices=[1,2,3] if label=='chloride' else [3,9,11,13]
        comparisons=[]
        for index in indices:
            a=opener(base['content']['content'][index]);b=opener(candidate['content']['content'][index])
            comparisons.append({'paragraph_index':index,'before_opening':a,'after_opening':b,'changed':a!=b})
        evidence['opening_comparisons']=comparisons
        if label=='moisture':
            evidence['clear_roadmap_kept']=base['content']['content'][11]==candidate['content']['content'][11]
        write=folder/'delivery-checks.json';write.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8');summary.append(evidence)
        score_before=next(s for s in before['scores'] if s['id']=='expression')
        score_after=next(s for s in after['scores'] if s['id']=='expression')
        body='<section><h2>'+name+' · 首次通用回归记录</h2><p>模型原始表达自评分 '+str(score_before['score'])+' → '+str(score_after['score'])+' / 20，仅供回查。作者点名覆盖与实际读感另行检查，不据高分宣布验收通过。</p><p>'+esc(score_after['reason'])+'</p>'
        body+='<h3>关键句实际输出</h3>'
        for row in comparisons:
            body+='<article><h4>原生段落 '+str(row['paragraph_index'])+'</h4><p><b>修改前：</b>'+esc(row['before_opening'])+'</p><p><b>修改后：</b>'+esc(row['after_opening'])+'</p>'
            body+='<details><summary>查看完整段落上下文</summary><p>'+esc(text(base['content']['content'][row['paragraph_index']]))+'</p><p>'+esc(text(candidate['content']['content'][row['paragraph_index']]))+'</p></details></article>'
        if label=='moisture':
            body+='<h3>摘要收尾实际输出</h3><p>'+esc(text(candidate['content']['content'][3]).split('。')[-2]+'。')+'</p>'
        body+='<h3>工作流如何判断</h3>'
        diag=load(folder/'diagnosis.json')
        key_review=before.get('key_sentence_review',diag.get('key_sentence_review',[]))
        for row in key_review:
            body+='<details><summary>'+esc(str(row.get('location',row.get('paragraph_id',''))))+' · '+esc(str(row.get('action','')) )+'</summary><pre>'+esc(row)+'</pre></details>'
        body+='<h3>选中并应用的修改</h3>'
        for edit in report['accepted']:
            body+='<details><summary>'+esc(', '.join(edit_issue_ids(edit)))+' · '+esc(str(edit['path']))+'</summary><p><b>原文：</b>'+esc(edit['before'])+'</p><p><b>候选：</b>'+esc(edit['after'])+'</p><p>'+esc(edit.get('reason',''))+'</p></details>'
        body+='<h3>复评</h3><pre>'+esc(review.get('key_sentence_checks',review.get('after_assessment',{}).get('key_sentence_checks',[])))+'</pre>'
        body+='<p><a href="'+label+'/changes.html">打开完整原文差异</a>　<a href="'+label+'/action-summary.json">实际 MCP 与模型调用记录</a></p></section>'
        sections.append(body)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>关键句表达工作流回归</title><style>
body{max-width:1120px;margin:36px auto;padding:0 24px;color:#17251e;background:white;font:17px/1.8 "Microsoft YaHei",sans-serif}h1{font-size:30px}h2{margin-top:42px;border-bottom:2px solid #37654d}h3{margin-top:28px}article{padding:16px 20px;margin:18px 0;border:1px solid #9ba89f}h4{margin:0}a{color:#15528c}pre{white-space:pre-wrap;word-break:break-word;font:15px/1.7 "Microsoft YaHei",sans-serif}details{margin:12px 0;padding:12px 16px;background:#f2f6f3}summary{cursor:pointer;font-weight:600}</style>
<h1>关键句表达工作流回归</h1><p>本次改进针对关键位置的表达直接性、主干清楚程度与阅读顺畅度，沿用原有科学意思。未通过拔高贡献、增添发现或重设主线来增强语气。</p>
<p>新流程依次执行：复述原句的科学意思与读者障碍 → 选择必要项及作者已指定的同义表达项 → 依据完整段落重组句子 → 对照原文复评意思是否保留、阅读障碍是否消除。新增表达语料与判据通过实际 MCP 读取。</p>
<p>首次通用回归还保留了作者不满意的一个入口句，并把摘要的验证提醒移到了倒数第二句。虽然模型自评分很高，这两个结果没有被作为满足作者要求的依据。随后增加作者点名逐项覆盖检查，并明确不能通过移动提醒的位置完成摘要修订。</p>
<p>初次回归版本为1111-20261103.4；点名反馈补测采用.5；摘要补测采用.6。当前代码整合了这些改进。原正式稿与上一轮 Word 未覆盖。</p>'''+focused+''.join(sections)+'''<p>相关软件测试37项通过，只支持流程与选择规则的程序结论。本轮实际样本不能保证所有学科、段落均达到作者要求；具体表达仍由作者阅读验收。</p></html>'''
    (OUT/'关键句工作流回归.html').write_text(page,encoding='utf8')
    (OUT/'结果汇总.json').write_text(json.dumps({'general_regression':summary,'focused_feedback':focused_results},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'general_regression':summary,'focused_feedback':focused_results},ensure_ascii=False))


if __name__=='__main__':main()
