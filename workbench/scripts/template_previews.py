"""Render the real Word-based manuscript styles used by the workbench."""
from pathlib import Path
import os,tempfile,sys
import fitz
from server.manuscripts import TEMPLATES,export_manuscript

data=Path(os.environ.get('WORKBENCH_DATA','/app/data/research-workbench'))
output=data/'styles/previews';output.mkdir(parents=True,exist_ok=True)

def para(text,kind='paragraph',level=1):
    return {'type':kind,**({'attrs':{'level':level}} if kind=='heading' else {}),'content':[{'type':'text','text':text}]}

for spec in TEMPLATES:
    if len(sys.argv)>1 and spec['id'] not in sys.argv[1:]:continue
    chinese=spec['language']=='zh-CN'
    with tempfile.TemporaryDirectory(prefix='template-preview-',dir=data) as folder:
        root=Path(folder);(root/'manuscript/assets').mkdir(parents=True)
        content=[para('作者姓名 / Author Name'),para('摘要' if chinese else 'Abstract','heading'),para('此处呈现研究问题、所采用的方法、关键结果及其意义。模板保留正文、数学公式与表格的可编辑结构，便于审阅与修改。' if chinese else 'This preview shows the editable manuscript style. The abstract states the research question, methods, principal findings and their significance.'),para('1  引言' if chinese else '1. Introduction','heading'),para('研究从明确的问题出发，通过控制方程与相关证据建立联系。正文采用统一字体、段落间距与标题层级，图表紧随相关论述排列。' if chinese else 'The manuscript connects its research question to the governing equations and the supporting evidence. Figures and tables are placed close to the relevant discussion.'),{'type':'blockMath','attrs':{'latex':r'\frac{\partial c}{\partial t}=\nabla\cdot(D\nabla c)'}},para('2  方法' if chinese else '2. Methods','heading'),para('方法部分说明变量、单位、初始条件和边界条件。数学表达采用原生公式，表格采用可编辑的三线表。' if chinese else 'Define the variables, units, initial conditions and boundary conditions. Mathematical expressions and tables remain editable.'),{'type':'table','content':[{'type':'tableRow','content':[{'type':'tableHeader','content':[para('变量' if chinese else 'Quantity')]},{'type':'tableHeader','content':[para('符号' if chinese else 'Symbol')]}]},{'type':'tableRow','content':[{'type':'tableCell','content':[para('浓度' if chinese else 'Concentration')]},{'type':'tableCell','content':[para('c')]}]},{'type':'tableRow','content':[{'type':'tableCell','content':[para('扩散系数' if chinese else 'Diffusivity')]},{'type':'tableCell','content':[para('D')]}]}]}]
        manuscript={'title':'研究论文标题' if chinese else 'Title of the research article','template':spec['id'],'columns':spec['columns'][0],'content':{'type':'doc','content':content},'comments':[]}
        pdf,_,_=export_manuscript(root,manuscript,'pdf',False,data/'styles')
        document=fitz.open(stream=pdf,filetype='pdf');document[0].get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(output/(spec['id']+'.png'));document.close()
        print('Rendered actual manuscript template:',spec['id'],flush=True)
