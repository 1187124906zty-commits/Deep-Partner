"""Render the actual current manuscript and verify one-column equation exports."""
from pathlib import Path
from io import BytesIO
import json,re,sys
import fitz
from docx import Document
from server.app import store
from server.manuscripts import export_manuscript
from server.journals import compile_preview,crossref_journal

owner='u_731b4f07a23742f0917ac6eb77df5df4';pid='05a893386c09449d88366cf6dfdc825f'
root=store.path(owner,pid);source=store.manuscript(owner,pid);folder=root/'.workbench/template-check';folder.mkdir(exist_ok=True)
translation=source.get('translation');assert translation and not translation['stale'] and translation['prompt_version']==3
source_count=[0]
def count_math(node):
 if node.get('type') in ('inlineMath','blockMath'):source_count[0]+=1
 for child in node.get('content',[]):count_math(child)
count_math(source['content'])
cas_only='--cas-only' in sys.argv
report={'source_revision':source['revision'],'source_math_nodes':source_count[0],'paragraph_translation_segments':translation['segments'],'word':{}}

for label,document,name in [('chinese',{**source,'template':'chinese','columns':2},'中文稿-西北工业大学学报'),('english',{**source,**translation,'template':'elsevier','columns':2,'references':source['references']},'英文稿-CAS')]:
 data=(folder/(label+'.docx')).read_bytes() if cas_only else export_manuscript(root,document,'docx')[0];word=Document(BytesIO(data));math=len(word.element.body.xpath('.//m:oMath'))
 assert math==source_count[0],(label,'Editable mathematical object lost',math,source_count[0])
 (folder/(label+'.docx')).write_bytes(data)
 if not cas_only:store.replace(owner,pid,root/'manuscript/exports'/(name+'.docx'),data,'单栏内公式分行与原生可编辑 Word')
 details={'editable_equations':math,'images':len(word.inline_shapes),'tables':len(word.tables),'sections':len(word.sections),'bytes':len(data)}
 if label=='chinese':
  data=(folder/'chinese.pdf').read_bytes() if cas_only else export_manuscript(root,document,'pdf')[0];(folder/'chinese.pdf').write_bytes(data)
  if not cas_only:store.replace(owner,pid,root/'manuscript/exports'/(name+'.pdf'),data,'中文原生模板 · 公式适应单栏')
  with fitz.open(stream=data,filetype='pdf') as pdf:
   details['pages']=len(pdf);details['replacement_characters']=sum(page.get_text().count('\ufffd') for page in pdf);details['empty_math_placeholders']=sum(page.get_text().count('¿') for page in pdf);details['render_marker_leaks']=sum(len(re.findall(r'wbmathstyle|font serif|nitalic',page.get_text())) for page in pdf);assert details['render_marker_leaks']==0,'Rendering command appeared in mathematical content';cross=[];tags=[]
   assert details['empty_math_placeholders']==0,'Word-to-PDF rendered an empty math placeholder'
   for i,page in enumerate(pdf):
    page_data=page.get_text('dict');page_has_equations=bool(re.search(r'\((?:[1-9]|1[0-6])\)',page.get_text()))
    for b in page_data['blocks']:
     for line in b.get('lines',[]):
      for span in line['spans']:
       if re.fullmatch(r'\((?:3|5|8|9|11|16)\)',span['text'].strip()):
        tags.append({'number':span['text'],'page':i+1,'bounds':span['bbox']});page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(folder/('chinese-equation-page-'+str(i+1)+'.png'))
       if page_has_equations and any(v in span['font'] for v in ('Math','Italic','Symbol')) and span['bbox'][0]<295 and span['bbox'][2]>300:cross.append({'page':i+1,'text':span['text'],'bounds':span['bbox']})
   header_gaps=[]
   for i,page in enumerate(pdf):
    if i==0:continue
    header_spans=[span for block in page.get_text('dict')['blocks'] for line in block.get('lines',[]) for span in line['spans'] if ('西 北 工 业' in span['text'] or 'Journal of Northwestern' in span['text']) and span['bbox'][1]<120]
    if not header_spans:continue
    header_bottom=max(span['bbox'][3] for span in header_spans)
    rules=[]
    for drawing in page.get_drawings():
     rect=drawing['rect']
     if rect.width>400 and rect.height<2 and -1<rect.y0-header_bottom<5:rules.append(float(rect.y1))
    if not rules:continue
    baseline=max(rules)
    starts=[span['bbox'][1] for block in page.get_text('dict')['blocks'] for line in block.get('lines',[]) for span in line['spans'] if span['bbox'][1]>=baseline and span['bbox'][1]<160 and span['size']>=9]
    if starts:
     first_baselines=[span['origin'][1] for block in page.get_text('dict')['blocks'] for line in block.get('lines',[]) for span in line['spans'] if baseline<span['bbox'][1]<min(starts)+2 and span['size']>=9]
     header_gaps.append({'page':i+1,'rule_y':baseline,'first_body_y':min(starts),'gap_pt':min(starts)-baseline,'first_baseline_clearance':min(first_baselines)-baseline if first_baselines else None})
   details['header_to_body_gaps']=header_gaps
   if header_gaps:assert min(gap['gap_pt'] for gap in header_gaps)>1.5 and min(gap['first_baseline_clearance'] for gap in header_gaps if gap['first_baseline_clearance'] is not None)>8,'Native header intersects the first body line'
   details.update(tags=tags,math_spans_crossing_gutter=cross)
   assert not cross,('Mathematics crosses the text gutter',cross)
 report['word'][label]=details;print(label,json.dumps(details,ensure_ascii=False),flush=True)

journal=crossref_journal({'title':'Cement and Concrete Research','publisher':'Elsevier','ISSN':['0008-8846']})
prepared={**source,**translation,'references':source['references']};result=compile_preview(store,owner,pid,prepared,journal,2)
preview=root/'.workbench/journal-preview';log=(preview/'preview.log').read_text(errors='replace');compile_log=(preview/'compile.txt').read_text(errors='replace')
measurements=[(float(a),float(b)) for a,b in re.findall(r'WB-MATH=([0-9.]+)pt;([0-9.]+)pt',log)];scales=[min(1,b/a) for a,b in measurements if a]
assert 'Missing character:' not in compile_log,'The native math font is missing a symbol'
report['cas']={'pages':result['pages'],'template_class':result['template_class'],'equation_measurements':len(measurements),'minimum_equation_scale':min(scales) if scales else None,'glyph_warnings':0}
with fitz.open(preview/'preview.pdf') as pdf:
 text='\n'.join(page.get_text() for page in pdf);report['cas']['remaining_cjk']=len(re.findall(r'[\u4e00-\u9fff]',text));report['cas']['replacement_characters']=text.count('\ufffd')
 for i,page in enumerate(pdf):
  if i==0 or '(8)' in page.get_text() or '(9)' in page.get_text():page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(folder/('cas-equation-page-'+str(i+1)+'.png'))
assert store.manuscript(owner,pid)['content']==source['content'],'Verification changed the original manuscript'
report['source_content_unchanged']=True
(folder/'column-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
