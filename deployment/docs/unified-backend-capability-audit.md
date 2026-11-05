# 统一会话、执行与成果审查：服务端复用核查

核查日期：2026-11-02。只读检查本机源码与已保存的生产验证记录；未连接生产服务、未提交模型请求、未运行部署脚本，本文不把历史验证记录当成本轮在线健康证明。范围为 `D:/Development/research-workbench/server/`、`D:/Development/询问/dify-research-deployment/bridge/`，以及必要的 `C:/Users/DEVELOPER/DeepTutor/deeptutor/` 会话协议。未读桌面 Rust 或 DeepTutor 前端。已读两项目适用 AGENTS.md。

## 1. 建议采用的主线

正式桌面应用应以 DeepTutor 已有 `SessionStore → TurnApplicationService → /ws v2` 为唯一主会话和执行入口，以工作台已有项目、文件版本、批注和回执作为成果层，以 Dify bridge 作为工作流运行与交付记录层。无需再建一套聊天 messages/session 表。

“DeepPartner”可能只是桌面产品名。下面的 persona Partner 接口是已有可选运行分支，不能仅因产品命名把 `/api/partners` 强加为主会话依赖。

最小数据关系：

```text
authenticated owner
  └─ workbench project_id ↔ native workspace_id (= project.native_id)
       └─ native session_id
            └─ native turn_id + client_submission_id
                 ├─ 折叠工具步骤：Dify workflow_run_id / bridge run_id / workbench job_id
                 └─ 成果反馈：annotation_ids → artifact binding → receipt → quality review
```

前三层已有；turn 到工作流、批注、成果和审查之间的显式关联是最小新增接缝。桌面只需呈现会话、折叠活动和成果反馈，不需要按评分、检索、交付分别建立会话界面。

## 2. 已有持久会话与可恢复执行

| 现有接口/函数 | 已提供的能力 | 直接复用方式 |
|---|---|---|
| `GET /api/sessions`；`api/routers/sessions.py:247 list_sessions` | limit/offset；workspace_id；all_workspaces；原生会话清单 | 桌面会话列表，筛选当前原生工作区 |
| `GET /api/sessions/{session_id}`；同文件 `:447 get_session` | messages、偏好、运行状态；消息自带 events；恢复失败 turn 到原用户消息 | 打开会话/重新加载后的权威快照 |
| `GET /api/sessions/{sid}/messages/{mid}/events?after_seq=&limit=`；`:461 get_message_events` | 分页读取完整消息 trace；大 tool_result 在会话快照中会截断 | 展开历史工具步骤时按需加载 |
| `PATCH /api/sessions/{sid}`、`PATCH /{sid}/organization` 等；同文件 | 重命名、工作区归属/归档/固定等组织状态，编辑分支 | 延用原生组织功能，不复制成工作台侧会话属性 |
| `/ws`；`api/routers/unified_ws.py:44 unified_websocket` | `start_turn`、订阅 turn/session、续传、取消、等待输入和命令 ack | 首选实时主会话连接 |
| `app/service.py:113 TurnApplicationService.start_turn` | 输入验证、幂等提交、工作区绑定、持久 turn、协调执行 | 任何新增 HTTP/SSE 适配器也调用同一应用服务 |
| 同文件 `:248 subscribe_turn`、`:346 subscribe_session` | 持久事件重放与当前运行订阅 | 重连按 turn 游标恢复 |

`services/session/__init__.py:get_session_store()` 会根据集成配置选择 PocketBase 或 SQLite；不要直接把 SQLite 文件当作全部部署的公共契约。`services/session/sqlite_store.py:283 _initialize` 已建 `sessions/messages/turns/turn_submissions/turn_events`；turn_events 具有 `(turn_id, seq)` 唯一键；turn_submissions 将 `client_submission_id`、workspace、session 和 turn 关联。`services/session/scope.py` 按 backend/resource/owner 区分存储作用域。

### 工作区提交字段与流式事件

`core/turn_request.py:127 TurnRequest` 是正式字段来源；`api/contracts/turn_protocol.py:69 StartTurnCommand` 加入 type 和 protocol_version。可直接提交：

```json
{
  "type": "start_turn",
  "protocol_version": "2.0",
  "client_submission_id": "desktop-unique-stable-submission-id",
  "content": "本次用户问题或带定位的成果修改请求",
  "capability": "chat",
  "workspace_id": "ws_selected_native_workspace",
  "session_id": "existing-native-session-id",
  "attachments": [],
  "knowledge_bases": [],
  "skills": [],
  "mcp": []
}
```

新会话省略 session_id，由原生服务返回真实标识；继续会话时可省略 workspace_id，继承绑定。`workspace_id` 的“省略”与 null/空串有不同含义：后者选择 general workspace。`TurnRequest.to_payload()` 用 exclude_unset 保留这种差别。`skills=[]`、`mcp=[]` 表示继承工作区允许项；非空列表只能缩小权限。另有 `llm_selection={profile_id,model_id}`、persona、parent_message_id、config、reading references 等字段，按实际需要传入；不应把外部运行编号任意塞进顶层，模型配置为 `extra='forbid'`。

`api/contracts/turn_protocol.py:177 StreamEvent` 包含 `type/source/stage/content/metadata/session_id/turn_id/seq/timestamp/protocol_version`。事件已有 `content`、`thinking`、`tool_call`、`tool_result`、`progress`、`sources`、`stage_start/end`、`result/error/done`、`wait_for_input`。因此检索、评分、工作流步骤可成为折叠活动，正文 content 保持普通回答。客户端按 `(turn_id,seq)` 去重。

重连发送 `subscribe_turn {turn_id, after_seq, protocol_version:'2.0'}` 或 `resume_from {turn_id,seq,...}`。注意 `subscribe_session` 当前实现只找到当时 active turn，再转 `subscribe_turn`；它不是跨所有未来 turn 的永久总线。恢复历史用 sessions/message events；当前活动用 check_active_turn/subscribe_turn。取消和用户补充须遵守 command_id 及 ack 协议。

### bearer 登录到 WebSocket 的真实边界

`api/routers/auth.py:541 ws_require_auth` 在开启认证时只读取 query `token` 或认证 cookie，**不读取 HTTP Authorization header**；成功后同时安装用户和工作区上下文。原生 HTTP API 可用 bearer，但不能据此推断同一个 Authorization header 能认证 `/ws`。

`workbench/server/native.py:12 headers` 会为 HTTP 代理同时保留 cookie、Authorization、Origin；而 `server/reviews.py:82 submit_review` 连接 WS 时仅转 Cookie，没有 bearer 转换。因此本机 CLI/桌面的 bearer 身份经过当前 submit_review handoff 会丢失。正式实现必须沿用原生支持的 WS 凭据通道，或增加受认证的 HTTP/SSE 转接调用同一个 TurnApplicationService；不可把“能请求 /api/auth/profile”当作 WS 已登录。token/cookie 不写入活动、回执或日志。

## 3. 工作台成果、批注、版本与审查

| 现有模块 | 持久内容与关联 | 直接复用接口 |
|---|---|---|
| `server/storage.py:55 Store` | SQLite projects/jobs/trash；projects 以 owner 过滤，native_id 绑定原生 workspace | `/research/api/projects`、`/{pid}/jobs` |
| `Store.path:82 / bind_native:95` | project_root 必须在 WORKBENCH_NATIVE_ROOTS 挂载范围；项目根与原生工作区相连 | 继续用现有项目绑定和文件路径，不另复制工作目录 |
| `Store.replace:181 / discard:165` | 正式路径只保留当前文件，旧内容移 `.trash`，登记原因/时间及 artifact.replaced 事件 | `/file`、`/files`、`/trash`、恢复与 revision diff |
| `Store.save_manuscript:232` | revision 乐观锁；保存前旧版归档；manuscript.revised 事件 | `GET/PUT /manuscript` |
| `server/annotations.py:8 ensure_schema / :43 save_annotation` | owner+project、area、asset、quote、body、locator、状态；review_events 追加审查过程 | `GET/POST /annotations`，更新/删除，`GET /review-history` |
| `server/app.py:201 agent_receipt` | question_ids 必须属于本项目；产物必须存在；写 agent.receipt，按 resolved 处理批注，启动 quality job | `POST /agent-receipt` |
| `server/quality_api.py:41 file_binding / :49 current_bindings` | 产物路径+mtime_ns+size，来源版本、规则版本；当前材料变化会使 gate 失效 | `/quality/reviews`、`/quality/gate`、`/quality/rubric` |
| `server/stage_reviews.py:590 save_review / :647 list_reviews` | operation_id 幂等，追加保存 review；记录 parent/root review、作者 override，当前绑定必须吻合 | 审查作为同一成果的反馈详情，沿用原来的 gate |

批注状态为 open/submitted/resolved/deleted。当前 `server/app.py:630 annotations_submit` 调 `reviews.submit_review()`，创建原生 turn 后仅把 `session_url` 放到 locator，并在 questions.submitted 事件中保存 session_id/turn_id。没有正式 session FK/turn FK，不宜继续依赖解析 URL。

当前 `server/app.py:597 review_chat_send` 并不适合作为统一会话库：它按 area 保存 `.workbench/review-chats/<area>.json`，有账户 API key 时走 `models.py:7 complete` 同步 chat completion；否则新建一次原生 start_turn，再由 `sync_review_answers` 拉原生会话并拼接全部 assistant 消息。前者无原生持久 turn，后者会分裂会话且缺少精确 turn 回写目标。

`reviews.submit_review` 目前 start_turn 不传 session_id，所以每次批注/图形反馈默认新会话。正式修改只需让它接受当前 native session_id，传原始 workspace_id、稳定 client_submission_id，完整返回 turn_id；批注处保存结构化 native_session_id/native_turn_id/operation_id，session_url 只作导航。纯对话反馈也应经原生主会话，避免经过 review_chat 的第二份消息文件。

`agent_receipt` 目前只保存 question_ids/artifacts/validation/limitations/created；即使调用者提交 operation_id/session_id/turn_id，这些也不会进入 agent.receipt 的 record（operation_id 仅传给 quality 触发）。这是统一活动关联必须修正的少量字段之一。未标 stage 的旧客户端仍收到 `quality.status=not_reviewed`；有 stage 的新交付异步返回 quality job_id，不能把成果 saved 当作质量通过。

## 4. Dify bridge 已有真实工作流与回执

`bridge/app.py` 的已安装入口：

- `GET /research/dify/api/context?project_id=&workspace_id=&task=`：取得当前规范、完整任务技能、原生 workspace、稿件结构及交付约定。
- `POST /research/dify/api/deliver`：提交已有成果及验证记录。
- `GET /research/dify/api/runs/{run_id}`：交付状态、workflow_run_id、回执、automation 摘要。
- `GET /research/dify/api/activity`：当前项目最近 20 次交付及服务检查。
- `POST /research/dify/api/evidence`、`GET /api/evidence/{run_id}`：联合检索及状态；检索结果应作为 tool_result/sources 接回当前 turn。
- `POST /research/dify/api/runs/{run_id}/acknowledge`：技术问题处理说明，不修改失败原始证据，也不等于作者批准科学结论。

`bridge/delivery.py:79 Delivery` 已有 project_id/workspace_id/session_id/task/standard_version/request_id/question_ids/artifact/validation/limitations。`DeliveryService:93` 持久 deliveries 表，唯一键是 `(owner,request_id)`。`:387 deliver` 验 owner、项目与 workspace 一致性，先落 pending，再调用 Dify blocking 工作流；相同编号不同 payload 返回409；失败/中断可沿用同一编号恢复。session_id 目前只是 payload/最终回执字段，没有验证归属、没有 turn_id、也没有将完成结果追加到原生会话。

`:241 prepare` 校验 current standard_version 和技能原文；原生 Dify `sys.workflow_run_id` 通过 X-Dify-Workflow-Run-Id 在写前记录。`:305 commit` 负责版本保存和回读，文件替换需要 expected_modified；稿件携带 revision；二进制 existing 不进提示词。`:268 verify_delivery` 重新核验 owner/project、当前产物、review-history 中精确匹配的 agent.receipt。`:25 workflow_receipt` 只有 Dify succeeded 且最终 receipt 与当前 run/历史核验一致，才确认完整交付。

`bridge/automation.py:18 DeliveryAutomation` 已有持久 automation_events、指纹去重、重试、Webhook分支回执、reconcile 和 activity。HTTP 接受状态是 dispatched，不能当完成。服务重启将 pending/prepared/written 标记 interrupted；授权 tickets 只在内存保留十分钟，重启不盲目重新写入。Dify响应丢失但成果保存成功时保留 saved + workflow_status unknown，后续 reconcile 查询同一 workflow_run_id。

已保存的生产证据：`reports/workflow-optimization.json` 记录成果交付应用 `5c9d68ae-3847-4774-8e94-ecbfa9543e25` 已发布，6个业务节点；`ops/optimize_workflow.py:71 optimize` 的实际顺序是 start→prepare→commit→delivery_verify→delivery_summary→end；发布入口在 main，不应使用初始 `ops/build_workflow.py` 覆盖生产图。`reports/workflow-identity-live.json` 记录 prepare trace 解析了真实 Dify运行编号。`tests/test_workflow_identity.py` 覆盖终态响应丢失后的恢复，属于已有测试，本轮未运行。

## 5. 能力清单、发布更新与本机执行现状

| 需求 | 已有事实 | 最小补充 |
|---|---|---|
| 服务端能力清单 | `GET /api/capabilities/registered`，`api/routers/capabilities.py:25` 返回实际注册能力 id/kind/available/manifest/config_schema；工作台 `/research/api/integrations/workbench` 返回 features/MCP工具清单；`/research/api/schema` 返回实际路由 | 可聚合成 desktop manifest，增加 manifest版本、兼容协议、工作流稳定 ID、已发布版本与可用性；不在客户端硬编码全部工具 |
| skills发布 | `server/standards.py VERSION='2026-11-02-quality1'`；catalog 逐请求读 vendor/workbench-skills；prepare_project 刷新 `.workbench/standards`；context 返回完整原文；bridge在prepare拒绝旧版本 | 服务端部署生效后，新 context 能看到；客户端遇409刷新再提交，运行中的旧请求保留原版本 |
| Dify发布 | optimize脚本真实调用 `/workflows/publish`；每次运行通过独立API key对应应用 | 目前没有面向桌面的“统一已发布 workflow release manifest”；标准版本、Dify应用发布版本、MCP schema版本需明确分开 |
| MCP更新 | bridge挂载 `/research/dify/mcp`，FastMCP stateless HTTP；RunClient限制当前项目、当前run产物根；维护脚本会 refresh Dify MCP tool schemas | 只发布Python代码未必刷新已缓存的Dify工具schema；沿用该 refresh+publish 运维动作，并在manifest反映版本 |
| 本机Codex/Claude等 | 原生 `/api/subagents/detect`、`/connections`、`/backends/options` 已存在，api/routers/subagents.py 明确CLI在**服务宿主机**以宿主凭据运行 | 远端DeepTutor检测的是远端容器/宿主，并不等于用户桌面CLI；桌面桥应复用本地CLI适配器再把任务/事件/回执绑定到native turn |
| 本机设备队列 | workbench `server/download_bridge.py:52 pair / :129 next_job / :147 progress / :176 result` 已有下载设备配对、owner范围、claim、heartbeat、恢复和结果回执；只支持literature-download | 这是ScanSci论文下载专用协议；尚无通用device register/capabilities/execute/cancel/lease/artifact协议。可借用模式，不能声称已经接通通用Codex/Claude/dp任务 |

前端可手动升级而服务端流程自动生效的前提是：保持 v2 会话事件兼容、由服务端发现能力/配置、工作流步骤按通用活动渲染、成果使用稳定API。新增原生组件类型或破坏 wire schema 仍需客户端升级；不要把技能版本变化当成UI版本变化。

## 6. 最小接口接缝与修改候选

以下是实现候选，本文未修改源码。

1. **原生会话继续作为权威。** 桌面从现有 sessions恢复，使用现有 `/ws v2` 发用户消息。若HTTP/SSE更利于桌面认证，只加一个受认证适配器，内部调用 `TurnApplicationService.start_turn/subscribe_turn`，保留 client_submission_id、workspace省略语义和seq，不创建新聊天存储。
2. **工作台反馈回到当前session。** 精确修改 `server/reviews.py:82 submit_review` 与 `server/app.py:630 annotations_submit` 的请求体，接受/校验native session_id；解析并绑定native turn，保留批注asset/locator/question_ids。继续原生会话时使用原生应用服务的workspace检查，不能只信前端传sid。`review_chat_send` 可保留旧入口兼容，但正式桌面不使用其JSON消息文件。
3. **只增加跨服务关联记录。** 为一次动作维护 `owner/project_id/workspace_id/session_id/turn_id/client_submission_id/operation_id`，并可关联 job_id、bridge run_id、workflow_run_id、review_id、artifact bindings。可在已有 review_events/回执增加结构化关联字段及必要查询索引；需要独立表时只存映射和游标，不存另一份chat正文。`bridge Delivery` 增加可选turn/operation字段需保持旧payload可读，服务端核验会话归属。
4. **活动聚合读取已有状态。** 新的薄接口按session/turn返回对应 jobs、Dify runs、批注与成果审查；现有 `/jobs` 只取最近20条，`review-history`最近300条，`activity`最近20条，不能仅靠这些上限列表保证关联不丢。映射查询应按真实ID读取，并支持游标。事件既可通过原生工具tool_call/tool_result写入trace，也可作为独立成果活动投影；不要伪造一条“assistant完成回答”掩盖异步未完成。
5. **异步回执保留分层终态。** 保存成功、Dify终态、processing_history_verified、quality job与gate分别报告。审查放在折叠步骤，具体问题显示在成果反馈；gate当前绑定失效时必须重新计算。必要时以同一operation的幂等状态更新活动，不重复覆盖产物。
6. **本机CLI单独适配执行。** 用户桌面提供本地执行事件，服务器继续认定owner、workspace、turn和成果版本；不让远端subagents接口假装发现桌面CLI。通用设备任务协议仅在已授权的本机接入实现时增加，下载worker继续使用原协议。

推荐首轮实现范围：会话列表+v2主会话、成果反馈→同session、已有jobs/Dify/quality投影、结构化关联和鉴权接缝。无需重写工作台存储、现有Dify交付流程、质量模型或persona Partner系统。

## 7. 生产兼容事项

- **账户与挂载路径：** 所有工作台项目操作都用真实profile owner；项目ID与native workspace必须对应。Store.bind_native/path 依赖真实挂载的WORKBENCH_NATIVE_ROOTS，桌面本地路径不能直接发成服务端project_root。写类HTTP带正确Origin；bridge的MCP运行票据限制project与输出根目录。
- **文件版本单位：** 工作台普通file optimistic lock使用stat mtime秒；quality绑定使用mtime_ns；manuscript使用revision。不要把三者混用为同一version整数。已有receipt.verify核验的是保存与记录一致，科研有效性仍由真实validation证据和审查决定。
- **任务恢复：** 工作台ThreadPoolExecutor仅2个worker；普通queued/running jobs重启标interrupted。下载worker有自己的claim/heartbeat。原生turn lease恢复、Dify回执恢复与这两类任务不能合并成一个无限重试策略。
- **配额有源码差异：** `server/app.py:56` 安装了account_policy接口，支持管理员按revision更新配额；但当前 `server/workspace_files.py:21 usage / :43 require_space` 仍直接使用固定QUOTA=2GiB，没有调用account_policy.policy/check_write。account_policy的“下一次写入立即生效”文案与这份写路径不一致，不能把接口存在当作配额已全面生效。本轮仅记录，需单独定向连通，原生KB/Code/缓存全局配额本就不在该接口声称范围。
- **历史输出/旧客户端：** 保留缺session/turn关联的旧回执可读；新字段可选迁移。质量回执without stage仍有旧行为。不能为了统一显示而重跑已有付费模型任务、已有workflow或重写旧产物。
- **服务部署事实边界：** 本机源码与保存的生产报告可证明设计与历史部署结果；本轮没有实时探测，正式合并前需用当前受权身份对会话读取、bearer到WS、同session批注回流、异步回执恢复做有限集成检查。

## 8. 可选persona Partner兼容条目

`api/routers/partners.py` 提供 sessions/history/history-page、归档/恢复/分支、web-continuity。`:1752 POST /api/partners/{id}/chat/execute-stream` 只发session、thinking、最终content、done/error；没有token delta游标，而且连接结束finally会取消未完成task，不能作为通用可恢复会话主线。

`:1765 /ws/partners/{id}` 会发完整stream_event，并支持action=attach恢复实例内在途turn、stop、actor-scoped跨渠道活动；断开只detach drain，不停止原执行。它的session_key/actor访问和运行时生命周期与原生sessions/turns v2不同。若用户明确选择persona Partner，应保留该适配器边界；不要把session_key冒充native session_id，或假定它有相同的持久seq重放保证。
