"""Finite slide geometry checks and a check of the actual rendered PDF."""
from copy import deepcopy
import math,re,unicodedata


def units(value):
    return sum(1 if ord(c)>255 else .56 for c in str(value))


def lines(value,width_pt,font_pt):
    columns=max(1,width_pt/font_pt*.94)
    return sum(max(1,math.ceil(units(line)/columns))+.16 for line in str(value).splitlines()) or 0


def chunks(value,width_pt,height_pt,font_pt):
    value=str(value).strip();capacity=height_pt/(font_pt*1.25)
    if not value:return ['']
    result=[]
    while value:
        if lines(value,width_pt,font_pt)<=capacity:result.append(value);break
        low,high=1,len(value)
        while low<high:
            mid=(low+high+1)//2
            if lines(value[:mid],width_pt,font_pt)<=capacity:low=mid
            else:high=mid-1
        cut=low
        for i in range(cut-1,max(0,int(cut*.55)),-1):
            if value[i] in '\n。；;.!?':cut=i+1;break
        if cut<2:raise ValueError('当前模板的正文区域过小，请调整模板')
        result.append(value[:cut].strip());value=value[cut:].strip()
    return result


def resolve_template_font_sizes(sample,public_template=False):
    """Keep parsed private-template sizes; identify each missing-size fallback."""
    result={}
    for role,fallback,minimum,maximum in [('title',32,28,40),('body',24,20,24)]:
        raw=(sample.get(role+'_box') or {}).get('font_pt')
        try:value=float(raw)
        except (TypeError,ValueError):value=None
        parsed=value is not None and math.isfinite(value) and value>0
        value=value if parsed else fallback
        origin='parsed_template' if parsed else 'product_fallback'
        if public_template:
            value=min(maximum,max(minimum,value))
            origin='public_product_default' if parsed else 'product_fallback'
        result[role]={'font_pt':value,'origin':origin}
    return result


def layout_sections(plan,manifest):
    """Split excessive density while preserving all text and all referenced assets."""
    width,height=manifest['width'],manifest['height'];out=[]
    from .presentation_catalog import catalog
    template_id=plan.get('visual_template') or manifest.get('name')
    public_template=template_id in {'minimal',*(t['id'] for t in catalog()['templates'])}
    figures={f['id'] for f in plan.get('source_figures',[])};tables={t['id']:t for t in plan.get('source_tables',[])}
    for index,source in enumerate(plan.get('sections') or plan.get('slides') or []):
        section=deepcopy(source);role=section.get('role') or ('cover' if index==0 else 'content')
        sample=manifest['slides'][int(manifest['examples'].get(role,manifest['examples']['content']))-1]
        font_resolution=resolve_template_font_sizes(sample,public_template=public_template)
        title_size=font_resolution['title']['font_pt']
        title_width=width*.88/12700
        if lines(section.get('title',''),title_width,title_size)>2.32:raise ValueError(f'第{index+1}页标题超过两行，请缩短标题并把解释放入备注')
        refs=[]
        for key,available in [('figures',figures),('tables',tables)]:
            for ref in section.get(key,[]):
                identifier=ref if isinstance(ref,str) else ref.get('figure_id' if key=='figures' else 'table_id','')
                if identifier not in available:raise ValueError('幻灯片引用的图表不在原稿中：'+identifier)
                refs.append((key,identifier))
        for asset_index,(key,identifier) in enumerate(refs or [('',None)]):
            current=deepcopy(section);current['role']=role;current['figures']=[];current['tables']=[]
            if key:current[key]=[identifier]
            font=font_resolution['body']['font_pt']
            w=width*.87*(.45 if key=='figures' else 1)/12700
            h=height*.55/12700
            if role in ('cover','section','ending'):h=height*.24/12700
            if key=='tables':h*=.35
            parts=chunks(current.get('content',''),w,h,font)
            row_groups=[None]
            if key=='tables':
                rows=section.get('table_rows') or tables[identifier]['rows']
                if not rows or max(map(len,rows))>7:raise ValueError('宽表需要先选择关键列后再生成PPT')
                row_groups=[rows[:1]+rows[i:i+5] for i in range(1,len(rows),5)] or [rows]
            for n in range(max(len(parts),len(row_groups))):
                part=deepcopy(current);part['content']=parts[n] if n<len(parts) else ''
                part['id']=str(section.get('id') or 'slide-'+str(index+1))+(('-'+str(asset_index+1)+'-'+str(n+1)) if len(refs)>1 or len(parts)>1 or len(row_groups)>1 else '')
                part['_font']=font;part['_title_font']=title_size
                part['font_resolution']=deepcopy(font_resolution)
                if key=='tables':part['_rows']=row_groups[min(n,len(row_groups)-1)];part['table_rows']=part['_rows']
                out.append(part)
    return out


def verify_rendered(path,expected):
    import fitz
    canonical=lambda value:re.sub(r'\s+','',unicodedata.normalize('NFKC',value))
    pdf=fitz.open(path);issues=[];checked=0
    if len(pdf)!=len(expected):issues.append('渲染页数与内容不一致')
    for i,values in enumerate(expected):
        if i>=len(pdf):break
        page=pdf[i];rendered=canonical(page.get_text())
        for value in values:
            if not canonical(value):continue
            checked+=1
            if canonical(value) not in rendered:issues.append(f'第{i+1}页文字未完整渲染：{str(value)[:35]}')
        boxes=[]
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                if line.get('spans'):boxes.append(fitz.Rect(line['bbox']))
                for span in line.get('spans',[]):
                    x0,y0,x1,y1=span['bbox']
                    if x0<-.5 or y0<-.5 or x1>page.rect.width+.5 or y1>page.rect.height+.5:issues.append(f'第{i+1}页文字超出页面')
        for n,box in enumerate(boxes):
            for other in boxes[n+1:]:
                overlap=box&other
                if not overlap.is_empty and overlap.get_area()>min(box.get_area(),other.get_area())*.18:issues.append(f'第{i+1}页文字行发生重叠')
            for img in page.get_images():
                for rect in page.get_image_rects(img[0]):
                    # LibreOffice rasterizes some header bands. These are
                    # intentional decoration behind the heading, not a chart.
                    if rect.y1<page.rect.height*.22 or rect.y0>page.rect.height*.88 or (rect.width>page.rect.width*.95 and rect.height>page.rect.height*.75):continue
                    overlap=box&rect
                    if not overlap.is_empty and overlap.get_area()>box.get_area()*.25:issues.append(f'第{i+1}页正文与图像重叠')
    count=len(pdf);pdf.close()
    if issues:raise ValueError('；'.join(issues[:6]))
    return {'pages':count,'checked_text_blocks':checked,'complete_visible_text':True,'page_bounds':True,'text_line_overlap':False,'content_text_image_overlap':False,'renderer':'LibreOffice PDF + PyMuPDF'}
