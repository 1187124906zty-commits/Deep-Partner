"""Prepare editable example documents from downloaded sources and actual reports."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def p(value):return {'type':'paragraph','content':[{'type':'text','text':value}]}
def h(value):return {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':value}]}
def eq(value):return {'type':'blockMath','attrs':{'latex':value}}
def table(rows):return {'type':'table','content':[{'type':'tableRow','content':[{'type':'tableHeader' if i==0 else 'tableCell','content':[p(value)]} for value in row]} for i,row in enumerate(rows)]}

root=ROOT/'examples/pinn-burgers';report=json.loads((root/'project/results/reference-summary.json').read_text())
manifest={'id':'pinn-burgers','name':'PINN · Burgers','language':'en','description':'英文稿件、作者代码与参考数据、结果图和组会汇报','repository':'https://github.com/maziarraissi/PINNs','article':'https://arxiv.org/abs/1711.10561','knowledge_base':'PINN_Burgers','image':'results/burgers-reference.png','compute_program':'src/Burgers.py',
 'literature':[{'file':'pinn-burgers/literature/arxiv_1711.10561.pdf','stage':'问题与方法','title':'Physics Informed Deep Learning (Part I): Data-driven Solutions of Nonlinear Partial Differential Equations'},
 {'file':'reference-downloads/arxiv_2001.04536.pdf','stage':'训练与验证','title':'Understanding and mitigating gradient pathologies in physics-informed neural networks'},
 {'file':'reference-downloads/arxiv_1711.10566.pdf','stage':'相关工作','title':'Physics Informed Deep Learning (Part II): Data-driven Discovery of Nonlinear Partial Differential Equations'}]}
write(root/'manifest.json',manifest)
content=[h('Abstract'),p('This example organizes the Burgers-equation materials released with the PINNs project. It combines the original paper, author-provided code and reference data, an editable manuscript and a presentation. The displayed fields are supplied reference solutions; this demonstration does not train a PINN.'),
 h('1. Research question'),p('Physics-informed neural networks approximate a solution while incorporating a differential-equation residual into training. The Burgers problem provides a compact example in which advection, diffusion and a steepening spatial profile can be inspected together [1].'),
 h('2. Governing equation'),eq(r'u_t+u u_x-\frac{0.01}{\pi}u_{xx}=0,\quad x\in[-1,1],\quad t\in[0,1]'),eq(r'u(0,x)=-\sin(\pi x),\qquad u(t,-1)=u(t,1)=0'),p('The conditions above are taken from Eq. (3) of the downloaded Part I paper, PDF page 5. Coordinates and field values are treated as dimensionless in this example.'),
 h('3. Reference data'),p('The supplied burgers_shock.mat file contains 256 spatial locations and 100 saved times, from t = 0 to t = 0.99. The plotting script reads this file without changing it and draws the space-time field and four time slices.'),
 {'type':'image','attrs':{'src':'asset:burgers-reference.png','title':'Figure 1. Author-supplied Burgers reference solution and time slices. This is reference data, not a network prediction.','alt':'Burgers reference field and time slices'}},
 table([['Quantity','Observed value'],['Spatial locations',str(report['shape'][0])],['Saved times',str(report['shape'][1])],['Initial-condition maximum difference',f"{report['initial_max_error']:.3e}"],['Finite entries','All entries checked']]),
 h('4. Verification and limits'),p('The initial slice agrees with −sin(πx) to floating-point precision. This check verifies the identity and interpretation of the supplied array. Network training accuracy, optimization stability and generalization require separate experiments. Gradient-related training issues are discussed in the validation reference [2].'),
 h('5. Reproducibility'),p('Run python src/plot_reference.py from the program folder. The original Burgers.py is retained for inspection; it uses the upstream TensorFlow 1-era training API. Code is pinned to commit 932f50a2d8ef4e80d1456bbae6887a73ff5166ef under the MIT license. The present plotting task was run through Slurm, and its numerical report is in results/reference-summary.json.'),
 h('References'),p('[1] Raissi, Perdikaris and Karniadakis. Physics Informed Deep Learning (Part I), arXiv:1711.10561. The downloaded file is the Part I preprint.'),p('[2] Wang, Teng and Perdikaris. Understanding and mitigating gradient pathologies in physics-informed neural networks, arXiv:2001.04536.'),p('[3] Raissi, Perdikaris and Karniadakis. Physics Informed Deep Learning (Part II), arXiv:1711.10566.')]
write(root/'manuscript.json',{'title':'Inspecting a physics-informed Burgers example','template':'elsevier','content':{'type':'doc','content':content},'comments':[]})
write(root/'slides.json',{'title':'PINN：Burgers 方程示例','sections':[{'id':'cover','role':'cover','title':'PINN：Burgers 方程示例','content':'从原始文献、作者代码到数据图与审阅稿'},
 {'id':'question','role':'content','title':'物理残差如何约束网络解','content':'原论文在数据误差之外加入 Burgers 方程残差。\n初始条件为 −sin(πx)，两端取零值。\n本示例使用作者提供的参考解，尚未执行网络训练。'},
 {'id':'figure','role':'content','title':'参考数据中的时空演化','content':'256 个空间点、100 个保存时刻。\n左图显示参考场，右图比较时间切片。','figures':['Figure 1']},
 {'id':'ending','role':'ending','title':'从资料整理到可复现实验','content':'原始 PDF 已按问题、训练验证与相关工作归入知识库。\n绘图脚本、原始数据和结果图相互关联。\n后续训练应单独检验误差、优化稳定性和泛化。'}]})
(root/'project/requirements.txt').write_text('numpy\nscipy\nmatplotlib\n',encoding='utf8')
(root/'project/README.md').write_text('''# PINN / Burgers workbench example

Author source: https://github.com/maziarraissi/PINNs
Paper read: https://arxiv.org/abs/1711.10561 (Part I preprint)

`python src/plot_reference.py` regenerates `results/burgers-reference.png` from the authors' `data/burgers_shock.mat`. The input stays unchanged. Install the small plotting dependencies with `pip install -r requirements.txt` if needed.

This example visualizes supplied reference data. It does not present a trained PINN. `src/Burgers.py` is the original TensorFlow 1-era training script and requires its upstream environment. See `docs/UPSTREAM.md` and `LICENSE`.
''',encoding='utf8')

root=ROOT/'examples/fno-darcy';report=json.loads((root/'project/results/reference-summary.json').read_text())
manifest={'id':'fno-darcy','name':'FNO · Darcy 中文','language':'zh-CN','description':'中文整理稿、官方算子学习代码与小样本数据、结果图和汇报','repository':'https://github.com/neuraloperator/neuraloperator','article':'https://arxiv.org/abs/2010.08895','knowledge_base':'FNO_Darcy','image':'results/darcy-reference.png','compute_program':'src/plot_FNO_darcy.py',
 'literature':[{'file':'reference-downloads/arxiv_2010.08895.pdf','stage':'问题与方法','title':'Fourier Neural Operator for Parametric Partial Differential Equations'},
 {'file':'reference-downloads/arxiv_2111.03794.pdf','stage':'训练与验证','title':'Physics-Informed Neural Operator for Learning Partial Differential Equations'},
 {'file':'reference-downloads/arxiv_1910.03193.pdf','stage':'相关工作','title':'DeepONet: Learning nonlinear operators for identifying differential equations based on the universal approximation theorem of operators'}]}
write(root/'manifest.json',manifest)
content=[h('摘要'),p('本示例以 Fourier Neural Operator 的 Darcy 流问题为线索，把原始论文、作者维护的代码、公开小样本数据和可编辑稿件放在同一工作区。图中展示的是代码仓库附带的参考数据，本次运行完成数据读取、检查和绘图，尚未训练 FNO。'),
 h('1  研究问题'),p('参数化偏微分方程需要对不同输入场反复求解。FNO 学习输入函数到解函数的映射，并在傅里叶空间中参数化积分核。Darcy 流算例将空间变化的系数场作为输入，将稳态解作为输出[1]。'),
 h('2  方程与条件'),eq(r'-\nabla\cdot(a(x)\nabla u(x))=1,\quad x\in(0,1)^2'),eq(r'u(x)=0,\quad x\in\partial(0,1)^2'),p('以上条件依据已下载 FNO 论文附录 A.3.2。原论文的系数取两个正值，参考解采用 421×421 网格计算后降采样。本工作区使用当前 NeuralOperator 仓库的小型示例文件，不将它等同于原论文全部基准数据。'),
 h('3  数据与结果图'),p('当前数据文件把输入相位存为 torch.bool 类型。图中左侧直接显示保存的 0/1 编码，右侧显示配套参考解；没有将 0/1 冒充带物理单位的渗透率，也没有自行恢复未核实的编码映射。'),
 {'type':'image','attrs':{'src':'asset:darcy-reference.png','title':'图1  NeuralOperator 小型 Darcy 测试样本：保存的二值输入编码与配套参考解。','alt':'Darcy 数据中的输入相位编码与参考解'}},
 table([['检查项','本次结果'],['输入数组形状',' × '.join(map(str,report['shape']))],['输入存储类型','torch.bool，相位编码'],['数据有效性','所有数组项均为有限值'],['网络训练','本示例未执行']]),
 h('4  验证应回答什么'),p('资料整理与预测模型验证承担不同任务。当前结果用于核对文件、图像和程序索引是否一致；若开展训练，需要在独立测试样本上报告误差，并说明训练分辨率、测试分辨率和归一化方式。知识库中的 PINO 文献[2]可用于考察物理约束，DeepONet 文献[3]提供另一类算子表示作为相关方法。'),
 h('5  运行与来源'),p('在程序目录运行 python src/plot_reference.py 可重建图1。src/plot_FNO_darcy.py 为作者维护的训练示例，src/fno.py 为同一提交的模型实现；完整训练需安装并遵从上游 NeuralOperator 环境。本地副本固定为 a6648eeeb60fe0837f2d7d021517a945a159a0c8，保留 MIT 许可证。计算图在已登记集群的 Slurm 作业中生成。'),
 h('参考文献'),p('[1] Li 等. Fourier Neural Operator for Parametric Partial Differential Equations. ICLR 2021, arXiv:2010.08895。'),p('[2] Li 等. Physics-Informed Neural Operator for Learning Partial Differential Equations, arXiv:2111.03794。'),p('[3] Lu、Jin、Karniadakis. DeepONet: Learning nonlinear operators for identifying differential equations based on the universal approximation theorem of operators, arXiv:1910.03193。')]
write(root/'manuscript.json',{'title':'Darcy 流算子学习：从公开资料到可审阅结果','template':'chinese','content':{'type':'doc','content':content},'comments':[]})
write(root/'slides.json',{'title':'Darcy 流算子学习示例','sections':[{'id':'cover','role':'cover','title':'Darcy 流算子学习示例','content':'文献、代码、参考数据与可编辑稿件'},
 {'id':'method','role':'content','title':'从系数函数映射到解函数','content':'Darcy 方程给定空间变化系数场，求稳态解。\nFNO 在傅里叶空间参数化算子。\n公开小型数据用于展示资料与图像的对应关系。'},
 {'id':'results','role':'content','title':'输入编码与参考解需要区分','content':'左图为当前文件保存的二值相位编码。\n右图为同一样本的参考解。\n本次完成绘图与数据核对，尚未训练网络。','figures':['Figure 1']},
 {'id':'ending','role':'ending','title':'进一步研究需要补齐的证据','content':'核对归一化、训练条件和独立测试集。\n比较不同分辨率与不同算子模型。\n在相同条件下讨论误差与计算开销。'}]})
(root/'project/requirements.txt').write_text('numpy\nmatplotlib\ntorch\n',encoding='utf8')
(root/'project/README.md').write_text('''# FNO / Darcy 中文示例

上游：https://github.com/neuraloperator/neuraloperator
原始论文：https://arxiv.org/abs/2010.08895

运行 `python src/plot_reference.py` 从仓库附带的 `data/darcy_test_16.pt` 生成结果图。绘图依赖见 `requirements.txt`，原始文件不改动。

输入在该文件中以 torch.bool 保存，图中显示原始二值编码，不把它当作实际渗透率数值。当前小型数据不等同于原论文完整 421×421 基准。本示例未训练网络，不报告复现出的 FNO 性能。

`src/plot_FNO_darcy.py` 与 `src/fno.py` 为固定提交的作者源码，训练示例需完整的 `neuraloperator` 上游环境。见 `docs/UPSTREAM.rst`、`docs/darcy_dataset.py` 与 `LICENSE`。
''',encoding='utf8')
print('Prepared two editable, source-bound example packages')
