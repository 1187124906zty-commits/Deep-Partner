"""Diagnose the native Writer import of explicit mathematical styles."""
from pathlib import Path
import subprocess,os
from server.manuscripts import export_manuscript
root=Path('/app/data/research-workbench/runtime-home/descriptor-diagnostic');root.mkdir(exist_ok=True)
(root/'manuscript').mkdir(exist_ok=True)
math=r'H_{obs}+x_j+\text{ln}H+\text{tanh}(x)+\mathbf{\theta}_H+\mathrm{m}/\mathrm{s}'
doc={'title':'Descriptor style diagnostic','template':'chinese','columns':1,'revision':1,'comments':[],'content':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'Baseline '},{'type':'inlineMath','attrs':{'latex':math}},{'type':'text','text':' measured.'}]}]}}
data,_,_=export_manuscript(root,doc,'docx');path=root/'descriptor.docx';path.write_bytes(data)
worker=Path('/workbench/server/uno_pdf_worker.py').read_text();worker=worker.replace('formula,restored=restore_math_styles(model.Formula,styles);styles_restored+=restored',"print('IMPORTED-FORMULA',repr(model.Formula),flush=True);formula,restored=restore_math_styles(model.Formula,styles);styles_restored+=restored;print('STYLED-FORMULA',repr(formula),flush=True)")
script=root/'worker.py';script.write_text(worker)
r=subprocess.run(['/usr/bin/python3',str(script),str(path),str(root/'descriptor.pdf'),'--profile',str(root/'profile'),'--font','Times New Roman','--size','10.5'],capture_output=True,text=True,timeout=100,env={**os.environ,'PYTHONPATH':'/workbench/server'});print(r.stdout);print(r.stderr);assert r.returncode==0
import fitz,json
with fitz.open(root/'descriptor.pdf') as pdf:
 print(json.dumps([{'text':s['text'],'font':s['font'],'size':s['size']} for b in pdf[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']],ensure_ascii=False))
