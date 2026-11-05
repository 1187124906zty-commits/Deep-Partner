# 架构审查入口

本文件描述 2026-11-05 工程快照中可从源码追踪的职责和状态。它是代码导航与审查范围，不等同于已经完成独立架构验收。

## 1. 先区分各个系统

| 系统 | 核心职责 | 主要入口 | 它持有的状态 |
|---|---|---|---|
| DeepTutor | 身份、工作区、研究会话、持久化回合、能力与工具执行 | native/DeepTutor/deeptutor/api/routers/unified_ws.py；app；runtime；services/session | 原生 Session、Turn、执行事件与会话恢复 |
| Research Workbench | 项目、文件与版本、文献、稿件、项目研究流程和成果回读 | workbench/server/app.py、storage.py、research_flow.py | 项目及 jobs 数据表、项目目录和 .workbench 中的流程状态 |
| Dify 与交付桥 | 执行已配置的交付/证据/事件工作流，关联产物保存与工作流回执 | deployment/bridge/app.py、delivery.py、automation.py；deployment/ops/optimize_workflow.py | Dify 自身运行记录；交付桥 deliveries 与 automation_events |
| 工具桥与集群服务 | 原生工具执行连接、明确输入的解析与仿真、SSH/Slurm 提交、结果收集 | integrations/codex/deep-partner-research/scripts/tool_runtime.py；cluster/research-compute | 工具桥执行记录和绑定、远端作业请求、Slurm Job、输出与回执 |

浏览器中的任务面板是这些状态的展示入口。审查时不能把它显示的“完成”自动解释成外部作业成功、文件已经保存或科学结论已经通过验证。

## 2. 三条主要调用链

### 原生对话与代码执行

统一前端 → DeepTutor WebSocket/HTTP → TurnApplicationService/持久化回合 → 能力/工具 → 原生代码服务或工作台适配器 → 结果事件 → 原会话。

重点入口：

- native/DeepTutor/deeptutor/api/routers/unified_ws.py
- native/DeepTutor/deeptutor/services/session/turns/
- native/DeepTutor/deeptutor/runtime/
- deployment/tutor-extension/
- integrations/deeptutor-extension/

核对取消命令是否到达实际执行进程，终态事件是否来自同一 Turn，以及客户端断开是否改变服务端执行状态。

### 项目类型化工作流与外部执行

统一前端/项目客户端 → research_flow.install → 工作台持久化 run/state → research_tool_flow 或 research_simulation_flow → 项目工具桥 start/status/collect → 原生执行或集群提交 → 工作台文件保存与回读 → 项目图谱/界面。

重点入口：

- workbench/server/research_flow.py：流程、持久化、恢复与结果整理。
- workbench/server/research_tool_flow.py：bound_call、claim_run、tool_call、native_code、parse_pdf。
- workbench/server/research_simulation_flow.py：输入、执行权限、提交绑定与结果回交。
- integrations/codex/deep-partner-research/scripts/tool_runtime.py：实际工具桥状态与原生会话绑定。
- integrations/codex/deep-partner-research/scripts/cluster_simulation_runtime.py、simulation_worker.py。
- cluster/research-compute/cluster_dispatch.py、cluster_runner.py。

项目流程和较早的 research-compute 接入是并存路径。先从当前路由及调用点确认具体走哪一条，不把相近名称理解成同一个执行器。

### Dify 成果交付

原生工具/已授权客户端 → 交付桥 deliver → 校验当前账户、项目及工作区 → deliveries 登记 → Dify Workflow Run → prepare/commit/verify 回调 → 工作台保存与回读 → 交付回执 → 事件队列与后续协调。

重点入口：

- deployment/bridge/delivery.py：DeliveryService.deliver、prepare、commit、verify_delivery、status。
- deployment/bridge/automation.py：enqueue、dispatch、worker、reconcile。
- deployment/bridge/workbench_mcp/：工作台 API 与 MCP 的边界。
- deployment/ops/optimize_workflow.py：实际交付节点与核验要求。
- deployment/research-delivery.dsl.json：保留的 DSL；图定义与程序化更新脚本一并审查。
- native/Dify/api/：Dify 自身的运行、事件和节点实现。

## 3. 状态与标识符的关系

| 标识/记录 | 事实来源 | 关联用途 |
|---|---|---|
| owner、project_id、native_id/workspace_id | 账户服务与工作台项目记录 | 身份与项目隔离；不能只靠前端选择状态 |
| native Session/Turn | DeepTutor 原生会话服务 | 持久化对话、事件重放及执行身份 |
| 工作台 jid/rid、state.json | 工作台流程与 jobs 记录 | 流程阶段、外部任务绑定、恢复次数和下一次查询时间 |
| 工具桥 operation ID | tool_runtime 的 jobs 与执行绑定 | start/status/collect 去重和原生外部任务追踪 |
| request_id、交付 run_id | 交付桥 deliveries | 同一交付请求去重、文件保存状态和回执 |
| workflow_run_id | Dify | 该工作流运行的事实与终态核对 |
| experiment_id/job_id | 集群调度文件与 Slurm | 提交及查询同一远端作业，保存真实输出 |

关键问题：重复请求是否沿用同一 ID？相同 ID 的不同负载是否拒绝？客户端状态丢失后，能否从持久记录恢复外部关联？

## 4. 已有恢复机制

- 工作台 claim_run 使用操作系统持有的非阻塞文件锁，在不同线程/实例/进程之间竞争同一执行所有权。
- bound_call 在提交状态不明时先查询同一工具 ID；明确确认不存在后才使用原请求及相同 ID 重试。
- research_flow 区分外部任务仍运行、可恢复基础设施错误、需要用户输入和其他失败，保留恢复次数与 retry_after。
- waiting_service 路径使用健康检查再接续，避免把服务离线直接当成重新创建研究任务的理由。
- Dify 交付桥将原生保存回执和 Dify 工作流终态分开；保存已经核验但终态响应中断时，可返回 workflow_status=unknown。
- 自动化协调按已经登记的 workflow_run_id 查询运行状态，并对持久事件继续处理。
- 集群 dispatch 使用实验记录、锁和 Slurm ID 组织提交与查询；原始结果保留远端。

这些机制各自解决局部恢复。是否形成一致的端到端恢复语义，需要以下故障试验来确认。

## 5. 首轮审查应验证的情形

1. **提交成功、响应丢失**：分别在工具桥、Dify 和 sbatch 返回边界注入断连；确认不会产生第二个外部任务。
2. **进程重启、外部作业仍运行**：重启工作台/工具桥后，应先找回原执行 ID 和状态，避免把 running 直接覆盖成 failed 后重做。
3. **文件已写、回执未记**：验证下一轮如何识别已写内容及版本，不覆盖用户并发修改。
4. **同一项目被多个恢复实例扫描**：确认锁的实际存储位置在实例间共享，且任务认领、持久化和重试条件一致。
5. **凭据失效与授权撤销**：授权绑定只记录身份关系；检查恢复时仍需哪些有效权限，避免把绑定当成永久执行令牌。
6. **取消与终态竞态**：已取消任务之后到来的完成事件，不应把项目或会话重新标为成功执行。
7. **局部成功**：下载成功、解析失败、保存成功、Dify 失败、仿真完成但数值判据不通过，都应保留各阶段真实状态。
8. **历史接入并存**：确认原 research-compute、类型化仿真工作流和原生 Code 交付路径各自被哪些调用方使用，避免跨路径重复提交。

## 6. 需要特别检查的实现点

交付桥的运行 ticket 是内存对象，并有到期时间；deliver 的 finally 路径会释放 ticket。应检查 Dify 回调延迟、进程重启和超时后，哪些步骤还能仅凭持久记录继续。不要根据“已有 SQLite 记录”就推断所有授权与回调材料都可恢复。

工作台 jobs、项目 state.json 和工具桥 jobs 是多个存储副本。应检查每次外部提交之前和之后的写入顺序，以及崩溃窗口内哪一份记录能够证明执行已经发生。

生产中存在多个共享工作台源码/数据的专用 worker。应核对路由、runtime_generation、项目允许列表和进程锁共同形成的执行边界，而不只检查单进程单元测试。

## 7. 给外部开发 Agent 的任务

先完成以上四类边界审查，以“源码位置 → 可触发情形 → 影响 → 有界修正 → 验证证据”的方式报告。先处理最有证据的一项。新增组件必须说明它接管了哪一项状态，以及原所有者如何退出；不额外叠加一个同时拥有重试和运行终态的调度器。
