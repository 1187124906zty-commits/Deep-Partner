"""Single/two-column source reading order and original-vector mathematics."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import fitz
from server.reader_processor import parse,span_is_math
assert span_is_math({"font":"TimesNewRomanPS-ItalicMT","text":"H"})
assert span_is_math({"font":"rtxmi","text":"x"})
assert not span_is_math({"font":"TimesNewRomanPSMT","text":"moisture transport"})

fonts=Path('/usr/share/fonts/truetype/research-workbench')
with TemporaryDirectory() as folder:
    root=Path(folder);pdf=fitz.open()
    for columns in (1,2):
        page=pdf.new_page(width=595,height=842)
        page.insert_font(fontname='mathfont',fontfile=str(fonts/'STIXTwoMath-Regular.otf'))
        page.insert_text((48,50),'Single column layout' if columns==1 else 'Two column layout',fontsize=18)
        for column in range(columns):
            for i in range(5):
                x=48+column*260;y=100+i*80
                value=('LEFT' if column==0 else 'RIGHT')+' paragraph '+str(i+1)+'. Humidity is measured at five locations. This observation retains the measurement conditions.'
                page.insert_textbox(fitz.Rect(x,y,x+(480 if columns==1 else 225),y+60),value,fontsize=11)
        page.insert_text((80,575),'∇ H = −D ∈ R',fontname='mathfont',fontsize=15)
        page.insert_text((500 if columns==1 else 230,575),'(10)',fontsize=10)
    source=root/'layout.pdf';pdf.save(source);pdf.close()
    output=root/'analysis';manifest=parse(source,output)
    assert manifest['parserVersion']==3 and manifest['sourceLanguage']=='en'
    prose=[b for b in manifest['blocks'] if b['label']=='text' and b['page']==2]
    values=[b['text'] for b in prose];left=[i for i,v in enumerate(values) if 'LEFT paragraph' in v];right=[i for i,v in enumerate(values) if 'RIGHT paragraph' in v]
    assert left and right and max(left)<min(right),'PDF columns interleaved in paragraph order'
    assert any(p['columns']==1 and p['page']==1 for p in manifest['pageLayouts'])
    assert any(p['columns']==2 and p['page']==2 for p in manifest['pageLayouts'])
    protected=[p for b in manifest['blocks'] for p in b.get('protected',[])]
    formulas=[b for b in manifest['blocks'] if b['label']=='display_formula']
    assert protected or formulas,'Mathematical objects were flattened into translated text'
    for item in [*protected,*formulas]:
        assert (output/item['vector']).is_file() and '<svg' in (output/item['svg']).read_text()
        with fitz.open(output/item['vector']) as asset:assert len(asset)==1
    assert 'page 2' in (output/'paper.md').read_text()
    print(json.dumps({'passed':True,'checks':['single-column identification','two-column identification','left-before-right paragraph order','PDF/SVG math assets','page-bound Markdown'],'math_assets':len(protected)+len(formulas)},ensure_ascii=False))
