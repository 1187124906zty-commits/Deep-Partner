# Deep Partner：固定研究路线与自动纠错

2026-11-05。本说明更新此前“自动研究工作流”的实际接入范围。

研究以真实项目和会话为归属。固定的是阶段依赖、输入输出合同和完成条件；可变的是论文、查询、知识、程序、参数和研究判断。按需要选择工具能力，不要求每个任务机械调用全部工具。

```mermaid
flowchart LR
    A[绑定项目和会话] --> B[Scholar 原生检索]
    B --> C[ScanSci 下载并核对]
    C --> D[原 PDF 入库与集群副本]
    D --> E[集群 Slurm 解析]
    E --> F[Markdown与原始页码]
    F --> G[指定页段阅读与研究综合]
    G --> H[研究记录和知识图谱]
    H --> I[DeepCode 原生工作流]
    H --> J[Paper2Slides]
    I --> K[执行、验证与产物回交]
    J --> K
```

## 已运行的解析与归档链

PDF 上传或下载入库后自动创建解析任务；上传响应返回解析任务 ID，不等待计算完成。原 PDF 保留，已核验的集群副本可复用。计算通过现有 `research-cluster-xh5` 的 Slurm 运行，文字层与版面解析复用已有 `reader_processor`，文字稀少的页面交给已安装 MinerU OCR。解析输出为逐页文本、Markdown和来源回执；它们进入当前项目 `docs/literature/parsed/<source-hash>/`。

解析文件与原 PDF 的来源身份相符时复用。研究综合通过 `read_pages` 指定下一批页码；无指定时按有限摘录规则读取，保留真正提供的页码。公式和复杂图表仍需在具体研究引用时回看原页。

实际验收：15页论文在计算节点 `a04r01n04` 完成，Slurm `25408168` 为 `COMPLETED / 0:0`。自动上传钩子创建任务 `ba9f4a8492dc46fca0bd1526e0793fcc`，复用该解析，没有重复计算；产物保存和回读通过。后续研究工作流实际读取第7、8页，并返回对应解析作业ID。

## 恢复时接续已有任务

`stage_receipts` 保存已完成阶段。`dp workflow resume --project PROJECT_ID --id RUN_ID` 使用原研究任务ID及保存的请求；已完成阶段跳过，外部工具与集群作业通过其原ID查询。解析缓存、文献身份和实际文件回执共同决定能否继续。

模型结构化输出违反来源或页码合同时，使用相同来源包附具体错误进行一次修正。集群提交结果不明时先核对已有提交，避免重复占用资源。已知、可修复的错误有明确诊断和有限重试，失败记录保留。

12项后端定向测试通过，包括指定解析页段、源文件版本核验、原任务恢复、工具离线等待后同任务接续，以及明确的原生工具选择。解析服务重启后也会读取队列中的已存在任务，等待本机工具恢复后继续。本机工具服务已设置为用户登录时恢复；运行时定期核对实际反向连接，断开后重建，复用现有工具环境。

## DeepCode 的真实能力

当前安装的上游 MCP 原本提供 `deepcode` 与 `deepcode-reply` 两个工具。新增的 `deepcode_workflow` 是本机适配器，调用 DeepCode 自己的 `workflow/start/read/respond/retry/interrupt` 和 Artifact 接口；没有在外层重写它的规划或代码生成循环。

- 源文档驱动的实现使用原生 Paper2Code，保留准备、规划、计划交互、实现、验证和回交。
- 普通编码选择 `code_engine=agent`，调用真实 `deepcode`。
- 同一项目会话的后续编码复用会话绑定，调用 `deepcode-reply`，或复用原生工作流线程。
- 工具暴露遵循按需读取。先发现接口，再调用所选能力。

原生工作流实测先后暴露日志格式不兼容、规划输出格式合同不完整和合法YAML被长度/代码围栏启发式拒绝的问题。已对实际安装的原生运行时定向修复，保留各次失败和 `retryOf`。后续实际通过原生代码生成工具写出程序。验证阶段又发现子目录测试未发现和Windows误选另一Python的问题，已定向修复。对既有产物接续验证，16项测试通过；5份实际源码由验收客户端保存到软件验收项目并逐份回读。原生工作流的历史失败状态保留，恢复验证有独立回执。第三入口的真实MCP调用也已接续原生验证阶段并返回通过。

作者随后明确回答“允许本项目修改与测试”。已通过 DeepCode 自身的 `settings/update` 对工作台项目设置文件修改及 Python 测试规则，保留 workspace 边界与命令沙箱，未改全局默认。原生 `deepcode-reply` 续接会话 `4028c003`，实际完成 Scholar 四文件修改、编译检查和14项合同测试。

Deep Partner 集成项目及软件验收项目已按项目启用原生执行，其他项目不继承这次放行。正式代码路由的实际验收会话 `4cfbf911` 创建程序和测试，4项测试通过。回交时发现运行时权限配置及锁文件也被收集，已加入排除规则并以同一原生会话复测；结果见 `partner-native-authorized-live.json`，运行时配置不作为源码产物交付。

## Scholar 的实际状态

已直接通过官方 MCP 初始化、列工具并分别调用 `search_papers_by_topic` 和 `get_author_papers`，均返回真实题录及下一页游标。它们按用途选择，不需要每次全部调用。

研究路由不再默认在首次错误后静默切 Crossref，只有请求明确启用 `allow_search_fallback` 才使用题录备用来源。新版桥接已经支持实际工具选择、年份上下限、不透明 cursor、能力发现和受鉴权保护的诊断/恢复接口。解释器、模块、MCP协议、桥接/隧道、网络/代理、限流和验证要求分别记录；可恢复故障先诊断，按已配置的恢复动作处理，再用相同参数重试原工具一次。限流与验证要求不进入自动修复循环。

14项 Scholar 合同测试加5项项目路由/恢复测试在生产候选中全部通过。正式项目实际完成三次检索：主题检索、作者检索、主题下一页，各返回2条记录；主题分页的输入/输出游标为 `null→2`、`2→4`。三次均关闭备用检索，只使用 Scholar 发现题录；Crossref仍可用于已有题录的身份核验，不作为此次检索失败后的替代来源。回执见 `partner-scholar-contract-live.json`。

DeepCode 的首次真实诊断使用通用测试解释器，明确识别其中缺少 `scholar_mcp`。后续复用本机已安装的专用 Scholar 环境完成实际检索，无需重装依赖。桥接或隧道完全不可达时，不能通过同一失效桥接执行恢复；本机启动恢复入口负责连接，服务端保留诊断和原任务状态。恢复命令只取自已有明确配置，不接受客户端任意命令。

## 使用入口

```powershell
$dp = 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe'
& $dp workflow routes --project PROJECT_ID --kind survey
& $dp workflow run --project PROJECT_ID --file 'D:/任务/request.json'
& $dp workflow status --project PROJECT_ID --id RUN_ID
& $dp workflow resume --project PROJECT_ID --id RUN_ID
```

例如读取已入库论文的指定页段：

```json
{
  "kind": "analyze",
  "query": "比较该文数值实现与验证条件",
  "assets": ["reading/paper.pdf"],
  "read_pages": {"reading/paper.pdf": [7, 8]},
  "max_sources": 1,
  "request_id": "read-paper-pages-7-8"
}
```

本次公开结果及理由、实际回执、失败范围与后续修复均进入“Deep Partner 研究工作流与工具集成”项目。idea memo 同步仍沿用原绑定。
