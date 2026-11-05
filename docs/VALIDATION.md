# 本次源码归集检查

- 公开内容扫描：Gitleaks 8.30.1，使用逐项审阅的上游测试/示例误报例外；未发现未处理的命中。
- 关键工程入口：工作台、DeepTutor、Dify、交付桥、工具桥、集群运行器及桌面端已纳入。
- 工作台同一任务恢复测试：24 项通过。命令：`python -X utf8 -m unittest discover -s tests -p test_workflow_recovery.py -q`，在 workbench 目录运行。Windows 的默认 GBK 编码曾使读入 UTF-8 状态文件失败，使用明确 UTF-8 模式后通过；未修改生产恢复算法。
- 集群契约测试依赖 Linux 的 fcntl，不应以 Windows 导入失败解释为集群实现失败。

这些检查不代表完整安装、全系统构建或科研结果复现已经完成。四系统边界的端到端故障试验见 ARCHITECTURE_REVIEW.md。
