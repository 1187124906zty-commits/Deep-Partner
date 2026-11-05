"""Real storage, document conversion and editable master-based PPT acceptance."""
from pathlib import Path
import json
import os
import tempfile
import zipfile
from io import BytesIO
from lxml import etree as ET
from PIL import Image,ImageDraw
from server.storage import Store,Conflict,child
from server.manuscripts import export_manuscript,import_manuscript,make_reference
from server.slides import inspect_template,make_deck,render_presentation

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path(os.environ.get('WORKBENCH_TEST_OUTPUT',str(ROOT/'verification')))
OUTPUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);store=Store(root/'state');p=store.create('acceptance-a','格式与文件验收');pid=p['id'];project=store.path('acceptance-a',pid)
    with zipfile.ZipFile(make_reference(root/'styles','elsevier')) as z:
        styles=ET.fromstring(z.read('word/styles.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        headings=[node for node in styles.findall('w:style',ns) if node.find('w:name',ns) is not None and node.find('w:name',ns).get('{'+ns['w']+'}val','').lower() in ['heading 1','heading 2','heading 3']]
        check(len(headings)==3 and all(node.find('w:pPr/w:numPr/w:numId',ns).get('{'+ns['w']+'}val')=='0' for node in headings),'publisher style import suppresses duplicate automatic heading numbers')
    files=store.inventory('acceptance-a',pid)['items']
    check(all((project/'project'/d).is_dir() for d in ['src','data','results','docs']) and not list((project/'project/data').glob('*/')),'four research folders exist with no prebuilt task-specific subdivisions')
    check(next(x for x in files if x['name']=='src')['count']==0,'empty folder has a visible zero count')
    script=project/'project/src/check.py';store.replace('acceptance-a',pid,script,b'print(285)\n')
    src=next(x for x in store.inventory('acceptance-a',pid)['items'] if x['name']=='src')
    check(src['count']==1 and src['types']=={'PY':1} and src['size']==11,'file inventory reports actual extension, recursive count and bytes')
    store.replace('acceptance-a',pid,script,b'print(286)\n');trash=store.trash('acceptance-a',pid)
    check(len(trash)==1 and script.read_text()=='print(286)\n','only latest file stays active and old file moves to reversible trash')
    store.restore('acceptance-a',pid,trash[0]['id']);check(script.read_text()=='print(285)\n','trash restoration returns original bytes without losing current replacement')
    try:store.get('acceptance-b',pid);raise AssertionError('cross-account project leaked')
    except KeyError:checks.append('account ownership prevents cross-account project reads')
    try:child(project/'project','../../elsewhere');raise AssertionError('path traversal allowed')
    except ValueError:checks.append('file operations stay inside the selected project')
    doc=store.manuscript('acceptance-a',pid);store.save_manuscript('acceptance-a',pid,doc)
    try:store.save_manuscript('acceptance-a',pid,doc);raise AssertionError('stale revision accepted')
    except Conflict:checks.append('stale editor revision cannot overwrite a newer manuscript')
    image=Image.new('RGB',(600,250),'white');draw=ImageDraw.Draw(image);draw.line([(35,215),(570,215)],fill='#666666',width=2);draw.line([(35,215),(35,25)],fill='#666666',width=2);draw.line([(35+i,180-int(120*(i/520)**.5)) for i in range(520)],fill='#466d55',width=4)
    image.save(project/'manuscript/assets/figure.png')
    def run(value,marks=None):return {'type':'text','text':value,**({'marks':marks} if marks else {})}
    def para(value):return {'type':'paragraph','content':[run(value)]}
    common={'changeId':'fixture-change','authorId':'reviewer','authorName':'格式审阅','authorColor':'#36745b','timestamp':'2026-10-31T10:00:00Z'}
    content={'type':'doc','content':[
      {'type':'heading','attrs':{'level':1},'content':[run('扩散方程与格式验收')]},
      para('此稿仅用于工作台排版与文件验证，不代表研究结果。'),
      {'type':'paragraph','content':[run('数值验证需要'),run('只检查程序运行',[{'type':'deletion','attrs':common}]),run('核对边界条件与守恒',[{'type':'insertion','attrs':common},{'type':'commentAnchor','attrs':{'id':'fixture-comment'}}]),run('。')]},
      {'type':'blockMath','attrs':{'latex':r'\frac{\partial c}{\partial t}=D\nabla^2 c'}},
      {'type':'paragraph','content':[run('其中 '),{'type':'inlineMath','attrs':{'latex':'D'}},run(' 为扩散系数，单位为 m²/s。')]},
      {'type':'table','content':[{'type':'tableRow','content':[{'type':'tableHeader','content':[para('检查量')]},{'type':'tableHeader','content':[para('验收用途')]}]},{'type':'tableRow','content':[{'type':'tableCell','content':[para('质量守恒')]},{'type':'tableCell','content':[para('验证传输实现')]}]}]},
      {'type':'image','attrs':{'src':f'/research/api/projects/{pid}/manuscript/assets/figure.png','alt':'排版示意','title':'图1 排版验收示意'}}]}
    manuscript={'title':'研究工作台导出验收','template':'elsevier','content':content,'comments':[{'id':'fixture-comment','body':'请保留单位与边界条件。','quote':'核对边界条件与守恒','author':'格式审阅','created':'2026-10-31T10:00:00Z'}]}
    for review in [False,True]:
        data,suffix,mime=export_manuscript(project,manuscript,'docx',review,root/'styles')
        (OUTPUT/(('review' if review else 'clean')+'.docx')).write_bytes(data)
        with zipfile.ZipFile(BytesIO(data)) as z:
            xml=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
            check(len(xml.findall('.//m:oMath',ns))>=2,('review' if review else 'clean')+' Word retains native editable Office equations')
            check(len(xml.findall('.//w:tbl',ns))==1 and len(xml.findall('.//w:drawing',ns))==1,'Word retains native table and source image')
            if review:
                check(len(xml.findall('.//w:ins',ns))>=1 and len(xml.findall('.//w:del',ns))>=1,'review Word contains native insert and delete revision records')
                check('word/comments.xml' in z.namelist() and len(xml.findall('.//w:commentRangeStart',ns))>=1,'review Word contains native anchored comments')
            else:check(not xml.findall('.//w:del',ns) and '只检查程序运行' not in ''.join(xml.itertext()),'clean Word excludes deleted material and review metadata')
        imported=import_manuscript(project,pid,data,'roundtrip.docx')
        check('blockMath' in json.dumps(imported) and 'image' in json.dumps(imported),'Word imports with editable math and original embedded image')
        from server.manuscripts import text
        check(not any(n.get('type')=='paragraph' and text(n).strip()=='图1 排版验收示意' for n in imported['content']) and any(n.get('type')=='image' and n.get('attrs',{}).get('title')=='图1 排版验收示意' for n in imported['content']),'Word roundtrip retains one editable figure caption without a duplicate paragraph')
    for review in [False,True]:
        data,_,_=export_manuscript(project,manuscript,'pdf',review,root/'styles');name='review' if review else 'clean';(OUTPUT/(name+'.pdf')).write_bytes(data)
        import fitz
        document=fitz.open(stream=data,filetype='pdf');page=document[0];page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(OUTPUT/(name+'.png'))
        check(len(document)>=1 and page.get_images(),'PDF actually renders source image and manuscript pages')
        check('∂' in page.get_text() and 'D' in page.get_text(),'PDF displays the actual equation glyphs')
        if review:check(sum(len(list(p.annots() or [])) for p in document)>=1,'review PDF contains actual review annotations')
        document.close()
    tex,suffix,_=export_manuscript(project,manuscript,'tex',True,root/'styles')
    (OUTPUT/'manuscript-tex.zip').write_bytes(tex)
    with zipfile.ZipFile(BytesIO(tex)) as z:
        check('manuscript.tex' in z.namelist() and 'review.json' in z.namelist() and any(n.startswith('assets/') for n in z.namelist()),'TeX exports portable images and complete editable review sidecar')
        check(any(command in z.read('manuscript.tex').decode() for command in ['\\sout','\\st{','\\textst{']),'TeX review visibly preserves deletions')
    source=ROOT/'templates/presentations/research-group.pptx';manifest=inspect_template(source,root/'template')
    check(manifest['master_count']>0 and manifest['layouts'] and manifest['examples'],'uploaded content-bearing template yields real master, layouts and classified example pages')
    plan={'title':'工作台验收','sections':[{'id':'one','title':'研究项目的连续工作','content':'文献与问题\n程序与验证\n稿件与汇报','role':'cover'},{'id':'two','title':'保留可编辑内容与原母版','content':'正文、图表和公式分别组织。\n本页为产品验收示例。','role':'content'}]}
    deck=root/'deck.pptx';report=make_deck(source,manifest,plan,deck)
    check(report['all_template_parts_preserved'],'generated PPT preserves uploaded master, layout and theme XML parts')
    from pptx import Presentation
    prs=Presentation(deck);check(len(prs.slides)==2 and any(s.has_text_frame and '可编辑' in s.text for s in prs.slides[1].shapes),'generated slides contain editable native PowerPoint text')
    with zipfile.ZipFile(deck) as z:
        # python-pptx renames part names in memory when accessing slides;
        # use the saved package relationships to locate the actual XML.
        import posixpath
        ids=ET.fromstring(z.read('ppt/presentation.xml')).findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId')
        rid=ids[1].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel=next(n for n in ET.fromstring(z.read('ppt/_rels/presentation.xml.rels')) if n.get('Id')==rid)
        target=rel.get('Target');name=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('ppt',target))
        xml=ET.fromstring(z.read(name));ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        runs=xml.findall('.//a:rPr',ns)
        check(all(r.find('a:latin',ns) is not None and r.find('a:latin',ns).get('typeface')=='Times New Roman' and r.find('a:ea',ns) is not None and r.find('a:ea',ns).get('typeface')=='微软雅黑' for r in runs),'PPT text explicitly assigns Times New Roman and Microsoft YaHei by script')
    rendered=render_presentation(deck,OUTPUT/'slide-render');check(rendered['pages']==2 and (OUTPUT/'slide-render/page-1.png').is_file(),'PPT and PDF preview are actually rendered')
    (OUTPUT/'sample.pptx').write_bytes(deck.read_bytes());(OUTPUT/'template-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
report={'passed':True,'checks':checks,'model_calls':0,'real_documents_rendered':True,'real_template':True}
(OUTPUT/'server-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
