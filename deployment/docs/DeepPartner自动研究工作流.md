# Deep Partner 自动研究工作流

2026-11-05。已发布到正式网站，并提供原生 `dp` 命令和轻量 MCP 入口。

同日后续更新：集群自动解析、原生工具工作流与阶段恢复见 [固定路线与自动纠错](DeepPartner固定路线与自动纠错.md)。该说明记录最新实现及待完成项；下文保留首轮集成验收。

本次集成与记录归属：[Deep Partner 研究工作流与工具集成](https://tutor.example.invalid/research/?project=c37b9168a0db40e3b258c9c03cd56697)。实际下载、代码执行与对话故障测试使用独立的软件验收项目，不混入作者的科学研究项目。

## 一次选择任务类型，程序执行后续步骤

研究先绑定真实项目和会话，再选择结构化任务类型。后端负责调用顺序、下载回执、项目保存、任务状态和图谱更新；需要理解论文的步骤调用模型进行有来源的研究综合。

| 类型 | 实际路由 | 项目中保存的结果 |
| --- | --- | --- |
| `search` | Google Scholar MCP；失败时保留原因并切换 Crossref | 题录、查询范围、来源状态与执行记录 |
| `download` | 已配对的 ScanSci → PDF 身份核对 → 项目文献库 | 原始 PDF、题录、入库回执与读取范围 |
| `survey` | 检索 → ScanSci → 项目入库 → 分批原文摘录 → 研究综合 | 文献、研究记录、带页码的图谱节点和关系 |
| `analyze` | 当前项目明确选中的 PDF → 有限摘录 → 研究综合 | 方法、发现、局限、范围内的空缺和候选想法 |
| `code` | DeepCode 任务接口 → 实际执行 → 按产物清单保存 → 文件回读 | 明确交接的源码、执行记录、项目文件保存回执 |
| `slides` | Paper2Slides 内容规划；可选导出沿用现有评审及作者决定 | `slides/plan.json`；允许继续后生成 PPT/PDF |

检索与下载启动时检查现有本机桥接和配对设备。恢复使用原有运行环境、数据及当前账户的已授权配对，不创建另一套机构会话。新登录、验证码等仍在原下载工具的授权窗口完成。

## 图谱表达研究关系

在画布中选择“研究知识图谱”，可以看到论文、方法、发现、局限、研究空缺、候选想法、研究决定和备忘录。关系包括使用、支持、反证、受限于、引出、提出、来源于和回应。

节点保存可公开的研究结论、理由摘要和来源定位。文献方法及发现需要来源；引自 PDF 的内容保留实际提供的页码。新想法标为 `proposed`；检索没有命中时标为 `not_found_in_scope`，同时保存查询、来源和时间，避免把有限检索扩大成“全世界没人做过”。

图谱与可读材料同时保存。主要位置为：

- 文献：对应项目文献库。
- 研究记录：`docs/research/records/*.md` 及同名 JSON。
- 工作流记录：`docs/research/runs/*.md`。
- 对话归档：与同一项目关联的会话材料。
- idea memo：`docs/idea-memo/` 中的可读正文和增量回查材料。

本次 idea memo 已绑定集成项目。其他 memo 需要绑定其真实所属项目一次，后续保存自动同步；未绑定的 memo 保留本机副本。不会根据相似名称猜测上传项目。

## 控制每次读取的材料量

入口只提供六个 MCP 工具：项目、研究任务、记录、图谱、会话和 memo。技能目录读取名称和描述，选中功能后再读取对应正文。

研究综合默认一批最多三篇，每篇最多 14,000 字符，并保存实际摘录页码。当前摘录优先前六页及最后两页，在字符预算内停止；这表示有范围的阅读，不代表逐页读完全文。后续阅读可以明确指定下一批材料。代码只交接 `input_paths` 指定的项目文件，不自动附带几十个项目文本。

## `dp` 对话连接

已安装命令位置：

```text
C:\Users\DEVELOPER\AppData\Local\Programs\Deep partner\dp.exe
```

在 PowerShell 中：

```powershell
$dp = 'C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe'
& $dp project list --json
& $dp chat list --project PROJECT_ID
& $dp chat send --project PROJECT_ID --message '本次研究问题……' --jsonl
& $dp chat send --project PROJECT_ID --session SESSION_ID --file 'D:/任务/下一条消息.txt' --jsonl
& $dp chat history --project PROJECT_ID --session SESSION_ID --limit 12
& $dp chat resume --project PROJECT_ID --session SESSION_ID --jsonl
```

首条发送可以不指定会话，返回的实际 `session_id` 用于继续连接。`resume` 读取已有任务进度，不重新提交原提问；本机保存项目对应的恢复位置。跨项目会话会被拒绝。`chat reply` 用于回复会话中的待答问题，`chat stop` 用于明确停止当前会话任务。

## 启动与查询工作流

将请求保存为 UTF-8 JSON。例如，已有 DOI 的下载请求：

```json
{
  "kind": "download",
  "entries": [{"doi": "10.1038/s41598-022-22684-1"}],
  "request_id": "download-selected-paper-1"
}
```

调用命令：

```powershell
& $dp workflow routes --project PROJECT_ID --kind download
& $dp workflow run --project PROJECT_ID --file 'D:/任务/request.json'
& $dp workflow status --project PROJECT_ID --id RUN_ID
& $dp workflow graph --project PROJECT_ID --limit 80 --offset 0
```

同一操作重试沿用 `request_id`，程序返回原任务，避免重复执行。提交成功仅代表排队；以状态和保存回执判断执行结果。部分文献下载未完成时保留已完成材料及具体阻碍。

代码任务另支持 `session_id`、`input_paths` 和用于恢复既有执行回交的 `code_task_id`。代码任务等待必要信息时，用 `workflow reply --project PROJECT_ID --id RUN_ID --file ANSWER_JSON` 回复，JSON 格式为 `{"answer":"具体答复"}`。汇报使用真实的 `confirmation_id`；`export_slides: true` 表示计划完成后请求导出，评审或作者决定尚未满足时会返回等待状态。

## 已完成的实际验证

- 后端 8 项定向测试通过，涵盖项目归属、来源定位、读取范围、结构化协议和图谱持久化。
- 前端 40 项工作台测试和 47 项统一界面测试通过；正式网站已显示图谱节点、语义关系和保留的活动视图。
- MCP 完成协议握手和实际项目读取，不只检查配置文件。
- 同一项目两轮流式对话保留上下文，回复进入项目；强制结束客户端后恢复同一任务，没有重复提问。
- Scholar 恢复后返回真实题录；ScanSci 下载 3,842,041 字节的实际 PDF，经身份核对、集群副本验收后进入同一项目文献库。
- 实际文献综合生成 17 个带来源的节点及 35 条关系，保存了本次确实读取的第 1—4 页范围。此项验证工作流，不作为全面的新颖性调研。
- DeepCode 新任务实际执行脚本，项目源码保存后回读一致；另一个既有已执行任务也成功恢复回交。
- idea memo 首次绑定同步和后续增量保存自动同步均已验证。
- Paper2Slides 实际生成三段内容计划并保存；验收材料被现有内容评审判为需要修改，未把它声明为完整 PPT 导出成功。

各项原始验收记录位于本仓库 `reports/partner-*.json`，汇总见 `reports/partner-workflow-release.json`。

## 配置入口

已从用户级 `C:/Users/DEVELOPER/.codex/AGENTS.md` 移除旧研究编排入口，并在 `config.toml` 停用 `research-agent-orchestrator`。新入口技能位于 `C:/Users/DEVELOPER/.codex/skills/deep-partner-research/SKILL.md`，`deep-partner` MCP 已注册。

已打开的 Codex 会话可能保留启动时的工具与技能清单。配置刷新或新会话后使用新 MCP；当前会话可以立即通过 `dp` 执行同一流程。这里修改的是用户级指令、技能与工具配置。
