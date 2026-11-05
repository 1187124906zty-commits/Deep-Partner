"""Check the supplied Chinese writing example against real Word/PDF output."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json,re
import fitz
from docx import Document
from docx.oxml.ns import qn
from PIL import Image
import numpy as np
from server.manuscripts import export_manuscript,template_info
from server.math_layout import typographic_math
from server.storage import Store

out=Path('/app/data/research-workbench/runtime-home/chinese-writing-example/check')
out.mkdir(parents=True,exist_ok=True)
def p(value,heading=False):
    return {'type':'heading' if heading else 'paragraph',**({'attrs':{'level':1}} if heading else {}),'content':[{'type':'text','text':value}]}
def equation(value,number):
    return {'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[p('')]},{'type':'tableCell','content':[{'type':'blockMath','attrs':{'latex':value}}]},{'type':'tableCell','content':[p('('+str(number)+')')]}]}]}
formulas=[
    r'\mathbf{h}_H^{(\ell)}=\text{tanh}(\mathbf{W}_H^{(\ell)}\mathbf{h}_H^{(\ell-1)}+\mathbf{b}_H^{(\ell)}),\quad\ell=1,\ldots,L_H.',
    r'\mathcal R_{H,diff}(\mathbf x,t;\mathbf\theta_H,\mathbf\eta_D)=\frac{\partial\hat H}{\partial t}-\nabla\cdot[D(\hat H;\mathbf\eta_D)\nabla\hat H]-S_H.',
    r'\mathcal R_{H,b}=\left\{\begin{matrix}\hat H-H_b(t),&\text{给定表面RH},\\-D(\hat H;\mathbf\eta_D)\nabla\hat H\cdot\mathbf n-j_{H,b}(\hat H,t),&\text{给定通量关系}.\end{matrix}\right.',
    r'\underset{\theta,\eta}{arg\, min}\mathcal J(\theta,\eta).',
]
value=r'\text{ln}H+\text{sin}(x)+\underset{\theta}{arg\, min}J+{RMSE}_H'
assert typographic_math(typographic_math(value))==typographic_math(value)
with TemporaryDirectory() as folder:
    store=Store(Path(folder));project=store.create('writing-example-qa','Chinese writing example');root=store.path('writing-example-qa',project['id'])
    Image.new('RGB',(400,160),(0,70,180)).save(root/'manuscript/assets/line-height.png')
    source={'title':'中文公式字体与条件分支检查','template':'chinese-mechanics','columns':1,'revision':1,'comments':[],
      'content':{'type':'doc','content':[p('作者姓名'),p('工作单位'),p('1 方法',True),
      {'type':'paragraph','content':[{'type':'text','text':'变量 '},{'type':'inlineMath','attrs':{'latex':'x'}},{'type':'text','text':' 与正文对齐。函数 '},{'type':'inlineMath','attrs':{'latex':r'\text{ln}H+\text{sin}(x)'}},{'type':'text','text':' 使用正体。'}]},
      *[equation(value,i+1) for i,value in enumerate(formulas)],
      {'type':'image','attrs':{'src':'/research/api/projects/'+project['id']+'/manuscript/assets/line-height.png','width':60,'title':'图1 图像应完整显示'}}]}}
    original=deepcopy(source)
    data,_,_=export_manuscript(root,source,'docx');(out/'fixture.docx').write_bytes(data);word=Document(BytesIO(data))
    assert len(word.element.body.xpath('.//m:oMath'))==6
    assert len(word.sections)==1
    assert len(word.inline_shapes)==1
    for paragraph in word.paragraphs:
        if paragraph._p.find('.//'+qn('w:drawing')) is not None:
            assert paragraph.paragraph_format.line_spacing==1,'Fixed body line height clips the figure'
    assert word.sections[0]._sectPr.find(qn('w:cols')).get(qn('w:num'))=='1'
    assert abs(word.sections[0].top_margin.mm-21.996)<.02
    assert abs(word.sections[0].bottom_margin.mm-22.983)<.02
    assert not word.element.body.xpath('.//m:mr/m:e[not(.//m:t)]')
    assert word.settings.element.xpath('.//m:mathFont')[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val')=='Cambria Math'
    data,_,_=export_manuscript(root,source,'pdf');(out/'fixture.pdf').write_bytes(data)
    with fitz.open(stream=data,filetype='pdf') as pdf:
        assert len(pdf)==1
        page=pdf[0];text=page.get_text()
        assert all(bad not in text for bad in ['¿','\ufffd','wbmathstyle','font serif','nitalic'])
        spans=[s for b in page.get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans']]
        for number in range(1,5):
            tags=[s for s in spans if s['text'].strip()=='('+str(number)+')']
            assert len(tags)==1 and tags[0]['bbox'][2]>530,(number,tags)
        assert any('TimesNewRoman' in s['font'] for s in spans), 'Requested Times New Roman math letters not rendered'
        assert any('TimesNewRoman' in s['font'] and 'Italic' in s['font'] and 'x' in s['text'] for s in spans), 'Variables lost italic style'
        assert 'ℛ' in text and '𝒥' in text,'An OfficeMath script alphabet became an ordinary Latin letter'
        labels=[s for s in spans if '给定表面RH' in s['text'] or '给定通量关系' in s['text']]
        assert len(labels)==2
        for label in labels:
            row=[s for s in spans if abs(s['origin'][1]-label['origin'][1])<4 and s['bbox'][0]<label['bbox'][0]-20 and ('Cambria' in s['font'] or 'TimesNewRoman' in s['font'])]
            assert row,'Condition label separated from its mathematical expression'
        pix=page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False);pixels=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n)
        blue=(pixels[:,:,0]<20)&(pixels[:,:,1]>50)&(pixels[:,:,1]<90)&(pixels[:,:,2]>150)
        assert int(blue.sum())>20000,'The image is clipped by a fixed paragraph line height'
        page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(out/'fixture.png')
        (out/'spans.json').write_text(json.dumps(spans,ensure_ascii=False,indent=2),encoding='utf8')
    assert source==original
    print(json.dumps({'passed':True,'pages':1,'native_math_objects':6,'condition_branches_on_same_rows':2,'source_unchanged':True,'template':template_info('chinese-mechanics')['name']},ensure_ascii=False))
