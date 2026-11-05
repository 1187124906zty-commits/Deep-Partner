"""Inspect text/math baselines in the actual exported PDF, not XML alone."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,os
import fitz
from server.storage import Store
from server.manuscripts import export_manuscript

out=Path('/app/data/research-workbench/runtime-home/typography-diagnostic');out.mkdir(exist_ok=True)
with TemporaryDirectory() as folder:
 store=Store(Path(folder));p=store.create('typography-qa','Typography');root=store.path('typography-qa',p['id'])
 content={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'Author'}]},{'type':'paragraph','content':[{'type':'text','text':'Affiliation'}]},{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'1 Method'}]},{'type':'paragraph','content':[{'type':'text','text':'Baseline '},{'type':'inlineMath','attrs':{'latex':'x'}},{'type':'text','text':' measured. 中文湿度 '},{'type':'inlineMath','attrs':{'latex':'H(x,t;\\theta_H)'}},{'type':'text','text':' 对齐。'}]},{'type':'paragraph','content':[{'type':'text','text':'Styles '},{'type':'inlineMath','attrs':{'latex':r'H_{obs}+x_j+\ln H+\text{tanh}(x)+\text{exp}(x)+\mathbf{\theta}_H+\mathrm{m}/\mathrm{s}'}}]}]}
 document={'title':'Text and equation alignment','revision':1,'template':'chinese','columns':1,'content':content,'comments':[]}
 pdf,_,_=export_manuscript(root,document,'pdf');(out/'baseline.pdf').write_bytes(pdf)
 with fitz.open(stream=pdf,filetype='pdf') as rendered:
  page=rendered[0];page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(out/'baseline.png');rows=[]
  for block in page.get_text('dict')['blocks']:
   for line in block.get('lines',[]):
    spans=line['spans']
    if any('Baseline' in s['text'] for s in spans):
     rows=[{'text':s['text'],'font':s['font'],'size':s['size'],'origin':s['origin']} for s in spans]
  assert rows,'No text/math baseline fixture rendered'
  text_base=next(r['origin'][1] for r in rows if 'Baseline' in r['text'])
  math_rows=[r for r in rows if 'Italic' in r['font'] and r['size']>9]
  assert math_rows and all(abs(r['size']-10.5)<.3 for r in math_rows),'Math font size differs from the journal body'
  assert all(abs(r['origin'][1]-text_base)<.65 for r in math_rows),'Inline math baseline drifts from surrounding text'
  spans=[span for block in page.get_text('dict')['blocks'] for line in block.get('lines',[]) for span in line['spans']]
  upright=lambda value:any(value==s['text'].strip() and 'Ital' not in s['font'] for s in spans)
  assert upright('obs') and upright('ln') and upright('m') and upright('s'),'An explicit descriptor, function or unit lost its upright style'
  assert any(s['text'].strip()=='j' and 'Ital' in s['font'] for s in spans),'An algebraic index lost its italic style'
  assert any(s['text'].strip()=='θ' and 'Bold' in s['font'] and 'Ital' in s['font'] for s in spans),'A vector lost its bold italic style'
  assert not any(any(v in s['text'] for v in ['wbmathstyle','font serif','nitalic','¿']) for s in spans),'A render-only marker or empty operand leaked into PDF'
  (out/'baseline.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print('BASELINE',json.dumps(rows,ensure_ascii=False),flush=True)
