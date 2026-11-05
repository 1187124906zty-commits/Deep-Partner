"""Revise the physical modeling argument, preserving the existing later research spine."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/氯硫建模逻辑图-20261104'
SOURCE = ROOT/'reports/氯硫框架具体化/workflow-20261104/氯硫引言_研究群体综合候选.md'
original = SOURCE.read_text(encoding='utf8')
body, refs = original.split('## 参考文献', 1)
old = [p.strip() for p in body.split('\n\n') if p.strip() and not p.strip().startswith('#')]
assert len(old) == 8

physical = [
    '氯盐与硫酸盐共同侵蚀下，混凝土耐久性预测需要同时回答侵蚀离子如何进入、进入后怎样与水化基体反应，以及这些反应何时改变传输通道并引起损伤。共同暴露试验显示，胶凝材料组成、养护状态与暴露历程改变时，离子侵入和材料劣化的响应也会改变，因而不能用固定的促进或抑制关系概括氯硫共同作用[1–3]。面向长期建模，这一条件依赖要求把离子迁移、化学分配和损伤反馈连接为随材料状态更新的过程，使自由氯的累积与基体劣化能够在同一描述下预测。',
    '经典扩散—反应模型以离子质量守恒为基础，将传输通量与反应、结合关系联立。Fick定律描述浓度梯度驱动的扩散；Nernst–Planck方程进一步引入电迁移，多离子模型还可结合液相流动描述对流及浸出[51–52]。这些通量关系本身不确定离子与水化产物之间的反应，化学作用仍需通过结合关系、反应动力学或相平衡闭合。扩散—反应及多离子耦合模型已据此描述氯硫竞争、结合能力变化和离子分布的时空演化[12–18]。当研究目标进一步涉及水化产物的溶解、沉淀与相转化时，热力学平衡将局部组成联系到孔液物种和固相含量，表面络合则补充离子吸附的描述[4–11,53]。因此，化学描述的差别在于采用了怎样的反应闭合，以及它能否随局部组分更新；平衡计算的适用性仍取决于反应相对于传输足够快，并受到所选相集合和热力学数据的限制。',
    '反应的闭合还不足以给出材料损伤，化学变化必须通过膨胀或压力关系进入力学描述。体积增长理论由固相体积变化及孔隙容纳估计化学膨胀，结晶压理论则把过饱和状态与孔内约束联系到产物施加的压力；二者都需要进一步描述基体约束，不能由产物总量直接判定开裂[19–23]。在此基础上，损伤函数或连续损伤关系可表征劣化，并修正氯离子扩散和结合，使化学—损伤—传输模型反映侵蚀早期孔隙填充与后期损伤加速侵入的不同作用[24–26]。当目标涉及裂纹路径、局部传输通道或剥落形貌时，细观断裂和非局部模型进一步引入裂纹空间演化[31–34]；相场断裂则通过连续裂纹变量求解起裂与扩展，并将裂纹和孔隙状态反馈至传输[35–37]。这一扩展提高了对局部破坏的表征能力，也要求化学膨胀、断裂驱动力与通量修正之间具有明确联系。',
    '上述物理描述还需随服役条件选择扩展。对于显著钙溶蚀的环境，除侵蚀离子的传输与结合外，还应描述含钙固相向孔液释放钙及其迁出；在局部平衡近似成立时，可将钙的固液平衡曲线与传输方程联立，或通过更完整的矿相溶解模型更新孔隙与基体软化[11,28,30,51]。对于非等温或非饱和暴露，温度、含水状态和水分运动又会改变迁移与反应条件，需要相应的热湿控制方程及参数关系[27–30]。这些扩展由环境对预测目标的实际影响决定。有限元等方法承担所选方程的离散与求解，可以联立或交替推进传输、反应和力学；数值平台及其PDE接口本身并不提供缺失的反应、损伤或温湿度关系[51–52]。随着局部化学和裂纹状态持续交换，多场迭代与裂纹区域的空间分辨需求增加了参数校准及多工况比较的计算成本[38]。'
]
later = old[2:]
later[0] = later[0].replace('把不同材料和暴露条件下的响应学习为可重复调用的映射，为减少上述计算负担提供了深度学习途径。',
    '将不同材料和暴露条件下的耦合响应学习为可重复调用的映射，为减少反复数值求解提供了深度学习途径。')
later[-2] = later[-2].replace('其需要衔接的对象', '需要衔接的对象')
paras = physical + later
additions = '''

[51] 王鹏刚; 莫芮; 隋晓萌; 田砾; 徐俊; 金祖权. 混凝土中氯盐-硫酸盐耦合侵蚀的化学-损伤-传输模型研究进展. 硅酸盐学报, 2022, 50(2): 512–521. [DOI](https://doi.org/10.14062/j.issn.0454-5648.20210248)

[52] Björn Johannesson; Kazuo Yamada; Lars-Olof Nilsson; Yoshifumi Hosokawa. Multi-species ionic diffusion in concrete with account to interaction between ions in the pore solution and the cement hydrates. Materials and Structures, 2007, 40(7): 651–665. [DOI](https://doi.org/10.1617/s11527-006-9176-y)

[53] Yoshifumi Hosokawa; Kazuo Yamada; Björn Johannesson; Lars-Olof Nilsson. Development of a multi-species mass transport model for concrete with account to thermodynamic phase equilibriums. Materials and Structures, 2011, 44: 1577–1592. [DOI](https://doi.org/10.1617/s11527-011-9720-2)
'''
text = '# 氯硫耦合建模引言：按模型能力与研究问题重组的候选\n\n' + '\n\n'.join(paras) + '\n\n## 参考文献\n' + refs.rstrip() + additions
(OUT/'氯硫建模引言_修订候选.md').write_text(text,encoding='utf8')
(OUT/'建模部分_四段修订.md').write_text('# 氯硫耦合侵蚀的物理建模部分\n\n'+'\n\n'.join(physical)+'\n',encoding='utf8')
# Keep existing stable numbering; all references must actually participate.
used=set()
for match in re.finditer(r'\[([\d,–—\- ]+)\]', '\n'.join(paras)):
    for part in match[1].split(','):
        part=part.strip()
        if re.fullmatch(r'\d+[–—-]\d+',part):
            a,b=map(int,re.split('[–—-]',part));used.update(range(a,b+1))
        elif part.isdigit():used.add(int(part))
assert used==set(range(1,54)), sorted(set(range(1,54))-used)
receipt={'source_candidate':str(SOURCE),'confirmed_structure':'传输基础→反应闭合→膨胀/损伤及反馈；钙溶蚀和温湿度条件分支；数值求解单列，之后承接既有学习主线',
    'changed':'原物理建模两段重组为意义一段和建模三段；后续六段保留研究范围并调整承接句。',
    'paragraphs':len(paras),'references_in_text':len(used),'manuscript_status':'new candidate; original retained',
    'source_limits':['王综述4.2.2中温湿度共同作用PDE实现被表述为未来工作；本稿没有将其写成该综述已完成验证。','Johannesson题录按Lund作者机构记录修正为2007、651–665；原文献已含简单离子交换，不写为完全无化学作用。','相场与有限元分属物理描述和数值求解，可组合。'],
    'prose':'Only the approved structural revision has been made; no experimental or computational performance results were added.'}
(OUT/'引言修订记录.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'paragraphs':len(paras),'references':len(used),'physical_characters':sum(map(len,physical)),'full_characters':sum(map(len,paras))},ensure_ascii=False))
