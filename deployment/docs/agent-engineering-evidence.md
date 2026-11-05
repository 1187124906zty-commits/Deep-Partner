# 现有研究助手的 Agent 工程依据与整改建议

核验日期：2026-11-01。结论是保留 DeepTutor 的研究对话与工具循环，复用 DeepCode 的实现和计算能力，让研究工作台保存文件、版本与证据；Dify 展示业务阶段并调用这些能力。认证、版本条件、提交和回读应由现有 Python 适配器统一执行。这个职责划分是结合当前架构作出的工程判断，官方文章没有直接评测本项目或证明其故障原因。

采用以下六项第一方来源，已阅读正文与有关协议条款：

| 来源及版本 | 本次使用的依据与边界 |
| --- | --- |
| Anthropic：[Building effective agents](https://www.anthropic.com/research/building-effective-agents)，2024-12-19 | 区分预设工作流与模型控制的工具循环；强调简单实现、环境反馈和可测结果。页面已注明工具生态变化，本文只借用架构原则。 |
| Anthropic：[Writing effective tools for agents](https://www.anthropic.com/research/writing-tools-for-agents)，2025-09-11 | 工具职责、命名、输入说明、返回信息和真实任务评测。属于厂商工程经验，收益需在本项目验证。 |
| Anthropic：[Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents)，2025-09-29 | 减少功能重叠，按需取上下文，在外部保存状态与笔记。本文不据此扩展多智能体。 |
| LangChain：[Functional API overview](https://docs.langchain.com/oss/python/langgraph/functional-api)，“Resuming / Determinism / Idempotency” | 恢复会重放；已完成任务可读检查点，未完成任务仍可能重跑。原 durable-execution 地址核验时已重定向，故引用当前官方页面；文档滚动更新，不代表项目已安装对应版本。 |
| MCP：[Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)，2025-11-25 | 工具输入/输出 Schema、结构化内容、协议错误和执行错误。按此明确版本讨论，不假定现有客户端全部支持。 |
| MCP：[Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)，2025-11-25 | 初始化、版本与能力协商、逐请求超时、最大超时和关闭。协议能力不等于具体 SDK 或 Dify 插件已经实现。 |

以下八条中，“依据”概括来源事实，“建议”是对本项目的推断与实施取舍。

1. **一个研究决策入口，一个写入规则实现。** 依据：预设路径适合固定任务，工具循环适合步骤随问题变化的任务。[Anthropic 架构说明](https://www.anthropic.com/research/building-effective-agents) 建议：DeepTutor 负责研究问题、解释和下一步选择；DeepCode 负责实现、数据处理及计算检查；Python 适配器负责写入约束。Dify 不再另行实现账户判断、项目规则、版本比较和保存成功判定，避免两份实现随修改漂移。Dify 对输入形状的检查仍可保留。

2. **画布使用研究阶段表达，技术调用留在服务内部。** 依据：框架抽象会遮住实际行为；工具可封装经常连续发生的多个底层调用。[架构说明](https://www.anthropic.com/research/building-effective-agents)、[工具设计](https://www.anthropic.com/research/writing-tools-for-agents) 建议：把“HTTP 上下文→代码解析→MCP 账户→MCP 规则→代码检查”收敛为“载入研究上下文”，把“HTTP 提交→回执检查→历史→历史检查”收敛为“保存并核对版本”。整体可读为“接收问题→载入研究上下文→研究讨论与必要执行→检查证据→保存并核对版本→交付或显示等待”。阶段封装应保持可追踪的子操作记录；节点减少本身不证明可靠性提高。

3. **工具按用户意图划界，参数表达真实资源。** 依据：工具功能重叠会干扰选择；说明应交代用途、边界和明确参数。[工具设计](https://www.anthropic.com/research/writing-tools-for-agents) 建议：分别暴露“读取项目上下文”“提交指定版本的产物”“提交计算任务”“查询已有任务”“读取计算结果”等能力，避免同一提交既可走通用 HTTP 又可走另一套 MCP 写入。描述写清前置条件、适用时机、何时改用别的工具及副作用；参数使用 `project_id`、`artifact_id`、`expected_version`、`run_id`，说明 ID 来源，避免模糊的 `data`、`user`。名称以本地评测结果决定。

4. **错误要能指导下一步，输出要能校验。** 依据：MCP 用 JSON-RPC error 表达未知工具、请求结构等协议问题，用结果中的 `isError: true` 表达 API、参数值或业务执行失败；可提供 `outputSchema` 和 `structuredContent`。[MCP Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) 建议：在兼容客户端上提供稳定 Schema；若客户端只读文本，则在 `TextContent` 同时返回序列化 JSON，并在唯一适配层解析。业务字段可约定 `error_code`、`message`、`retryable`、`next_action`、`request_id`。这几个字段是项目建议，属于业务契约。认证失败提示重新认证，版本冲突要求刷新基线，暂时网络故障才允许有限重试；超时后写入结果未知时先查状态。

5. **长任务以持久 ID 接续，重试复用同一操作身份。** 依据：LangGraph 恢复使用同一线程标识，按检查点重放；开始但未记下完成结果的任务可能再执行，仍需幂等键或已有结果核对。[LangChain 恢复与幂等](https://docs.langchain.com/oss/python/langgraph/functional-api) 建议：Slurm 提交快速返回 `run_id` 和 `job_id`，后续调用查询/取结果；保存使用 `operation_id`，同键同载荷返回同一回执，变更载荷拒绝复用。持久记录输入版本、外部任务 ID、状态、产物位置和最后错误，断连后先协调已有任务，避免重提作业。MCP 请求 ID、对话 ID 和业务操作 ID 分开。采用这些原则不要求迁移到 LangGraph；MCP 的任务增强也只有双方协商支持后才可使用。

6. **连接、执行、验证和保存分别报告。** 依据：Agent 应依据工具与执行结果获得环境反馈；评测应绑定可核验结果。[Anthropic 架构说明](https://www.anthropic.com/research/building-effective-agents)、[工具评测](https://www.anthropic.com/research/writing-tools-for-agents) 建议：明确区分“接口可达”“任务已受理”“计算已完成”“诊断已通过”“产物已保存并回读”。`HTTP 200`、`isError: false` 或存在 Slurm ID 都不足以宣布研究结论有效。计算输出同时返回检查项、观察值、阈值、原始输出路径和限制；数值诊断未通过时保留输出，标明验证失败，阻止依赖该证据的结论升级。保存回执至少关联项目、产物、版本与可读取引用。

7. **上下文保留索引与当前约束，正文按需加载。** 依据：上下文是有限资源；轻量引用与外部笔记可支持按需取数及长期任务。[上下文工程](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents) 建议：载入项目时给当前问题、已确认约束、版本、待处理事项和证据引用；论文全文、完整作业日志、历史文件按范围读取。证据引用携带来源、定位、产物版本和用途限制，防止摘要脱离原文。对话摘要帮助续接，研究工作台中的版本化原件承担事实回查。

8. **用真实故障场景验证可靠性，先定位失败层。** 依据：MCP 要求初始化先完成版本/能力协商；应配置请求超时，并在进度通知延长等待时仍保留最大超时。[MCP Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) 工具工程还要求用真实任务结果、调用记录、耗时和错误评测改进。[工具评测](https://www.anthropic.com/research/writing-tools-for-agents) 建议：先记录失败属于传输、初始化、发现、Schema、认证、业务执行还是回读，再修改对应层。至少验证“写入成功但回执丢失后重试”“旧版本冲突”“Slurm 排队期间客户端断连”“任务失败仍可取日志”“服务重启后恢复”“计算完成但诊断未通过”。验收看不重复写入/提交、正确恢复、原始证据可读和用户状态准确；不要用连通性测试代替完整研究任务。

建议先收敛适配器契约与错误结构，再整理 Dify 画布，最后用上述场景验证。这里给出的阶段名称、字段与恢复方案均为待实施建议；未在本次研究中改动或部署代码，也未运行本地 MCP。现有工作流和适配器的事实范围来自本次任务交接，故可以判断重复职责的风险，但不能据此断言某个 MCP 不稳定已经由哪一行代码造成。
