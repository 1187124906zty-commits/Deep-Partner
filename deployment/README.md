# Tutor 域名上的 Dify 与科研工作台接入

## 独立管理员入口（2026-11-05）

新增免登录的 [管理员工作台](https://tutor.example.invalid/admin/)，原 /research/、登录、注册申请和账户认证保持原有行为。新入口使用独立网关，在服务器端连接现有管理员账户；浏览器不接收该登录 cookie。可向 Linear 等外部工具提供 [架构正文](https://tutor.example.invalid/admin/architecture.md) 或 [工作台 API 定义](https://tutor.example.invalid/admin/research/api/schema)。这是开放的管理员入口，具有管理员账户的项目与操作权限。

部署说明见 [管理员入口架构](docs/DeepPartner管理员入口架构.md)，发布与匿名浏览器验证记录分别位于 reports/admin-gateway-deployment.json 和 reports/admin-gateway-verification.json。

针对只能读取 HTML 正文、不能执行 JavaScript 的外部对话工具，新增 [实际界面审阅页](https://tutor.example.invalid/admin/review) 和 [纯文本审阅资料](https://tutor.example.invalid/admin/review.md)。审阅材料包含 8 个实际渲染页面的截图及可见文字；它支持视觉与信息结构检查，交互测试仍需真实浏览器。管理员 SPA 的原始 HTML 同时提供正文和审阅入口。资料由 ops/capture_admin_review.py 采集，静态读取回归入口为 ops/verify_admin_reader.py。

## Deep Partner 自动研究入口（2026-11-05）

研究入口已改为 Deep Partner 项目。新增 `dp chat` 与 `dp workflow`，按结构化任务路由到 Scholar、ScanSci、DeepCode 与 Paper2Slides；文献、可公开的研究判断、来源关系和 idea memo 保存到所属项目，并显示在研究知识图谱中。工具与文献按当前步骤读取。实际验证、命令示例和配置生效范围见 [DeepPartner自动研究工作流](docs/DeepPartner自动研究工作流.md)。

## 模型生成等待（2026-11-03）

按作者要求，生产模型生成链路已取消固定超时，包括原90秒流读取与SDK默认600秒限制。等待持续到模型完成、真实报错或用户停止；明确繁忙和限流继续如实返回。部署后9项回归通过，真实SSE连续静默100秒后正常收到回答且只发出一次请求，同一路由的 `gpt-6.1-sol / max` 实际调用成功。持久部署、验证及范围见 [模型等待超时取消](docs/模型等待超时取消.md)。

## 对话起步、图形编辑与项目材料（2026-11-02）

当前统一前端构建 25223865：新项目默认研究对话，拖入或粘贴附件后保存到项目，PDF 加入文献库并后台建立语义索引，支持消息图片和侧栏网页/正文阅读。侧栏保留创作分组，底部合并“文献与知识库”。日常复杂导入入口与导入后强制阶段评分已移除。

图形沿用已关联的绘图对象，点击直接编辑内容、字体、线条、坐标轴与图例；图内 AI 面板改为原生 Dito。Dito 自动跟随当前图片元素、文档页码或代码行，发送时携带当前预览与修改状态，知识库保持项目级。具体使用与实际导入范围见 [新手工作流与三个项目实际交付](docs/新手工作流与三个项目实际交付.md)。

本轮三个私人项目为水分扩散、硫酸盐侵蚀微观建模、氯硫耦合传输损伤代理建模；共 11 份 PDF、18 份源码抽样回读、1,966 份原始文件路径/大小回读均有实际结果，三个知识库已完成并通过语义检索。旧管理员项目按作者要求移出活跃列表，原材料与项目记录在服务器可恢复归档；下文更早的旧项目链接保留为历史部署记录。

## DeepPartner 统一桌面与研究界面（2026-11-02）

正式研究入口 `/research/` 已改为统一的项目、会话和成果界面，直接复用生产 DeepTutor 1.7 聊天、缓存、主题与动态组件。桌面 0.4.0 以 Tauri/WebView2 内嵌同一份静态前端，前端手动更新，兼容服务端流程在线用于后续任务。真实同会话批注、Dify 保存与回读、原生 CLI 任务、WebView 登录及主题重启恢复均已验收。

主说明见 [DeepPartner0.4实际交付](docs/DeepPartner0.4实际交付.md)，设计依据见 [统一产品框架](docs/DeepPartner统一产品框架.md)。本机 Codex 已真实执行，Claude 当前未安装；现有个人 SSH 工具桥保留为兼容连接，公网通用设备配对与完整交互终端未在本版本实现。

## 阶段评分与用途规则（2026-11-02）

生产工作台已启用13阶段评分、六种PPT用途规则及可单独配置的评审模型，默认继承Tutor。核心分项0–4且至少3，关键硬检查独立；评审绑定产物、来源与规则版本。PPT计划最多两轮定向修订，其他阶段交相应执行器处理具体问题。

实际结果与边界见 [阶段评分与知识库实际接入结果](docs/阶段评分与知识库实际接入结果.md)。145项后端、17项交付桥接、12项MCP合同和42项前端通过；真实Tutor模型与正式网站桌面/移动端分别有回执。MinerU三书及六用途资料的真实状态以 `reports/mineru-books/` 与 `reports/presentation-source-ingest.json` 为准，原始OCR、物理页恢复与原页补充分别保留。

本批已完成三书1,042页和11项用途资料的真实MinerU转换、分层阅读稿与集群归档；14项首选文本已进入[本作者私人参考项目](https://tutor.example.invalid/research/?project=69c79a679648428aae6d8e06f4006f70)，索引与关键词/语义检索实检通过。真实摄取评审四项3/4、展示75、当前gate通过；全文未逐页复核的范围保留。

当前使用 Dify 1.18.0 官方发布源码与镜像。服务器为现有的 `papers-research`（203.0.113.10），部署目录 `/srv/dify-research`。

## 入口与职责

- Tutor 与 Agent 会话：https://tutor.example.invalid/
- 当前科研工作台：https://tutor.example.invalid/research
- Dify 管理界面（完成前端发布后）：https://tutor.example.invalid/dify/apps

DeepTutor 保留原生用户身份、当前工作区、会话、模型和技能执行。原生扩展提供 `research_workbench` 工具；Agent 读取项目上下文、按需检索与委派 Code，再交付成果。Dify 承接并行取证、成果交付、网页读取、交付事件与定时协调；项目身份、版本、写入和回读规则统一由适配器实现。工作台保存程序、数据、稿件、文件、模板和版本。

`status=saved` 表示成果已写入并回读一致。它不表示科学结论、数值计算或排版已经通过验收；这些证据由实际执行的研究任务提供。普通聊天无需创建文件。

## 当前支持

公网多用户的数据分层、个人知识库隔离、动态配额与本机 ScanSci 设备方案见 [公网多用户存储与长期记忆方案](docs/公网多用户存储与长期记忆方案.md)。已部署工作台配额与下载设备隔离；集群归档为已验收的基础层，尚未迁移原生账户、活跃知识库、对话和正式项目。

当前已发布五个相互配合的原生 Dify 流程：多来源联合检索、公开网页证据读取、研究成果交付、Webhook 交付事件处理、每五分钟交付协调。完整入口、真实负载结果和故障恢复范围见 [工作流与验收说明](docs/工作流与高强度验收说明.md)。

联合检索使用三个独立并行分支：当前项目已绑定的原生 RAG、公开网页、学术题录。合流后分别报告成功、空结果、超时、未配置和失败；同一来源标识与片段去重时保留全部 provenance。Tutor 新增 `evidence`、`evidence_status` 和 `activity` 动作。当前 MCP 保留并发现 41 个工具。

交付结束自动发送持久事件，由 Dify Webhook、IfElse 和 MCP 回调登记实际结果。定时触发器核对状态不明的既有任务、遗漏回调和服务健康。收到 Webhook 的 202 只表示受理；同一事件回调完成才表示自动处理结束。Dify 在校验与检索节点主动登记原生运行编号，终态断连后按原编号核对，不重复保存成果。预期故障验收记录可附技术处理说明，原始失败证据仍保留。

当前功能与操作入口见 [DeepTutor扩展功能说明](docs/DeepTutor扩展功能说明.md)。Agent 工程依据与适用限制见 [工程依据](docs/agent-engineering-evidence.md)。

2026-11-01 的整理已发布到原有应用：十一项底层节点收敛为六个业务步骤，上方另有三张职责说明卡。顺序为“成果交付请求 → 项目与版本校验 → 成果版本化保存 → 成果保存与记录核验 → 交付回执生成 → 交付结果”。38 个工作台 MCP 工具保留现有名称；新增的 `workbench_delivery_verify` 统一处理最终成果与历史核验。

已采用 Dify 内置 WebScraper，发布独立的 [网页证据读取流程](https://tutor.example.invalid/dify/app/2f0d0b10-0d03-4a92-89b5-f8f07a51769a/workflow)。该流程不调用 LLM，不改项目文件；保留公开网页链接、正文与读取时间。单独 API Key 保存在服务器 private 目录，通过只读挂载供适配器使用。

Tutor 原生 `research_workbench` 新增 `search` 动作：`search_kind=papers/web/page/sources`。检索和读取不要求先创建成果交付。已经用真实 Tutor 会话完成 Scholar 检索和 Dify 网页正文读取，回执见 `reports/extension-optimization-verification.json`。

当前稳定性处理覆盖：一次临时读取断线的有限重试、搜索错误与空结果区分、Scholar 超时/限流/人工验证的不同恢复提示、题录核验的等待上限、auto 模式下明确标明来源的 Crossref 降级、公共网页成功结果两分钟缓存。明确选择 Scholar 时不暗中切换来源；写入不自动重复。外部公共搜索仍可能波动，不能将短时实测升级为所有 MCP 长期可靠的结论。

文本文件写入、现有文件登记、工作台原生可编辑稿件更新；代码、PPT、图片及二进制由原生工具先生成，再登记交付。目标项目必须属于当前用户，并与会话工作区一致。替换现有文件需要读取修改时间，稿件提交需要当前 revision。保存时记录会话、任务、问题、验证证据、限制和回执。重复请求沿用同一交付记录。

扩展位于 `tutor-extension/`，独立适配服务位于 `bridge/`。通过 DeepTutor 公开 Python entry point 接入；不修改其核心 Agent 循环。Dify 本次用于确定的成果交付流程，没有额外配置一个独立研究 Agent。

## 部署方式

上游 Dify 位于 `/srv/dify-research/upstream/docker`，使用官方 Compose 与 `compose.override.yaml`。镜像内容记录在 `images.lock.json`。Nginx 仅监听服务器回环地址 `127.0.0.1:8088`，Caddy 承担域名 HTTPS。`/research/dify/` 转发到适配器；`/dify/` 转发到按该 basePath 构建的 Dify 前端，管理 API 则去掉前缀后转发。

管理账号与工作流密钥分别保存在远端 `private/admin-login.json`、`private/workflow-key`，不写进 DSL 或源代码。Dify 管理账号独立于 Tutor 登录。凭据的本地副本位于 `.local/admin-login.json`（交付时复制，禁止提交）。

前端从官方同版本源码构建。业务源码不修改，部署构建参数为 `NEXT_PUBLIC_BASE_PATH=/dify`。为适应本机构建资源，使用 Next.js 的 Webpack 构建方式、2 个静态页面生成进程与 webpackMemoryOptimizations；容器使用 `ops/Dockerfile.web-subpath`。临时编译目录的 Next.js 配置只增加这些构建设置。升级时需要重新构建同一路径并进行登录、静态资源和真实写回验证。

## 运维

查看服务：

```sh
ssh papers-research 'docker ps --format "{{.Names}} {{.Status}}"'
```

查看 Dify 配置或启动服务：

```sh
cd /srv/dify-research/upstream/docker
docker compose -f docker-compose.yaml -f ../../compose.override.yaml config --quiet
docker compose -f docker-compose.yaml -f ../../compose.override.yaml up -d
```

服务使用自动重启策略。适配器的持久化交付记录位于 `state/deliveries.sqlite3`，Dify 使用 PostgreSQL、Redis、Qdrant 和原生挂载存储。

执行备份：

```sh
bash /srv/dify-research/ops/backup.sh
```

备份包括 Dify 两个数据库、交付数据库、配置、密钥及应用存储，位于远端 `private/backups/`。不要将 private 目录或备份发布到网站。

## 验证材料

`reports/live-verification.json`：实际 Dify 工作流、登录限制、重复交付、项目绑定、版本冲突和稿件回读。

`reports/agent-verification.json`：真实 DeepTutor 会话调用 `research_workbench`，保存代数守恒算例并回读。验证项目名为“Dify 部署与交付验证”。算例明确标记为软件接入验证，不是实验数据。

`reports/persistence-verification.json`：重启后会话、Dify 运行记录及交付回执的持久化（运行成功后复制）。

`reports/domain-verification.json`：域名入口、HTTPS、前端资源和管理账号登录验证（发布成功后生成）。

本地 Python 测试位于 `tests/`，覆盖交付及原生扩展的关键边界。需要真实服务的验证脚本位于 `ops/verify_*.py`。不要在正式项目中运行会写入演示稿件的验收脚本。

## 最初部署结果（2026-11-01，后续扩展见当前支持）

正式域名已发布，浏览器使用管理员账号登录成功，四个节点的交付工作流画布可见，状态为已发布。域名部署后真实 Dify Workflow 再次运行成功，文件和可编辑稿件回读一致。

本地关键测试为 16 passed，使用已有 DeepTutor 虚拟环境执行：

```powershell
& 'C:/Users/DEVELOPER/DeepTutor/.venv/Scripts/python.exe' -m pytest 'D:/Development/询问/dify-research-deployment/tests' -q
```

`reports/domain-verification.json` 记录 HTTPS、页面资源、管理账号登录、工作流可见性和域名切换后的成果写回。工作流 ID 为 `5c9d68ae-3847-4774-8e94-ecbfa9543e25`，可直接访问：

https://tutor.example.invalid/dify/app/5c9d68ae-3847-4774-8e94-ecbfa9543e25/workflow

最终配置备份：`/srv/dify-research/private/backups/20261101T114605Z`。本机构建所用临时 WSL 设置已恢复，临时编译磁盘已移除。

## 当前维护入口

`ops/optimize_workflow.py` 是成果交付画布的维护入口；原 `configure_mcp_workflow.py` 命令转到同一实现，避免重复生成旧画布。`ops/build_workflow.py` 只用于 MCP 注册前的初始引导，不用于覆盖当前生产画布。`ops/setup_web_reader.py` 管理按需网页读取应用。

`workbench-search/server/` 保存本轮涉及的工作台检索模块，对应服务器 `/srv/research-workbench/source/server/`。修改仅针对检索与错误契约，未复制完整工作台代码。完整部署及验证结果见 `reports/optimization-acceptance.json`；修改前后的工作流图结构保存在相邻 JSON 文件中。


本轮连接、新会话、文献原文优先显示及会话文件侧栏修复，见 [自动连接与会话文件侧栏修复](docs/自动连接与会话文件侧栏修复.md)。网站与桌面构建 25228429 已实际验收，结果在 `reports/connection-product-release.json`。


任务面板改为按执行实例独立成卡、按任务类型固定阶段，详见 [任务卡与固定流程](docs/任务卡与固定流程.md)。网站与安装包构建 25228885。

本机下载设备离线的问题已修复：登录后恢复已配对的 ScanSci worker；BFGS 原任务与自动领取的 Adam 任务均完成集群验收、文献入库和全文回读。实际结果、登录恢复范围与证据见 [真实下载链路与登录恢复](docs/真实下载链路与登录恢复.md)。

文献拖入识别、NeoRead 多语言阅读和选文批注、双语同步、统一稿件导出、原版 Word 模板全文预览、项目记忆检索画布及四主题对比度已发布，见 [文献阅读与工作区交互改版](docs/文献阅读与工作区交互改版.md)。网站、主程序和安装包使用构建 25235686；六页四种宽度的布局和实际 Windows 保存流程均已验证。

用户反馈后的主题恢复、文字对比度修正、文件与任务响应提速，以及集群编译与开发资料迁移，见 [集群开发与界面恢复](docs/集群开发与界面恢复.md)。网站当前构建 25239676；Windows 包的实际状态以 `reports/ui-restoration-release.json` 为准。

`dp.exe` 已增加指定项目的命令行文件上传与分类，支持多文件、递归文件夹、文献用途、分类覆盖和 dry-run。用法见 [命令行上传项目文件](docs/命令行上传项目文件.md)，真实六类材料上传与回读结果见 `reports/cli-upload-live.json`。
