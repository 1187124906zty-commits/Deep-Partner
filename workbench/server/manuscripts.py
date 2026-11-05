"""Tiptap document -> editable Word equations, PDF and portable TeX.

Pandoc owns document conversion; WordprocessingML adds native review marks.
The editing canvas uses Word manuscript styles, never a LaTeX page template.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from lxml import etree as ET
from functools import lru_cache
from .storage import atomic_json,child

TEMPLATES = [
 {'id':'journal-zh','name':'中文期刊','language':'zh-CN','columns':[2],'primary':True,'native':True,'native_exact':True,'font':'Times New Roman','font_cjk':'SimSun','math_font':'Cambria Math','math_letter_font':'Times New Roman','math_script_percent':73,'heading_cjk':'SimHei','title_cjk':'SimHei','size':10.5,'leading':1,'line_pt':15.6,'heading':12,'title_size':22,'caption_size':9,'table_size':9,'margin':19.51,'column_gap':21.25,'source_file':'chinese-journal.docx','original_file':'chinese-journal.docx','preview_pdf':'chinese-journal.pdf','basis':'','source':''},
 {'id':'journal-en','name':'Journal template','language':'en','columns':[1],'primary':True,'native':True,'native_exact':True,'font':'Times New Roman','font_cjk':'SimSun','math_font':'Cambria Math','math_letter_font':'Times New Roman','size':12,'leading':2,'heading':14,'title_size':14,'caption_size':12,'table_size':12,'margin':25.4,'column_gap':36,'source_file':'elsevier-research.docx','original_file':'elsevier-research.docx','preview_pdf':'elsevier-research.pdf','basis':'','source':'https://legacyfileshare.elsevier.com/promis_misc/Research%20Article%20template%20and%20guidance.docx'},
 {'id':'generic-zh','name':'通用中文学术稿','language':'zh-CN','columns':[1,2],'native':False,'generic':True,'font':'Times New Roman','font_cjk':'SimSun','math_font':'Cambria Math','math_letter_font':'Times New Roman','math_script_percent':73,'heading_cjk':'SimHei','title_cjk':'SimHei','size':10.5,'leading':1.5,'heading':12,'heading_sizes':[12,11,10.5],'margin':24,'title_size':18,'caption_size':9.5,'table_size':9.5,'authors_size':11,'affiliation_size':10,'column_gap':21,
  'source_file':'','basis':'工作台通用学术版式：A4，宋体与 Times New Roman，公式字母用新罗马、数学结构保留原生公式；单栏或双栏。包含原稿作者资料与明确标识的预览日期。此版式不代表任何期刊的发表排版。','source':'/research/api/standards'},
 {'id':'generic-en','name':'通用英文学术稿','language':'en','columns':[1,2],'native':False,'generic':True,'font':'Times New Roman','font_cjk':'SimSun','math_font':'Cambria Math','math_letter_font':'Times New Roman','size':11,'leading':1.4,'heading':13,'heading_sizes':[13,12,11],'margin':24,'title_size':18,'caption_size':9,'table_size':9,'authors_size':11,'affiliation_size':10,'column_gap':21,
  'source_file':'','basis':'Generic academic manuscript: A4, Times New Roman, editable equations, one or two columns, author details and a labelled preview date. This is a workbench layout, not a publisher production proof.','source':'/research/api/standards'},
 {'id':'chinese-mechanics','name':'中文 · 力学进展写作范例','language':'zh-CN','columns':[1,2],'native':True,'font':'Times New Roman','font_cjk':'SimSun','math_font':'Cambria Math','math_letter_font':'Times New Roman','math_script_percent':73,'abstract_cjk':'SimSun','heading_cjk':'SimHei','title_cjk':'SimHei','size':10.5,'leading':1,'line_pt':15.6,'line_at_least':True,'heading':12,'heading_sizes':[12,10.5,10.5],'heading_before':7.8,'heading_after':7.8,'margin':19.51,'title_size':28,'caption_size':10.5,'table_size':10.5,'authors_size':14,'affiliation_size':10,'column_gap':21.1,
  'source_file':'chinese-writing-example.docx','original_file':'chinese-writing-example.doc','basis':'使用你提供的《力学进展》写作范例（2015）：默认单栏，正文五号宋体与 Times New Roman，沿用原稿A4、页边距及15.6pt网格；公式字母按当前选择使用 Times New Roman，数学结构由 Cambria Math 补足；变量斜体、向量和矩阵黑斜体、说明性下标与函数正体、编号右齐。双栏为工作台阅读适配。',
  'source':'/research/api/manuscript-template-source/chinese-mechanics'},
 {'id':'chinese','name':'中文 · 西北工业大学学报','language':'zh-CN','columns':[2,1],'native':True,'font':'Times New Roman','font_cjk':'SimSun','heading_cjk':'SimHei','title_cjk':'SimHei','size':10.5,'leading':1,'line_pt':15.65,'heading':14,'heading_sizes':[14,10.5,10.5],'margin':19.51,'title_size':22,'caption_size':9,'table_size':9,'column_gap':21.1,
  'source_file':'chinese-user-260909.docx','original_file':'chinese-user-260909.doc','basis':'使用你提供的《西北工业大学学报》论文模板260909.doc：题名二号黑体、正文五号宋体与 Times New Roman，正文行距15.65pt、图表小五号、公式整体居中且编号右齐；多行组内部按本次要求左对齐。默认保留原稿双栏；单栏为同一格式的阅读选项。',
  'source':'/research/api/manuscript-template-source/chinese'},
 {'id':'elsevier','name':'Elsevier · CAS 可编辑 Word','language':'en','columns':[2,1],'native':False,'font':'STIX','size':10,'leading':1.2,'heading':12,'heading_sizes':[12,11,10.5],'margin':18.1,'title_size':17.28,'title_bold':False,'caption_size':8,'table_size':8,'column_gap':18,
  'source_file':'cas-editable.docx','original_file':'els-cas-templates.zip','basis':'按你提供的 CAS 2.4 原生 LaTeX 类映射的可编辑 Word：双栏对应 cas-dc，单栏对应 cas-sc，保留原生公式和表格。CAS 原包没有官方 Word 文件，PDF 期刊预览使用原生 CAS 类。',
  'source':'https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions'},
 {'id':'springer','name':'Springer · AAS 原生 Word','language':'en','columns':[1],'native':True,'font':'Times New Roman','size':12,'leading':2,'heading':12,'margin':25.4,'title_size':18,
  'source_file':'springer-aas.docx','basis':'Springer AAS 2025 作者指南链接的官方 Word 模板，Times New Roman 12磅正文、双倍行距、单栏，保留原文件纸张与页边距。',
  'source':'https://media.springer.com/full/springer-instructions-for-authors-assets/pdf/376_AAS_Author%20Guide_2025.pdf'},
 {'id':'chinese-engineering','name':'中文 · 中国工程科学','language':'zh-CN','columns':[2,1],'native':True,'font':'Times New Roman','font_cjk':'SimSun','heading_cjk':'SimHei','title_cjk':'SimHei','size':10.5,'leading':1.15,'heading':12,'heading_sizes':[12,10.5,10.5],'margin':20,'title_size':22,'caption_size':9,'column_gap':21.25,'source_file':'chinese-engineering.docx','basis':'《中国工程科学》官方原生 Word：二号题名、宋体正文、小五摘要及双栏正文。保留源模板的纸张和页边距。','source':'https://www.engineering.org.cn/sscae/CN/templates'},
 {'id':'cirp','name':'CIRP Annals · 原生 Word','language':'en','columns':[2,1],'native':True,'font':'Cambria','size':9,'leading':1.15,'heading':10,'heading_sizes':[10,9,9],'margin':20,'title_size':14,'caption_size':8,'source_file':'cirp-annals-2026.docx','original_file':'cirp-annals-2026.doc','basis':'CIRP Annals 2026 官方 Word；与通用 CAS 类分开匹配该期刊。保留 Cambria 字体、字号、双栏和原稿纸张。','source':'https://cirp.net/mainmenu-publications/cirp-annals-col-200/authors-submit-a-paper.html'},
 {'id':'rsc','name':'RSC Article · 原生 Word','language':'en','columns':[2],'native':True,'font':'Arial','size':9,'leading':1.05,'heading':12,'heading_sizes':[12,9,9],'margin':15,'title_size':14.5,'caption_size':7,'table_size':8,'column_gap':11.35,'source_file':'rsc-article.docx','basis':'RSC 官方 Article Word 模板；双栏。适用普通 Article、Review 和 Edge；ChemComm Communication 使用专用模板，不套用此项。','source':'https://www.rsc.org/publishing/publish-with-us/publish-a-journal-article/article-templates','style_map':{'Title':'RSC H01 Paper Title','Authors':'RSC H02 Paper Authors and Byline','Abstract':'RSC B01 ART Abstract','Normal':'RSC B02 Article Text','Body Text':'RSC B02 Article Text','First Paragraph':'RSC B02 Article Text','Heading 1':'RSC B04 A Heading (Section)','Heading 2':'RSC B06 B Heading (Sub-Section)','Heading 3':'RSC B08 C Heading (In-line)','Caption':'RSC I04 Caption to Figure/Scheme/Chart','Table Caption':'RSC T02 Table title without top bar','Bibliography':'RSC R02 References'}},
 {'id':'rsc-faraday','name':'Faraday Discussions · 原生 Word','language':'en','columns':[1],'native':True,'font':'Arial','size':9,'leading':1.05,'heading':12,'heading_sizes':[12,9,9],'margin':15,'title_size':14.5,'caption_size':7,'table_size':8,'source_file':'rsc-faraday.docx','basis':'RSC 为 Faraday Discussions 单独提供的原生单栏 Word 模板，按期刊名精确匹配。','source':'https://www.rsc.org/publishing/publish-with-us/publish-a-journal-article/article-templates','style_map':{'Title':'RSC H01 Paper Title','Authors':'RSC H02 Paper Authors and Byline','Abstract':'RSC B01 ART Abstract','Normal':'RSC B02 Article Text','Body Text':'RSC B02 Article Text','First Paragraph':'RSC B02 Article Text','Heading 1':'RSC B04 A Heading (Section)','Heading 2':'RSC B06 B Heading (Sub-Section)','Heading 3':'RSC B08 C Heading (In-line)','Caption':'RSC I04 Caption to Figure/Scheme/Chart','Table Caption':'RSC T02 Table title without top bar','Bibliography':'RSC R02 References'}},

]

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
M='http://schemas.openxmlformats.org/officeDocument/2006/math'
NS={'w':W,'m':M}


def pandoc():
    executable=os.environ.get('WORKBENCH_PANDOC') or shutil.which('pandoc')
    if not executable:
        candidate=Path(__file__).resolve().parents[1]/'tools/pandoc/bin/pandoc'
        if candidate.is_file():executable=str(candidate)
    if not executable:raise RuntimeError('Pandoc 转换器尚未安装')
    return executable


@lru_cache(maxsize=1)
def pandoc_api_version():
    value=subprocess.run([pandoc(),'-f','markdown','-t','json'],input=b'',capture_output=True,check=True)
    return json.loads(value.stdout)['pandoc-api-version']


def template_info(name):
    return next((t for t in TEMPLATES if t['id']==name),TEMPLATES[0])


def text(node):
    if node.get('type')=='citation':return '['+str(node.get('attrs',{}).get('number','?'))+']'
    if node.get('type')=='text':return node.get('text','')
    if node.get('type') in ('inlineMath','blockMath'):return node.get('attrs',{}).get('latex','')
    return ''.join(text(n) for n in node.get('content',[]))


def plain_document(doc):
    return '\n\n'.join(text(n) for n in doc.get('content',[]))


def make_reference(folder:Path,name,columns=2):
    from .word_layout import make_reference as build
    return build(folder,name,columns)


def format_word(path,template,content=None,columns=2):
    """Native journal table rules and figure positioning, after conversion."""
    from docx import Document
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document(path)
    def border(parent,side,size=6,value='single'):
        n=OxmlElement('w:'+side);n.set(qn('w:val'),value);n.set(qn('w:sz'),str(size));n.set(qn('w:color'),'444444');parent.append(n)
    from .equation_layout import is_equation_table
    source_tables=[]
    def find_tables(n):
        if n.get('type')=='table':source_tables.append(n)
        for child in n.get('content',[]):find_tables(child)
    if content:find_tables(content)
    for table_index,table in enumerate(doc.tables):
        source_table=source_tables[table_index] if table_index<len(source_tables) else {}
        equation=is_equation_table(source_table)
        from .cas_typesetting import table_header_rows
        header_count=0 if equation else table_header_rows(source_table) if source_table else 1
        props=table._tbl.tblPr
        old=props.find(qn('w:tblBorders'))
        if old is not None:props.remove(old)
        rules=OxmlElement('w:tblBorders');props.append(rules)
        for side in ['top','bottom']:border(rules,side,8,value='nil' if equation else 'single')
        for side in ['left','right','insideH','insideV']:border(rules,side,value='nil')
        for ri,row in enumerate(table.rows):
            header=ri<header_count
            for old_header in row._tr.get_or_add_trPr().findall(qn('w:tblHeader')):old_header.getparent().remove(old_header)
            if header:row._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
            for ci,cell in enumerate(row.cells):
                if equation:
                    cell.vertical_alignment=1
                    cell.width=Pt((doc.sections[0].page_width-doc.sections[0].left_margin-doc.sections[0].right_margin)/12700*([.11,.78,.11] if len(row.cells)==3 else [.88,.12])[ci])
                    tc=cell._tc.get_or_add_tcPr();edges=tc.find(qn('w:tcBorders'))
                    if edges is None:edges=OxmlElement('w:tcBorders');tc.append(edges)
                    for side in ['top','bottom','left','right']:border(edges,side,value='nil')
                if ri==header_count-1 and not equation:
                    tc=cell._tc.get_or_add_tcPr();edges=tc.find(qn('w:tcBorders'))
                    if edges is None:edges=OxmlElement('w:tcBorders');tc.append(edges)
                    border(edges,'bottom',5)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.first_line_indent=Pt(0)
                    paragraph.paragraph_format.space_before=Pt(1 if equation else 3);paragraph.paragraph_format.space_after=Pt(1 if equation else 3)
                    if equation:paragraph.alignment=2 if ci==len(row.cells)-1 else 1;paragraph.paragraph_format.line_spacing=1.05
                    paragraph.paragraph_format.keep_with_next=header
                    if header:
                        for run in paragraph.runs:run.bold=True
    images=[]
    def collect(node):
        if node.get('type')=='image':images.append(node.get('attrs',{}))
        for child in node.get('content',[]):collect(child)
    if content:collect(content)
    image_index=0
    for paragraph in doc.paragraphs:
        if paragraph._p.find('.//'+qn('w:drawing')) is not None:
            attrs=images[image_index] if image_index<len(images) else {};image_index+=1
            paragraph.alignment={'left':0,'center':1,'right':2}.get(attrs.get('align'),1);paragraph.paragraph_format.first_line_indent=Pt(0);paragraph.paragraph_format.keep_with_next=True
            # A fixed body-line height clips an inline figure to one text line.
            # Let the paragraph grow to the image's actual height.
            paragraph.paragraph_format.line_spacing=1
    from .word_layout import layout_word
    layout_word(doc,template,content,columns)
    # Text inside an OfficeMath run uses its real CJK font, not a math alphabet.
    spec=template_info(template)
    settings=doc.settings.element
    math_properties=settings.find('{'+M+'}mathPr')
    if math_properties is None:math_properties=ET.SubElement(settings,'{'+M+'}mathPr')
    math_font=math_properties.find('{'+M+'}mathFont')
    if math_font is None:math_font=ET.SubElement(math_properties,'{'+M+'}mathFont')
    math_font.set('{'+M+'}val',spec.get('math_font','Cambria Math'))
    for run in doc.element.body.findall('.//{'+M+'}r'):
        value=''.join(run.itertext())
        rpr=run.find('{'+W+'}rPr')
        if rpr is None:
            rpr=ET.Element('{'+W+'}rPr');run.insert(1 if run.find('{'+M+'}rPr') is not None else 0,rpr)
        size=rpr.find('{'+W+'}sz')
        if size is None:size=ET.SubElement(rpr,'{'+W+'}sz');size.set('{'+W+'}val',str(round(spec['size']*2)))
        fonts=rpr.find('{'+W+'}rFonts')
        if fonts is None:fonts=ET.SubElement(rpr,'{'+W+'}rFonts')
        letter_font=spec.get('math_letter_font',spec['font'] if spec.get('language')=='zh-CN' else spec.get('math_font','Cambria Math'))
        for key in ('ascii','hAnsi','cs'):fonts.set('{'+W+'}'+key,letter_font)
        if not re.search(r'[\u4e00-\u9fff]',value):continue
        normal=run.find('{'+M+'}rPr')
        if normal is None:normal=ET.Element('{'+M+'}rPr');run.insert(0,normal)
        if normal.find('{'+M+'}nor') is None:ET.SubElement(normal,'{'+M+'}nor')
        for key,font in [('eastAsia',spec.get('font_cjk','SimSun')),('ascii',spec['font']),('hAnsi',spec['font'])]:fonts.set('{'+W+'}'+key,font)
    # Multiline imported formula groups use a stable 1.5-line matrix setting.
    # The supplied author template defines no explicit multiline equation gap.
    for tag in ('mPr','eqArrPr'):
        for properties in doc.element.body.findall('.//{'+M+'}'+tag):
            for key,value in [('rSpRule','4'),('rSp','3')]:
                setting=properties.find('{'+M+'}'+key)
                if setting is None:setting=ET.SubElement(properties,'{'+M+'}'+key)
                setting.set('{'+M+'}val',value)
    doc.save(path)


class PandocDocument:
    def __init__(self,root:Path,comments,review=False,visual_review=False):
        self.root=root;self.review=review;self.visual_review=visual_review
        self.styles={};self.comments={str(c['id']):c for c in comments if not c.get('resolved')}
        self.assets={};self.counter=0

    def style(self,marks):
        if not marks:return ''
        key='RW'+str(len(self.styles)+1).zfill(5);self.styles[key]=marks;return key

    def inlines(self,nodes):
        out=[]
        for node in nodes:
            kind=node.get('type');attrs=node.get('attrs',{});marks=node.get('marks',[])
            deleted=next((m for m in marks if m['type']=='deletion'),None)
            if deleted and not self.review:continue
            if kind=='text':
                pieces=re.split(r'(\s+)',node.get('text',''));inline=[]
                for part in pieces:
                    if not part:continue
                    inline.append({'t':'Space'} if part.isspace() else {'t':'Str','c':part})
            elif kind=='hardBreak':inline=[{'t':'LineBreak'}]
            elif kind=='citation':inline=self.inlines([{'type':'text','text':'['+str(attrs.get('number','?'))+']'}])
            elif kind in ('inlineMath','blockMath'):
                inline=[{'t':'Math','c':[{'t':'DisplayMath' if kind=='blockMath' else 'InlineMath'},attrs.get('latex','')]}]
            else:inline=self.inlines(node.get('content',[]))
            for mark in marks:
                mk=mark['type'];attr=mark.get('attrs',{})
                wrap={'bold':'Strong','italic':'Emph','strike':'Strikeout','underline':'Underline','subscript':'Subscript','superscript':'Superscript','code':'Code'}.get(mk)
                if wrap=='Code':inline=[{'t':'Code','c':[['',[],[]],node.get('text','')]}]
                elif wrap:inline=[{'t':wrap,'c':inline}]
                elif mk=='link':inline=[{'t':'Link','c':[['',[],[]],inline,[attr.get('href',''),attr.get('title','') or '']]}]
            review_marks=[m for m in marks if m['type'] in ('insertion','deletion','formatChange','commentAnchor')]
            if review_marks and self.review:
                style=self.style(review_marks);inline=[{'t':'Span','c':[['',[],[['custom-style',style]]],inline]}]
            out+=inline
        return out

    def asset(self,url):
        match=re.search(r'/manuscript/assets/([^/?#]+)',url)
        if match:file=child(self.root/'manuscript/assets',match[1])
        elif re.match(r'^/research/api/projects/[a-f0-9]{32}/file\?path=',url):
            from urllib.parse import urlparse,parse_qs
            file=child(self.root/'project',parse_qs(urlparse(url).query).get('path',[''])[0])
        else:raise ValueError('导出的图片需要来自当前稿件或工作台')
        if not file.is_file():raise ValueError('稿件图片原文不存在')
        self.assets[file.name]=file;return file

    def blocks(self,nodes):
        out=[]
        for node in nodes:
            kind=node.get('type');attrs=node.get('attrs',{});children=node.get('content',[])
            if kind in ('paragraph','heading'):
                inline=self.inlines(children)
                out.append({'t':'Header','c':[int(attrs.get('level',1)),['',[],[]],inline]} if kind=='heading' else {'t':'Para','c':inline})
            elif kind=='blockMath':out.append({'t':'Para','c':self.inlines([node])})
            elif kind=='image':
                file=self.asset(attrs.get('src',''));width=max(10,min(100,float(attrs.get('width') or 90)))
                caption={'t':'Div','c':[['',[],[['custom-style','Caption']]],[{'t':'Para','c':self.inlines([{'type':'text','text':attrs.get('title','')}])}]]}
                if attrs.get('title') and attrs.get('captionPosition')=='top':out.append(caption)
                out.append({'t':'Para','c':[{'t':'Image','c':[['',[],[['width',str(width)+'%']]],self.inlines([{'type':'text','text':attrs.get('alt') or ''}]),[str(file),attrs.get('title') or '']]}]})
                if attrs.get('title') and attrs.get('captionPosition')!='top':out.append(caption)
            elif kind in ('bulletList','orderedList'):
                items=[self.blocks(n.get('content',[])) for n in children]
                out.append({'t':'BulletList','c':items} if kind=='bulletList' else {'t':'OrderedList','c':[[attrs.get('start',1),{'t':'Decimal'},{'t':'Period'}],items]})
            elif kind=='blockquote':out.append({'t':'BlockQuote','c':self.blocks(children)})
            elif kind=='codeBlock':out.append({'t':'CodeBlock','c':[['',[attrs.get('language') or ''],[]],text(node)]})
            elif kind=='horizontalRule':out.append({'t':'HorizontalRule'})
            elif kind=='table':
                rows=[]
                from .cas_typesetting import table_layout,table_header_rows
                grid,cols,widths,aligns,authored=table_layout(node)
                for row in children:
                    cells=[]
                    for cell in row.get('content',[]):
                        ca=cell.get('attrs',{});cells.append([['',[],[]],{'t':'AlignDefault'},ca.get('rowspan',1),ca.get('colspan',1),self.blocks(cell.get('content',[]))])
                    rows.append([['',[],[]],cells])
                from .equation_layout import is_equation_table
                equation=is_equation_table(node)
                head_count=table_header_rows(node)
                out.append({'t':'Table','c':[['',[],[]],[None,[]],([[{'t':'AlignRight' if i==cols-1 else 'AlignCenter'},{'t':'ColWidth','c':([.11,.78,.11] if cols==3 else [.88,.12])[i]}] for i in range(cols)] if equation else [[{'t':{'left':'AlignLeft','center':'AlignCenter','right':'AlignRight'}.get(aligns[i],'AlignDefault')},{'t':'ColWidth','c':widths[i]}] for i in range(cols)]),[['',[],[]],rows[:head_count]],[[['',[],[]],0,[],rows[head_count:]]],[['',[],[]],[]]]})
            else:out+=self.blocks(children)
        return out

    def build(self,doc,title):
        return {'pandoc-api-version':pandoc_api_version(),'meta':{'title':{'t':'MetaInlines','c':[{'t':'Str','c':title}]}},'blocks':self.blocks(doc.get('content',[]))}


def qn(tag):return '{'+W+'}'+tag


def word_review(path:Path,conversion:PandocDocument):
    with zipfile.ZipFile(path) as z:parts={n:z.read(n) for n in z.namelist()}
    document=ET.fromstring(parts['word/document.xml']);comments=ET.Element(qn('comments'),nsmap={'w':W})
    ids={key:i for i,key in enumerate(conversion.comments)};anchors={};revision=1
    for run in list(document.findall('.//w:r',NS)):
        style=run.find('w:rPr/w:rStyle',NS)
        if style is None:continue
        marks=conversion.styles.get(style.get(qn('val')))
        if not marks:continue
        style.getparent().remove(style)
        for mark in marks:
            typ=mark['type'];a=mark.get('attrs',{})
            if typ=='commentAnchor':
                cid=str(a.get('id',''))
                if cid in ids:anchors.setdefault(cid,[]).append(run)
            elif typ in ('insertion','deletion'):
                if conversion.visual_review:
                    props=run.find('w:rPr',NS)
                    if props is None:props=ET.Element(qn('rPr'));run.insert(0,props)
                    color=ET.SubElement(props,qn('color'));color.set(qn('val'),'B02F29' if typ=='deletion' else '1E7254')
                    flag=ET.SubElement(props,qn('strike') if typ=='deletion' else qn('u'));flag.set(qn('val'),'true' if typ=='deletion' else 'single')
                    continue
                parent=run.getparent();position=parent.index(run);parent.remove(run)
                change=ET.Element(qn('del' if typ=='deletion' else 'ins'))
                change.set(qn('id'),str(revision));revision+=1
                change.set(qn('author'),str(a.get('authorName') or '审阅者'))
                change.set(qn('date'),str(a.get('timestamp') or datetime.now(timezone.utc).isoformat()))
                if typ=='deletion':
                    for t in run.findall('.//w:t',NS):t.tag=qn('delText')
                change.append(run);parent.insert(position,change)
    for cid,comment in conversion.comments.items():
        value=ET.SubElement(comments,qn('comment'));value.set(qn('id'),str(ids[cid]));value.set(qn('author'),comment.get('author','审阅者'));value.set(qn('date'),comment.get('created') or datetime.now(timezone.utc).isoformat())
        p=ET.SubElement(value,qn('p'));r=ET.SubElement(p,qn('r'));t=ET.SubElement(r,qn('t'));t.text=comment.get('body','')
        runs=anchors.get(cid,[])
        if not runs:
            for run in document.findall('.//w:r',NS):
                if comment.get('quote') and comment['quote'] in ''.join(run.itertext()):runs=[run];break
        if not runs:
            first=document.find('.//w:body/w:p/w:r',NS)
            if first is not None:runs=[first]
        if runs:
            first,last=runs[0],runs[-1]
            start=ET.Element(qn('commentRangeStart'));start.set(qn('id'),str(ids[cid]));first.addprevious(start)
            end=ET.Element(qn('commentRangeEnd'));end.set(qn('id'),str(ids[cid]));last.addnext(end)
            ref=ET.Element(qn('r'));r=ET.SubElement(ref,qn('commentReference'));r.set(qn('id'),str(ids[cid]));end.addnext(ref)
    if conversion.comments:
        parts['word/comments.xml']=ET.tostring(comments,xml_declaration=True,encoding='UTF-8',standalone=True)
        rels=ET.fromstring(parts['word/_rels/document.xml.rels']);ET.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',Id='rIdReviewComments',Type=R+'/comments',Target='comments.xml')
        parts['word/_rels/document.xml.rels']=ET.tostring(rels,xml_declaration=True,encoding='UTF-8')
        types=ET.fromstring(parts['[Content_Types].xml']);ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',PartName='/word/comments.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
        parts['[Content_Types].xml']=ET.tostring(types,xml_declaration=True,encoding='UTF-8')
    parts['word/document.xml']=ET.tostring(document,xml_declaration=True,encoding='UTF-8',standalone=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)


def export_manuscript(root,manuscript,format,review=False,templates=None):
    if format not in ('docx','pdf','tex'):raise ValueError('选择 Word、PDF 或 TeX')
    root=Path(root);temp=Path(tempfile.mkdtemp(prefix='export-',dir=root/'manuscript'))
    try:
        reference=make_reference(Path(templates or root/'.workbench/styles'),manuscript.get('template','elsevier'),manuscript.get('columns',2))
        from docx import Document
        from .math_layout import export_math_document
        section=Document(reference).sections[0]
        columns=manuscript.get('columns',2);spec=template_info(manuscript.get('template','elsevier'))
        if columns not in spec.get('columns',[1]):columns=spec.get('columns',[1])[0]
        available=(section.page_width-section.left_margin-section.right_margin)/12700
        content=export_math_document(manuscript['content'],spec['id'],columns,available)
        converter=PandocDocument(root,manuscript.get('comments',[]),review,format=='pdf')
        ast=converter.build(content,manuscript.get('title') or '研究稿件')
        source=temp/'document.json';source.write_text(json.dumps(ast,ensure_ascii=False),encoding='utf8')
        docx=temp/'manuscript.docx'
        conversion=subprocess.run([pandoc(),str(source),'-f','json','-t','docx','--reference-doc',str(reference),'-o',str(docx)],check=True,capture_output=True,timeout=60)
        if b'Could not convert TeX math' in conversion.stderr:raise ValueError('公式转换未完成：'+conversion.stderr.decode('utf8',errors='replace')[-1200:])
        format_word(docx,manuscript.get('template','elsevier'),content,columns)
        if review:word_review(docx,converter)
        if format=='docx':return docx.read_bytes(),'docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if format=='tex':
            # Preserve portable image names and review choices in an ordinary article.
            if review:
                def visible_changes(value):
                    if isinstance(value,dict):
                        if value.get('t')=='Span':
                            attrs=dict(value['c'][0][2]);marks=converter.styles.get(attrs.get('custom-style'),[])
                            for mark in marks:
                                if mark['type'] in ('insertion','deletion'):
                                    value={'t':'Strikeout' if mark['type']=='deletion' else 'Underline','c':value['c'][1]}
                                    break
                        return {k:visible_changes(v) for k,v in value.items()}
                    if isinstance(value,list):return [visible_changes(v) for v in value]
                    return value
                ast=visible_changes(ast);source.write_text(json.dumps(ast,ensure_ascii=False),encoding='utf8')
            tex=temp/'manuscript.tex';subprocess.run([pandoc(),str(source),'-f','json','-t','latex','--standalone','-o',str(tex)],check=True,capture_output=True,timeout=45)
            result=tex.read_text(encoding='utf8')
            for name,file in converter.assets.items():result=result.replace(str(file),'assets/'+name)
            if review:
                notes='\n'.join('% 批注 '+c.get('quote','')+': '+c.get('body','') for c in converter.comments.values())
                result=result.replace('\\end{document}',notes+'\n\\end{document}')
                # A sidecar preserves exact review records even for unsupported TeX marks.
            if converter.assets or review:
                bundle=temp/'manuscript-tex.zip'
                with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
                    z.writestr('manuscript.tex',result)
                    if review:z.writestr('review.json',json.dumps({'comments':manuscript.get('comments',[]),'document':manuscript['content']},ensure_ascii=False,indent=2))
                    for name,file in converter.assets.items():z.write(file,'assets/'+name)
                return bundle.read_bytes(),'zip','application/zip'
            return result.encode(),'tex','application/x-tex'
        profile=temp/'lo-profile'
        pdf=temp/'manuscript.pdf'
        spec=template_info(manuscript.get('template','elsevier'))
        letter_font=spec.get('math_letter_font',spec['font'] if spec.get('language')=='zh-CN' else spec.get('math_font',spec['font']))
        p=subprocess.run(['/usr/bin/python3',str(Path(__file__).with_name('uno_pdf_worker.py')),str(docx),str(pdf),'--profile',str(profile),'--font',spec['font'],'--math-font',letter_font,'--cjk',spec.get('font_cjk',spec['font']),'--size',str(spec['size']),*(['--script-percent',str(spec['math_script_percent'])] if spec.get('math_script_percent') else [])],capture_output=True,text=True,timeout=180)
        if p.returncode==0:
            print('Word PDF mathematical layout: '+p.stdout.strip(),flush=True)
        if p.returncode or not pdf.is_file():raise RuntimeError('PDF 排版未完成：'+p.stderr[-400:])
        if review and converter.comments:
            import fitz
            document=fitz.open(pdf)
            for comment in converter.comments.values():
                quote=comment.get('quote','')[:120]
                found=False
                for page in document:
                    hits=page.search_for(quote) if quote else []
                    if hits:
                        note=page.add_highlight_annot(hits);note.set_info(content=comment.get('body',''),title=comment.get('author','审阅者'));note.update();found=True;break
                if not found:
                    page=document[0];note=page.add_text_annot((page.rect.width-22,35+18*list(converter.comments).index(str(comment['id']))),comment.get('body',''));note.set_info(title=comment.get('author','审阅者'));note.update()
            document.save(temp/'annotated.pdf');document.close();pdf=temp/'annotated.pdf'
        return pdf.read_bytes(),'pdf','application/pdf'
    finally:shutil.rmtree(temp)


def import_manuscript(root,pid,data,filename,media_prefix=''):
    """Pandoc retains Word/TeX equations as editable math nodes, not screenshots."""
    root=Path(root);suffix=Path(filename).suffix.lower();readers={'.docx':'docx','.md':'markdown','.txt':'markdown','.tex':'latex','.html':'html'}
    if suffix not in readers:raise ValueError('导入Word、Markdown或TeX稿件；PDF请在文献区阅读原版')
    temp=Path(tempfile.mkdtemp(prefix='import-',dir=root/'manuscript'))
    try:
        source=temp/('source'+suffix);source.write_bytes(data)
        p=subprocess.run([pandoc(),str(source),'-f',readers[suffix],'-t','json','--track-changes=all','--extract-media='+str(temp/'media')],capture_output=True,check=True,timeout=60)
        ast=json.loads(p.stdout)
        def inline(items,marks=None):
            result=[];marks=marks or []
            for item in items:
                typ=item['t'];c=item.get('c')
                if typ in ('Str','Space','SoftBreak','LineBreak'):
                    value=c if typ=='Str' else '\n' if typ=='LineBreak' else ' '
                    node={'type':'text','text':value}
                    if marks:node['marks']=deepcopy(marks)
                    result.append(node)
                elif typ=='Math':result.append({'type':'inlineMath','attrs':{'latex':c[1]}})
                elif typ=='Image':
                    file=Path(c[2][0]);
                    if not file.is_absolute():file=temp/file
                    if file.is_file() and file.resolve().is_relative_to(temp.resolve()):
                        name=(media_prefix+'-'+file.name) if media_prefix else uuid.uuid4().hex+file.suffix;dest=root/'manuscript/assets'/name;shutil.copyfile(file,dest)
                        result.append({'type':'image','attrs':{'src':f'/research/api/projects/{pid}/manuscript/assets/{name}','alt':''.join(x.get('c','') for x in c[1] if x['t']=='Str'),'title':c[2][1]}})
                elif typ=='Span':
                    classes=c[0][1];extra=deepcopy(marks);attrs=dict(c[0][2])
                    if 'insertion' in classes or 'deletion' in classes:
                        extra.append({'type':'insertion' if 'insertion' in classes else 'deletion','attrs':{'changeId':uuid.uuid4().hex,'authorName':attrs.get('author','导入修订'),'authorId':'imported','authorColor':'#356b58','timestamp':attrs.get('date')}})
                    result+=inline(c[1],extra)
                elif typ=='Link':result+=inline(c[1],marks+[{'type':'link','attrs':{'href':c[2][0]}}])
                elif typ=='Code':result.append({'type':'text','text':c[1],'marks':marks+[{'type':'code'}]})
                elif typ in ('Strong','Emph','Strikeout','Underline','Subscript','Superscript'):
                    result+=inline(c,marks+[{'type':{'Strong':'bold','Emph':'italic','Strikeout':'strike','Underline':'underline','Subscript':'subscript','Superscript':'superscript'}[typ]}])
                elif typ=='Quoted':result+=inline(c[1],marks)
            return result
        def blocks(items):
            result=[]
            for item in items:
                typ=item['t'];c=item.get('c')
                if typ in ('Para','Plain','Header'):
                    values=c[2] if typ=='Header' else c
                    if len(values)==1 and values[0]['t']=='Math' and values[0]['c'][0]['t']=='DisplayMath':result.append({'type':'blockMath','attrs':{'latex':values[0]['c'][1]}});continue
                    pieces=inline(values);paragraph=[]
                    for node in pieces:
                        if node['type']=='image':
                            if paragraph:result.append({'type':'paragraph','content':paragraph});paragraph=[]
                            result.append(node)
                        else:paragraph.append(node)
                    if paragraph or not pieces:
                        result.append({'type':'heading','attrs':{'level':c[0]},'content':paragraph} if typ=='Header' else {'type':'paragraph','content':paragraph})
                elif typ in ('BulletList','OrderedList'):
                    rows=c if typ=='BulletList' else c[1]
                    result.append({'type':'bulletList' if typ=='BulletList' else 'orderedList','content':[{'type':'listItem','content':blocks(r)} for r in rows]})
                elif typ=='CodeBlock':result.append({'type':'codeBlock','attrs':{'language':c[0][1][0] if c[0][1] else None},'content':[{'type':'text','text':c[1]}]})
                elif typ=='BlockQuote':result.append({'type':'blockquote','content':blocks(c)})
                elif typ=='Div':result+=blocks(c[1])
                elif typ=='Figure':
                    figure_blocks=blocks(c[2]);caption=' '.join(text(n) for n in blocks(c[1][1]))
                    for node in figure_blocks:
                        if node.get('type')=='image' and caption:node['attrs']['title']=caption
                    result+=figure_blocks
                elif typ=='HorizontalRule':result.append({'type':'horizontalRule'})
                elif typ=='Table':
                    rows=list(c[3][1])
                    for body in c[4]:rows+=body[2]+body[3]
                    rows+=c[5][1];converted=[]
                    for ri,row in enumerate(rows):
                        cells=[]
                        for cell in row[1]:cells.append({'type':'tableHeader' if ri<len(c[3][1]) else 'tableCell','attrs':{'rowspan':cell[2],'colspan':cell[3]},'content':blocks(cell[4]) or [{'type':'paragraph'}]})
                        converted.append({'type':'tableRow','content':cells})
                    result.append({'type':'table','content':converted})
            cleaned=[]
            for node in result:
                if node.get('type')=='paragraph' and cleaned and cleaned[-1].get('type')=='image':
                    caption=cleaned[-1].get('attrs',{}).get('title','').strip()
                    if caption and text(node).strip()==caption:continue
                cleaned.append(node)
            return cleaned
        return {'type':'doc','content':blocks(ast['blocks']) or [{'type':'paragraph'}]}
    finally:shutil.rmtree(temp)
