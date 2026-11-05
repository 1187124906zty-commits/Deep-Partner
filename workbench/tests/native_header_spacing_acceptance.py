"""Keep native header geometry and do not create a third header line."""
from pathlib import Path
from tempfile import TemporaryDirectory
from docx import Document
from server.word_layout import make_reference
ROOT=Path(__file__).resolve().parents[1]
source=Document(ROOT/'templates/manuscripts/source/chinese-user-260909.docx')
with TemporaryDirectory() as folder:
 current=Document(make_reference(Path(folder),'chinese',2));a=source.sections[0];b=current.sections[0]
 for field in ('top_margin','bottom_margin','left_margin','right_margin','header_distance','footer_distance'):
  assert getattr(a,field)==getattr(b,field),'Native header/body geometry changed: '+field
 for name in ('header','first_page_header','even_page_header'):
  original=getattr(a,name);header=getattr(b,name)
  assert len(original.paragraphs)==len(header.paragraphs),'Native header paragraph structure changed'
  assert not header._element.xpath('.//w:br'),'A manual break introduced an extra header row'
 assert b.header.paragraphs[0].text=='西 北 工 业 大 学 学 报'
 assert b.header.paragraphs[1].text=='Journal of Northwestern Polytechnical University'
 from server.manuscripts import export_manuscript
 import fitz,json
 root=Path(folder);(root/'manuscript').mkdir(exist_ok=True)
 nodes=[{'type':'paragraph','content':[{'type':'text','text':'作者'}]},{'type':'paragraph','content':[{'type':'text','text':'单位'}]},{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'1 页眉与正文间距'}]}]
 nodes.extend({'type':'paragraph','content':[{'type':'text','text':str(i)+' 本段用于检验正文与页眉横线的留白。中文采用宋体，西文采用 Times New Roman。保持原稿的行距和页边距。'*3}]} for i in range(50))
 pdf,_,_=export_manuscript(root,{'title':'原生页眉留白检查','template':'chinese','columns':2,'revision':1,'content':{'type':'doc','content':nodes},'comments':[]},'pdf')
 gaps=[]
 with fitz.open(stream=pdf,filetype='pdf') as rendered:
  for i,page in enumerate(rendered):
   if i==0:continue
   rules=[d['rect'].y1 for d in page.get_drawings() if d['rect'].width>400 and d['rect'].height<2 and 35<d['rect'].y0<105]
   if not rules:continue
   y=max(rules);spans=[span for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for span in l['spans'] if span['bbox'][1]>=y and span['bbox'][1]<160 and span['size']>=10]
   if spans:gaps.append({'page':i+1,'rule_y':y,'gap_pt':min(span['bbox'][1] for span in spans)-y})
 assert len(gaps)>=2 and min(g['gap_pt'] for g in gaps)>5,'The native odd/even header leaves insufficient body gap'
 print(json.dumps({'passed':True,'native_geometry_unchanged':True,'header_paragraphs_unchanged':True,'gaps':gaps},ensure_ascii=False))
