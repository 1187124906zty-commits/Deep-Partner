"""Read real PPTX masters and example pages; fill editable slides from a plan."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR
from collections import Counter
from lxml import etree as ET
from .storage import atomic_json,child

ROLES={'cover':'封面','outline':'目录','section':'章节','content':'正文','two_column':'对照','ending':'结束'}


A='http://schemas.openxmlformats.org/drawingml/2006/main'


def template_palette(path):
    with zipfile.ZipFile(path) as archive:
        theme=ET.fromstring(archive.read('ppt/theme/theme1.xml'))
    scheme=theme.find('.//{'+A+'}clrScheme')
    colors={ET.QName(n).localname:(n[0].get('lastClr') or n[0].get('val')) for n in scheme}
    for key,target in [('tx1','dk1'),('tx2','dk2'),('bg1','lt1'),('bg2','lt2')]:colors[key]=colors[target]
    return colors


def shape_info(shape,palette=None):
    text=shape.text if shape.has_text_frame else ''
    placeholder=None
    if shape.is_placeholder:
        placeholder={'idx':shape.placeholder_format.idx,'type':str(shape.placeholder_format.type)}
    sizes=[];latin=Counter();east_asian=Counter();colors=Counter();weights=Counter()
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                if run.font.size:sizes.append(run.font.size.pt)
                props=run._r.rPr
                if props is None:continue
                weight=max(1,len(run.text))
                for script,count in [('latin',latin),('ea',east_asian)]:
                    node=props.find('{'+A+'}'+script)
                    if node is not None and node.get('typeface') and not node.get('typeface').startswith('+'):count[node.get('typeface')]+=weight
                color=props.find('{'+A+'}solidFill')
                if color is not None and len(color):
                    node=color[0];value=node.get('val')
                    if ET.QName(node).localname=='schemeClr':value=(palette or {}).get(value)
                    if value and re.fullmatch(r'[A-Fa-f0-9]{6}',value):colors[value.upper()]+=weight
                if props.get('b') is not None:weights[props.get('b')=='1']+=weight
    face=latin.most_common(1)[0][0] if latin else 'Times New Roman'
    cjk=east_asian.most_common(1)[0][0] if east_asian else face if re.search('[\u4e00-\u9fff]',face) else '微软雅黑'
    if re.search('[\u4e00-\u9fff]',face):face='Times New Roman'
    return {'id':shape.shape_id,'name':shape.name,'text':text,'x':shape.left,'y':shape.top,
            'width':shape.width,'height':shape.height,'placeholder':placeholder,
            'font_pt':max(sizes,default=None),'font_latin':face,'font_cjk':cjk,
            'color':colors.most_common(1)[0][0] if colors else None,
            'bold':weights.most_common(1)[0][0] if weights else False,
            'kind':'image' if shape.shape_type==13 else 'text' if text else 'shape'}


def inspect_template(path,output):
    path=Path(path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    prs=Presentation(path);slides=[];examples={};palette=template_palette(path)
    for index,slide in enumerate(prs.slides):
        shapes=[shape_info(s,palette) for s in slide.shapes];value='\n'.join(s['text'] for s in shapes if s['text']);flat=value.lower()
        if index==0:role='cover'
        elif any(t in flat for t in ['目录','contents','outline','汇报提纲','报告提纲']):role='outline'
        elif index>len(prs.slides)-3 and any(t in flat for t in ['谢谢','感谢','thank','汇报完毕','批评指正']):role='ending'
        elif len(value.strip())<65:role='section'
        else:
            bodies=[s for s in shapes if len(s['text'])>35 and s['y']>prs.slide_height*.2]
            role='two_column' if len(bodies)>1 and max(s['x'] for s in bodies)-min(s['x'] for s in bodies)>prs.slide_width*.3 else 'content'
        title_candidates=[s for s in shapes if s['text'] and s['y']<prs.slide_height*.32]
        title=max(title_candidates,key=lambda s:((s['font_pt'] or 18),-s['y']),default=None)
        body_candidates=[s for s in shapes if s['text'] and s is not title and s['y']>prs.slide_height*.22 and s['y']<prs.slide_height*.82]
        body=max(body_candidates,key=lambda s:len(s['text']),default=None)
        slides.append({'page':index+1,'role':role,'role_label':ROLES[role],'layout':slide.slide_layout.name,
                       'layout_index':list(prs.slide_layouts).index(slide.slide_layout),
                       'title_box':title,'body_box':body,'text':value[:500],'objects':shapes})
        examples.setdefault(role,index+1)
    if path.stem in ('beamer-default','beamer-madrid','metropolis'):
        roles=['cover','outline','section','content','two_column','ending'];examples={role:i+1 for i,role in enumerate(roles)}
        for i,role in enumerate(roles):slides[i].update(role=role,role_label=ROLES[role])
    if 'content' not in examples:examples['content']=min(2,len(slides))
    layouts=[]
    for index,layout in enumerate(prs.slide_layouts):
        layouts.append({'index':index,'name':layout.name,'placeholders':[shape_info(s,palette) for s in layout.placeholders]})
    manifest={'name':path.stem,'width':prs.slide_width,'height':prs.slide_height,
              'slide_count':len(slides),'master_count':len(prs.slide_masters),'layouts':layouts,
              'examples':examples,'slides':slides,'palette':palette,'style_version':2,
              'source_size':path.stat().st_size,'source_modified':path.stat().st_mtime_ns,'preview_ready':False}
    atomic_json(output/'manifest.json',manifest)
    return manifest


def render_presentation(path,output,*,pages=None):
    import fitz
    path=Path(path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    profile=Path(tempfile.mkdtemp(prefix='lo-slide-'))
    try:
        pdf=output/(path.stem+'.pdf')
        # LibreOffice can exit successfully while refusing to overwrite an old
        # PDF. Force a fresh conversion so previews cannot reuse stale pages.
        pdf.unlink(missing_ok=True)
        p=subprocess.run(['libreoffice','-env:UserInstallation='+profile.as_uri(),'--headless','--convert-to','pdf','--outdir',str(output),str(path)],capture_output=True,text=True,timeout=150)
        if p.returncode or not pdf.is_file():raise RuntimeError('PPT 预览转换失败：'+p.stderr[-300:])
        doc=fitz.open(pdf);numbers=pages or list(range(1,len(doc)+1))
        for number in sorted(set(numbers)):
            if number<1 or number>len(doc):continue
            page=doc[number-1];scale=1600/max(page.rect.width,page.rect.height)
            page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).save(output/f'page-{number}.png')
        count=len(doc);doc.close();return {'pages':count,'pdf':str(pdf)}
    finally:shutil.rmtree(profile)


def prepare_template(path,output):
    info=inspect_template(path,output)
    render_presentation(path,output,pages=info['examples'].values())
    info['preview_ready']=True;atomic_json(Path(output)/'manifest.json',info);return info


def create_minimal(path):
    path=Path(path)
    if path.exists():return
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    for role,title in [('cover','研究报告'),('outline','目录'),('section','章节标题'),('content','本页结论'),('two_column','结果比较'),('ending','讨论')]:
        slide=prs.slides.add_slide(prs.slide_layouts[6]);box=slide.shapes.add_textbox(Inches(.75),Inches(.6),Inches(11.8),Inches(1.1))
        box.text=title
        for p in box.text_frame.paragraphs:
            for r in p.runs:r.font.size=Pt(32);r.font.bold=True;r.font.color.rgb=RGBColor.from_string('243A55')
        if role not in ('cover','section','ending'):
            body=slide.shapes.add_textbox(Inches(.8),Inches(2),Inches(11.6),Inches(4.5));body.text='以证据连接研究问题与结论'
            body.text_frame.paragraphs[0].runs[0].font.size=Pt(22)
    path.parent.mkdir(parents=True,exist_ok=True);prs.save(path)


def table_display_text(value):
    value=str(value)
    for name,symbol in {'pm':'±','times':'×','alpha':'α','beta':'β','theta':'θ','eta':'η','rho':'ρ','sigma':'σ','lambda':'λ','pi':'π'}.items():value=re.sub(r'\\'+name+r'(?![A-Za-z])',lambda _:symbol,value)
    value=re.sub(r'\\(?:text|mathrm|operatorname)\{([^{}]*)\}',r'\1',value)
    superscript=str.maketrans('0123456789+-=()','⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾')
    value=re.sub(r'\^\{([\d+\-=()\s]+)\}',lambda m:re.sub(r'\s+','',m[1]).translate(superscript),value)
    subscript=str.maketrans('0123456789aehijklmnoprstuvx','₀₁₂₃₄₅₆₇₈₉ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ')
    value=re.sub(r'_\{([\daehijklmnoprstuvx]+)\}',lambda m:m[1].translate(subscript),value)
    value=re.sub(r'\\(?:left|right)\b','',value);value=re.sub(r'\\[,;! ]',' ',value)
    if '\\' not in value:value=value.replace('{','').replace('}','')
    return value.strip()


def source_elements(document,root):
    from .manuscripts import text
    figures=[];tables=[];counter=0
    def caption_at(nodes,index):
        for nearby in [nodes[index+1:index+3],list(reversed(nodes[max(0,index-2):index]))]:
            for item in nearby:
                value=text(item).strip()
                if not value:continue
                if re.match(r'^(?:图\s*\d+|Fig(?:ure)?\.?\s*\d+)\s*[.．:：、]?',value,re.I):return value
                break
        return ''
    def walk(nodes):
        nonlocal counter
        for index,node in enumerate(nodes):
            if node.get('type')=='image':
                counter+=1;a=node.get('attrs',{});match=re.search(r'/manuscript/assets/([^/?]+)',a.get('src',''))
                if match:
                    file=child(Path(root)/'manuscript/assets',match[1])
                    if file.is_file():figures.append({'id':'Figure '+str(len(figures)+1),'path':str(file),'caption':a.get('title') or caption_at(nodes,index) or a.get('alt') or '研究图表'})
            if node.get('type')=='table':
                original=[[text(cell) for cell in row.get('content',[])] for row in node.get('content',[])]
                def has_math(item):return item.get('type') in ('inlineMath','blockMath') or any(has_math(n) for n in item.get('content',[]))
                equation=len(original)==1 and len(original[0])<=3 and has_math(node) and re.fullmatch(r'\(\s*\d+[a-z]?\s*\)',original[0][-1].strip())
                if not equation:
                    occupied={};columns=0;header_rows=1
                    for ri,row in enumerate(node.get('content',[])):
                        ci=0
                        for cell in row.get('content',[]):
                            while (ri,ci) in occupied:ci+=1
                            attrs=cell.get('attrs',{});rs=max(1,int(attrs.get('rowspan') or 1));cs=max(1,int(attrs.get('colspan') or 1))
                            if ri==0:header_rows=max(header_rows,rs)
                            for dr in range(rs):
                                for dc in range(cs):occupied[ri+dr,ci+dc]=table_display_text(text(cell))
                            ci+=cs;columns=max(columns,ci)
                    grid=[[occupied.get((ri,ci),'') for ci in range(columns)] for ri in range(len(original))]
                    header_rows=min(header_rows,len(grid));headers=[]
                    for ci in range(columns):headers.append(' / '.join(dict.fromkeys(grid[ri][ci] for ri in range(header_rows) if grid[ri][ci])))
                    tables.append({'id':'Table '+str(len(tables)+1),'rows':[headers]+grid[header_rows:],'source_rows':original,'header_rows':header_rows})
            walk(node.get('content',[]))
    walk(document.get('content',[]));return figures,tables


def plan_with_paper2slides(document,title,root,api,request='',length='medium'):
    import sys
    vendor=Path(__file__).resolve().parents[1]/'vendor'
    if str(vendor) not in sys.path:sys.path.insert(0,str(vendor))
    from paper2slides.generator import ContentPlanner,GenerationInput,GenerationConfig,OutputType,SlidesLength,StyleType
    from paper2slides.summary import GeneralContent,OriginalElements,TableInfo,FigureInfo
    from .manuscripts import plain_document
    figures,tables=source_elements(document,root)
    instructions=('按研究自身的论证组织汇报，突出问题、方法为何成立、关键证据与结论之间的关系。'
      '不按论文目录平铺直叙，不添加制作说明或额外小字。每页聚焦一个可展示的认识，具体图表应承担论证。'
      '忠实保留输入稿件的数值、条件和不确定性，没有的研究结果不可编造。输出中文，术语保持原意。'
      '图表引用使用输入中的Figure/Table编号。用户补充：'+request)
    source='# '+title+'\n\n'+plain_document(document)+'\n\n'
    source+='\n'.join(f"{f['id']}: {f['caption']}" for f in figures)
    source+='\n'+ '\n'.join(t['id']+': '+json.dumps(t['rows'],ensure_ascii=False) for t in tables)
    class NativePlanner(ContentPlanner):
        def _truncate(self,value,max_len):return value
        def _fallback_sections(self):raise ValueError('模型返回的汇报结构无法解析；请重试或更换支持JSON输出的模型')
        def _call_multimodal_llm(self,prompt,figure_images):
            from .standards import instructions as output_instructions
            return super()._call_multimodal_llm(output_instructions('slides',instructions+'\n\n'+prompt),figure_images)
    planner=NativePlanner(api_key=api['api_key'],base_url=api.get('base_url'),model=api['model'],max_tokens=12000)
    # Existing Paper2Slides planning/parser; text and original assets stay editable below.
    planner.client=planner.client.with_options(timeout=180,max_retries=1)
    config=GenerationConfig(output_type=OutputType.SLIDES,slides_length=SlidesLength(length),style=StyleType.ACADEMIC)
    import html
    elements=OriginalElements(figures=[FigureInfo(f['id'],f['caption'],f['path']) for f in figures],tables=[TableInfo(t['id'],t['id'],'<table>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in t['rows'])+'</table>') for t in tables])
    result=planner.plan(GenerationInput(config,GeneralContent(content=source),elements))
    plan=result.to_dict();plan.update({'title':title,'planner':'HKUDS/Paper2Slides ContentPlanner','source_figures':figures,'source_tables':tables})
    if not plan.get('sections') or not any(s.get('content','').strip() for s in plan['sections']):raise ValueError('模型没有返回有效的幻灯片正文，请调整要求后重试')
    for i,section in enumerate(plan['sections']):section.setdefault('role','cover' if i==0 else 'ending' if section.get('type')=='ending' else 'content')
    return plan


def title_box(slide,info,width,height):
    template=info.get('title_box') or {}
    return (template.get('x',int(width*.06)),template.get('y',int(height*.06)),
            min(max(template.get('width',0),int(width*.82)),int(width*.92)-template.get('x',int(width*.06))),
            max(template.get('height',int(height*.12)),int(height*.1)))


def font_pair(run,latin='Times New Roman',cjk='微软雅黑'):
    run.font.name=latin
    props=run._r.get_or_add_rPr()
    for script,face in [('latin',latin),('ea',cjk),('cs',latin)]:
        node=props.find('{'+A+'}'+script)
        if node is None:node=ET.SubElement(props,'{'+A+'}'+script)
        node.set('typeface',face)


def add_text(slide,value,x,y,w,h,size=22,bold=False,color='141414',center=False,latin='Times New Roman',cjk='微软雅黑'):
    box=slide.shapes.add_textbox(int(x),int(y),int(w),int(h));frame=box.text_frame
    frame.word_wrap=True;frame.margin_left=frame.margin_right=Inches(.02);frame.margin_top=frame.margin_bottom=0
    lines=str(value).strip().splitlines() or ['']
    for i,line in enumerate(lines):
        p=frame.paragraphs[0] if i==0 else frame.add_paragraph();p.text=line.strip();p.space_after=Pt(size*.16);p.line_spacing=1.18
        if center:p.alignment=PP_ALIGN.CENTER
        for r in p.runs:font_pair(r,latin,cjk);r.font.size=Pt(size);r.font.bold=bold;r.font.color.rgb=RGBColor.from_string(color)
    return box


def make_deck(template,manifest,plan,output):
    from PIL import Image
    prs=Presentation(template);width,height=prs.slide_width,prs.slide_height;original=list(prs.slides)
    from .slide_quality import layout_sections
    sections=layout_sections(plan,manifest);visible_text=[]
    public_visual=None
    if plan.get('visual_template')!='uploaded' and Path(template).stem in ('beamer-default','beamer-madrid','metropolis'):
        from .presentation_catalog import visual
        public_visual=visual(Path(template).stem)
    if not sections:raise ValueError('幻灯片内容为空')
    source_figures={f['id']:f for f in plan.get('source_figures',[])}
    source_tables={t['id']:t for t in plan.get('source_tables',[])}
    for index,section in enumerate(sections):
        role=section.get('role') or ('cover' if index==0 else 'content')
        page=int(manifest['examples'].get(role,manifest['examples'].get('content',1)))
        sample=original[page-1];info=manifest['slides'][page-1]
        slide=prs.slides.add_slide(sample.slide_layout)
        for s in list(slide.shapes):
            if s.is_placeholder:s.element.getparent().remove(s.element)
        # Preserve source decoration, logos and background. Replace example content.
        if sample.background._cSld.bg is not None:slide._element.cSld.insert(0,deepcopy(sample.background._cSld.bg))
        for s in sample.shapes:
            if (s.has_text_frame and s.text.strip()) or s.is_placeholder:continue
            small=s.height<height*.16 or s.top<height*.12 or s.top>height*.85
            if not small:continue
            if s.shape_type==13:
                from io import BytesIO
                slide.shapes.add_picture(BytesIO(s.image.blob),s.left,s.top,s.width,s.height)
            else:
                decoration=deepcopy(s.element);slide.shapes._spTree.insert_element_before(decoration,'p:extLst')
                if public_visual and public_visual['id']=='metropolis' and s.top>height*.96:
                    slide.shapes[-1].width=int(width*(index+1)/len(sections))
        x,y,w,h=title_box(slide,info,width,height)
        title=section.get('title') or plan.get('title','研究报告')
        title_style=info.get('title_box') or {};body_style=info.get('body_box') or {}
        title_size=section['_title_font']
        h=max(h,int(1.2*914400));w=min(w,int(width*.88))
        visible_text.append([title])
        add_text(slide,title,x,y,w,h,title_size,True,title_style.get('color') or '0000CC',role in ('cover','section','ending'),title_style.get('font_latin','Times New Roman'),title_style.get('font_cjk','微软雅黑'))
        content=section.get('content','');body_top=max(y+h+int(height*.025),int(height*.24));body_height=int(height*.84)-body_top
        if role in ('cover','section','ending'):body_top=max(body_top,int(height*.49));body_height=int(height*.77)-body_top
        visible_text[-1].extend(content.splitlines())
        refs=section.get('figures',[]);pics=[]
        for ref in refs:
            key=ref if isinstance(ref,str) else ref.get('figure_id','')
            if key in source_figures:pics.append(source_figures[key])
        trefs=section.get('tables',[]);tab=[]
        for ref in trefs:
            key=ref if isinstance(ref,str) else ref.get('table_id','')
            if key in source_tables:tab.append(source_tables[key])
        font=section['_font']
        body_options={'latin':body_style.get('font_latin','Times New Roman'),'cjk':body_style.get('font_cjk','微软雅黑'),'color':public_visual['palette']['foreground'] if public_visual else '141414'}
        # Limit density by adding continuation pages upstream, not shrinking unreadably.
        left=int(width*.065);usable=int(width*.87)
        if pics:
            text_width=int(usable*.45);add_text(slide,content,left,body_top,text_width,body_height,font,**body_options)
            figure=pics[0];file=Path(figure['path'])
            with Image.open(file) as image:ratio=image.width/image.height
            fx=left+text_width+int(width*.04);fw=usable-text_width-int(width*.04);fh=min(body_height*.88,fw/ratio);pw=fh*ratio
            slide.shapes.add_picture(str(file),int(fx+(fw-pw)/2),int(body_top),width=int(pw),height=int(fh))
            caption=figure['caption']
            from .slide_quality import lines
            if lines(caption,fw/12700,14)>2.3:caption=figure['id'];section['notes']=(section.get('notes','')+'\n'+figure['caption']).strip()
            add_text(slide,caption,fx,body_top+fh+int(height*.02),fw,height*.095,14,**body_options);visible_text[-1].append(caption)
        elif tab:
            rows=section.get('_rows') or tab[0]['rows'];columns=max(len(r) for r in rows)
            th=min(body_height*.6,height*.48);table=slide.shapes.add_table(len(rows),columns,left,body_top,usable,int(th)).table
            for ri,row in enumerate(rows):
                for ci,value in enumerate(row):
                    cell=table.cell(ri,ci);cell.text=str(value);visible_text[-1].append(str(value))
                    palette=public_visual['palette'] if public_visual else {'primary':manifest.get('palette',{}).get('accent1','23373B'),'background':'FFFFFF'}
                    primary=palette['primary'];background=palette['background']
                    tint=''.join(f'{round(int(primary[i:i+2],16)*.06+int(background[i:i+2],16)*.94):02X}' for i in (0,2,4))
                    cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string(primary if ri==0 else tint if ri%2 else background)
                    for p in cell.text_frame.paragraphs:
                        for r in p.runs:font_pair(r,body_options['latin'],body_options['cjk']);r.font.size=Pt(20 if public_visual else font);r.font.bold=ri==0;r.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '141414')
            add_text(slide,content,left,body_top+th+height*.03,usable,body_height-th-height*.03,font,**body_options)
        else:add_text(slide,content,left,body_top,usable,body_height,font,center=role in ('cover','section','ending'),**body_options)
        if hasattr(slide,'notes_slide'):slide.notes_slide.notes_text_frame.text=section.get('notes','') or content
    for s in list(prs.slides._sldIdLst)[:len(original)]:
        prs.part.drop_rel(s.rId);prs.slides._sldIdLst.remove(s)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);prs.save(output)
    # Reuse the previous PPT workflow's exact template-part preservation. The
    # python-pptx serializer normalizes XML even when the master was not edited.
    import posixpath
    with zipfile.ZipFile(template) as before,zipfile.ZipFile(output) as after:
        parts={n:after.read(n) for n in after.namelist()}
        queue=[n for n in before.namelist() if n.startswith(('ppt/slideMasters/','ppt/slideLayouts/','ppt/theme/'))]
        seen=set()
        while queue:
            name=queue.pop()
            if name in seen or name not in before.namelist() or name.endswith('/'):continue
            seen.add(name);parts[name]=before.read(name)
            if name.endswith('.rels'):
                from lxml import etree
                folder=posixpath.dirname(posixpath.dirname(name))
                rels=etree.fromstring(parts[name])
                for rel in rels:
                    if rel.get('TargetMode')=='External':continue
                    target=posixpath.normpath(posixpath.join(folder,rel.get('Target','')))
                    if target in before.namelist() and target not in seen:queue.append(target)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in parts.items():archive.writestr(name,data)
    # Master/layout/theme XML must remain the uploaded template's own parts.
    with zipfile.ZipFile(template) as before,zipfile.ZipFile(output) as after:
        relevant=[n for n in before.namelist() if n.startswith(('ppt/slideMasters/','ppt/slideLayouts/','ppt/theme/')) and n.endswith('.xml')]
        preserved=sum(before.read(n)==after.read(n) for n in relevant)
    plan['sections']=[{k:v for k,v in part.items() if not k.startswith('_')} for part in sections]
    return {'visible_text':visible_text,'min_body_font_pt':min((float(x.get('_font',24)) for x in sections if x.get('content')),default=None),'density_split':True,'slides':len(sections),'native_text':True,'template_parts':len(relevant),'template_parts_preserved':preserved,'all_template_parts_preserved':preserved==len(relevant)}
