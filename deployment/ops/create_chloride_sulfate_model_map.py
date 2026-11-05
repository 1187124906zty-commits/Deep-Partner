"""Build an editable capability map from FigureSpec plus explicit connector routes."""
from pathlib import Path
from copy import deepcopy
import html
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/氯硫建模逻辑图-20261104'
OUT.mkdir(exist_ok=True)
RENDERER = Path('C:/Users/DEVELOPER/.codex/skills/figure-spec/scripts/figure_renderer.py')
module = importlib.util.spec_from_file_location('figure_renderer', RENDERER)
renderer = importlib.util.module_from_spec(module)
module.loader.exec_module(renderer)
S = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', S[1:-1])

nodes, labels, routes, panels = [], [], [], []


def node(ident, label, x, y, w, h, fill='#FFFFFF', size=19, sub='', **extra):
    n = dict(id=ident, label=label, x=x, y=y, width=w, height=h,
        shape='rounded', fill=fill, stroke='#75808A', text_color='#111111', font_size=size)
    if sub:
        n['sublabel'] = sub
    n.update(extra)
    nodes.append(n)


def label(text, x, y, size=18, color='#111111', **extra):
    labels.append(dict(text=text, x=x, y=y, font_size=size, color=color, **extra))


def route(ident, points, color='#222222', dashed=False, arrow=True, text='', text_xy=None):
    routes.append(dict(id=ident, points=points, color=color, dashed=dashed, arrow=arrow,
        label=text, label_xy=text_xy))


label('氯盐—硫酸盐耦合侵蚀：从物理问题到模型能力', 800, 48, 30)
label('先选择需要描述的物理关系，再选择数值求解方法', 800, 82, 19, '#52606C')

stages = [
    (170, '离子如何进入与迁出', '#EAF2FA'),
    (480, '如何计入水化产物反应', '#EAF4EE'),
    (790, '反应如何引起膨胀', '#FFF3E0'),
    (1100, '损伤如何反馈离子侵入', '#F0ECF7'),
]
for i, (x, title, fill) in enumerate(stages):
    panels.append(dict(x=x-145, y=150, width=290, height=348, fill=fill, stroke='#DBE0E3'))
    label(title, x, 129, 21)

node('fick', 'Fick', 94, 245, 128, 104, '#FFFFFF', 21, '浓度扩散')
node('np', 'Nernst–Planck', 246, 245, 148, 104, '#FFFFFF', 18, '扩散与电迁移')
node('transport', '离子传输\n浓度场与通量', 170, 408, 272, 82, '#FFFFFF', 20)
label('单独的传输项不确定化学反应', 170, 477, 16, '#4A5965')

node('kinetics', '动力学／\n结合关系', 404, 245, 130, 104, '#FFFFFF', 19, '指定反应与参数')
node('equilibrium', '热力学平衡', 556, 245, 144, 104, '#FFFFFF', 19, '可联用表面络合')
node('reaction', '水化产物反应与离子结合\n相组成可由平衡模型细化', 480, 408, 272, 82, '#FFFFFF', 19)
label('平衡闭合仍需检验反应时间尺度', 480, 477, 16, '#4A5965')

node('volume', '体积增长\n理论', 714, 245, 130, 104, '#FFFFFF', 20, '体积与孔隙容纳')
node('pressure', '结晶压\n理论', 866, 245, 144, 104, '#FFFFFF', 20, '过饱和度与约束')
node('expansion', '化学膨胀或孔内压力\n连接化学变化与力学作用', 790, 408, 272, 82, '#FFFFFF', 19)
label('产物量不能直接等同于开裂', 790, 477, 16, '#4A5965')

node('damage', '损伤函数', 1024, 245, 130, 104, '#FFFFFF', 20, '表征劣化与反馈')
node('phasefield', '相场断裂', 1176, 245, 144, 104, '#FFFFFF', 20, '求起裂与扩展')
node('damage_result', '劣化程度或裂纹演化\n更新传输与结合关系', 1100, 408, 272, 82, '#FFFFFF', 19)
label('损伤函数本身不追踪裂纹路径', 1100, 477, 16, '#4A5965')

for i, x in enumerate([170, 480, 790, 1100]):
    route('method-left-'+str(i), [[x-76,297],[x-76,332],[x,332]], arrow=False)
    route('method-right-'+str(i), [[x+76,297],[x+76,332],[x,332]], arrow=False)
    route('method-merge-'+str(i), [[x,332],[x,360]])
for i, (a, b) in enumerate([(170,480),(480,790),(790,1100)]):
    route('physical-'+str(i), [[a+138,408],[b-143,408]])
route('feedback', [[1238,428],[1268,428],[1268,535],[10,535],[10,428],[27,428]],
    text='孔隙、损伤与裂纹反过来改变传输（结合反馈需另给关系）', text_xy=[635,535])

label('按工况增加物理分支（可不启用）', 630, 586, 19)
route('branch-left', [[630,601],[320,601],[320,627]], '#6E7B85', True)
route('branch-right', [[630,601],[930,601],[930,627]], '#6E7B85', True)
node('leaching', '需要描述显著脱钙／浸出时\n钙传输＋固液平衡曲线或热力学溶解\n更新脱钙与孔隙；软化另接本构关系', 320, 698, 575, 134, '#F7F9FB', 20,
    conditional=True)
node('environment', '温湿度变化影响预测时\n热湿场或给定温湿历程＋参数关系\n更新含水状态及迁移、反应条件', 930, 698, 575, 134, '#F7F9FB', 20,
    conditional=True)

label('怎样计算', 1430, 129, 21)
node('solver', '数值求解\n \n有限元等空间离散\n传输—反应—力学\n联立或分步交替推进\n \nCOMSOL PDE／自编程序\n＋化学求解器（按需）\n \n得到离子分布、膨胀与损伤',
    1430, 424, 264, 548, '#F5F5F2', 20)
label('相场是裂纹描述', 1430, 744, 18)
label('有限元是离散求解', 1430, 773, 18)
route('to-solver', [[1238,408],[1291,408]])
route('conditional-solve-left', [[320,768],[320,820],[1260,820],[1260,640],[1291,640]], '#6E7B85', True)
route('conditional-solve-right', [[1220,698],[1260,698]], '#6E7B85', True, False)
label('实线：主体关系与反馈　　虚线：随工况选用的扩展', 800, 865, 17, '#4A5965')
label('方法能力由所选方程和闭合关系决定；软件求解不会自动补齐缺失的物理过程。', 800, 895, 17, '#4A5965')

spec = dict(title='氯盐—硫酸盐耦合侵蚀建模能力图', canvas=dict(width=1600,height=920),
    style=dict(font_family='Microsoft YaHei, Noto Sans CJK SC, sans-serif', font_size=20,
        bg_color='#FFFFFF', palette=['#607789','#5D8170','#A18A61','#796C91']),
    nodes=nodes, edges=[], labels=labels, groups=[],
    extension=dict(description='Explicit orthogonal routes and panel bounds; source-driven task renderer',
        panels=panels, routes=routes))
(OUT/'建模逻辑图.figurespec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')
issues=renderer.validate_spec(spec)
assert not any(x.startswith('CRITICAL') for x in issues),issues
base=ET.fromstring(renderer.render_svg(spec))
defs=base.find(S+'defs')
for color, name in [('#222222','logic'),('#6E7B85','optional')]:
    marker=ET.SubElement(defs,S+'marker',dict(id='map-arrow-'+name,viewBox='0 0 10 10',refX='9',refY='5',markerWidth='7',markerHeight='7',orient='auto',markerUnits='strokeWidth'))
    ET.SubElement(marker,S+'path',dict(d='M 0 0 L 10 5 L 0 10 z',fill=color))
background=ET.Element(S+'g',{'id':'panels'})
for p in panels:
    attrs={k:str(v) for k,v in p.items()};attrs.update(rx='12',**{'stroke-width':'1'})
    ET.SubElement(background,S+'rect',attrs)
base.insert(2,background)
connections=ET.Element(S+'g',{'id':'connections'})
for r in routes:
    attrs={'id':r['id'],'d':' '.join(('M' if i==0 else 'L')+' '+str(x)+' '+str(y) for i,(x,y) in enumerate(r['points'])),
        'stroke':r['color'],'stroke-width':'1.8','fill':'none','stroke-linejoin':'round'}
    if r['dashed']:attrs['stroke-dasharray']='7 5'
    if r['arrow']:attrs['marker-end']='url(#map-arrow-'+('optional' if r['dashed'] else 'logic')+')'
    ET.SubElement(connections,S+'path',attrs)
    if r['label']:
        x,y=r['label_xy'];width=len(r['label'])*16+20
        ET.SubElement(connections,S+'rect',dict(x=str(x-width/2),y=str(y-16),width=str(width),height='30',fill='#FFFFFF'))
        t=ET.SubElement(connections,S+'text',{'x':str(x),'y':str(y+5),'font-size':'17','text-anchor':'middle','fill':'#111111'})
        t.text=r['label']
base.insert(3,connections)
# Associate actual editable shapes and text with scientific content identifiers.
children=list(base)
for n in nodes:
    group=ET.Element(S+'g',{'id':'node-'+n['id'],'data-node-id':n['id'],'class':'model-node','tabindex':'0','role':'button','aria-label':n['label'].replace('\n',' ')})
    for e in children:
        if e.tag==S+'rect' and e.get('x')==f"{n['x']-n['width']/2:.1f}" and e.get('y')==f"{n['y']-n['height']/2:.1f}" and e.get('width')==f"{n['width']:.1f}":
            group.append(e);base.remove(e)
            if n.get('conditional'):e.set('stroke-dasharray','6 4')
            e.set('stroke-width','1.4')
        elif e.tag==S+'text' and e.get('x')==f"{n['x']:.1f}":
            # Only text within the node's declared bounds, never free labels.
            y=float(e.get('y','-999'))
            if n['y']-n['height']/2<y<n['y']+n['height']/2:
                group.append(e);base.remove(e)
                e.set('fill','#111111');e.set('font-weight','500')
    base.append(group)
svg=ET.tostring(base,encoding='unicode')
(OUT/'氯硫耦合建模逻辑图.svg').write_text(svg,encoding='utf8')
(OUT/'svg-only.html').write_text('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:white}svg{display:block;width:1600px;height:920px}</style>'+svg,encoding='utf8')
print(json.dumps({'svg':str(OUT/'氯硫耦合建模逻辑图.svg'),'nodes':len(nodes),'routes':len(routes),'validation':issues},ensure_ascii=False))
