# FNO / Darcy 中文示例

上游：https://github.com/neuraloperator/neuraloperator
原始论文：https://arxiv.org/abs/2010.08895

运行 `python src/plot_reference.py` 从仓库附带的 `data/darcy_test_16.pt` 生成结果图。绘图依赖见 `requirements.txt`，原始文件不改动。

输入在该文件中以 torch.bool 保存，图中显示原始二值编码，不把它当作实际渗透率数值。当前小型数据不等同于原论文完整 421×421 基准。本示例未训练网络，不报告复现出的 FNO 性能。

`src/plot_FNO_darcy.py` 与 `src/fno.py` 为固定提交的作者源码，训练示例需完整的 `neuraloperator` 上游环境。见 `docs/UPSTREAM.rst`、`docs/darcy_dataset.py` 与 `LICENSE`。
