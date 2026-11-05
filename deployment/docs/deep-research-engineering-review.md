# 现有 DeepTutor / DeepCode / 工作台 / Dify 的深度研究工程复核

核验日期：2026-11-01。本次只读核验官方文档和公开代码，写入此研究笔记；没有修改服务、启用模型、发送邮件或运行本地联调。现有模块的职责来自任务交接，Webhook 成果事件、IfElse、每 5 分钟状态协调及联合检索为主协调正在推进的工作，本笔记不将其记作已经实施通过。

建议保留 **DeepTutor 作为唯一研究主控，DeepCode 处理实现与计算，研究工作台保管证据、版本和作者决定，Dify 承担可见业务阶段及事件协调**。可借用成熟研究系统的分解、联合检索、原始笔记与限额设计；没有依据再增加一套完整研究主控。

## 来源、版本与实际阅读范围

| 第一方来源 | 阅读范围与使用边界 |
| --- | --- |
| Anthropic：[How we built our multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system)，2025-06-13 | 正文全部：适用任务、任务边界、搜索迭代、引用、评测、持久恢复及附录。性能和 token 数字来自其内部任务与模型，不外推为本项目收益。 |
| Anthropic：[Writing effective tools for agents](https://www.anthropic.com/research/writing-tools-for-agents)，2025-09-11 | 正文全部：工具边界、返回信息、描述、真实任务与留出评测；为工程经验，需本地验证。 |
| LangChain：[Open Deep Research](https://github.com/langchain-ai/open_deep_research) | README 全部、GitHub 仓库元数据；官方仓库现为 archived/read-only。按官方 API 核对代码版本 `1b7d2e80db9faa586165c60e09096dbbfd483a64`，提交时间 2026-08-10；仓库页面显示 2026-08-21 归档。适合参考，不作为持续维护服务推荐。 |
| LangChain：固定版本的 [configuration.py](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/configuration.py)、[deep_researcher.py](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py)、[utils.py](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/utils.py) | 配置；supervisor/researcher 的工具循环、并行、退出、压缩及报告；搜索去重、摘要超时回退和 MCP 加载。没有执行仓库或采用其默认模型。 |
| Dify self-host：[Knowledge Retrieval](https://docs.dify.ai/en/self-host/use-dify/nodes/knowledge-retrieval)、[Integrate Knowledge within Apps](https://docs.dify.ai/en/self-host/use-dify/knowledge/integrate-knowledge-within-application)、[Test Knowledge Retrieval](https://docs.dify.ai/en/self-host/use-dify/knowledge/test-retrieval) | 节点正文全部；多库检索、Rerank、元数据、输出引用与 FAQ；检索测试及记录全部。节点页更新于 2026-06-25，滚动文档不保证本机版本支持全部选项。 |
| Dify self-host：[Orchestration Logic](https://docs.dify.ai/en/self-host/use-dify/build/orchestrate-node)、[Iteration](https://docs.dify.ai/en/self-host/use-dify/nodes/iteration) | 串并行、合流、复用、迭代输入输出与全部错误策略；未使用文章生成示例证明研究有效性。 |
| Dify：[HTTP Request](https://docs.dify.ai/en/self-host/use-dify/nodes/http-request)、[Handle Errors and Rate Limits](https://docs.dify.ai/en/api-reference/guides/errors) | 超时、重试、状态输出；错误包络、流内错误、并发/配额差异及重试规则。页面分别更新于 2026-08-25、2026-10-28；API 规则须对照本机版本实测。 |
| Dify：[Human Input](https://docs.dify.ai/en/self-host/use-dify/nodes/human-input)、[Human Input API Integration Flow](https://docs.dify.ai/en/api-reference/guides/human-input-flow) | 节点正文全部，API 表单获取、提交、同用户接续、停止、过期与投递限制。节点页更新于 2026-07-29。不能凭文档认定现有部署已启用。 |
| Dify：[Schedule Trigger](https://docs.dify.ai/en/self-host/use-dify/nodes/trigger/schedule-trigger) | 正文全部：Workflow 限制、cron、时间变量、测试方式；更新于 2026-07-09。定时触发并不提供业务去重或恢复保证。 |

## 八条会影响真实失败率的建议

1. **复用现有主控，将 skill、MCP 和业务工作流接成能力，而不是增加研究指挥层。** 官方事实：Anthropic 的并行研究适合可独立展开的宽问题，也明确指出共享大量上下文、依赖密集的任务不适合直接并行。[研究系统](https://www.anthropic.com/research/multi-agent-research-system) 项目建议：DeepTutor 决定问题分解、搜索修订和何时证据足够；现有研究/文献 skill 提供方法要求，MCP 提供真实检索与操作，Dify 呈现阶段及等待状态，DeepCode 接收有边界的实现任务。先由协调者盘点实际 API、模型别名、检索库、embedding、reranker 和调用限额，再做各自连通性与业务调用；“配置文件存在”“本机安装了 skill”都不能替代运行时能力验证。反例：把 Open Deep Research 的 supervisor 嵌到 Dify 后又让 Tutor 重新规划，会产生两个预算、完成判定和补查循环。

2. **联合检索先并行取证，再由 Tutor 按缺口补查。** 官方事实：Dify 原生支持并行分支在下游合流；一个 Knowledge Retrieval 节点可同时搜索多个知识库，再合并与重排。[编排](https://docs.dify.ai/en/self-host/use-dify/build/orchestrate-node)、[检索节点](https://docs.dify.ai/en/self-host/use-dify/nodes/knowledge-retrieval) 项目建议：当前联合检索子流程只接已经存在的工作台/项目上下文、已核验的本地 RAG、外部原始文献/网页检索。三路以同一问题及范围约束独立运行，合流后按 DOI、规范 URL 或文档身份去重。输出未回答问题、冲突及覆盖状态，Tutor 再定向补查。原生多知识库检索只覆盖所选库，不等于联网搜索。反例：一次 top-k 后直接写长报告，会漏掉反证；每个来源都启动完整 agent，则放大成本及限流。

3. **统一证据记录，同时保留可回读原件。** 官方事实：Open Deep Research 搜索会按 URL 去重、保留标题/URL，并把压缩研究与 raw notes 分开；Dify 检索结果包含片段、元数据和标题。[检索实现](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/utils.py)、[研究状态处理](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py) 项目建议：各路映射为 `{source_id, query, status, title, url_or_document_id, locator, excerpt, retrieved_at, artifact_version}`，字段为建议契约。区分搜索摘要、已读原文、推断和新提议；引用要指向支持该主张的具体位置。工作台保存原文/日志与版本，Tutor 使用摘要和引用继续讨论，DeepCode 返回代码/数据/诊断产物引用。反例：只保存最后的自然语言总结，会让后续修改无法回查其证据。

4. **局部失败必须可见，不能伪装成空检索。** 官方事实：Dify Iteration 提供终止、失败位置输出 null、移除失败结果三种策略；Open Deep Research 的 supervisor 异常分支会结束研究阶段，其代码含 `is_token_limit_exceeded(...) or True`。[Iteration](https://docs.dify.ai/en/self-host/use-dify/nodes/iteration)、[固定版本代码](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py) 项目建议：联合检索每路返回 `ok / empty / failed / timed_out`、实际来源数量和错误原因。允许已有证据继续交付，但缺少关键来源时将结果标记 `partial`，向 Tutor 暴露待补查项。IfElse 按状态判断，不能只判断数组非空。反例：使用 Remove Failed Results 后将两个成功分支当作三路完整覆盖，或捕获异常只返回字符串后照常宣布完成。

5. **把并发、超时和重试预算放在同一个适配器内协调。** 官方事实：Open Deep Research 配置显式提醒并发会触发限流；Dify HTTP 节点分别配置连接/读/写超时，节点可重试，但 API 对并发限制、配额、认证和参数错误给出不同恢复动作。[配置](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/configuration.py)、[HTTP](https://docs.dify.ai/en/self-host/use-dify/nodes/http-request)、[错误分类](https://docs.dify.ai/en/api-reference/guides/errors) 项目建议：按实际 provider/API key 共用并发额度，先以 2–3 路独立检索作为待测起点；重试由一层主导，设总调用数与总墙钟上限。短暂 `too_many_requests`、网络故障和可恢复 5xx 才退避；认证、参数、配额先纠正。SSE 需检查 `error` 事件，HTTP 200 不能当整轮成功。反例：Dify 重试×SDK 重试×agent 再试，既放大请求又拖延失败反馈；把所有 429 都当短暂拥塞。

6. **成果 Webhook 与 Schedule 共同协调同一持久任务。** 官方事实：Dify Schedule 只提供定时启动；Anthropic 强调长任务故障后应恢复已有进度，重头再跑成本高。[Schedule](https://docs.dify.ai/en/self-host/use-dify/nodes/trigger/schedule-trigger)、[生产可靠性](https://www.anthropic.com/research/multi-agent-research-system) 项目建议：沿用现有 compute MCP 的 `run_id / job_id` 与工作台产物版本。Webhook 到达即处理，5 分钟 Schedule 查询仍未终结的任务；两者调用同一个适配器状态转换与保存逻辑，复用事件/操作 ID。提交快速返回受理身份，后续只查询/取结果；落盘后回读再生成交付回执。反例：每次定时触发都新提 Slurm 作业；Webhook 与定时扫描各提交一次同一成果；Dify HTTP 一直等待整个训练或排队过程。

7. **人工判断沿用工作台作者确认，原生 Human Input 只在兼容入口接入。** 官方事实：Dify Human Input 可暂停并按按钮分支，默认等待三天；Web app 投递不适用于 Trigger 启动的流程。Service API 仅能驱动 Web app 表单；成功提交后表单关闭，接续需保存 `workflow_run_id` 并使用同一 `user`。[Human Input](https://docs.dify.ai/en/self-host/use-dify/nodes/human-input)、[API 接续](https://docs.dify.ai/en/api-reference/guides/human-input-flow) 项目建议：关键科学选择、证据不足下的结论采用等决定，指向现有 Tutor/工作台确认页面，并绑定产物 ID、版本和决定内容。Trigger 流程记录 `awaiting_author` 及已有确认链接；若普通交互入口使用 Human Input，先验证现有 Dify 版本和前端处理完整生命周期，再映射到同一作者决定记录。超时记为过期/待处理，不等同批准。反例：Webhook 后直接接 Web app 表单却无人可见；Dify 和工作台各留一份互不一致的批准；用旧稿确认自动批准新版本。

8. **高强度验证覆盖联合状态与证据结果。** 官方事实：工具工程强调真实任务、可核验结果、调用错误与留出测试；Dify 检索测试页的调参只作用于当前测试会话，记录中包含关联 app 的实际检索。[工具评测](https://www.anthropic.com/research/writing-tools-for-agents)、[检索测试](https://docs.dify.ai/en/self-host/use-dify/knowledge/test-retrieval) 项目建议：固定约 20 个有依据的研究问题，包含精确术语、跨语言、反证、无答案和已知版本冲突，比较单路 RAG、联合检索和 Tutor 定向补查。另注入单路超时、临时限流、配额耗尽、服务重启、重复事件、丢失回执、SSE 断连和旧版本确认。检查来源支持率/覆盖缺口、恢复后的唯一产物及作业数、实际作者决定、耗时/调用量和状态准确性；用本机发布版本运行，保存输入、配置别名与结果引用。反例：仅健康检查、几次成功截图或 LLM 对自己输出打分，无法证明整条研究链可靠；测试页调好 RAG 后未保存正式配置，也不能算上线生效。

这些建议依赖对现有 API/RAG、部署版本与真实失败日志的独立核查。本笔记提供工程选择及反例；本地能力发现、功能实施和压力/故障测试结果应由各自执行记录确认。
