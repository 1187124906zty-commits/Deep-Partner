"""Render the unmodified author template and compare page-header geometry."""
from pathlib import Path
import subprocess,json
import fitz
root=Path('/app/data/research-workbench/runtime-home/native-header-source');root.mkdir(exist_ok=True)
source=Path('/workbench/templates/manuscripts/source/chinese-user-260909.docx')
p=subprocess.run(['libreoffice','-env:UserInstallation='+(root/'profile').as_uri(),'--headless','--convert-to','pdf','--outdir',str(root),str(source)],capture_output=True,text=True,timeout=100);print(p.stdout,p.stderr);assert p.returncode==0
with fitz.open(root/'chinese-user-260909.pdf') as pdf:
 for i,page in enumerate(pdf):
  spans=[s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['bbox'][1]<150]
  rules=[float(d['rect'].y1) for d in page.get_drawings() if d['rect'].width>400 and d['rect'].height<2 and 35<d['rect'].y0<115]
  print(json.dumps({'page':i+1,'rules':rules,'top_spans':[{'text':s['text'][:60],'y':s['bbox'][1]} for s in spans[:8]]},ensure_ascii=False))
