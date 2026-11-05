"""PDF-native semantic layout, reading order and immutable mathematical assets."""
from pathlib import Path
import argparse,json,re
import fitz

PARSER_VERSION=3
MATH_FONT=re.compile(r'math|symbol|cmmi|cmsy|cmex|rtxmi|rtxr|txsy|ms[ab]m|stix.*(?:integral|symbol|size)',re.I)


def crop_asset(pdf,page,rectangle,output,stem):
    """Keep a vector PDF/SVG in addition to the high-resolution screen image."""
    rectangle=fitz.Rect(rectangle)&page.rect
    vector=fitz.open();target=vector.new_page(width=rectangle.width,height=rectangle.height)
    target.show_pdf_page(target.rect,pdf,page.number,clip=rectangle)
    vector.save(output/'assets'/(stem+'.pdf'),garbage=3,deflate=True)
    (output/'assets'/(stem+'.svg')).write_text(target.get_svg_image(text_as_path=True),encoding='utf8')
    target.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False).save(output/'assets'/(stem+'.png'));vector.close()
    return 'assets/'+stem+'.png','assets/'+stem+'.svg','assets/'+stem+'.pdf'


def span_is_math(span):
    value=span.get('text','').strip();font=span.get('font','')
    if value.lower() in {'a','i','of','in','to','an','on','by','as','or','is','at','be','we','it','he','do','no','so','am','us','up','if'} and not MATH_FONT.search(font):return False
    return bool(value and (MATH_FONT.search(font) or ((span.get('flags',0)&2 or re.search(r'Ital',font,re.I)) and len(value)<=2 and re.fullmatch(r'[A-Za-zα-ωΑ-Ω0-9_()]+',value))))


def structured_text(box,pdf,page,output,ident):
    raw=[];protected=[];safe=[]
    for line in (box.get('textlines') or []):
        spans=(line.get('spans') or []);line_raw=[];line_safe=[];i=0;last=None
        while i<len(spans):
            span=spans[i];value=span.get('text','');rect=fitz.Rect(span['bbox'])
            gap=last is not None and rect.x0-last>max(1,float(span.get('size',10))*.12)
            if gap and line_raw and not line_raw[-1].endswith((' ','-')) and not re.search(r'[\u4e00-\u9fff]$',line_raw[-1]):line_raw.append(' ');line_safe.append(' ')
            if span_is_math(span):
                start=i;parts=[value];j=i+1
                while j<len(spans):
                    following=spans[j];small=following.get('text','')
                    if not span_is_math(following) and not (len(small.strip())<18 and re.fullmatch(r'[\s0-9+−\-*/=<>≤≥.,;:()\[\]{}]+',small)):break
                    if fitz.Rect(following['bbox']).x0-rect.x1>max(3,float(span.get('size',10))*.5):break
                    rect|=fitz.Rect(following['bbox']);parts.append(small);j+=1
                token='__WBM'+str(len(protected))+'__';image,svg,vector=crop_asset(pdf,page,rect+(-.3,-.3,.3,.3),output,ident+'-m'+str(len(protected)))
                protected.append({'token':token,'text':''.join(parts),'image':image,'svg':svg,'vector':vector,'heightEm':min(3,max(.75,rect.height/max(1,float(span.get('size',10))))),'bounds':{'x':rect.x0/page.rect.width,'y':rect.y0/page.rect.height,'width':rect.width/page.rect.width,'height':rect.height/page.rect.height}})
                line_raw.append(''.join(parts));line_safe.append(token);last=rect.x1;i=j
            else:line_raw.append(value);line_safe.append(value);last=rect.x1;i+=1
        raw.append(''.join(line_raw));safe.append(''.join(line_safe))
    def join(lines):
        value='\n'.join(lines);value=re.sub(r'(?<=[A-Za-z])-\n(?=[a-z])','',value);value=re.sub(r'(?<=[\u4e00-\u9fff])\n(?=[\u4e00-\u9fff])','',value)
        return re.sub(r'\s*\n\s*',' ',value).strip()
    return join(raw),join(safe),protected


def semantic_parse(source,output,first=0,last=0):
    import pymupdf4llm
    output=Path(output);output.mkdir(parents=True,exist_ok=True);(output/'assets').mkdir(exist_ok=True)
    pdf=fitz.open(source);pages=list(range(max(0,first-1),min(last or len(pdf),len(pdf))))
    value=pymupdf4llm.to_json(pdf,pages=pages,use_ocr=False)
    value=json.loads(value) if isinstance(value,str) else value
    blocks=[];warnings=[];layouts=[]
    labels={'page-header':'header','page-footer':'footer','section-header':'paragraph_title','title':'doc_title','formula':'display_formula','picture':'image','caption':'caption','table':'table','list-item':'text','text':'text'}
    for result in value['pages']:
        number=result['page_number'];page=pdf[number-1];width=page.rect.width;height=page.rect.height;left=right=0;text_count=0
        for index,box in enumerate(result.get('boxes',[])):
            rectangle=fitz.Rect([box[k] for k in ('x0','y0','x1','y1')])&page.rect
            if rectangle.is_empty:continue
            ident=f'p{number}-b{index+1}';label=labels.get(box.get('boxclass'), 'text')
            item={'id':ident,'page':number,'label':label,'bounds':{'x':rectangle.x0/width,'y':rectangle.y0/height,'width':rectangle.width/width,'height':rectangle.height/height},'text':''}
            if label in ('display_formula','image','table'):
                image,svg,vector=crop_asset(pdf,page,rectangle,output,ident);item.update(image=image,svg=svg,vector=vector)
                item['text']=' '.join(''.join(s.get('text','') for s in (line.get('spans') or [])) for line in (box.get('textlines') or []))
                if label=='display_formula':item['formulaPolicy']='preserve'
            else:
                raw,safe,protected=structured_text(box,pdf,page,output,ident);item['text']=raw
                if not raw:continue
                text_count+=len(raw)
                if protected:item.update(protectedText=safe,protected=protected)
                if label=='text' and rectangle.width<.62*width:
                    left+=rectangle.x1<.57*width;right+=rectangle.x0>.43*width
            blocks.append(item)
        columns=2 if left>=2 and right>=2 else 1;layouts.append({'page':number,'columns':columns,'width':width,'height':height})
        if text_count<20:warnings.append(f'第 {number} 页文字层稀少；原 PDF 与公式矢量保留，此次未执行 OCR。')
        print(json.dumps({'event':'page','page':number,'total':len(pdf)}),flush=True)
    prose=''.join(b['text'] for b in blocks if b['label']=='text')[:15000];cjk=len(re.findall(r'[\u4e00-\u9fff]',prose))
    source_language='zh-CN' if cjk>max(20,len(prose)*.1) else 'en'
    manifest={'metadata':pdf.metadata or {},'pages':len(pdf),'blocks':blocks,'warnings':warnings,'incompletePages':[],'parserVersion':PARSER_VERSION,'parser':'PyMuPDF4LLM semantic layout / original PDF vector assets','pageLayouts':layouts,'sourceLanguage':source_language,'targetLanguage':'en' if source_language=='zh-CN' else 'zh-CN'}
    if first:manifest['parsedPages']=[i+1 for i in pages]
    markdown=[]
    for block in blocks:
        if block['label'] in ('header','footer'):continue
        markdown.append(f'<!-- page {block["page"]}; {block["id"]} -->')
        if block.get('image'):markdown.append('!['+(block.get('caption') or block['id'])+']('+block['image']+')')
        else:
            text=block.get('protectedText',block['text'])
            for part in block.get('protected',[]):text=text.replace(part['token'],'!['+part['text']+']('+part['svg']+')')
            markdown.append(('## ' if block['label'] in ('doc_title','paragraph_title') else '')+text)
    (output/'paper.md').write_text('\n\n'.join(markdown)+'\n',encoding='utf8')
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf8')
    import hashlib,importlib.metadata
    with open(source,'rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    (output/'paper.md.source.json').write_text(json.dumps({'source':str(source),'sha256':digest,'mode':'offline-semantic-layout','parser_version':PARSER_VERSION,'pymupdf':importlib.metadata.version('pymupdf'),'pymupdf4llm':importlib.metadata.version('pymupdf4llm'),'pages':[i+1 for i in pages],'formula_policy':'original PDF/SVG objects; no OCR'},ensure_ascii=False,indent=2),encoding='utf8')
    pdf.close();return manifest


def parse(source,output,first=0,last=0):
    try:import pymupdf4llm
    except ImportError:pass
    else:return semantic_parse(source,output,first,last)
    output=Path(output);output.mkdir(parents=True,exist_ok=True);(output/'assets').mkdir(exist_ok=True)
    pdf=fitz.open(source);blocks=[];warnings=[]
    for n in range(max(0,first-1),min(last or len(pdf),len(pdf))):
        page=pdf[n];w,h=page.rect.width,page.rect.height
        raw=page.get_text('dict');count=0
        spans=[s for b in raw['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans'] if s['text'].strip()]
        sizes=sorted(s['size'] for s in spans);median=sizes[len(sizes)//2] if sizes else 10
        # Sort each text column in reading order, preserving exact PDF coordinates.
        entries=sorted(raw['blocks'],key=lambda b:(0 if b['bbox'][2]-b['bbox'][0]>.72*w else 1,round(b['bbox'][0]/(w/2)),b['bbox'][1]))
        for b in entries:
            count+=1;ident=f'p{n+1}-b{count}';x0,y0,x1,y1=b['bbox']
            bounds={'x':max(0,x0/w),'y':max(0,y0/h),'width':max(0,min(1,x1/w)-max(0,x0/w)),'height':max(0,min(1,y1/h)-max(0,y0/h))}
            item={'id':ident,'page':n+1,'label':'text','bounds':bounds,'text':''}
            if b['type']==0:
                item['text']='\n'.join(''.join(s['text'] for s in line['spans']) for line in b['lines']).strip()
                if not item['text']:continue
                largest=max((s['size'] for line in b['lines'] for s in line['spans']),default=median)
                if len(item['text'])<220 and (largest>median*1.2 or re.match(r'^\d+(?:\.\d+)*\s+[A-Z]',item['text'])):item['label']='title'
            else:
                item['label']='image';item['image']='assets/'+ident+'.png'
                page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=fitz.Rect(b['bbox']),alpha=False).save(str(output/item['image']))
            blocks.append(item)
        if not spans:warnings.append(f'第 {n+1} 页没有可提取文本；仍可阅读原 PDF，本解析器未执行 OCR。')
        print(json.dumps({'event':'page','page':n+1,'total':len(pdf)}),flush=True)
    manifest={'metadata':pdf.metadata or {},'pages':len(pdf),'blocks':blocks,'warnings':warnings,'incompletePages':[]}
    if first:manifest['parsedPages']=list(range(first,min(last or len(pdf),len(pdf))+1))
    markdown=[]
    for block in blocks:
        if block.get('image'):markdown.append('!['+(block.get('caption') or block['id'])+']('+block['image']+')')
        elif block.get('text'):markdown.append(('## ' if block['label']=='title' else '')+block['text'])
    (output/'paper.md').write_text('\n\n'.join(markdown)+'\n',encoding='utf8')
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--from-page',type=int,default=0);p.add_argument('--to-page',type=int,default=0);a=p.parse_args()
    parse(a.input,a.output,a.from_page,a.to_page)
