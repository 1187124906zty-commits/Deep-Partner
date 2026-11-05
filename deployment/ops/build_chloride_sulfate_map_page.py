"""Interactive reading of the capability diagram and the revised introduction."""
from pathlib import Path
import html
import json
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/氯硫建模逻辑图-20261104'
svg=(OUT/'氯硫耦合建模逻辑图.svg').read_text(encoding='utf8')
intro=(OUT/'氯硫建模引言_修订候选.md').read_text(encoding='utf8')

def md_blocks(text):
    result=[]
    for block in text.strip().split('\n\n'):
        if not block.strip():continue
        if block.startswith('# '):result.append('<h2>'+html.escape(block[2:])+'</h2>');continue
        if block.startswith('## '):result.append('<h3>'+html.escape(block[3:])+'</h3>');continue
        escaped=html.escape(block)
        escaped=re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)',r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',escaped)
        result.append('<p>'+escaped+'</p>')
    return '\n'.join(result)

sources={
 'review':{'title':'王鹏刚等，2022，综述4.1—4.3','url':'https://doi.org/10.14062/j.issn.0454-5648.20210248','scope':'已读用户PDF原文：第3—7页相关段落。温湿度联合PDE实现为综述提出的后续方向。'},
 'np':{'title':'Johannesson等，2007，作者机构记录','url':'https://lup.lub.lu.se/search/publication/688899','scope':'机构摘要明确NP多离子模型、有限元求解和简单离子交换；不将该模型写为完全没有化学作用。'},
 'eq':{'title':'Hosokawa等，2011，出版社摘要','url':'https://doi.org/10.1617/s11527-011-9720-2','scope':'传输与化学平衡耦合，预测孔液与固相组成随时间变化。'},
 'damage':{'title':'Zhang等，2021，TU Delft作者记录','url':'https://research.tudelft.nl/en/publications/numerical-investigation-of-external-sulfate-attack-and-its-effect/','scope':'损伤函数表示硫酸盐损伤对氯扩散和结合的影响。'},
 'phase':{'title':'Luo等，2024，出版社模型与实现说明','url':'https://www.sciencedirect.com/science/article/pii/S0020740324007355','scope':'化学—传输—力学相场模型，膨胀驱动裂纹并将孔隙和裂纹反馈至扩散；此图不复用该文优先权主张。'},
 'phreeqc':{'title':'USGS PHREEQC官方说明','url':'https://www.usgs.gov/software/phreeqc-version-3','scope':'化学反应模块可接入反应传输模拟；平衡和动力学能力须按实际反应选择。'},
 'comsol':{'title':'COMSOL官方物理接口说明','url':'https://doc.comsol.com/6.4/doc/com.comsol.help.chem/chem_introduction.02.03.html','scope':'NP、电中性、对流、热传输和反应接口可组合；软件接口与物理闭合分开判断。'}
}
details={
 'fick':('Fick：扩散通量','描述浓度梯度驱动的扩散。放入质量守恒式后，可与给定的结合项或反应项组成扩散—反应模型。','Fick通量本身不确定结合、沉淀、溶解或损伤；不能因模型使用Fick就认定整个模型完全无反应。',['review']),
 'np':('Nernst–Planck：多离子迁移','描述扩散与电迁移；与流速关系联用可加入对流。多组分计算还需要电荷约束与边界条件。','它不是反应闭合。Johannesson等的具体模型已另加简单离子交换，不能把“方程本身不含反应闭合”说成“相关多离子研究完全没考虑反应”。',['review','np','comsol']),
 'transport':('离子传输：浓度场与通量','给定传输关系、初边界条件和反应闭合后，计算侵入与迁出。','多离子浓度同时求解，不自动意味着水化产物反应及矿相量已经被正确计算。',['review','np']),
 'kinetics':('动力学／结合关系：指定化学作用','可按给定反应速率、吸附关系或容量关系计算离子交换与消耗释放。','能力取决于写入的反应和参数。经验结合关系不能自动给出完整水化相组成。',['review']),
 'equilibrium':('热力学平衡：反应与相组成','由局部组成、活度及选定相集合计算平衡分配和溶解／沉淀；表面络合另行描述吸附。','平衡本身不提供真实反应速率，也不直接给出裂纹。局部平衡近似要与反应和传输时间尺度相容。',['review','eq','phreeqc']),
 'reaction':('反应闭合：把传输接到水化基体','选择结合／动力学关系或更完整的平衡反应描述，使孔液和固相之间能够交换组分。','两类闭合可组合；详细程度更高也意味着更多相集合、数据库或动力学参数需要核定。',['review','eq']),
 'volume':('体积增长理论：化学体积到膨胀','由相体积变化及孔隙容纳关系形成化学膨胀或本征应变，再进入约束力学。','相体积增加不等同于全部转成宏观膨胀，孔隙可容纳部分产物。',['review']),
 'pressure':('结晶压理论：受限生长到压力','将过饱和状态与孔内生长约束联系起来，形成作用于基体的结晶压力。','压力传递、受压区域和材料强度仍需力学描述；热力学相量不能单独替代这些关系。',['review']),
 'expansion':('化学—力学接口','把反应造成的相体积变化或孔内压力，传递到应力、损伤和断裂驱动。','这是从化学到开裂的必要联系。体积增长与结晶压是可选或可组合的建模路线，不要求重复计算同一膨胀作用。',['review','phase']),
 'damage':('损伤函数：劣化及反馈','可用损伤变量或裂纹密度等修正扩散和结合关系，描述侵蚀过程中材料性质退化。','函数本身不自动求出裂纹路径。损伤如何产生、如何演化，以及怎样影响扩散／结合都需定义。',['review','damage']),
 'phasefield':('相场断裂：起裂与扩展','以连续断裂场求解裂纹起裂、扩展和路径，可与化学膨胀、孔隙和传输耦合。','仍需化学闭合、断裂性质及裂纹—通量关系。相场是物理／场描述，可由有限元或其他数值方法求解。',['phase']),
 'damage_result':('反馈：更新传输与结合','将孔隙、损伤或裂纹状态接回有效传输参数，并按需要修正结合关系。','裂纹增大通量与损伤降低结合不是同一关系，不能用一个未定义的“耦合”箭头代替二者。',['review','damage','phase']),
 'leaching':('条件分支：钙溶蚀','当脱钙会显著改变孔隙、化学状态或力学性质时，加入钙传输，并用固液平衡曲线或矿相溶解模型计算钙的固液交换。','固液平衡曲线只是闭合方式之一。若已经在完整化学模块内描述同一固相溶解，应在同一守恒体系计算，避免重复计入；基体软化需另接本构关系。',['review','phreeqc']),
 'environment':('条件分支：温度与湿度','可给定温湿历程并更新扩散／反应参数；需要空间场时，再求热传输、水分迁移及其与离子传输的关系。','王综述4.2.2提出温湿度共同作用的PDE实现方向，未把它作为文中已完成验证的联合模型。需要相应参数和边界数据，不能只增加PDE接口。',['review','comsol']),
 'solver':('数值实现：离散与多场推进','有限元等方法将所选守恒、反应和力学关系离散，采用整体联立或分步交替计算；COMSOL、自编程序与化学内核可承担不同子步。','有限元与相场属于不同层级，可在同一模型中组合。软件求得的是输入模型的解，物理能力仍由方程、闭合关系和参数决定。',['np','phase','phreeqc','comsol'])
}
data={k:dict(title=v[0],capability=v[1],boundary=v[2],sources=[sources[s] for s in v[3]]) for k,v in details.items()}
(OUT/'建模能力与证据.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>氯硫耦合：建模逻辑图与引言修订</title>
<style>
:root{font-family:"Microsoft YaHei UI","Noto Sans CJK SC",sans-serif;color:#17212a;background:#f4f5f3;line-height:1.75}*{box-sizing:border-box}body{margin:0}header{background:white;border-bottom:1px solid #dbe0df;padding:18px 30px}h1{font-size:23px;margin:0 0 8px}button,a,input{font:inherit}button{cursor:pointer;background:white;border:1px solid #c5ceca;border-radius:5px;padding:6px 14px;color:inherit}button[aria-pressed=true]{background:#e8f0ec;border-color:#729281}a{color:#24654c}nav{display:flex;gap:9px;flex-wrap:wrap;align-items:center}.spacer{flex:1}.downloads{display:flex;gap:12px;font-size:13px}main{padding:18px 24px}.tools{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin:0 0 12px;font-size:14px}.canvas{background:white;border:1px solid #dbe0df;overflow:auto;max-height:calc(100vh - 200px)}.canvas svg{display:block;width:100%;height:auto;min-width:1020px}.model-node{cursor:pointer;outline:none}.model-node:hover>rect,.model-node:focus>rect{stroke:#164f3d;stroke-width:2.4}.reading{max-width:1020px;margin:auto;background:white;padding:32px 42px}.reading p{margin:0 0 22px;line-height:2.05}.reading h2{font-size:24px}.reading h3{font-size:20px;margin-top:35px}.note{color:#5b6763;font-size:14px}.detail{position:fixed;right:20px;top:145px;bottom:22px;overflow:auto;width:430px;background:white;border:1px solid #9daea5;border-radius:8px;box-shadow:0 12px 40px #263e3020;padding:22px;z-index:3}.detail h2{font-size:20px;margin:0 28px 18px 0}.detail h3{font-size:14px;color:#63746a;margin:20px 0 5px}.detail p{font-size:15px;margin:0 0 15px}.close{position:absolute;right:10px;top:9px;border:0;padding:2px 8px;font-size:22px}.source{padding:12px 0;border-top:1px solid #e3e8e4}.source small{display:block;font-size:13px;color:#5c6a62;margin-top:5px}[hidden]{display:none!important}@media(max-width:700px){header{padding:14px}h1{font-size:20px}main{padding:12px}.detail{width:calc(100vw - 24px);right:12px;top:150px}.reading{padding:20px}.downloads{width:100%}}
</style><header><h1>氯硫耦合侵蚀：建模逻辑图与引言修订</h1><nav><button id="show-map" aria-pressed="true">建模逻辑图</button><button id="show-intro" aria-pressed="false">修订引言</button><span class="spacer"></span><div class="downloads"><a href="氯硫耦合建模逻辑图.svg" download>可编辑SVG</a><a href="氯硫耦合建模逻辑图.png" download>高清PNG</a><a href="氯硫耦合建模逻辑图.pdf" download>矢量PDF</a><a href="氯硫建模引言_修订候选.md" download>引言Markdown</a></div></nav></header>
<main><section id="map-view"><div class="tools"><label><input id="leach-toggle" type="checkbox" checked> 钙溶蚀分支</label><label><input id="env-toggle" type="checkbox" checked> 温湿度分支</label><button id="zoom-in">放大</button><button id="zoom-reset">适合宽度</button><span class="note">点击方法或能力框，查看适用范围与依据。</span></div><div class="canvas" aria-label="氯硫耦合建模能力图">__SVG__</div></section><section id="intro-view" class="reading" hidden>__INTRO__</section></main><aside class="detail" id="detail" hidden aria-label="方法能力与依据"></aside>
<script id="model-data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.querySelector('#model-data').textContent),detail=document.querySelector('#detail'),svg=document.querySelector('.canvas svg');
function showDetail(id){const d=data[id];if(!d)return;detail.replaceChildren();const close=document.createElement('button');close.className='close';close.textContent='×';close.setAttribute('aria-label','收起方法详情');close.onclick=()=>detail.hidden=true;detail.append(close);const add=(tag,text)=>{const el=document.createElement(tag);el.textContent=text;detail.append(el);return el};add('h2',d.title);add('h3','能够描述');add('p',d.capability);add('h3','仍需补充或限定');add('p',d.boundary);add('h3','原文与官方依据');for(const s of d.sources){const item=add('div','');item.className='source';const a=document.createElement('a');a.textContent=s.title;a.href=s.url;a.target='_blank';a.rel='noreferrer';item.append(a);const small=document.createElement('small');small.textContent=s.scope;item.append(small)}detail.hidden=false}
document.querySelectorAll('[data-node-id]').forEach(n=>{n.onclick=()=>showDetail(n.dataset.nodeId);n.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showDetail(n.dataset.nodeId)}}});
function toggleBranch(which,on){for(const id of which==='leach'?['node-leaching','branch-left','conditional-solve-left']:['node-environment','branch-right','conditional-solve-right']){const el=document.getElementById(id);if(el)el.style.display=on?'':'none'}}
document.querySelector('#leach-toggle').onchange=e=>toggleBranch('leach',e.target.checked);document.querySelector('#env-toggle').onchange=e=>toggleBranch('env',e.target.checked);
let zoom=1;document.querySelector('#zoom-in').onclick=()=>{zoom=Math.min(2.5,zoom+.25);svg.style.width=(zoom*100)+'%'};document.querySelector('#zoom-reset').onclick=()=>{zoom=1;svg.style.width='100%'};
for(const which of ['map','intro'])document.querySelector('#show-'+which).onclick=()=>{detail.hidden=true;for(const v of ['map','intro']){document.querySelector('#'+v+'-view').hidden=v!==which;document.querySelector('#show-'+v).setAttribute('aria-pressed',String(v===which))}};
</script></html>'''
page=page.replace('__SVG__',svg).replace('__INTRO__',md_blocks(intro)).replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
(OUT/'index.html').write_text(page,encoding='utf8')
print(OUT/'index.html')
