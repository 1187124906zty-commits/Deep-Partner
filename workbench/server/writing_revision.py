"""Small text edits to native manuscript nodes, with round-by-round proposals."""
from copy import deepcopy
from difflib import SequenceMatcher,HtmlDiff
import html
import json
import re
from .writing_expression import EXPRESSION_GUIDE


def text(node):
    if node.get('type')=='text':return node.get('text','')
    if node.get('type')=='citation':return '[CITE:'+str(node.get('attrs',{}).get('number','?'))+']'
    if node.get('type') in ('inlineMath','blockMath'):return '[MATH:'+node.get('attrs',{}).get('latex','')+']'
    return ''.join(text(n) for n in node.get('content',[]))


def revision_sections(document):
    """Keep authors, references, equations, figures and tables as native objects."""
    sections=[];current={'title':'稿件前置内容','paragraphs':[]};body=False
    first_heading=next((text(n) for n in document['content']['content'] if n['type']=='heading'),'')
    if not first_heading or re.search(r'参考文献|^references$',first_heading.strip(),re.I):
        body=True;current['title']='Introduction'
    for i,node in enumerate(document['content']['content']):
        if node['type']=='heading':
            title=text(node)
            if re.search(r'参考文献|^references$',title.strip(),re.I):break
            if current['paragraphs']:sections.append(current)
            current={'title':title,'paragraphs':[]};body=True
        elif node['type']=='paragraph' and body:
            fragments=[]
            def walk(value,path):
                if value.get('type')=='text' and value.get('text','').strip():
                    fragments.append({'path':path,'text':value['text']})
                for j,child in enumerate(value.get('content',[])):walk(child,path+[j])
            walk(node,[i])
            if fragments:current['paragraphs'].append({'id':'p'+str(i),'context':text(node),'fragments':fragments})
    if current['paragraphs']:sections.append(current)
    return sections


def at(document,path):
    node=document['content']
    for index in path:node=node['content'][index]
    return node


def protected_numbers(value):
    return re.findall(r'\d+(?:[.,]\d+)*',value)


def edit_issue_ids(edit):
    value=edit.get('issue_ids',edit.get('issue_id',''))
    values=value if isinstance(value,list) else re.split(r'[\s,，;；]+',str(value))
    return list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def protected_values(value,references):
    """Keep scientific numbers and registered reference identities separate."""
    known={str(r.get('number',i+1)) for i,r in enumerate(references)};citations=[]
    def citation(match):
        expanded=[]
        for part in re.split(r'\s*[,，;；]\s*',match[0][1:-1].strip()):
            interval=re.fullmatch(r'(\d+)\s*[-–—]\s*(\d+)',part)
            if interval:
                left,right=map(int,interval.groups())
                if right<left or right-left>=len(known):return match[0]
                expanded.extend(str(n) for n in range(left,right+1))
            else:expanded.append(str(int(part)))
        if not expanded or any(n not in known for n in expanded):return match[0]
        citations.extend(expanded);return ' '
    remaining=re.sub(r'\[\s*\d+(?:\s*(?:[,，;；]|[-–—])\s*\d+)*\s*\]',citation,value)
    return protected_numbers(remaining),citations


def apply_edits(document,edits):
    output=deepcopy(document);accepted=[];rejected=[]
    eligible={tuple(f['path']) for s in revision_sections(document) for p in s['paragraphs'] for f in p['fragments']}
    for edit in edits:
        try:
            key=tuple(edit['path'])
            if key not in eligible:raise ValueError('该节点不是本轮可修改的正文文本')
            node=at(output,edit['path'])
            if node['type']!='text':raise ValueError('只能修改原生文本节点')
            before=edit['before'];after=edit['after']
            if not isinstance(after,str) or not after.strip():raise ValueError('替换文本不能为空')
            if node['text']!=before:raise ValueError('原句已变化，需基于本轮实际版本重新修改')
            if protected_values(before,document.get('references',[]))!=protected_values(after,document.get('references',[])):
                raise ValueError('本轮文字润色改变了数值或引文身份、顺序，需单独说明并处理')
            node['text']=after
            accepted.append({**edit,'change_ratio':1-SequenceMatcher(None,before,after).ratio()})
        except (KeyError,TypeError,IndexError,ValueError) as exc:rejected.append({**edit,'error':str(exc)})
    return output,{'accepted':accepted,'rejected':rejected,'edited_fragments':len(accepted)}


def difference(before,after,title='稿件逐轮修改'):
    left=[text(n) for n in before['content']['content']];right=[text(n) for n in after['content']['content']]
    table=HtmlDiff(wrapcolumn=70).make_table(left,right,fromdesc='本轮修改前',todesc='本轮修改后',context=True,numlines=2)
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{font:16px/1.7 system-ui;color:#15221e;background:#fff;margin:30px}table{border-collapse:collapse;font-size:14px;width:100%}td{vertical-align:top;padding:6px}.diff_add{background:#d9f2df}.diff_sub{background:#f8dddd}.diff_chg{background:#fff1b8}.diff_header{background:#eee}h1{font-size:22px}</style><h1>'+html.escape(title)+'</h1>'+table+'</html>'


INCREMENTAL='''你是本文当前轮次的学术编辑。按用户“全文多次小改、润色，不推翻原稿”的要求，
只对输入的正文文本节点提出小范围替换。先读完整段落及全文提要，保留章节、论点、实验、方法、图表、公式、数值、引文和结果。
当前轮次的编辑重点由user_request与选中问题决定，不按轮次编号预设修改任务；保留已经清楚的句子。
只有输入fragments中的path可以编辑。before必须逐字等于该节点原text；after是同一节点的修订文本；不改数值和引文编号。
不需要修改的节点不输出。发现需要作者判断的内容记入author_notes，正文不添加编辑说明。
需要表达范例时可用MCP的RAG和原文读取，按当前句子的作用借鉴表达。
返回JSON：{"edits":[{"path":[3,0],"before":"原text全文","after":"小改后的text全文","reason":"本次具体改善","issue_ids":["评分中对应的一个或多个必要修改编号"]}],"author_notes":[]}。'''
INCREMENTAL+='\n'+EXPRESSION_GUIDE
