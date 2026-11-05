"""Render the actual Chinese manuscript with the author's new writing example."""
from pathlib import Path
from io import BytesIO
from copy import deepcopy
import json,re
import fitz
from docx import Document
from server.app import store
from server.manuscripts import export_manuscript

owner='u_731b4f07a23742f0917ac6eb77df5df4';pid='05a893386c09449d88366cf6dfdc825f'
root=store.path(owner,pid);source=store.manuscript(owner,pid)
out=root/'.workbench/chinese-writing-example';out.mkdir(exist_ok=True)
document={**source,'template':'chinese-mechanics','columns':1}
counts={'math':0,'image':0}
def count(node):
    if node.get('type') in ('inlineMath','blockMath'):counts['math']+=1
    if node.get('type')=='image':counts['image']+=1
    for c in node.get('content',[]):count(c)
count(source['content'])
data,_,_=export_manuscript(root,document,'docx');(out/'chinese.docx').write_bytes(data);word=Document(BytesIO(data))
assert len(word.element.body.xpath('.//m:oMath'))==counts['math']
assert len(word.inline_shapes)==counts['image']
assert not word.element.body.xpath('.//m:mr/m:e[not(.//m:t)]')
assert len(word.tables)==20
for index in [17,18]:
    assert word.tables[index]._tbl.xpath('.//w:vMerge[@w:val="restart"]'),'Merged data-table header lost'
data,_,_=export_manuscript(root,document,'pdf');(out/'chinese.pdf').write_bytes(data)
report={'source_revision':source['revision'],'template':'chinese-mechanics','columns':1,'math_objects':counts['math'],'images':counts['image'],'equations':[]}
with fitz.open(stream=data,filetype='pdf') as pdf:
    report['pages']=len(pdf);full='\n'.join(p.get_text() for p in pdf)
    for old in out.glob('page-*.png'):old.unlink()
    for bad in ['¿','\ufffd','wbmathstyle','font serif','nitalic']:
        assert bad not in full,('Invalid formula render',bad)
    assert 'ℛ' in full and '𝒥' in full and 'ℒ' in full,'Mathematical script alphabet lost'
    for i,page in enumerate(pdf):
        page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(out/('page-'+str(i+1)+'.png'))
        spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
        tags=[s for s in spans if re.fullmatch(r'\((?:[1-9]|1[0-6])\)',s['text'].strip()) and s['bbox'][0]>500]
        for s in tags:report['equations'].append({'number':s['text'].strip(),'page':i+1,'bounds':s['bbox']})
        if any(s['text'].strip() in ('(5)','(8)','(9)','(15)','(16)') for s in tags):
            page.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(out/('equations-page-'+str(i+1)+'.png'))
    assert sorted(int(t['number'][1:-1]) for t in report['equations'])==list(range(1,17)),report['equations']
    table_row=[]
    for i,page in enumerate(pdf):
        spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
        values={text:[s for s in spans if s['text'].strip()==text] for text in ['1.87','3.24','0.990','0.955']}
        if all(values.values()):
            row=[values[text][0] for text in values]
            if max(s['origin'][1] for s in row)-min(s['origin'][1] for s in row)<2:table_row=[i+1,[s['origin'] for s in row]];break
    assert table_row,'The actual model-comparison table no longer has aligned numeric columns'
    report['merged_table_row_check']={'page':table_row[0],'origins':table_row[1],'passed':True}
assert store.manuscript(owner,pid)==source,'Export changed the scientific manuscript'
report['source_content_unchanged']=True
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
for kind in ['docx','pdf']:
    store.replace(owner,pid,root/'manuscript/exports'/('中文稿-力学进展写作范例.'+kind),(out/('chinese.'+kind)).read_bytes(),'按用户提供写作范例生成的中文稿')
print(json.dumps(report,ensure_ascii=False),flush=True)
