"""Bind the actual model's prose to first-appearance references and render Word."""
from copy import deepcopy
from pathlib import Path
import base64
import gzip
import json
import subprocess
import sys

from run_journal_synthesis_regression import REPORT, LIVE, STATE, REMOTE_ROOT, SSH


def main():
    sys.stdout.reconfigure(encoding='utf8')
    rid=json.loads(STATE.read_text(encoding='utf8'))['run_id']
    correction_path=REPORT/'qa/accepted-corrections.json'
    corrections=json.loads(correction_path.read_text(encoding='utf8')) if correction_path.exists() else []
    code='RID='+repr(rid)+'\nROOT='+repr(REMOTE_ROOT)+'\nPROSE_CORRECTIONS='+repr(corrections)+r'''
from copy import deepcopy
from pathlib import Path
import base64,gzip,json,re,subprocess
from server.writing_synthesis import apply_section_restructure
from server.manuscripts import export_manuscript
from docx import Document
from docx.oxml.ns import qn
from docx.shared import RGBColor,Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import fitz

root=Path(ROOT);folder=root/'.workbench/writing/runs'/RID
state=json.loads((folder/'state.json').read_text())
assert state['stage'] in ('review','deliver') or state['status']=='completed', 'Only export after the actual prose stage has returned'
raw=json.loads((folder/'wide.json').read_text())
for correction in PROSE_CORRECTIONS:
 paragraph=raw['sections'][0]['paragraphs'][correction['paragraph']-1]
 assert paragraph.count(correction['before'])==1,'Accepted correction must have one exact target'
 raw['sections'][0]['paragraphs'][correction['paragraph']-1]=paragraph.replace(correction['before'],correction['after'])
baseline=deepcopy(state['source_document'])
manifest=deepcopy(state['source_manifest'])
corrections=[]
for source in (baseline['references'],manifest):
 for entry in source:
  if entry['id']=='ref-kulik2012' and entry.get('year')!=2013:
   corrections.append({'id':entry['id'],'field':'year','from':entry['year'],'to':2013,'basis':'published Computational Geosciences volume 17 (2013); original DOI unchanged'})
   entry['year']=2013
  if entry['id']=='ref-chen2024' and entry['authors'][2]!='Dinghui Chen':
   corrections.append({'id':entry['id'],'field':'authors[2]','from':entry['authors'][2],'to':'Dinghui Chen','basis':'primary article PDF page 1 author line; DOI unchanged'})
   entry['authors'][2]='Dinghui Chen'
candidate,report=apply_section_restructure(baseline,raw['sections'],state['editorial_scope']['sections'],manifest,state['reference_policy'])
assert len(candidate['references'])==len(set(r['id'] for r in candidate['references']))
body=candidate['content']['content'];cited=[]
for node in body:
 if node.get('type')=='heading':break
 for child in node.get('content',[]):
  if child.get('type')=='citation':cited.append(child['attrs']['refId'])
assert list(dict.fromkeys(cited))==[r['id'] for r in candidate['references']]
assert all(r['number']==i+1 for i,r in enumerate(candidate['references']))

# The editable native candidate retains each citation identity. Only the Word
# presentation copy joins adjacent numeric citations into customary ranges.
display=deepcopy(candidate)
def joined(numbers):
 parts=[];i=0
 while i<len(numbers):
  j=i
  while j+1<len(numbers) and numbers[j+1]==numbers[j]+1:j+=1
  parts.append(str(numbers[i]) if i==j else str(numbers[i])+'–'+str(numbers[j]))
  i=j+1
 return '['+','.join(parts)+']'
def compact(node):
 if 'content' not in node:return
 output=[];nodes=node['content'];i=0
 while i<len(nodes):
  child=nodes[i]
  if child.get('type')=='citation':
   values=[]
   while i<len(nodes) and nodes[i].get('type')=='citation':values.append(nodes[i]['attrs']['number']);i+=1
   output.append({'type':'text','text':joined(values)})
  else:compact(child);output.append(child);i+=1
 node['content']=output
compact(display['content'])
display['title']='氯硫侵蚀预测框架引言候选';display['columns']=1
target=folder/'journal-synthesis-final.docx'
data,_,_=export_manuscript(root,display,'docx');target.write_bytes(data)
doc=Document(target)
for style in doc.styles:
 if style.type==1:
  if style.name=='Title' or style.name.startswith('Heading'):style.font.color.rgb=RGBColor(0,0,0)
  if style.name=='Title':
   for border in list(style.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
for paragraph in doc.paragraphs:
 if paragraph.style.name=='Title':
  for border in list(paragraph._p.iter(qn('w:pBdr'))):border.getparent().remove(border)
  for run in paragraph.runs:run.font.color.rgb=RGBColor(0,0,0);run.underline=False
 elif paragraph.style.name in ('Authors','Affiliation'):
  paragraph.style='Body Text'
  paragraph.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
  paragraph.paragraph_format.line_spacing=1.5
  paragraph.paragraph_format.first_line_indent=Pt(21)
doc.save(target)
out=folder/'render-journal-synthesis-final'
result=subprocess.run(['python','/opt/workbench-tools/render_writing_docx.py',str(target),'--output_dir',str(out),'--emit_pdf'],capture_output=True,text=True,timeout=180)
assert result.returncode==0,result.stdout+result.stderr
pages=sorted(out.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
versions={s['stage']:s.get('prompt_version','') for s in state['stage_history']}
report.update({'raw_model_run':RID,'raw_prompt_version':versions['wide'],'stage_prompt_versions':versions,'reference_formatter_version':versions['wide'],'metadata_corrections':corrections,'narrative_changed_after_model_review':bool(PROSE_CORRECTIONS),'accepted_prose_corrections':PROSE_CORRECTIONS,'model_review_completed_at_export':'review' in versions,'first_appearance_numbering':True,'pages_rendered':len(pages),'visual_review':'pending','author_approval':'pending'})
files={'final-candidate-document.json':json.dumps(candidate,ensure_ascii=False,indent=2).encode(),'finalization.json':json.dumps(report,ensure_ascii=False,indent=2).encode(),'氯硫引言_研究群体综合候选.docx':target.read_bytes()}
for p in pages:files['render-final/'+p.name]=p.read_bytes()
print(base64.b64encode(gzip.compress(json.dumps({k:base64.b64encode(v).decode() for k,v in files.items()}).encode())).decode())
'''
    result=subprocess.run([*SSH,'docker exec -i research-workbench python -'],input=code,
        capture_output=True,text=True,encoding='utf8',timeout=240)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    encoded=result.stdout.strip().splitlines()[-1]
    files=json.loads(gzip.decompress(base64.b64decode(encoded)))
    for name,value in files.items():
        target=(REPORT/name) if name.endswith('.docx') or name.startswith('render-final/') else LIVE/name
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(value))
    print((LIVE/'finalization.json').read_text(encoding='utf8'))


if __name__=='__main__':main()
