"""Identify layout tables that contain a displayed equation and its number."""
import re


def is_equation_table(node):
    if node.get('type')!='table' or len(node.get('content',[]))!=1:return False
    cells=node['content'][0].get('content',[])
    if len(cells) not in (2,3):return False
    math=[];words=[]
    def collect(n):
        if n.get('type') in ('inlineMath','blockMath'):math.append(n);return
        if n.get('text'):words.append(n['text'])
        for c in n.get('content',[]):collect(c)
    collect(node)
    return bool(math) and bool(re.fullmatch(r'\s*[（(]\s*\d+[a-z]?\s*[)）]\s*',''.join(words)))


def mark_tables(node):
    if is_equation_table(node):node['attrs']={**node.get('attrs',{}),'equation':True}
    for child in node.get('content',[]):mark_tables(child)
