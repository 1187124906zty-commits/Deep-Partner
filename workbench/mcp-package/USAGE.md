# Research Workbench MCP

这是现有研究工作台的 MCP 客户端适配器，连接同一账户、项目、文献库和当前产物。37 个任务工具覆盖账户、项目文件、技能规范、知识库、联网检索、下载、阅读翻译、稿件引用、期刊模板、图形、汇报与处理回执。实际操作由工作台原 API 执行。

工作台网站：<https://tutor.example.invalid/research/>。API 与规则可在网站“工作台设置 → 使用与 MCP”查阅。该安装包不包含网站服务、账户数据、登录凭据或模型；运行时需要连接工作台服务。

## 安装与启动

解压后在 `research-workbench-mcp` 目录打开终端。已验证 Python 3.12.14、Windows 11、FastMCP 4.0.3；依赖完整固定在 `src/requirements.txt`。MCP 客户端只需 Python 与网络；PDF、Office、索引和模型运行依赖由现有网站服务提供。

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
& .venv/Scripts/python.exe -m pip install -r src/requirements.txt
& .venv/Scripts/python.exe -m pip check
& .venv/Scripts/python.exe -X utf8 src/workbench_auth.py login
& .venv/Scripts/python.exe -X utf8 src/workbench_auth.py status
& .venv/Scripts/python.exe -X utf8 src/project_mcp.py
```

POSIX 启动形式如下；本次交付的平台测试范围以实际验证记录为准。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python src/workbench_auth.py login
.venv/bin/python src/project_mcp.py
```

登录在命令行提示中输入用户名和密码。密码不作为 MCP 参数。私有会话默认保存到当前用户的 `~/.config/research-workbench/session.json`；另可通过 `WORKBENCH_SESSION_FILE` 指定受保护的文件，或由服务端提供合法 `WORKBENCH_TOKEN`。会话与服务 origin 绑定。服务拒绝公开登录入口时，使用该服务允许的专用前端登录方式；客户端不会伪造可信代理头。`workbench_auth.py logout` 撤销会话并移除本地文件。

`WORKBENCH_URL` 默认为 `https://tutor.example.invalid`，应为不带路径的 HTTPS origin。仅 localhost 调试允许 HTTP。`PYTHONUTF8=1` 避免 Windows 控制台编码问题。`WORKBENCH_OUTPUT_DIR` 设置未明确指定目的地时二进制原生响应的保存目录，默认用户 Downloads 下的 research-workbench 目录。

支持标准 stdio 的 MCP 客户端使用以下配置；将命令与参数改为本机解压目录的绝对路径。

```json
{
  "mcpServers": {
    "research-workbench": {
      "command": "<absolute-package-path>/.venv/Scripts/python.exe",
      "args": ["-X", "utf8", "<absolute-package-path>/src/project_mcp.py"],
      "env": {"PYTHONUTF8": "1"}
    }
  }
}
```

在 POSIX 使用 `.venv/bin/python`。客户端的工作目录可以不同；生产入口按自身文件位置导入工具，不依赖开发目录。无需执行权限恢复，均通过 Python 解释器启动。FastMCP 4.0.3 的 `install mcp-json` 可生成其他客户端格式；本包不自动注册或修改用户客户端配置。

## 一次任务如何完成

1. `workbench_account` 查看当前身份，`workbench_projects` 列出项目，选择实际拥有的 project_id。
2. `workbench_rules(action="context", project_id=..., task=...)` 取得当前项目、技能原文与写入/回执协议；按需要读取 `standards` 或单个 `skill`。
3. 调用相应任务工具。编辑文件和稿件时带回当前修改时间或 revision；冲突后重新读当前版本并理解差异。
4. 导出、翻译、索引和下载等操作保留原生 job_id 或专门任务状态。`workbench_jobs` 查询通用任务；下载使用 `workbench_paper_downloads`；阅读器翻译与知识索引使用各自原生状态。queued/running 表示尚未完成。
5. 读取实际结果和来源；需要本地文件时提供 `output_dir` 或 `output_path`，检查返回的绝对路径、文件内容和当前版本。
6. `workbench_review(action="receipt", stage=..., purpose=..., operation_id=..., ...)` 写入真实产物、来源、验证和限制，并触发当前阶段评分。stage与purpose取项目context，operation_id对同次交付保持稳定。旧调用省略stage时保留为尚未评审的保存回执。
7. `workbench_review(action="quality_rubric", ...)`读取尺度；`quality_submit`提交独立评审；`quality_list`读取依据与历史；`quality_gate`核对当前产物是否可继续。评审返回job_id时用workbench_jobs等到完成。下一自动阶段使用gate，文件、来源或规则改变后旧分数失效。

每次返回对象均含 `message`、`reference`、`artifacts`、`data`。`data` 保留有用的原生 JSON、原文文本或任务结果；`artifacts` 中列出已保存文件的绝对路径及字节数等。大文件通过文件/URL 交付。`reference` 指向实际工作台 API 来源。

## 工具目录

完整参数、默认值和分支必需项见 [TOOL_REFERENCE.md](TOOL_REFERENCE.md)。MCP `tools/list` 提供相同参数 schema。以下是稳定任务边界，许多工具以 `action` 选择同一任务的步骤。

| 任务 | 工具 |
| --- | --- |
| 用户、空间和项目 | `workbench_account`、`workbench_storage`、`workbench_projects` |
| 文件、恢复和材料导入 | `workbench_files`、`workbench_revisions`、`workbench_project_import` |
| 规则与接口配置 | `workbench_rules`、`workbench_settings`、`workbench_author_profile` |
| 知识库与原文检索 | `workbench_knowledge_bases`、`workbench_knowledge_files`、`workbench_knowledge_index`、`workbench_knowledge_search` |
| 联网发现与真实来源 | `workbench_search_sources`、`workbench_web_search`、`workbench_paper_search` |
| 文献和全文传输 | `workbench_literature`、`workbench_literature_organization`、`workbench_paper_downloads` |
| 论文阅读和翻译 | `workbench_reader`、`workbench_translation` |
| 稿件、引用和导出 | `workbench_manuscript`、`workbench_references`、`workbench_manuscript_templates`、`workbench_manuscript_export`、`workbench_export_download` |
| 期刊和官方模板 | `workbench_journals`、`workbench_journal_templates` |
| 图形、像素与审阅 | `workbench_figure`、`workbench_figure_chat`、`workbench_image_review`、`workbench_raster` |
| 研究汇报 | `workbench_slide_templates`、`workbench_slides` |
| 批注、处理和异步结果 | `workbench_annotations`、`workbench_review`、`workbench_jobs` |

## 检索、阅读和下载

先查询 `workbench_search_sources` 的实际状态。Google Scholar MCP、学术网页、已配置的 WoS Starter、Scholar SerpApi、Semantic Scholar 和 Crossref 为可区分的来源。自动选择依据连接账户的真实配置；检索结果显示实际 provider。Crossref 也用于候选题录的 DOI/作者/期刊身份核对。搜索片段不等同于全文依据。

`workbench_paper_search` 接收关键词、来源、年份、页码和数量。将选中的题录传给 `workbench_paper_downloads(action="enqueue", entries=[...])`，无需逐条输入 DOI。队列保留重复项处理、阶段、错误、重试、取消和验收回执。

下载依赖已配对的本机 ScanSci：本机下载 → research-cluster-xh5 上传与校验 → 所属用户文献文件夹。需要机构权限或验证码时，在 ScanSci 专用窗口人工完成。MCP 不导出日常浏览器 cookies；配对和传输密钥由部署侧管理。

项目知识检索有 `fulltext-keyword` 和 `semantic` 两种模式。前者返回实际 PDF 文本层或知识库原文预览命中和覆盖范围；后者调用 DeepTutor 原生 RAG，需要选择已绑定知识库、可用索引和检索模型。PDF 文本层解析不能代替扫描件 OCR。语义返回保留原文块和来源元数据；索引未就绪时按原状态处理。

阅读器原文、译文、图表和批注保留原文定位。稿件翻译与 PDF 阅读器翻译是不同流程；以对应任务的实际进度和译稿检查为准。任何方向的全篇学术翻译仍需检查术语、句法、数学和图表。

## 编辑、模板与成果

稿件默认通用学术版式；需要特定期刊时查询官方指南并下载官方模板原包。下载模板原包不表示已完成任意新期刊的排版适配。作者姓名、单位和邮箱使用已保存资料，预览日期与正式出版日期区分。

影响因子与分区按指标年份、学科及数据来源读取。Clarivate Journals API 与 WoS Starter 的授权不同；中科院分区也需要独立授权来源。缺少授权时保留 unavailable/not_configured，不将猜测值作为指标。

图形工具保留原始数据和原生版本冲突；对象精修、像素保存、审阅对话是不同动作。`workbench_image_review(send=false)` 仅准备审阅草稿。研究汇报需要用户选择并确认内容、受众和模板；`workbench_slides(action="confirm")` 记录该实际选择，模板变化后原确认可能失效。只有实际文件通过检查才能作为交付。

## Dify 与远程调用

Dify 使用 HTTP MCP 服务。stdio 安装包不能直接填入 Dify 的服务器 URL。现有私有部署使用与工作流绑定的 HTTP 服务，工具调用继承当前成果交付任务的账户和项目，调用参数额外提供该流程的 `run_id`。远程文件路径属于服务端项目与本次任务输出目录。本机文件应先经原上传/ScanSci 通道送入项目，再供远程流程使用。

远程服务地址、注册状态和工作流验收结果以部署交付记录为准。服务端鉴权由 Dify 工具凭据管理；密码和会话不放进模型提示或普通工具参数。标准 stdio 客户端仍可独立使用本包。

## 验证范围和外部条件

开发与独立验证将原接口的真实执行结果绑定到每个工具，检查变化输入、错误、账户范围、原文、文件和任务语义。最终交付另检查 stdio、全新运行环境与实际 ZIP 在新位置安装。项目的详细回执保存在交付工作区，不随包带入测试数据或账号文件。

模型、WoS/JCR 等授权、ScanSci 专用会话、索引和集群通道是运行时前提。本包的工具验证不表示所有外部模型质量、任意稿件、所有期刊排版或整篇论文科学结果已经得到验证。通用任务取消/重试仅在上游实际提供时可用；当前通用 job 列表之外的缺失任务不视为已完成。项目删除/归档等未提供的 API 不在本工具集中。
