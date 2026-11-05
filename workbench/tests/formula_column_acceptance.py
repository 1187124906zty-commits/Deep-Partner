"""Long equations remain editable and inside the selected text column."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json,re
from docx import Document
from server.math_layout import fold_math,width_em,typographic_math
from server.storage import Store
from server.manuscripts import export_manuscript

formulas=[
 r'\mathcal{R}_{H,diff}(\mathbf{x},t;\mathbf{\theta}_{H},\mathbf{\eta}_{D})=\frac{\partial\hat{H}}{\partial t}-\nabla\cdot\left[D(\hat H;\mathbf{\eta}_{D})\nabla\hat H\right]-S_H.',
 r'\Theta(H)=\left[1+\left(-\alpha_v\frac{RT_a}{M_wg}\ln H\right)^{n_v}\right]^{-m_v},\quad m_v=1-\frac{1}{n_v}.',
 r'R=\left\{\begin{matrix}\hat H-H_b(t),&\text{给定表面RH},\\-D(\hat H;\eta_D)\nabla\hat H\cdot n-j_{H,b}(\hat H,t),&\text{给定通量关系}.\end{matrix}\right.',
 r'\mathcal J(\theta_H,\eta_D)=\sum_{q\in\mathcal Q_H}b_{H,q}\lambda_{H,q}\mathcal L_{H,q}+\sum_{m\in\mathcal Q_D}b_{D,m}\mathcal L_{D,m}.',
 r'\begin{matrix}K(\Theta)&=K_s\Theta^{l_v},\\D(H;\eta)&=\frac{K}{(\theta_s-\theta_r)d\Theta/dH}.\end{matrix}',
]
# Word imports can end a system with an explicit TeX control-space.
formulas[2]+='\\ '
def signature(value):
 value=re.sub(r'\\(?:begin|end)\{(?:matrix|aligned|gathered|array)\}(?:\{[rl]\})?|\\displaystyle\s*','',value)
 value=re.sub(r'\\(?:quad|qquad)\b|\\\\|\\\s+\Z|&|\{\}|\s+','',value)
 return value
for formula in formulas:
 output=fold_math(formula,16.5)
 assert signature(output)==signature(formula),'Equation operands, signs or condition labels changed'
 assert width_em(output)<19,'Equation remains much wider than a column after reflow'
 if r'\begin{array}' in output:assert r'\begin{array}{l}' in output or r'\begin{array}{ll}' in output,'Equation group is not left aligned'
assert r'\begin{array}{ll}' in fold_math(r'\left\{\begin{matrix}a,&\text{flux},\\b,&\text{humidity}.\end{matrix}\right.',30),'Short piecewise formula not left aligned'
assert typographic_math(r'H_{j}^{obs}+\mathcal{R}_{H,diff}')==r'H_{j}^{\mathrm{obs}}+\mathcal{R}_{H,\mathrm{diff}}'

def p(value,heading=False):return {'type':'heading' if heading else 'paragraph',**({'attrs':{'level':1}} if heading else {}),'content':[{'type':'text','text':value}]}
def equation(value,number):
 return {'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[p('')]},{'type':'tableCell','content':[{'type':'blockMath','attrs':{'latex':value}}]},{'type':'tableCell','content':[p('('+str(number)+')')]}]}]}
with TemporaryDirectory() as folder:
 store=Store(Path(folder));project=store.create('math-column-qa','Math column fixture');root=store.path('math-column-qa',project['id'])
 source={'title':'单栏公式检查','revision':1,'template':'chinese','columns':2,'comments':[],'content':{'type':'doc','content':[p('作者'),p('工作单位'),p('摘要',True),p('长公式在当前文本栏内分行，编号居右。'),p('1 方法',True),{'type':'paragraph','content':[{'type':'inlineMath','attrs':{'latex':r'\mathbf{\theta}_H^{\ast}'}},{'type':'inlineMath','attrs':{'latex':r'\lbrack x,t\rbrack^{\mathsf{T}}'}}]},*[equation(value,i+1) for i,value in enumerate(formulas)]]}}
 original=deepcopy(source);data,_,_=export_manuscript(root,source,'docx');word=Document(BytesIO(data))
 assert source==original,'Export rewrote the scientific manuscript'
 assert len(word.sections)==2,'Equation introduced a full-width continuous section'
 assert len(word.tables)==5 and len(word.element.body.xpath('.//m:oMath'))==7
 assert word.element.body.xpath('.//m:eqArr | .//m:m/m:mr'),'Word equations did not retain editable multi-line layout'
 assert not word.element.body.xpath('.//m:mr/m:e[not(.//m:t)]'),'An empty alignment cell creates a visible Word math placeholder'
 section=word.sections[-1];width=(section.page_width-section.left_margin-section.right_margin)/12700
 for table in word.tables:
  from docx.oxml.ns import qn
  total=sum(int(c.get(qn('w:w'))) for c in table._tbl.tblGrid)
  assert total/20<width*.51,'Equation table occupies two text columns'
 pdf,_,_=export_manuscript(root,source,'pdf')
 import fitz
 with fitz.open(stream=pdf,filetype='pdf') as rendered:
  assert all('¿' not in p.get_text() for p in rendered),'PDF contains empty mathematical placeholders'
 print(json.dumps({'passed':True,'checks':['operand/sign/condition order','column-sized formula rows','no equation spans','native editable Word equation arrays','source document unchanged'],'equations':len(formulas),'sections':len(word.sections)},ensure_ascii=False))
