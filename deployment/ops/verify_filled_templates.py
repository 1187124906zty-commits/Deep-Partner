"""Generate and inspect source-styled editable manuscript acceptance artifacts."""
from pathlib import Path
import json,time
import fitz,httpx
from docx import Document
from docx.oxml.ns import qn
from PIL import Image,ImageDraw
from workspace_interactions_fixture import login,CACHE,STATE,ROOT,ORIGIN

def main():
    project=json.loads(STATE.read_text(encoding='utf8'))['project'];prefix='/research/api/projects/'+project['id'];out=CACHE/'filled-templates';out.mkdir(exist_ok=True);jobs=[]
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},trust_env=False,timeout=180) as client:
        login(client)
        for template,language in [('journal-zh','source'),('journal-en','translation')]:
            for fmt in ['docx','pdf']:
                response=client.post(prefix+'/manuscript/export',json={'format':fmt,'template':template,'columns':2 if template=='journal-zh' else 1,'language':language,'filename':template+'-filled.'+fmt,'preview':True});response.raise_for_status();jobs.append({'template':template,'language':language,'format':fmt,'job_id':response.json()['job_id']})
        print('Four filled-template artifacts queued',flush=True);deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            rows=client.get(prefix+'/jobs').json()['jobs']
            for item in jobs:
                if 'path' in item:continue
                job=next(row for row in rows if row['id']==item['job_id'])
                if job['status']=='failed':raise RuntimeError(job['error'])
                if job['status']=='completed':
                    response=client.get(job['result']['url']);response.raise_for_status();path=out/(item['template']+'-filled.'+item['format']);path.write_bytes(response.content);item.update(path=str(path),bytes=len(response.content),result=job['result']);print('Saved '+path.name,flush=True)
            if all('path' in row for row in jobs):break
            time.sleep(1)
        else:raise RuntimeError('Template export exceeded bound')
    report={'items':jobs,'all_generated':True,'model_calls':0,'native_reference_version':3}
    for name in ['journal-zh','journal-en']:
        document=Document(out/(name+'-filled.docx'));pdf=fitz.open(out/(name+'-filled.pdf'));tiles=[]
        for index,page in enumerate(pdf):
            pix=page.get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False);pix.save(out/(name+'-page-'+str(index+1)+'.png'));im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((370,500));tile=Image.new('RGB',(390,530),'#ddd');tile.paste(im,((390-im.width)//2,10));ImageDraw.Draw(tile).text((10,512),f'{name} | Page {index+1}/{len(pdf)}',fill='black');tiles.append(tile)
        columns=min(len(tiles),4);sheet=Image.new('RGB',(390*columns,530*((len(tiles)+columns-1)//columns)),'white')
        for index,tile in enumerate(tiles):sheet.paste(tile,((index%columns)*390,(index//columns)*530))
        sheet.save(out/(name+'-all-pages.png'))
        title_size=document.styles['Title'].font.size.pt
        bibliography_size=document.styles['Bibliography'].font.size.pt
        math=document._element.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')
        assert len(math)==1
        assert document.styles['Title'].element.find('.//'+qn('w:vertAlign')) is None
        assert bibliography_size==(7.5 if name=='journal-zh' else 12)
        spans=[span for page in pdf for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans']]
        title='阅读与排版验收' if name=='journal-zh' else 'Bilingual interaction fixture'
        title_spans=[span for span in spans if title in span['text']]
        assert title_spans and abs(title_spans[0]['size']-title_size)<.6,(name,title_size,title_spans)
        assert all(span['bbox'][0]>=-1 and span['bbox'][2]<=pdf[0].rect.width+1 for span in spans)
        if name=='journal-zh':
            # Source and output retain two body columns. Equations must remain
            # entirely to one side of the column gutter.
            gutter_left=pdf[0].rect.width/2-9;gutter_right=pdf[0].rect.width/2+9
            math_lines=[line for page in pdf for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] if any('∇' in span['text'] or '∂' in span['text'] for span in line['spans'])]
            assert math_lines and all(line['bbox'][2]<=gutter_right or line['bbox'][0]>=gutter_left for line in math_lines)
        report[name]={'pages':len(pdf),'title_font_pt':title_size,'rendered_title_pt':title_spans[0]['size'],'bibliography_font_pt':bibliography_size,'editable_equations':len(math),'body_columns':document.sections[-1]._sectPr.find(qn('w:cols')).get(qn('w:num')),'line_numbers':document.sections[-1]._sectPr.find(qn('w:lnNumType')) is not None,'all_text_inside_page_width':True,'equation_stays_in_one_column':True,'contact_sheet':str(out/(name+'-all-pages.png'))}
    report['passed']=True
    (ROOT/'reports/workspace-interactions-filled-templates.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='items'},ensure_ascii=False))

if __name__=='__main__':main()
