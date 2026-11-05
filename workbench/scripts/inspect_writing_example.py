"""Inspect the author's Chinese Word example without changing its source."""
from pathlib import Path
import json
import fitz
from docx import Document
from lxml import etree as ET

folder=Path('/app/data/research-workbench/runtime-home/chinese-writing-example')
doc=Document(folder/'chinese-writing-example.docx')
for i in [33,34,59,60,61,63,64,65,66]:
    p=doc.paragraphs[i]
    print('PARAGRAPH',i,p.text,ET.tostring(p._p,encoding='unicode').split('<w:pPr>')[-1][:1100])
for name in ['Normal','Body Text','Heading 1']:
    if name in doc.styles:
        s=doc.styles[name]
        print('STYLE',name,ET.tostring(s.element,encoding='unicode')[-2300:])
print('SETTINGS',ET.tostring(doc.settings.element,encoding='unicode')[-2000:])
with fitz.open(folder/'chinese-writing-example.pdf') as pdf:
    print('PAGES',len(pdf))
    for i,page in enumerate(pdf):
        text=page.get_text()
        print('PAGE',i+1,text[:100].splitlines())
        if '2.4' in text or '(1)' in text:
            page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(folder/('writing-example-page-'+str(i+1)+'.png'))
            spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
            print('MATH-SPANS',json.dumps([s for s in spans if s['text'].strip() in ['A','B','C','=','+','(1)'] or '公式' in s['text']],ensure_ascii=False))
