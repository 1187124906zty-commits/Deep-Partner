from pathlib import Path
from io import BytesIO
import json,re
import fitz
from docx import Document
from server.app import store
from server.manuscripts import export_manuscript,plain_document
owner='u_731b4f07a23742f0917ac6eb77df5df4';pid='05a893386c09449d88366cf6dfdc825f';root=store.path(owner,pid)
source=store.manuscript(owner,pid);translation=source['translation'];assert translation and not translation['stale']
prepared={**source,**translation,'template':'elsevier','columns':2,'references':source['references']}
folder=root/'.workbench/journal-preview';out=root/'.workbench/template-check';out.mkdir(exist_ok=True)
manifest=json.loads((folder/'manifest.json').read_text());text=''
with fitz.open(folder/'preview.pdf') as pdf:
 for i,page in enumerate(pdf):text+=page.get_text()
 for i in [0,min(2,len(pdf)-1),min(8,len(pdf)-1),len(pdf)-1]:pdf[i].get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(out/('cas-page-'+str(i+1)+'.png'))
report={'pages':manifest['pages'],'class':manifest['template_class'],'title':translation['title'],'remaining_cjk_text':len(re.findall(r'[\u4e00-\u9fff]',text)),'pdf_replacement_characters':text.count('\ufffd'),'translated_segments':translation['segments']}
log=(folder/'compile.txt').read_text();report['warnings']=[line for line in log.splitlines() if any(k in line.lower() for k in ['overfull','missing character','error:'])][:40]
# Source-bound language checks are separate from scientific editing.
data,_,_=export_manuscript(root,prepared,'docx');word=Document(BytesIO(data));report.update(word_bytes=len(data),editable_equations=len(word.element.body.xpath('.//m:oMath')),images=len(word.inline_shapes),tables=len(word.tables))
store.replace(owner,pid,root/'manuscript/exports/英文稿-CAS.docx',data,'CAS 可编辑英文 Word')
(out/'english-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
