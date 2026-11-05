"""Bounded compile/render for every installed journal family, with real native classes."""
from pathlib import Path
import tempfile,json,runpy,os,fitz
from server.storage import Store
from server.journals import compile_preview,crossref_journal
from server.manuscripts import export_manuscript,TEMPLATES
from server.journal_catalog import local_journals
output=Path('/app/data/research-workbench/runtime-home/native-template-acceptance');output.mkdir(parents=True,exist_ok=True)
def p(value,heading=False):return {'type':'heading' if heading else 'paragraph',**({'attrs':{'level':1}} if heading else {}),'content':[{'type':'text','text':value}]}
equation={'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[p('')]},{'type':'tableCell','content':[{'type':'blockMath','attrs':{'latex':r'\frac{\partial H}{\partial t}=\nabla\cdot[D(H)\nabla H]+S_H,\quad q\in\mathbb{R},\quad \mathbf{\theta}_{H}^{\ast}=\mathbf{b}_{obs}.'}}]},{'type':'tableCell','content':[p('(10)')]}]}]}
table={'type':'table','content':[{'type':'tableRow','content':[{'type':'tableHeader' if ri==0 else 'tableCell','content':[p(v)]} for v in row]} for ri,row in enumerate([['Parameter','Value','Unit'],['Diffusivity','1.0','m²/s'],['Humidity','0.5','1']])]}
content=[p('Tianyu Zhao, Mingkun Jia, Wenxiang Xu'),p('College of Mechanics and Engineering Science, Hohai University, Nanjing, China'),p('Abstract',True),p('A numerical framework reconstructs the humidity field from sparse observations while retaining the governing equation and the measurement conditions.'),p('Keywords: moisture transport; physics-informed learning'),p('1 Introduction',True),p('The original mathematical objects retain their gradients, minus signs, indices and equation numbers. The template is selected for the journal and article type.'),equation,p('Table 1. Numerical parameters.'),table,p('2 Methods',True),p('The moisture diffusivity is identified from limited observations. The output preserves mathematical symbols and editable text.'),p('References',True),p('[1] Author. A source-bound reference. Journal, 2025, 1: 1–5.')]
journals=[crossref_journal({'title':'Cement and Concrete Research','publisher':'Elsevier','ISSN':['0008-8846']}),crossref_journal({'title':'Structural Concrete','publisher':'Wiley','ISSN':['1464-4177']}),crossref_journal({'title':'IEEE Transactions on Neural Networks and Learning Systems','publisher':'IEEE','ISSN':['2162-237X']}),crossref_journal({'title':'Materials and Structures','publisher':'Springer','ISSN':['1359-5997']})]
report=[]
with tempfile.TemporaryDirectory(dir=output) as temporary:
 store=Store(Path(temporary));project=store.create('template-qa','Native template fixture');pid=project['id'];root=store.path('template-qa',pid)
 doc={'title':'Native journal template and equation validation','content':{'type':'doc','content':content},'revision':1,'comments':[],'template':'elsevier'}
 for journal in journals:
  try:
   result=compile_preview(store,'template-qa',pid,doc,journal,2)
   pdf=root/'manuscript/exports/期刊排版预览.pdf';kind=journal['template']['family']
   with fitz.open(pdf) as d:
    d[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(output/(kind+'.png'));text='\n'.join(page.get_text() for page in d)
   report.append({'family':kind,'status':'passed','pages':result['pages'],'class':result['template_class'],'replacement':text.count('\ufffd'),'math_symbols':{'nabla':'∇' in text,'member':'∈' in text,'number10':'(10)' in text}})
  except Exception as e:report.append({'family':journal['template']['family'],'status':'failed','error':str(e)})
 for spec in TEMPLATES:
  try:
   data,_,_=export_manuscript(root,{**doc,'template':spec['id'],'columns':spec['columns'][0]},'pdf')
   with fitz.open(stream=data,filetype='pdf') as d:d[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(output/('word-'+spec['id']+'.png'))
   report.append({'family':'word-'+spec['id'],'status':'passed','bytes':len(data)})
  except Exception as e:report.append({'family':'word-'+spec['id'],'status':'failed','error':str(e)[:1200]})
(output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
assert all(row['status']=='passed' for row in report),'A native journal template did not compile/render'
