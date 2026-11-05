"""Separate physical modules, peer model choices, tools and existing couplings."""
from pathlib import Path
import json
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
W,H=2000,1125
TEMPLATE=Path('C:/Users/DEVELOPER/Desktop/演示文稿48.pptx')
styles={'transport':{'color':'#21978D','dash':None},
        'reaction':{'color':'#202020','dash':'dot'},
        'mechanics':{'color':'#E34A48','dash':'dash'}}
nodes=[];edges=[];labels=[]

def node(ident,text,x,y,w,h,module,size=31):
    nodes.append(dict(id=ident,text=text,x=x,y=y,w=w,h=h,module=module,size=size))

def edge(ident,points,module,arrow=True):
    edges.append(dict(id=ident,points=points,module=module,arrow=arrow))

def branch(ident,root,ys,x_end,module,bus_x=290):
    x,y=root
    edge(ident+'-stem',[[x,y],[bus_x,y]],module,False)
    if len(ys)>1:edge(ident+'-bus',[[bus_x,min(ys)],[bus_x,max(ys)]],module,False)
    for i,yy in enumerate(ys):edge(ident+'-'+str(i),[[bus_x,yy],[x_end,yy]],module)

for text,x in [('物理模块',135),('模型与能力',540),('典型计算工具',1080),('已有耦合应用',1650)]:
    labels.append(dict(text=text,x=x,y=177,size=30))

# Diffusion retains its own discretization tools. Temperature/moisture is a
# selectable transport branch, not an added mandatory chemical stage.
node('transport','扩散／传输',135,310,210,92,'transport',33)
node('fick','Fick定律\n浓度扩散',540,245,390,94,'transport')
node('np','Nernst–Planck\n多离子迁移',540,345,390,94,'transport')
node('transport-tools','有限元／有限体积',1080,290,380,100,'transport')
node('transport-application','孔隙／损伤修正传输',1650,290,620,100,'transport')
node('environment','温湿度场',540,435,390,64,'transport')
node('environment-tools','热湿传输PDE',1080,435,380,64,'transport')
branch('transport',(244,310),[245,345,435],339,'transport')
edge('fick-tool',[[739,245],[815,245],[815,265],[883,265]],'transport')
edge('np-tool',[[739,345],[815,345],[815,315],[883,315]],'transport')
edge('transport-use',[[1275,290],[1333,290]],'transport')
edge('environment-tool',[[739,435],[883,435]],'transport')

# Two chemical closures are peers. Specific example branches show what each
# actually contributed to a published damage/fracture coupling.
node('reaction','反应',135,685,210,92,'reaction',33)
node('kinetics','反应动力学\n反应速率',540,555,390,96,'reaction')
node('kinetic-tools','COMSOL PDE',1080,555,380,96,'reaction')
node('kinetic-application','动力学—膨胀—相场\n硫酸盐混凝土',1650,555,620,96,'reaction',30)
node('equilibrium','热力学平衡\n相组成／固液分配',540,745,390,100,'reaction')
node('gems','GEMS／CemGEMS',1080,690,380,86,'reaction',29)
node('gems-application','水化相初始化—相场\n硫酸盐／淋失混凝土',1650,690,620,86,'reaction',29)
node('phreeqc','PHREEQC',1080,800,380,86,'reaction')
node('phreeqc-application','局部相平衡—软化—相场\n反应性多孔介质',1650,800,620,86,'reaction',29)
branch('reaction',(244,685),[555,745],339,'reaction')
edge('kinetic-tool',[[739,555],[883,555]],'reaction')
edge('kinetic-use',[[1275,555],[1333,555]],'reaction')
edge('equilibrium-to-tools-stem',[[739,745],[815,745]],'reaction',False)
edge('equilibrium-to-tools-bus',[[815,690],[815,800]],'reaction',False)
edge('equilibrium-gems',[[815,690],[883,690]],'reaction')
edge('equilibrium-phreeqc',[[815,800],[883,800]],'reaction')
edge('gems-use',[[1275,690],[1333,690]],'reaction')
edge('phreeqc-use',[[1275,800],[1333,800]],'reaction')

# Calcium leaching stays a condition-specific child of the solid-liquid closure.
node('leaching','固液平衡曲线\n钙溶蚀',540,885,390,84,'reaction',29)
node('leaching-tools','钙传输PDE',1080,885,380,68,'reaction',30)
node('leaching-application','脱钙软化—相场\n水泥基材料',1650,885,620,68,'reaction',28)
edge('leaching-branch',[[540,798],[540,837]],'reaction')
edge('leaching-tool',[[739,885],[883,885]],'reaction')
edge('leaching-use',[[1275,885],[1333,885]],'reaction')

# Damage/fracture has its own solver choices. No return loop crosses the map.
node('mechanics','力学',135,1025,210,92,'mechanics',33)
node('fracture','损伤／断裂模型\n劣化与裂纹',540,1025,390,96,'mechanics')
node('fem','有限元\n损伤本构／相场',1080,987,380,84,'mechanics',29)
node('discrete','近场动力学／离散元',1080,1080,380,64,'mechanics',29)
node('mechanics-application','体积增长／结晶压\n膨胀驱动—损伤反馈',1650,1025,620,128,'mechanics',30)
edge('mechanics-model',[[244,1025],[339,1025]],'mechanics')
edge('mechanics-tools-stem',[[739,1025],[815,1025]],'mechanics',False)
edge('mechanics-tools-bus',[[815,987],[815,1080]],'mechanics',False)
edge('mechanics-fem',[[815,987],[883,987]],'mechanics')
edge('mechanics-discrete',[[815,1080],[883,1080]],'mechanics')
edge('fem-application',[[1275,987],[1305,987],[1305,1000],[1333,1000]],'mechanics')
edge('discrete-application',[[1275,1080],[1305,1080],[1305,1050],[1333,1050]],'mechanics')

spec=dict(canvas=dict(width=W,height=H),styles=styles,nodes=nodes,edges=edges,labels=labels,
    encoding={'transport':'teal solid','reaction':'black dotted','mechanics':'red dashed'},
    diagram_scope='Representative model roles and published coupling examples; tools and examples are not exhaustive or exclusive.')
(OUT/'模块分层图_源.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')

S='{http://www.w3.org/2000/svg}';ET.register_namespace('',S[1:-1])
svg=ET.Element(S+'svg',dict(width=str(W),height=str(H),viewBox=f'0 0 {W} {H}',**{'font-family':'Microsoft YaHei,Arial,sans-serif'}))
ET.SubElement(svg,S+'rect',dict(width=str(W),height=str(H),fill='white'))
defs=ET.SubElement(svg,S+'defs')
for key,style in styles.items():
    marker=ET.SubElement(defs,S+'marker',dict(id='arrow-'+key,viewBox='0 0 10 10',refX='9',refY='5',markerWidth='7',markerHeight='7',orient='auto',markerUnits='strokeWidth'))
    ET.SubElement(marker,S+'path',dict(d='M 0 0 L 10 5 L 0 10 z',fill=style['color']))
ET.SubElement(svg,S+'path',dict(d='M 42 132 L 2000 132',stroke='#FF0000',**{'stroke-width':'2'}))
ET.SubElement(svg,S+'rect',dict(x='1520',y='124',width='480',height='16',fill='#FF0000'))
ET.SubElement(svg,S+'path',dict(d='M 74 74 L 106 42 L 138 74 L 106 106 Z',fill='#FF0000'))
tt=ET.SubElement(svg,S+'text',dict(x='370',y='90',fill='#0000BB',**{'font-size':'44','font-weight':'700'}));tt.text='3.2 建模逻辑'
for l in labels:
    t=ET.SubElement(svg,S+'text',dict(x=str(l['x']),y=str(l['y']),fill='#111111',**{'font-size':str(l['size']),'text-anchor':'middle','font-weight':'700'}));t.text=l['text']
for e in edges:
    st=styles[e['module']];attrs={'d':' '.join(('M' if i==0 else 'L')+f' {x} {y}' for i,(x,y) in enumerate(e['points'])),'stroke':st['color'],'stroke-width':'2.6','fill':'none','stroke-linejoin':'round'}
    if st['dash']:attrs['stroke-dasharray']='3 6' if st['dash']=='dot' else '11 7'
    if e['arrow']:attrs['marker-end']='url(#arrow-'+e['module']+')'
    ET.SubElement(svg,S+'path',attrs)
for n in nodes:
    st=styles[n['module']];g=ET.SubElement(svg,S+'g',id='node-'+n['id'])
    attrs=dict(x=str(n['x']-n['w']/2),y=str(n['y']-n['h']/2),width=str(n['w']),height=str(n['h']),fill='white',stroke=st['color'],**{'stroke-width':'3'})
    if st['dash']:attrs['stroke-dasharray']='3 6' if st['dash']=='dot' else '11 7'
    ET.SubElement(g,S+'rect',attrs)
    lines=n['text'].split('\n');lh=n['size']+6
    for i,line in enumerate(lines):
        y=n['y']-(len(lines)-1)*lh/2+i*lh+n['size']*.35
        t=ET.SubElement(g,S+'text',dict(x=str(n['x']),y=str(y),fill='#111111',**{'font-size':str(n['size']),'text-anchor':'middle','font-weight':'600'}));t.text=line
svg_text=ET.tostring(svg,encoding='unicode')
(OUT/'氯硫耦合建模逻辑图_模块分层.svg').write_text(svg_text,encoding='utf8')
(OUT/'氯硫耦合建模逻辑图.svg').write_text(svg_text,encoding='utf8')

prs=Presentation(TEMPLATE)
sid=prs.slides._sldIdLst[0];prs.part.drop_rel(sid.rId);prs.slides._sldIdLst.remove(sid)
slide=prs.slides[0]
for sh in list(slide.shapes):
    if sh.top>900000:slide.shapes._spTree.remove(sh._element)
for sh in slide.shapes:
    if getattr(sh,'has_text_frame',False) and '总结' in sh.text:
        sh.width=5400000
        p=sh.text_frame.paragraphs[0]
        for r in p.runs:r.text=''
        r=p.add_run();r.text='3.2 建模逻辑';r.font.name='微软雅黑';r.font.size=Pt(25);r.font.bold=True;r.font.color.rgb=RGBColor(0,0,192)
sx=prs.slide_width/W;sy=prs.slide_height/H
def X(v):return round(v*sx)
def Y(v):return round(v*sy)
def rgb(v):return RGBColor.from_string(v.lstrip('#'))
def line_style(sh,module):
    st=styles[module];sh.line.color.rgb=rgb(st['color']);sh.line.width=Pt(1.5)
    if st['dash']:
        ln=sh._element.spPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln')
        dash=OxmlElement('a:prstDash');dash.set('val','dot' if st['dash']=='dot' else 'dash');ln.append(dash)
def put_text(sh,text,size):
    tf=sh.text_frame;tf.clear();tf.margin_left=0;tf.margin_right=0;tf.margin_top=0;tf.margin_bottom=0;tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    p=tf.paragraphs[0];p.alignment=PP_ALIGN.CENTER
    r=p.add_run();r.text=text;r.font.name='微软雅黑';r.font.size=Pt(size*.48);r.font.bold=True;r.font.color.rgb=rgb('#111111')
for l in labels:
    sh=slide.shapes.add_textbox(X(l['x']-150),Y(l['y']-35),X(300),Y(55));put_text(sh,l['text'],l['size'])
for e in edges:
    for i,(a,b) in enumerate(zip(e['points'][:-1],e['points'][1:])):
        if a==b:continue
        sh=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,X(a[0]),Y(a[1]),X(b[0]),Y(b[1]));line_style(sh,e['module'])
        if e['arrow'] and i==len(e['points'])-2:
            ln=sh._element.spPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ln');ar=OxmlElement('a:tailEnd');ar.set('type','triangle');ar.set('w','med');ar.set('len','med');ln.append(ar)
for n in nodes:
    sh=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,X(n['x']-n['w']/2),Y(n['y']-n['h']/2),X(n['w']),Y(n['h']));sh.name='module-'+n['id'];sh.fill.solid();sh.fill.fore_color.rgb=rgb('#FFFFFF');line_style(sh,n['module']);put_text(sh,n['text'],n['size'])
for sh in slide.shapes:
    sppr=sh._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}spPr')
    if sppr is not None:
        for child in list(sppr):
            if child.tag.rsplit('}',1)[-1] in ('effectLst','effectDag'):sppr.remove(child)
        sppr.append(OxmlElement('a:effectLst'))
    for ref in sh._element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}effectRef'):ref.set('idx','0')
slide.notes_slide.notes_text_frame.text='''Scope: representative models, typical tools and documented applications. No claim that thermodynamic equilibrium has never been coupled to phase-field fracture.
Transport and reaction classification: Wang et al.(2022), DOI10.14062/j.issn.0454-5648.20210248, sections4.1–4.3; Hosokawa et al.(2011), DOI10.1617/s11527-011-9720-2.
Kinetics-sulfate-phase field: Luo et al.(2024), DOI10.1016/j.ijmecsci.2024.109694; Fang et al.(2025), DOI10.1016/j.engfracmech.2025.111479.
CemGEMS initialization, sulfate/leaching-phase field: Fang et al.(2026), DOI10.1016/j.ijmecsci.2026.111945, sections2.1 and2.5. The example uses CemGEMS; GEMS3K is a general embeddable equilibrium kernel, not a claim that Fang used that API.
Equilibrium-PHREEQC-phase field: Pena Clavijo et al.(2022), DOI10.1038/s41598-022-22684-1, methods and carbonate-cemented sandstone example; repeated local equilibrium, chemical softening and FEniCS fracture. Mollaali et al.(2025), DOI10.1002/nme.7621, supports equilibrium/kinetics-PHREEQC-OpenGeoSys fracture; later dissolution benchmark is kinetic.
Leaching curve and damage: Fang et al.(2026), same source; the curve is a reduced solid-liquid closure selected for leaching, not a separate thermodynamic law valid in every environment.
Mechanics role: volume growth/crystallization pressure connect chemistry to expansion; damage/phase field can use FEM. PD/DEM are alternative discrete implementations, not phase-field solvers. Sources in existing project evidence packet. PHREEQC can also solve kinetic reactions; the tool list is typical, not exclusive.'''
draft=BUILD/'建模逻辑_模块分层_draft.pptx';prs.save(draft)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>氯硫耦合建模：模块分层</title><style>html,body{margin:0;background:white;font-family:Microsoft YaHei,sans-serif}main{width:100%;overflow:auto}svg{width:100%;height:auto;min-width:1150px;display:block}nav{text-align:right;padding:8px 24px;font-size:14px}a{margin-left:20px;color:#24796c}</style><main>__SVG__</main><nav><a href="氯硫耦合建模逻辑图_模块分层.pptx" download>PowerPoint</a><a href="氯硫耦合建模逻辑图_模块分层.svg" download>SVG</a><a href="氯硫耦合建模逻辑图_模块分层.pdf" download>PDF</a></nav></html>'''.replace('__SVG__',svg_text)
(OUT/'index.html').write_text(page,encoding='utf8')
print(json.dumps({'draft':str(draft),'nodes':len(nodes),'local_routes':len(edges),'cross_module_routes':0},ensure_ascii=False))
