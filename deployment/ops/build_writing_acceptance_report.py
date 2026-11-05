"""Readable evidence and scored issues for the author's single editorial round."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import html
import json
import re
import sys
from stage_writing_agent import SOURCE
sys.path.insert(0,str(SOURCE))
from server.writing_scores import normalize_score
from server.writing_revision import edit_issue_ids,difference,apply_edits

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/真实写作验收'
LABELS=['氯硫','水分扩散']
CLASS={'necessary':'必要修改','potential':'潜在优化','author_decision':'作者判断'}


def read(path):return json.loads(path.read_text(encoding='utf8'))
def shown(value):return json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value or '')
def esc(value):
    escaped=html.escape(shown(value))
    return re.sub(r'\[([^\]]+)\]\((https://[^\s)]+)\)',r'<a href="\2">\1</a>',escaped)


def unchanged_structure(node):
    if isinstance(node,list):return [unchanged_structure(n) for n in node]
    if not isinstance(node,dict):return node
    return {k:('TEXT' if k=='text' and node.get('type')=='text' else unchanged_structure(v)) for k,v in node.items()}


def main():
    sys.stdout.reconfigure(encoding='utf8');all_sections=[];summary=[]
    for label in LABELS:
        folder=OUT/(label+'_实际工作流记录');run=read(folder/'run-summary.json')
        if run['status']!='completed':raise ValueError(label+'任务尚未完成')
        alignment=read(folder/'alignment.json');review=read(folder/'review.json')
        before=normalize_score(alignment['editorial_assessment'],use_baseline=True)
        after=normalize_score(review['after_assessment'])
        for key in ['resolved_issue_ids','remaining_issue_ids','author_notes']:
            if key not in after and key in review:after[key]=review[key]
        (folder/'original-assessment.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf8')
        base=read(folder/'baseline.json');candidate=read(folder/'candidate.json')
        edits=[];rejected=[];notes=[]
        for stage in ['narrow','wide']:
            p=folder/(stage+'-edits.json')
            if p.exists():
                report=read(p)
                for batch in report['reports']:
                    edits.extend(batch['accepted']);rejected.extend(batch['rejected'])
        invariants={'document_structure_and_nontext_objects_unchanged':unchanged_structure(base['content'])==unchanged_structure(candidate['content']),
            'references_unchanged':base.get('references')==candidate.get('references'),
            'title_unchanged':base.get('title')==candidate.get('title')}
        reconstructed,reconstruction=apply_edits(base,edits)
        invariants['all_text_changes_match_accepted_patches']=not reconstruction['rejected'] and reconstructed==candidate
        assert all(invariants.values()),(label,invariants)
        (OUT/(label+'_第一轮逐段对照.html')).write_text(difference(base,candidate,label+' · 第一轮逐段对照'),encoding='utf8')
        selected={i['id'] for i in before.get('issues',[]) if i['classification']=='necessary' and i.get('selected_for_this_round',True)}
        assert all(edit_issue_ids(e) and set(edit_issue_ids(e))<=selected for e in edits)
        applied_ids={issue for e in edits for issue in edit_issue_ids(e)}
        types=Counter(n['type'] for n in base['content']['content'])
        counts=Counter(i['classification'] for i in before.get('issues',[]))
        details={'task':label,'status':'awaiting_author_acceptance','run_id':run['id'],
            'before_score':before['total_score'],'after_score':after['total_score'],
            'issue_counts':dict(counts),'selected_necessary_ids':sorted(selected),
            'applied_fragments':len(edits),'changed_paragraphs':len({e['path'][0] for e in edits}),
            'rejected_proposals':len(rejected),'invariants':invariants,'original_objects':dict(types),
            'reference_count':len(base.get('references',[])),'resolved_issue_ids':after.get('resolved_issue_ids',[]),
            'remaining_issue_ids':after.get('remaining_issue_ids',[])}
        details['projected_scores_excluded_from_original']=any('projected_score' in s for s in before['scores'])
        details['review_claims_without_matching_patch']=sorted(set(after.get('resolved_issue_ids',[]))-applied_ids)
        (folder/'acceptance-checks.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf8');summary.append(details)
        md=['# '+label+' 第一轮评分与修改依据','',
            '本轮为候选稿，等待作者验收。评分是基于具体原文的模型编辑判断，不表示录用概率。只应用选定必要项；潜在优化与作者判断项未自动应用。','',
            '|维度|原稿|候选稿|满分|复评依据|','|---|---:|---:|---:|---|']
        score_html='<table><tr><th>维度</th><th>原稿</th><th>候选</th><th>满分</th><th>复评依据</th></tr>'
        before_by={s['id']:s for s in before['scores']}
        for s in after['scores']:
            old=before_by[s['id']]
            md.append('|'+s['name']+'|'+str(old['score'])+'|'+str(s['score'])+'|'+str(s['max'])+'|'+shown(s['reason']).replace('|','／').replace('\n',' ')+'|')
            score_html+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [s['name'],old['score'],s['score'],s['max'],s['reason']])+'</tr>'
        score_html+='</table>'
        md+=['','原稿总分：'+str(before['total_score'])+' / 100；候选总分：'+str(after['total_score'])+' / 100。','',
            '本轮修改 '+str(len(edits))+' 个文本片段，涉及 '+str(details['changed_paragraphs'])+' 个段落。','']
        issues_html=''
        for kind in CLASS:
            md+=['## '+CLASS[kind],''];issues_html+='<h3>'+CLASS[kind]+'</h3>'
            items=[i for i in before.get('issues',[]) if i['classification']==kind]
            if not items:md+=['未列出。',''];issues_html+='<p>未列出。</p>'
            for item in items:
                related=[e for e in edits if item['id'] in edit_issue_ids(e)]
                status='已应用 '+str(len(related))+' 处' if related else ('本轮选定，实际未应用' if item['id'] in selected else '保留供作者判断')
                md+=['### '+item['id']+' · '+shown(item.get('location'))+' · '+status,'',
                    '**原文**：'+shown(item.get('before')),'','**规则**：'+shown(item.get('rule')),'',
                    '**理由**：'+shown(item.get('reason')),'','**建议**：'+shown(item.get('suggested_after')),'']
                issues_html+='<article><h4>'+esc(item['id'])+' · '+esc(item.get('location'))+' · '+esc(status)+'</h4>'
                for key,title in [('before','原文'),('rule','规则'),('reason','理由'),('suggested_after','建议')]:
                    issues_html+='<p><b>'+title+'：</b>'+esc(item.get(key))+'</p>'
                if related:
                    md+=['关联实际修改：'+', '.join('T'+str(edits.index(e)+1) for e in related)+'。完整对照统一列于下文。','']
                    issues_html+='<p>关联实际修改：'+', '.join('<a href="#'+label+'-T'+str(edits.index(e)+1)+'">T'+str(edits.index(e)+1)+'</a>' for e in related)+'</p>'
                issues_html+='</article>'
        md+=['## 实际修改对照',''];patch_html='<h3>实际修改对照</h3>'
        for number,edit in enumerate(edits,1):
            title='T'+str(number)+' · '+', '.join(edit_issue_ids(edit))+' · 原生节点 '+shown(edit['path'])
            md+=['### '+title,'','**修改前**：'+edit['before'],'','**修改后**：'+edit['after'],'','**理由**：'+shown(edit.get('reason')),'']
            patch_html+='<article id="'+label+'-T'+str(number)+'"><h4>'+esc(title)+'</h4><div class="compare"><p><b>修改前：</b>'+esc(edit['before'])+'</p><p><b>修改后：</b>'+esc(edit['after'])+'</p></div><p>'+esc(edit.get('reason'))+'</p></article>'
        notes.extend(after.get('author_notes',[]))
        md+=['## 复评与剩余问题','',shown(after.get('resolved_issue_ids',[])),'',shown(after.get('remaining_issue_ids',[])),'',shown(notes),'',
            '## 软件核验','', '```json',json.dumps(details,ensure_ascii=False,indent=2),'```','']
        for e in rejected:md+=['未应用建议：'+shown(e),'']
        (OUT/(label+'_第一轮评分与修改依据.md')).write_text('\n'.join(md),encoding='utf8')
        all_sections.append('<section><h2>'+label+' · '+str(before['total_score'])+' → '+str(after['total_score'])+' / 100</h2><p><a href="'+label+'_第一轮逐段对照.html">打开逐段差异</a></p>'+score_html+
            '<p>必要修改 '+str(counts['necessary'])+' 项；潜在优化 '+str(counts['potential'])+' 项；作者判断 '+str(counts['author_decision'])+' 项。实际修改 '+str(len(edits))+' 个文本片段。</p>'+issues_html+patch_html+
            '<h3>复评与剩余问题</h3><pre>'+esc(notes)+'</pre></section>')
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>真实写作工作流 · 第一轮作者验收</title>
<style>body{max-width:1180px;margin:36px auto;padding:0 22px;font:17px/1.75 "Microsoft YaHei",sans-serif;color:#17231f;background:#fff}h1{font-size:30px}h2{margin-top:50px;border-bottom:2px solid #1f513c}h3{margin-top:32px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #a3aca6;text-align:left;padding:10px;vertical-align:top}article{margin:18px 0;padding:16px 20px;border:1px solid #a3aca6}h4{margin:0}pre{white-space:pre-wrap;word-break:break-word}.compare{padding:8px 16px;border-left:4px solid #276347;background:#f1f6f3}a{color:#15528c}</style>
<h1>真实写作工作流 · 第一轮作者验收</h1><p>本轮只做一次规则评分后的局部润色，复评后等待作者意见。分数用于比较具体修改，不表示期刊录用概率。必要修改、潜在优化与作者判断分别列出。</p>
<p><a href="氯硫_五段引言第一轮候选.docx">氯硫五段引言 Word</a>　<a href="水分扩散_第一轮小改候选.docx">水分扩散全文 Word</a>　<a href="水分扩散_原稿.docx">水分扩散原稿</a></p>
<p><a href="工作流工具与来源.md">实际工具与来源</a>　<a href="轮次与评分规则.md">轮次与评分规则</a></p>
<p>研究主题依据目标期刊的实际范围定位；标杆主要用于学习表达。RAG、MCP、skill、模型联网和下载的实际记录另附工具与来源文件。正式编辑器原稿未被本轮候选替换。</p>'''+''.join(all_sections)+'</html>'
    (OUT/'第一轮作者验收.html').write_text(document,encoding='utf8')
    (OUT/'第一轮验收汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
