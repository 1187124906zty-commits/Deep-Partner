---
name: deep-partner-research
description: 在 Deep Partner 项目内开展文献调研、方法比较、研究想法整理与代码或汇报交接；使用已实现的工作流路由，自动入库、保存研究记录并更新知识图谱。
---

# Deep Partner 研究入口

研究任务以 Deep Partner 的真实项目 ID 为归属。优先使用 `deep-partner` MCP 的少量入口；未在当前会话加载时使用 `C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe`。先列项目并复用当前任务绑定，不能把其他项目的材料或账户共享记忆混入。

任务开始只选择一次结构化类型，再由程序执行阶段和调用工具：

- `search`：调用 Scholar MCP 的真实检索工具。失败先诊断解释器、协议、桥接/隧道、网络、限流或验证，再修复可恢复问题并接续原工具；只有明确启用 `allow_search_fallback` 才使用其他题录来源。
- `survey`：检索 → 已配对的 ScanSci 下载 → PDF 身份核对及项目入库 → 集群解析 → 有页码的有限原文摘录 → 研究综合 → 项目材料与知识图谱。
- `download`：已有 DOI/arXiv 的文献下载和项目归档。
- `analyze`：对项目中明确的文献 assets 复用经源文件核验的集群 Markdown/逐页文本，按 `read_pages` 分批读取和综合。
- `code`：普通实现与修复默认 `code_engine=agent`，实际调用 `deepcode`，同会话续接调用 `deepcode-reply`。以原论文为来源的复现明确选择 `code_engine=paper2code`，保留其原生规划、实施、验证、交互、重试和产物状态。只交接 `input_paths` 指定材料。原生权限拒绝须由明确权限设置处理，不能换外层 LLM 代做。
- `slides`：调用项目的 Paper2Slides 流程，传入已保存的模板与结构确认 ID。
- `simulate`：明确工况和输入 → 现有集群运行时或 openPASO MCP → Slurm 求解 → 作业内结果核验 → 原始结果保留集群，摘要、报告及来源关系回到项目。参数见 [仿真接口](references/simulation.md)，仅在仿真任务时读取。

不默认读取全部技能、全文、历史和工具 schema。只读取当前路由和本次所需项目材料；默认每轮 3 篇、每篇 14000 字符，进一步阅读另开明确批次。搜索发现与全文证据分开。下载完成需有项目入库回执，索引状态单独读取。

代码交接先从已有任务与材料明确问题、方法、项目、实际入口和预期输出，放进现有说明即可。按有意义的阶段实现并集中验证，通过且没有新失败或改动即交付；不默认逐文件测试、重复审查或建立额外合同。数值计算保留影响当前结论的物理与独立参照检查。论文复现保持目标数据与实验范围，小运行通过不代表复现完成；无新诊断或证据时停止同一路径修复，报告真实缺口。工具连接恢复继续原 ID，不能据此自动反复重跑科学失败。

代码执行摘要、文件和工具日志保存在项目执行记录；成功执行不自动创建图谱节点。形成科学方法、发现或明确研究决定后，再用 `workflow record` 保存带证据的判断。保留已有研究材料，不因技术节点拥挤批量删除历史记录。

路线和完成条件固定，论文、知识、程序及任务参数可变。`dp workflow` 启动时恢复所需本机工具服务；每阶段保存回执，`resume` 接续原任务 ID。外部提交结果不明时先核对原任务，不能盲目重复提交。解析通过现有 SSH/Slurm 环境在计算节点运行；原 PDF 保留，Markdown、页码定位及集群作业回执写回所属项目，稀疏文字页交给已安装 MinerU OCR。

CLI 对应入口：

```powershell
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' project list --json
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' workflow routes --project PROJECT_ID --kind survey
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' workflow run --project PROJECT_ID --file REQUEST_JSON
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' workflow status --project PROJECT_ID --id RUN_ID
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' workflow resume --project PROJECT_ID --id RUN_ID
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' workflow record --project PROJECT_ID --file RECORD_JSON
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' chat send --project PROJECT_ID --session SESSION_ID --file MESSAGE_FILE --jsonl
& 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe' chat resume --project PROJECT_ID --session SESSION_ID --jsonl
```

`REQUEST_JSON` 的字段：`kind`、`query`、`instruction`、`entries`、`assets`、`read_pages`、`max_sources`、`session_id`、`confirmation_id`、`request_id`；检索另有 `search_tool/author/cursor/min_year/max_year/allow_search_fallback`，代码另有 `code_engine/workflow_options/input_paths/publish_root`。旧执行回交仅用 `code_task_id` 恢复。每个操作只传所需字段。重复请求沿用 `request_id`；按实际回执报告，不把接收任务当执行成功。工具合同和当前可用状态通过路由与运行回执读取。

`RECORD_JSON` 保存 `id/title/content/nodes/edges/search_scope`。节点类型包括 paper、method、finding、limitation、gap、idea、decision、memo；关系包括 uses、supports、contradicts、limited_by、motivates、proposes、derived_from、addresses。文献判断附 `evidence_refs`（asset、pages，或真实 URL），提议标 proposed。“没找到”标 not_found_in_scope 并保存查询、来源与日期，不改写成“没人做过”。

保存可公开的研究判断、理由摘要、证据、反证和候选方案，不保存隐藏思维链。idea-memo 仍保留本机可恢复副本；将具体 memo 与项目绑定后，记录工具会自动把正文及材料同步到项目文件与图谱。无绑定时只保存本地，不能猜测上传目标。

科学判断、实验设计和论文结构选择仍由作者与研究者作出；工作流负责执行和留存。沿用用户已给的授权，不因进入新工具重复询问。
