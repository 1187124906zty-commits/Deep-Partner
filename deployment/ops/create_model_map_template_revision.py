"""Minimal, editable logic diagram following the author's PowerPoint reference."""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET

from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Pt
from pptx.oxml.xmlchemy import OxmlElement

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/氯硫建模逻辑图-20261104'
BUILD=OUT/'.build';BUILD.mkdir(exist_ok=True)
TEMPLATE=Path('C:/Users/DEVELOPER/Desktop/演示文稿48.pptx')
W,H=1600,900
TEAL='#21978D';BLUE='#5275BD';RED='#DA4545';BLACK='#111111'
nodes=[];edges=[];texts=[]

def box(ident,text,x,y,w=238,h=64,color=TEAL,dashed=False,size=28):
    nodes.append(dict(id=ident,text=text,x=x,y=y,w=w,h=h,color=color,dashed=dashed,size=size))

def edge(ident,points,color=TEAL,dashed=False,arrow=True,label='',label_xy=None):
    edges.append(dict(id=ident,points=points,color=color,dashed=dashed,arrow=arrow,label=label,label_xy=label_xy))

def free(text,x,y,size=25,color=BLACK):texts.append(dict(text=text,x=x,y=y,size=size,color=color))

# The core advances only when the additional physical description is supplied.
box('transport','离子传输',245,390,240,68)
box('reaction','反应—传输',620,390,240,68)
box('mechanical','化学—损伤—传输',1060,390,300,68)
box('fick','Fick定律',150,205,165,72)
box('np','Nernst–Planck\n方程',355,205,225,72,size=25)
box('kinetics','反应动力学',565,205,175,72,size=27)
box('equilibrium','热力学平衡',760,205,190,72,size=27)
box('volume','体积增长理论',970,205,205,72,size=27)
box('pressure','结晶压理论',1190,205,200,72,size=27)

for name,x in [('fick',150),('np',355)]:
    edge(name+'-in',[[x,241],[x,290],[245,290]],arrow=False)
edge('transport-in',[[245,290],[245,351]])
for name,x in [('kinetics',565),('equilibrium',760)]:
    edge(name+'-in',[[x,241],[x,290],[620,290]],arrow=False)
edge('reaction-in',[[620,290],[620,351]])
for name,x in [('volume',970),('pressure',1190)]:
    edge(name+'-in',[[x,241],[x,290],[1060,290]],arrow=False)
edge('mechanics-in',[[1060,290],[1060,351]])

edge('add-reaction',[[369,390],[495,390]],RED,True,label='化学反应',label_xy=[432,355])
edge('add-damage',[[744,390],[905,390]],RED,True,label='损伤反馈',label_xy=[823,355])

# Optional processes remain branches rather than mandatory stages.
box('environment','温湿度场',245,590,240,64,dashed=True)
box('calcium','钙溶蚀',620,590,220,64,dashed=True)
box('solid-liquid','固液平衡曲线',620,730,250,64)
edge('environment-branch',[[245,558],[245,429]],TEAL,True)
edge('calcium-branch',[[620,558],[620,429]],TEAL,True)
edge('solid-liquid-to-calcium',[[620,698],[620,627]])

# Mechanical alternatives are shown before their numerical realization.
box('damage','损伤模型',975,555,200,62)
box('phase','相场法',1195,555,190,62)
box('pd','近场动力学',975,690,220,62)
box('dem','离散单元法',1220,690,220,62)
edge('mechanical-model-a',[[1060,428],[1060,470],[975,470],[975,519]])
edge('mechanical-model-b',[[1060,470],[1195,470],[1195,519]])
edge('mechanical-model-c',[[906,410],[825,410],[825,646],[975,646],[975,654]])
edge('mechanical-model-d',[[825,646],[1220,646],[1220,654]])

# FEM can solve transport and phase-field/damage descriptions. PD/DEM retain
# their own formulation instead of being mislabelled as children of FEM.
box('fem','有限元法',1450,390,200,68,color=TEAL)
edge('to-fem',[[1214,390],[1345,390]],BLUE)
edge('damage-fem',[[975,590],[975,615],[1332,615],[1332,416],[1345,416]],BLUE)
edge('phase-fem',[[1195,590],[1195,615]],BLUE,arrow=False)

edge('feedback',[[1450,428],[1450,825],[70,825],[70,410],[120,410]],BLUE,label='传输反馈',label_xy=[850,825])

spec=dict(title='氯硫耦合建模逻辑',canvas=dict(width=W,height=H),nodes=nodes,edges=edges,texts=texts,
    template=str(TEMPLATE),message='传输、反应与损伤由额外物理关系逐步连接，钙溶蚀和温湿度为分支。')
(OUT/'模板版建模逻辑图_源.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')

S='{http://www.w3.org/2000/svg}';ET.register_namespace('',S[1:-1])
svg=ET.Element(S+'svg',dict(width=str(W),height=str(H),viewBox=f'0 0 {W} {H}',**{'font-family':'Microsoft YaHei,Arial,sans-serif'}))
ET.SubElement(svg,S+'rect',dict(width=str(W),height=str(H),fill='white'))
defs=ET.SubElement(svg,S+'defs')
for color,name in [(TEAL,'green'),(BLUE,'blue'),(RED,'red')]:
    m=ET.SubElement(defs,S+'marker',dict(id='arrow-'+name,viewBox='0 0 10 10',refX='9',refY='5',markerWidth='7',markerHeight='7',orient='auto',markerUnits='strokeWidth'))
    ET.SubElement(m,S+'path',dict(d='M 0 0 L 10 5 L 0 10 z',fill=color))
ET.SubElement(svg,S+'path',dict(d='M 34 107 L 1600 107',stroke='#FF0000',**{'stroke-width':'2'}))
ET.SubElement(svg,S+'rect',dict(x='1216',y='100',width='384',height='14',fill='#FF0000'))
ET.SubElement(svg,S+'path',dict(d='M 60 60 L 86 34 L 112 60 L 86 86 Z',fill='#FF0000'))
t=ET.SubElement(svg,S+'text',dict(x='298',y='75',fill='#0000BB',**{'font-size':'36','font-weight':'700'}));t.text='3.2 建模逻辑'
t=ET.SubElement(svg,S+'text',dict(x='1380',y='43',fill=BLACK,**{'font-size':'28','font-family':'Times New Roman','font-weight':'700'}));t.text='1'
layer=ET.SubElement(svg,S+'g',id='connectors')
for e in edges:
    attrs={'d':' '.join(('M' if i==0 else 'L')+f' {x} {y}' for i,(x,y) in enumerate(e['points'])),'fill':'none','stroke':e['color'],'stroke-width':'2.3','stroke-linejoin':'miter'}
    if e['dashed']:attrs['stroke-dasharray']='9 7'
    if e['arrow']:attrs['marker-end']='url(#arrow-'+{TEAL:'green',BLUE:'blue',RED:'red'}[e['color']]+')'
    ET.SubElement(layer,S+'path',attrs)
    if e['label']:
        x,y=e['label_xy'];w=len(e['label'])*25+22
        ET.SubElement(layer,S+'rect',dict(x=str(x-w/2),y=str(y-24),width=str(w),height='46',fill='white'))
        tt=ET.SubElement(layer,S+'text',dict(x=str(x),y=str(y+9),fill=e['color'],**{'font-size':'25','text-anchor':'middle','font-weight':'600'}));tt.text=e['label']
for n in nodes:
    g=ET.SubElement(svg,S+'g',id='node-'+n['id'])
    attrs=dict(x=str(n['x']-n['w']/2),y=str(n['y']-n['h']/2),width=str(n['w']),height=str(n['h']),fill='white',stroke=n['color'],**{'stroke-width':'3'})
    if n['dashed']:attrs['stroke-dasharray']='9 6'
    ET.SubElement(g,S+'rect',attrs)
    lines=n['text'].split('\n');line_height=n['size']+3
    for i,line in enumerate(lines):
        yy=n['y']-(len(lines)-1)*line_height/2+i*line_height+n['size']*.35
        tt=ET.SubElement(g,S+'text',dict(x=str(n['x']),y=str(yy),fill=BLACK,**{'font-size':str(n['size']),'font-weight':'700','text-anchor':'middle'}));tt.text=line
svg_text=ET.tostring(svg,encoding='unicode')
(OUT/'氯硫耦合建模逻辑图.svg').write_text(svg_text,encoding='utf8')
(OUT/'svg-only.html').write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0}svg{display:block}</style>'+svg_text,encoding='utf8')

# A new one-slide editable file retains the reference master, background and
# header shapes; all model text and connections are native slide objects.
prs=Presentation(TEMPLATE)
remove_id=prs.slides._sldIdLst[0];prs.part.drop_rel(remove_id.rId);prs.slides._sldIdLst.remove(remove_id)
slide=prs.slides[0]
for shape in list(slide.shapes):
    if shape.top>900000:
        slide.shapes._spTree.remove(shape._element)
for shape in slide.shapes:
    if getattr(shape,'has_text_frame',False) and '总结' in shape.text:
        # Reuse the template title box and font sizes.
        shape.width=5400000
        p=shape.text_frame.paragraphs[0]
        for r in p.runs:r.text=''
        run=p.add_run();run.text='3.2 建模逻辑';run.font.name='微软雅黑';run.font.size=Pt(25);run.font.bold=True;run.font.color.rgb=RGBColor(0,0,192)

sx=prs.slide_width/W;sy=prs.slide_height/H
def emu_x(v):return round(v*sx)
def emu_y(v):return round(v*sy)
def rgb(v):return RGBColor.from_string(v.lstrip('#'))
def text_shape(text,x,y,w,h,size,color=BLACK,bold=True):
    sh=slide.shapes.add_textbox(emu_x(x-w/2),emu_y(y-h/2),emu_x(w),emu_y(h))
    sh.text_frame.margin_left=0;sh.text_frame.margin_right=0;sh.text_frame.margin_top=0;sh.text_frame.margin_bottom=0
    sh.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    p=sh.text_frame.paragraphs[0];p.alignment=PP_ALIGN.CENTER
    r=p.add_run();r.text=text;r.font.name='微软雅黑';r.font.size=Pt(size*.6);r.font.bold=bold;r.font.color.rgb=rgb(color)
    return sh
for e in edges:
    for i,(a,b) in enumerate(zip(e['points'][:-1],e['points'][1:])):
        if a==b:continue
        line=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,emu_x(a[0]),emu_y(a[1]),emu_x(b[0]),emu_y(b[1]));line.line.color.rgb=rgb(e['color']);line.line.width=Pt(1.4)
        ln=line._element.spPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln')
        if e['dashed']:
            d=OxmlElement('a:prstDash');d.set('val','dash');ln.append(d)
        if e['arrow'] and i==len(e['points'])-2:
            ar=OxmlElement('a:tailEnd');ar.set('type','triangle');ar.set('w','med');ar.set('len','med');ln.append(ar)
    if e['label']:
        x,y=e['label_xy'];w=len(e['label'])*25+22
        bg=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,emu_x(x-w/2),emu_y(y-25),emu_x(w),emu_y(48));bg.fill.solid();bg.fill.fore_color.rgb=rgb('#FFFFFF');bg.line.fill.background()
        text_shape(e['label'],x,y,w,48,25,e['color'])
for n in nodes:
    sh=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,emu_x(n['x']-n['w']/2),emu_y(n['y']-n['h']/2),emu_x(n['w']),emu_y(n['h']))
    sh.name='model-'+n['id'];sh.fill.solid();sh.fill.fore_color.rgb=rgb('#FFFFFF');sh.line.color.rgb=rgb(n['color']);sh.line.width=Pt(1.8)
    if n['dashed']:
        ln=sh._element.spPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln');d=OxmlElement('a:prstDash');d.set('val','dash');ln.append(d)
    sh.text_frame.clear();sh.text_frame.margin_left=0;sh.text_frame.margin_right=0;sh.text_frame.margin_top=0;sh.text_frame.margin_bottom=0;sh.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    p=sh.text_frame.paragraphs[0];p.alignment=PP_ALIGN.CENTER;r=p.add_run();r.text=n['text'];r.font.name='微软雅黑';r.font.size=Pt(n['size']*.6);r.font.bold=True;r.font.color.rgb=rgb(BLACK)
for shape in slide.shapes:
    sppr=shape._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}spPr')
    if sppr is not None:
        for effect in list(sppr):
            if effect.tag.rsplit('}',1)[-1] in ('effectLst','effectDag'):sppr.remove(effect)
        sppr.append(OxmlElement('a:effectLst'))
    for ref in shape._element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}effectRef'):
        ref.set('idx','0')
slide.notes_slide.notes_text_frame.text='Sources: 王鹏刚等(2022), DOI10.14062/j.issn.0454-5648.20210248, sections4.1–4.3; Hosokawa et al.(2011), DOI10.1617/s11527-011-9720-2; Zhang et al.(2021), DOI10.1016/j.conbuildmat.2021.122806; Luo et al.(2024), DOI10.1016/j.ijmecsci.2024.109694. The figure is a source-based synthesis of model roles, not a claim of a universal single solver.'
draft=BUILD/'建模逻辑_模板版_draft.pptx';prs.save(draft)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>氯硫耦合建模逻辑</title><style>html,body{margin:0;background:white;font-family:Microsoft YaHei,sans-serif}main{width:100%;overflow:auto}svg{width:100%;height:auto;min-width:1000px;display:block}nav{padding:8px 24px;text-align:right;font-size:14px}a{color:#24796c;margin-left:20px}</style><main>__SVG__</main><nav><a href="氯硫耦合建模逻辑图_模板版.pptx" download>PowerPoint</a><a href="氯硫耦合建模逻辑图.svg" download>SVG</a><a href="氯硫耦合建模逻辑图.pdf" download>PDF</a><a href="氯硫建模引言_修订候选.md">引言修订稿</a></nav></html>'''.replace('__SVG__',svg_text)
(OUT/'index.html').write_text(page,encoding='utf8')
page=page.replace('氯硫耦合建模逻辑图_模板版.pptx','氯硫耦合建模逻辑图_清晰版.pptx')
(OUT/'index.html').write_text(page,encoding='utf8')
print(json.dumps({'draft':str(draft),'nodes':len(nodes),'edges':len(edges),'slide_count':len(prs.slides)},ensure_ascii=False))
