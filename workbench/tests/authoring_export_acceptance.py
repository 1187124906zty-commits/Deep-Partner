"""Inspect real Word output from edited image and citation objects."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import json,os
from PIL import Image
from docx import Document
from server.storage import Store
from server.manuscripts import export_manuscript

checks=[]
with TemporaryDirectory() as folder:
    store=Store(Path(folder));p=store.create('export-qa','Export fixture');pid=p['id'];root=store.path('export-qa',pid)
    image=root/'manuscript/assets/fixture.png';Image.new('RGB',(300,200),'white').save(image)
    doc=store.manuscript('export-qa',pid);doc['template']='elsevier';doc['references']=[{'id':'ref-1','number':1,'title':'Fixture source','authors':['Researcher'],'verified':False,'raw':'Fixture source.'}]
    doc['content']={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'Source '},{'type':'citation','attrs':{'refId':'ref-1','number':1}}]},{'type':'blockMath','attrs':{'latex':'J=-D\\nabla c'}},{'type':'image','attrs':{'src':f'/research/api/projects/{pid}/manuscript/assets/fixture.png','width':37,'align':'right','title':'Caption above','captionPosition':'top'}}]}
    saved=store.save_manuscript('export-qa',pid,doc);data,_,_=export_manuscript(root,saved,'docx')
    word=Document(BytesIO(data));text='\n'.join(p.text for p in word.paragraphs)
    assert 'Source [1]' in text and '[1] Fixture source.' in text;checks.append('Word retains native citation labels and the synchronized bibliography')
    drawing=next(p for p in word.paragraphs if p._p.xpath('.//w:drawing'))
    assert drawing.alignment==2;checks.append('The image alignment selected in the editor reaches Word output')
    section=word.sections[0];available=(section.page_width-section.left_margin-section.right_margin)/2-18*12700/2
    assert abs(word.inline_shapes[0].width/available-.37)<.015;checks.append('Image width remains the selected percentage of the selected column')
    elements=list(word.element.body);caption=next(p for p in word.paragraphs if p.text=='Caption above');assert elements.index(caption._p)<elements.index(drawing._p);checks.append('Image caption order follows the editable image object')
    assert word.element.body.xpath('.//m:oMath');checks.append('Editable equations survive export')
    from docx.oxml.ns import qn
    assert word.sections[-1]._sectPr.find(qn('w:cols')).get(qn('w:num'))=='2';checks.append('Default editable Word body uses two columns')
    assert abs(word.styles['Title'].font.size.pt-17.28)<.3;checks.append('CAS title size derives from the native class')
    saved['template']='chinese';saved['columns']=2
    data,_,_=export_manuscript(root,saved,'docx');native=Document(BytesIO(data))
    assert native.styles['Title'].font.size.pt==22 and native.styles['Title'].font.bold
    assert abs(native.sections[-1].left_margin.mm-19.51)<.05 and '西 北 工 业 大 学 学 报' in native.sections[0].header.paragraphs[0].text
    checks.append('Supplied Chinese template retains journal header, measured page geometry and 22pt bold title')
report={'passed':len(checks),'checks':checks,'actual_docx_generated':True,'external_model_calls':0}
output=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','verification'));output.mkdir(parents=True,exist_ok=True);(output/'authoring-export-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
