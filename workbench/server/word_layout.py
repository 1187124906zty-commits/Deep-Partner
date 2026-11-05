"""Editable Word layouts derived from the supplied publisher templates."""
from copy import deepcopy
from pathlib import Path
import json,re


def columns_element(section,columns,gap=18):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    element=section.find(qn('w:cols'))
    if element is None:element=OxmlElement('w:cols');section.append(element)
    element.set(qn('w:num'),str(columns));element.set(qn('w:space'),str(round(gap*20)))
    for child in list(element):element.remove(child)
    return element


def make_reference(folder,name,columns=2):
    from docx import Document
    from docx.shared import Pt,Mm,RGBColor
    from docx.enum.text import WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from .manuscripts import template_info
    from .storage import atomic_json
    spec=template_info(name);columns=columns if columns in spec.get('columns',[1]) else spec.get('columns',[1])[0]
    if spec.get('native_exact'):
        from .native_word_templates import make_reference as native_reference
        return native_reference(folder,spec,columns)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);path=folder/(spec['id']+'-'+str(columns)+'.docx');stamp=path.with_suffix('.json')
    version={'style_version':14,'specification':spec,'columns':columns}
    if path.exists() and stamp.exists() and json.loads(stamp.read_text())==version:return path
    source=Path(__file__).resolve().parents[1]/'templates/manuscripts/source'/spec['source_file']
    doc=Document() if spec.get('generic') else Document(source);section=deepcopy(doc.sections[0]._sectPr)
    for element in list(doc._element.body):doc._element.body.remove(element)
    doc._element.body.append(section);section=doc.sections[0]
    if spec.get('generic'):
        section.page_width=Mm(210);section.page_height=Mm(297)
        section.left_margin=section.right_margin=section.top_margin=section.bottom_margin=Mm(spec['margin'])
        section.header_distance=section.footer_distance=Mm(12)
    if name=='elsevier':
        section.page_width=Mm(210 if columns==2 else 192);section.page_height=Mm(280 if columns==2 else 262)
        section.left_margin=section.right_margin=Mm(18.1 if columns==2 else 13.7)
        section.top_margin=Mm(19.5 if columns==2 else 19);section.bottom_margin=Mm(18.2 if columns==2 else 19)
    columns_element(section._sectPr,columns,spec.get('column_gap',18))
    if name.startswith('chinese'):
        # Retain the source header's paragraphs and their spacing. Adding a
        # manual line break to the first of two paragraphs created a third line
        # and consumed the native header-to-body gap.
        for header_index,header in enumerate((section.header,section.first_page_header,section.even_page_header)):
            paragraphs=header.paragraphs
            for paragraph in paragraphs:
                paragraph.clear()
                paragraph.paragraph_format.line_spacing=1
                paragraph.paragraph_format.space_before=Pt(0);paragraph.paragraph_format.space_after=Pt(0)
                # Header style inherits Normal. Keep its original single line
                # metrics when the body uses the journal's 15.65pt grid.

            lines=['力 学 进 展'] if name=='chinese-mechanics' else ['中国工程科学'] if name=='chinese-engineering' else ['西 北 工 业 大 学 学 报','Journal of Northwestern Polytechnical University']
            if name=='chinese-mechanics' and header_index==1:lines=[]
            if len(paragraphs)==1:lines=lines[:1]
            for paragraph,value in zip(paragraphs[-len(lines):] if lines else [],lines):
                paragraph.alignment=1
                run=paragraph.add_run(value);run.font.name='Times New Roman';run.font.size=Pt(9)
                run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'SimSun')
    else:
        for part in (section.header,section.first_page_header,section.even_page_header):
            for paragraph in part.paragraphs:paragraph.clear()
    for part in (section.footer,section.first_page_footer,section.even_page_footer):
        for paragraph in part.paragraphs:paragraph.clear()
    for key in ['Normal','Body Text','First Paragraph','Caption','Image Caption','Table Caption','Abstract','Bibliography','Title','Subtitle','Heading 1','Heading 2','Heading 3','Authors','Affiliation']:
        style=doc.styles[key] if key in doc.styles else doc.styles.add_style(key,1)
        style.font.name=spec['font'];style.font.size=Pt(spec['size']);style.font.bold=False;style.font.italic=False;style.font.color.rgb=RGBColor(0,0,0)
        fonts=style.element.get_or_add_rPr().get_or_add_rFonts();fonts.set(qn('w:eastAsia'),spec.get('font_cjk','SimSun'))
        for theme in ('asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme'):fonts.attrib.pop(qn('w:'+theme),None)
        pf=style.paragraph_format;pf.space_before=Pt(0);pf.space_after=Pt(0);pf.line_spacing=Pt(spec['line_pt']) if spec.get('line_pt') else spec['leading'];pf.keep_with_next=False
        if spec.get('line_at_least') and spec.get('line_pt'):pf.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
        pf.first_line_indent=Pt(spec['size']*2 if (name.startswith('chinese') or name=='generic-zh') and key in ('Normal','Body Text','First Paragraph') else 0)
        pf.alignment=3
        for border in style.element.findall('.//'+qn('w:pBdr')):border.getparent().remove(border)
    title=doc.styles['Title'];title.font.size=Pt(spec['title_size']);title.font.bold=spec.get('title_bold',True);title.paragraph_format.alignment=1 if name.startswith('chinese') else 0;title.paragraph_format.space_before=Pt(15.65 if name.startswith('chinese') else 0);title.paragraph_format.space_after=Pt(15.65 if name.startswith('chinese') else 12);title.paragraph_format.line_spacing=1
    title.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),spec.get('title_cjk','SimHei'))
    for level in range(1,4):
        style=doc.styles[f'Heading {level}'];style.font.size=Pt(spec.get('heading_sizes',[spec['heading'],spec['heading']-1,spec['heading']-2])[level-1]);style.font.bold=level<3 or name!='elsevier'
        style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),spec.get('heading_cjk','SimHei'))
        style.paragraph_format.space_before=Pt(spec.get('heading_before',10));style.paragraph_format.space_after=Pt(spec.get('heading_after',4));style.paragraph_format.keep_with_next=True;style.paragraph_format.alignment=0;style.paragraph_format.line_spacing=1
        ppr=style.element.get_or_add_pPr();old=ppr.find(qn('w:numPr'))
        if old is not None:ppr.remove(old)
        numbering=OxmlElement('w:numPr');value=OxmlElement('w:numId');value.set(qn('w:val'),'0');numbering.append(value);ppr.append(numbering)
    for key in ('Caption','Image Caption','Table Caption','Bibliography','Affiliation'):
        style=doc.styles[key];style.font.size=Pt(spec.get('affiliation_size',spec.get('caption_size',9)) if key=='Affiliation' else spec.get('caption_size',9));style.paragraph_format.line_spacing=1;style.paragraph_format.first_line_indent=Pt(0)
        if key not in ('Bibliography',):style.paragraph_format.alignment=1
        style.paragraph_format.space_before=Pt(4);style.paragraph_format.space_after=Pt(4)
    doc.styles['Table Caption'].font.bold=name.startswith('chinese')
    doc.styles['Authors'].font.size=Pt(spec.get('authors_size',14 if name.startswith('chinese') else 12));doc.styles['Authors'].paragraph_format.alignment=1 if name.startswith('chinese') else 0
    if name.startswith('chinese'):doc.styles['Authors'].element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'KaiTi')
    if name=='chinese-mechanics':doc.styles['Authors'].element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'FangSong')
    for target,original in spec.get('style_map',{}).items():
        if original not in doc.styles or target not in doc.styles:continue
        destination=doc.styles[target];source_style=doc.styles[original]
        for tag in ('pPr','rPr'):
            existing=destination.element.find(qn('w:'+tag))
            if existing is not None:destination.element.remove(existing)
            source_part=source_style.element.find(qn('w:'+tag))
            if source_part is not None:destination.element.append(deepcopy(source_part))
        if target.startswith('Heading'):
            ppr=destination.element.get_or_add_pPr();numbering=ppr.find(qn('w:numPr'))
            if numbering is not None:ppr.remove(numbering)
        if source_style.base_style:destination.base_style=source_style.base_style
    for part in (section.footer,section.first_page_footer,section.even_page_footer):
        footer=part.paragraphs[0];footer.alignment=1
        field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    doc.add_paragraph('Reference styles only');doc.save(path);atomic_json(stamp,version);return path


def layout_word(doc,template,content,columns=2):
    """Apply continuous Word sections, without rasterizing text or equations."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
    from .manuscripts import template_info
    spec=template_info(template);columns=columns if columns in spec.get('columns',[1]) else spec.get('columns',[1])[0]
    body=doc._element.body;final=body.sectPr;columns_element(final,columns,spec.get('column_gap',18))
    width=(doc.sections[0].page_width-doc.sections[0].left_margin-doc.sections[0].right_margin)/12700
    gap=spec.get('column_gap',18);column_width=(width-gap*(columns-1))/columns
    paragraphs=doc.paragraphs;body_start=next((p for p in paragraphs[1:] if re.match(r'^\s*1(?:[.、\s]|$)',p.text) and p.style.name.startswith('Heading')),None)
    if body_start is None:body_start=next((p for p in paragraphs[1:] if p.style.name.startswith('Heading') and not re.fullmatch(r'摘要|Abstract|关键词|Keywords?',p.text.strip(),re.I)),None)
    def end_section(after,current_columns):
        paragraph=OxmlElement('w:p');ppr=OxmlElement('w:pPr');paragraph.append(ppr);sect=deepcopy(final)
        columns_element(sect,current_columns,gap);typ=sect.find(qn('w:type'))
        if typ is None:typ=OxmlElement('w:type');sect.insert(0,typ)
        typ.set(qn('w:val'),'continuous');ppr.append(sect)
        spacing=OxmlElement('w:spacing');spacing.set(qn('w:before'),'0');spacing.set(qn('w:after'),'0');spacing.set(qn('w:line'),'20');spacing.set(qn('w:lineRule'),'exact');ppr.append(spacing)
        after.addnext(paragraph);return paragraph
    if columns==2 and body_start is not None:
        previous=body_start._p.getprevious()
        if previous is not None:end_section(previous,1)
    in_body=False
    for paragraph in paragraphs:
        if body_start is not None and paragraph._p is body_start._p:in_body=True
        value=paragraph.text.strip()
        if spec.get('native_exact') and not in_body and re.match(r'^(摘要|Abstract)\b|^摘要[：:\s]',value,re.I):paragraph.style='Abstract'
        if not in_body and paragraph.style.name!='Title' and value and paragraph.style.name not in ('Heading 1','Heading 2','Heading 3'):
            if paragraph is paragraphs[1]:paragraph.style='Authors'
            elif paragraph is paragraphs[2] and not re.match(r'^(摘要|Abstract)',value,re.I):paragraph.style='Affiliation'
            elif template.startswith('chinese'):
                paragraph.paragraph_format.left_indent=Pt(21);paragraph.paragraph_format.right_indent=Pt(21)
                for run in paragraph.runs:run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),spec.get('abstract_cjk','KaiTi'))
        if re.match(r'^(?:图\s*\d|Fig(?:ure)?\.?\s*\d)',value,re.I):paragraph.style='Caption'
        if re.match(r'^(?:表\s*\d|Table\s*\d)',value,re.I):paragraph.style='Table Caption'
        if re.match(r'^\[\d+\]',value):paragraph.style='Bibliography'
    # Large tables and landscape figures use a full-width continuous section.
    widths={};elements=list(body);images=[];source_tables=[]
    def collect(node):
        if node.get('type')=='image':images.append(node.get('attrs',{}))
        if node.get('type')=='table':source_tables.append(node)
        for child in node.get('content',[]):collect(child)
    if content:collect(content)
    table_index=0;image_index=0;equations={}
    for element in elements:
        if element.tag==qn('w:sectPr'):continue
        wide=element.tag==qn('w:tbl') and len(element.findall('./'+qn('w:tblGrid')+'/'+qn('w:gridCol')))>3
        if element.tag==qn('w:tbl'):
            from .equation_layout import is_equation_table
            source_table=source_tables[table_index] if table_index<len(source_tables) else {};table_index+=1
            if is_equation_table(source_table):
                sizes=[]
                def formulas(n):
                    if n.get('type') in ('blockMath','inlineMath'):sizes.append(n.get('attrs',{}).get('_column_font_pt',spec['size']))
                    for child in n.get('content',[]):formulas(child)
                formulas(source_table);equations[element]=min(sizes or [spec['size']]);wide=False
        extents=element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent')
        if extents:wide=any(int(e.get('cx','1'))/max(1,int(e.get('cy','1')))>1.55 for e in extents)
        # Display equations always stay in their text column, including image fallbacks.
        if element in equations or element.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'):wide=False
        available=width if columns==1 or wide else column_width;widths[element]=available
        if wide and columns==2 and body_start is not None:
            prior=element.getprevious()
            if prior is not None:end_section(prior,columns)
            last=element
            if element.tag!=qn('w:tbl'):
                following=element.getnext()
                if following is not None and re.match(r'^(?:图\s*\d|Fig(?:ure)?\.?\s*\d)',''.join(following.itertext()),re.I):last=following
            end_section(last,1)
        for extent in extents:
            attrs=images[image_index] if image_index<len(images) else {};image_index+=1
            cx=int(extent.get('cx','0'));limit=round(available*12700*min(1,max(.1,float(attrs.get('width') or 90)/100)))
            if cx and cx!=limit:
                ratio=limit/cx;extent.set('cx',str(limit));extent.set('cy',str(round(int(extent.get('cy','0'))*ratio)))
                drawing=extent.getparent().getparent()
                for size in drawing.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}ext'):
                    if size.get('cx'):size.set('cx',str(limit));size.set('cy',extent.get('cy'))
    for table in doc.tables:
        available=widths.get(table._tbl,column_width);grid=table._tbl.tblGrid;old=[int(c.get(qn('w:w'),'1')) for c in grid];total=sum(old) or 1
        if table._tbl in equations:
            table.autofit=False
            for run in table._tbl.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}r'):
                properties=run.find(qn('w:rPr'))
                if properties is None:
                    properties=OxmlElement('w:rPr');run.insert(1 if run.find('{http://schemas.openxmlformats.org/officeDocument/2006/math}rPr') is not None else 0,properties)
                size=properties.find(qn('w:sz'))
                if size is None:size=OxmlElement('w:sz');properties.append(size)
                size.set(qn('w:val'),str(round(equations[table._tbl]*2)))
        for c,w in zip(grid,old):c.set(qn('w:w'),str(round(available*20*w/total)))
        tw=table._tbl.tblPr.find(qn('w:tblW'))
        if tw is not None:tw.set(qn('w:type'),'dxa');tw.set(qn('w:w'),str(round(available*20)))
        seen=set()
        for row in table.rows:
            for cell in row.cells:
                if cell._tc in seen:continue
                seen.add(cell._tc)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.line_spacing=1
                    for run in paragraph.runs:run.font.size=Pt(spec['size'] if table._tbl in equations else spec.get('table_size',spec.get('caption_size',9)))
                tc=cell._tc.get_or_add_tcPr()
                if table._tbl in equations:
                    margins=OxmlElement('w:tcMar')
                    for side in ('left','right','top','bottom'):
                        edge=OxmlElement('w:'+side);edge.set(qn('w:w'),'20' if side in ('left','right') else '0');edge.set(qn('w:type'),'dxa');margins.append(edge)
                    old_margins=tc.find(qn('w:tcMar'))
                    if old_margins is not None:tc.remove(old_margins)
                    tc.append(margins)
                    nowrap=tc.find(qn('w:noWrap'))
                    if nowrap is not None:tc.remove(nowrap)
                cw=tc.find(qn('w:tcW'))
                if cw is not None and cw.get(qn('w:type'))=='dxa':cw.set(qn('w:w'),str(round(int(cw.get(qn('w:w'),'1'))*available*20/total)))
    return doc
