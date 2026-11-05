"""Public neutral visual templates and separate audience-centered talk profiles."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def catalog():return json.loads((ROOT/'templates/presentations/catalog.json').read_text(encoding='utf8'))
def visual(kind):
    if kind=='minimal':kind='beamer-default'
    value=next((t for t in catalog()['templates'] if t['id']==kind),None)
    if value is None:raise ValueError('请选择有来源的演示模板')
    return {**value,'layout':catalog()['layout']}

def purpose_rules():
    """Product guidance with explicit source scope, separate from visual themes."""
    return json.loads((ROOT/'templates/presentations/purpose-rules.json').read_text(encoding='utf8'))


def purpose_rule(identifier):
    found=next((p for p in purpose_rules()['profiles'] if p['id']==identifier),None)
    if found is None:raise ValueError('请选择汇报对象与用途')
    return found


# Keep the existing catalog response fields for clients that only need a choice.
PROFILE_FIELDS=('id','name','audience','purpose','structure','sources')
PROFILES=[{key:p[key] for key in PROFILE_FIELDS} for p in purpose_rules()['profiles']]
def profile(identifier):
    found=next((p for p in PROFILES if p['id']==identifier),None)
    if found is None:raise ValueError('请选择汇报对象与用途')
    return found

def generation_context(template,profile_id,manifest=None):
    """Use the selected purpose card and actual template readings independently."""
    purpose=purpose_rule(profile_id)
    if template=='uploaded':
        from .slide_quality import resolve_template_font_sizes
        spec={'id':'uploaded','name':'项目私人模板','kind':'uploaded',
              'font_policy':'已解析的模板字号优先；缺失值采用标明的产品回退，回退不代表原模板事实。',
              'font_fallbacks':resolve_template_font_sizes({}), 'pages':[]}
        if manifest is not None:
            spec.update({key:manifest[key] for key in ('width','height','examples') if key in manifest})
            spec['pages']=[{'page':page.get('page'),'role':page.get('role'),
                            'fonts':resolve_template_font_sizes(page)} for page in manifest.get('slides',[])]
        visual_instructions='上传模板已解析的数值优先，不用公共模板的正文或标题字号范围覆盖。未解析项须标明产品回退。'
    else:
        spec={**visual(template),'kind':'public_product_default','replaceable':True}
        visual_instructions=('当前公共模板产品默认：标题最多两行，正文20–24pt；正文有图时优先3–4条简短要点。'
                             '每页至多一个完整图或表；图表多时拆页，不缩小文字。')
    return ('本次已确认的汇报对象、用途与信息要求：'+json.dumps(purpose,ensure_ascii=False)+
      '\n本次已确认的视觉模板（与用途独立）：'+json.dumps(spec,ensure_ascii=False)+
      '\n用途规则属于有来源的产品指导，structure是可调整的组织参考。先按necessary_information检查信息覆盖，'
      '再按exceptions调整适用范围；不得凭空补足不存在的工作。评价维度按当前用途选择，硬检查与语义评分独立。'
      '每页聚焦一个主要认识；输出页内正文，详细解释放notes。保留图表编号、单位与原始出处。'+visual_instructions)

def create_public_template(kind,path):
    from pptx import Presentation
    from pptx.util import Inches,Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from .slides import add_text
    spec=visual(kind);layout=spec['layout'];palette=spec['palette'];prs=Presentation();prs.slide_width=Inches(layout['width_in']);prs.slide_height=Inches(layout['height_in']);W,H=prs.slide_width,prs.slide_height
    for role,title,body in [('cover','研究汇报','研究主题与报告信息'),('outline','报告结构','问题与目的\n方法与证据\n结论与讨论'),('section','研究问题',''),('content','关键结论与证据','围绕一个清楚的认识组织本页。\n文字支持图表，保留必要条件。'),('two_column','结果与比较','对照证据与解释'),('ending','结论与讨论','主要认识\n适用边界\n讨论问题')]:
        slide=prs.slides.add_slide(prs.slide_layouts[6]);slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string(palette['background'])
        if spec['header']=='band' and role not in ('cover','section','ending'):
            band=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,W,Inches(1.38));band.fill.solid();band.fill.fore_color.rgb=RGBColor.from_string(palette['primary']);band.line.fill.background()
        centered=role in ('cover','section','ending');top=Inches(2.0 if centered else .22);color=palette['foreground'] if centered or spec['header']=='plain' else 'FFFFFF'
        add_text(slide,title,Inches(.7),top,W-Inches(1.4),Inches(1.45 if centered else 1.15),layout['cover_font_pt'] if centered else layout['title_font_pt'],True,color,centered,layout['latin_font'],layout['cjk_font'])
        if body:add_text(slide,body,Inches(.7),Inches(3.6 if centered else 1.75),W-Inches(1.4),Inches(2.2 if centered else 4.8),layout['body_font_pt'],False,palette['foreground'],centered,layout['latin_font'],layout['cjk_font'])
        if spec['id']=='metropolis':
            line=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,H-Inches(.055),W if centered else int(W*.45),Inches(.055));line.fill.solid();line.fill.fore_color.rgb=RGBColor.from_string(palette['accent']);line.line.fill.background()
        if spec['id']=='beamer-madrid':
            band=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,H-Inches(.28),W,Inches(.28));band.fill.solid();band.fill.fore_color.rgb=RGBColor.from_string(palette['primary']);band.line.fill.background()
        for shape in slide.shapes:
            for effect in shape._element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}effectRef'):effect.set('idx','0')
    prs.core_properties.title=spec['name']+' editable PPTX adaptation';prs.core_properties.author='Research Workbench';prs.core_properties.comments=spec['source']+' | '+spec['license']+' | '+layout['font_adaptation']
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);prs.save(path);return spec
