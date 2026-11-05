"""Render the current author's native Chinese Word template without editing the manuscript."""
from pathlib import Path
from io import BytesIO
import json
from docx import Document
from server.app import store
from server.manuscripts import export_manuscript
import fitz
owner='u_731b4f07a23742f0917ac6eb77df5df4';pid='05a893386c09449d88366cf6dfdc825f'
root=store.path(owner,pid);source=store.manuscript(owner,pid);output=root/'.workbench/template-check';output.mkdir(parents=True,exist_ok=True)
prepared={**source,'template':'chinese','columns':2}
for kind in ['docx','pdf']:
 data,suffix,mime=export_manuscript(root,prepared,kind);(output/('chinese.'+suffix)).write_bytes(data)
 print(kind,len(data),flush=True)
 if kind=='docx':
  word=Document(BytesIO(data));report={'source_revision':source['revision'],'paragraphs':len(word.paragraphs),'tables':len(word.tables),'editable_equations':len(word.element.body.xpath('.//m:oMath')),'images':len(word.inline_shapes),'sections':len(word.sections)}
 else:
  with fitz.open(stream=data,filetype='pdf') as pdf:
   report['pages']=len(pdf);report['replacement_characters']=sum(p.get_text().count('\ufffd') for p in pdf)
   for index in [0,min(4,len(pdf)-1),min(10,len(pdf)-1)]:pdf[index].get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(output/('chinese-page-'+str(index+1)+'.png'))
assert store.manuscript(owner,pid)['content']==source['content'],'Source was changed during template verification'
(output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report),flush=True)
