# DeepTutor、Code 与研究工作台集成能力审计

审计时间：2026-11-01（北京时间）。范围为现有部署的只读代码与 API 检查；本审计未部署服务、未提交 Code/Slurm 任务、未创建或重建知识库。身份使用已保存的合法 Tutor 管理员登录；报告不保存密码、密钥、cookie、token 或完整环境变量。

## 结论与当前真实入口

现有能力足以组成“检索证据 → Tutor 判断 → Code 实施/验证 → 工作台交付”的流程。RAG 需要显式使用项目绑定的知识库；Code 应接当前 0.2.1 原生适配器。旧的 `coder-build/coder_service.py` 是历史实现，不能作为当前接口契约。

| 服务 | 公网入口或内部地址 | 运行依据 |
|---|---|---|
| DeepTutor | https://tutor.example.invalid；宿主回环 127.0.0.1:8008 → 容器 8001 | 容器 deeptutor |
| 研究工作台 | https://tutor.example.invalid/research；内部 127.0.0.1:47900 | research-workbench，uvicorn server.app:app，host 网络 |
| 工作台/Dify 适配器 | /research/dify；内部 127.0.0.1:47910 | dify-workbench-bridge |
| 当前 Code | /api/coder/*；内部 127.0.0.1:8010 | deeptutor-coder：python -m tutor_deepcode.worker；包 0.2.1 |
| 集群计算 MCP | Docker 内 http://research-compute:47920/mcp；宿主 127.0.0.1:47920/mcp | research-compute；带专用 bearer 认证 |
| Dify | /dify；宿主 127.0.0.1:8088 | Dify 1.18.0 |

Code 公网 health 实测 HTTP 200：`protocol_version=1`、`adapter_version=0.2.1`，tasks/questions/branch_ancestry/idempotency/artifacts 均 true；native probe 为 DeepCode 2.3.1、`adapter_revision=native-questions-cluster-v2`，native_turns、midtask_questions、structured_events、native_interrupt、registered_cluster_jobs 均 true。这证明运行时入口与依赖已就绪，不等同于本次新任务已执行。

## 1. RAG、知识库读取、索引任务与权限

### 账户资源与项目绑定

工作台身份经 `GET /api/auth/profile` 取得真实用户，项目查询在数据库以 `owner + project_id` 过滤。未登录不能访问；不接受请求方自行替换 owner。当前实测身份为 local-admin / admin，仅能由该身份的实际权限推导本报告中的资源可见性，不能推广到普通用户。

工作台项目必须绑定原生 workspace。原生 API 需携带 `dt_workspace={project.native_id}`。MCP 的 `WorkbenchClient.native_request` 会先读取当前账户项目，再自动附加 workspace；不要在 Dify 中手工猜测其他账户 workspace。

审计初始时两个现有项目均未绑定 KB：

| 项目 | project_id | native_id |
|---|---|---|
| Dify 部署与交付验证 | c0b9c547b07c401aa7fc7454b0104345 | ws_f5cecfd629bd4985be1624aefa509c5c |
| 计算验证能力验收 | 50313863a9544f72aae778d7381bfe79 | ws_f96bbe8cc54e4676bb821def0e102eff |

账户中 5 个可见且 ready 的 LlamaIndex 库如下。另有一个 workspace 局部库，不应自动混入账户级验证。

| qualified KB ID | 原始文档数 | 当前可读索引节点数 |
|---|---:|---:|
| account:kb:Peng Lan—入渗与物理学习 | 4 | 399 |
| account:kb:应用驱动深度学习框架 | 31 | 4076 |
| account:kb:氯-硫酸盐潜在数据 | 44 | 4619 |
| account:kb:科技论文写作 | 4 | 1140 |
| account:kb:耐久性综述 | 5 | 556 |

以上库的当前索引均为 `state=published, readiness_verified=true, ready=true, needs_reindex=false`，嵌入为 BAAI/bge-m3 / 1024 维。部分库保留未通过持久化验证的旧候选版本；检索应使用当前匹配且 published 的版本，不能把旧候选数量当成损坏结论。

绑定 API 为 `PATCH /research/api/projects/{pid}`。绑定会同时更新工作台配置和原生 workspace resources。服务先获取该账户可见资源集合，拒绝集合外的 KB（403）。例如主协调者如需在独立验证项目验证氯硫库，可使用：

```json
{"knowledge_bases":["account:kb:氯-硫酸盐潜在数据"]}
```

该操作不是复制、上传或重建源知识库。本只读审计没有执行绑定。绑定列表是完整替换；`[]` 表示清空，不能拿增量语义理解此字段。原生已分配的管理员资源可能只读；写入必须经过 `resolve_kb(..., require_write=True)`，不能因为能读取就推定能重索引。

### 项目检索契约

`POST /research/api/projects/{pid}/knowledge/search`

```json
{
  "query":"chloride diffusion sulfate",
  "mode":"semantic",
  "knowledge_base":"account:kb:氯-硫酸盐潜在数据",
  "limit":3
}
```

query 去首尾空白后截为 600 字符，至少 2 字符；limit 为 1–20。传入 KB 必须在项目绑定列表中，否则 403。semantic 必须显式选 KB。请求使用真实 Tutor cookie 或 bearer，写类 HTTP 方法附 `Origin: https://tutor.example.invalid`。

semantic 的外层响应：

```json
{
  "mode":"semantic",
  "query":"...",
  "knowledge_base":"...",
  "result":{
    "query":"...",
    "answer":"来源片段全文拼接",
    "content":"来源片段全文拼接",
    "sources":[],
    "provider":"llamaindex"
  },
  "source":"DeepTutor 原生 RAG",
  "checked":"ISO 时间"
}
```

LlamaIndex 当前查询返回的 answer/content 是实际检索片段的拼接，不是另一次 LLM 综合回答。sources 的基础字段为 `title, content, source, page, chunk_id, score`；content 是前 200 字符预览。带完整定位的节点另有 `document_key, source_digest, source_schema_version, page_index, page_label, parser_signature, page_status, visual_status, evidence_text`，其中 evidence_text 至多 6000 字符。图像节点可能增加 `visual_asset_id, source_document_id, bbox, caption, source_locator`。不要把 source 的本机路径直接当公网 URL。

semantic 首先通过带真实会话的原生 KB GET 确认可见性，再启动同账户、同 workspace 的原生 RAG helper。helper 的 subprocess communicate 硬超时为 120 秒；此前原生校验 HTTP 的单次超时另为 45 秒，认证也有自己的 HTTP。整个请求没有一个统一的 120 秒端到端上限。适配调用宜给出 180 秒级连接/响应预算，并明确超时发生在哪一层。

`mode=fulltext-keyword` 的请求字段相同，knowledge_base 可为空；为空时查当前项目文献和所有已绑定库，指定时仅查该库。响应为：

```json
{
  "mode":"fulltext-keyword",
  "query":"...",
  "items":[
    {"excerpt":"...","score":4,"chunk":1,"title":"...","library":"...","asset":"...","url":"...","evidence":"source-preview-text"}
  ],
  "documents_scanned":1,
  "coverage":[],
  "errors":[],
  "source":"项目全文关键词检索",
  "checked":"ISO 时间",
  "scope":"实际扫描范围说明"
}
```

关键词模式用词频、全词覆盖奖励排序，每个源最多取两段，每段至多 1000 字符。它不是向量检索；其 score 与 semantic score 没有可比单位。项目文献最多扫前 60 条 PDF，每个 PDF 最多前 300 页、200 万字符；原生每库最多前 60 文件，以文本预览范围为准。该路径没有总运行超时，原生文件列表/文本请求各自 45 秒且按文件顺序执行；大库不宜无选择地用于每轮全库并行。

部分文件不可读时，关键词路径可能仍 HTTP 200，必须检查 errors、coverage 与 documents_scanned。semantic helper 对 error_type 返回失败；但 needs_reindex 可能保留为 result 字段，调用方仍应检查 `result.error_type/result.needs_reindex`，不能只判断外层 HTTP 200。

### 读取与索引生命周期 API

所有带 KB 的原生路径都应 URL 编码 qualified ID，并携带 dt_workspace。

| 方法与路径 | 结果/用途 |
|---|---|
| GET /api/knowledge-bases?resource_library=true&dt_workspace=... | 当前账户可赋予资源库；保留 qualified ID |
| GET /api/knowledge-bases/{kb}?dt_workspace=... | KB 状态、metadata、statistics 与索引版本 |
| GET /api/knowledge-bases/{kb}/files | 原始文件清单 |
| GET /api/knowledge-bases/{kb}/file-preview-text/{filename:path} | 实际文本抽取预览 |
| GET /api/knowledge-bases/{kb}/files/{filename:path} | 源文件字节 |
| GET /api/knowledge-bases/{kb}/source-page | 原生来源页读取；以该端点实际参数为准 |
| GET /api/knowledge-bases/{kb}/indexing-readiness | parser、本地/云前置条件、embedding_model/configured、source_count |
| GET /api/knowledge-bases/{kb}/indexing-run | 持久 run 诊断；纯读取，不重新创建任务 |
| GET /api/knowledge-bases/{kb}/progress | 当前 progress 或 not_started |
| POST /api/knowledge-bases/{kb}/upload | multipart 上传，交原生后台索引 |
| POST /api/knowledge-bases/{kb}/reindex | 原生重新索引；不是只读验证 |
| POST /api/knowledge-bases/{kb}/retry | 仅失败 KB；健康 KB 返回 409；LightRAG rebuild 另有显式策略 |
| POST /api/knowledge-bases/{kb}/indexing-run/{task_id}/cancel | 安全边界取消请求；未完成任务才接受，否则 409 |
| GET /api/knowledge-bases/tasks/{task_id}/stream | text/event-stream，no-cache，X-Accel-Buffering=no |

`readiness.ready` 只说明前置条件，不能证明云响应、下载、资源限制及最终索引成功。重索引完成需再读 published/ready 与持久 run。模型策略旧接口可能 409；创建/重建前应读取真实 provider config，不向每 KB 塞入已弃用的 model override。

已有 MCP 可直接复用：`workbench_knowledge_bases`（list/details/create/bind）、`workbench_knowledge_files`、`workbench_knowledge_index`（readiness/run/progress/retry/cancel）、`workbench_knowledge_search`。这些位于 `bridge/workbench_mcp/tools/workspace_api.py`，无需新写一套同名权限逻辑。

### 已完成真实验证

本审计读取运行实例的 auth/profile、llm-options、KB 列表/rag-providers/health、工作台项目与来源状态，均成功。为检验真实索引和 embedding，而不改变项目绑定，使用与工作台 semantic 完全相同的 `server/native_rag.py` helper、当前合法用户/验证 workspace 查询氯硫库：

- query：chloride diffusion sulfate；limit：2。
- 实际用时 7.40 秒，provider=llamaindex，sources=2，content=6221 字符。
- result 键确认为 query/answer/content/sources/provider；无 error_type、无 needs_reindex。
- 报告仅记录结构和计数，不保存原文片段。
- 这证明 native RAG 路径可查询；项目 HTTP semantic 路径仍需在合法绑定后单独验收。

## 2. Code 任务、状态、结果与事件

### 应接当前原生适配器

运行源码位于容器 `/usr/local/lib/python3.12/site-packages/tutor_deepcode/{worker,protocol,store,native_runner,files}.py`。Tutor 侧为 Python 3.11 同包 `tutor_adapter.py`。宿主历史 `/srv/deeptutor/coder-build/coder_service.py` 的简单 task/sources 队列已不适用。

公网 `/api/coder/*` 通过 Tutor 登录验证且仅开放给管理员；POST 必须同站 Origin。内部无前缀 `/tasks` 接口使用 worker 专用 bearer。普通用户不能直接沿用管理员路径；不要把内部 bearer 写入 Dify 可见变量或页面。

提交 `POST /api/coder/tasks`（内部 `POST /tasks`）：

```json
{
  "protocol_version":1,
  "project":"dify_validation",
  "mode":"plan",
  "task":"读取输入并报告可执行验证步骤。",
  "identity":{
    "owner_id":"local-admin",
    "workspace_id":"ws_f5cecfd629bd4985be1624aefa509c5c",
    "session_id":"真实 Tutor session",
    "turn_id":"真实 turn",
    "command_id":"本次操作稳定编号",
    "ancestor_turn_ids":[]
  },
  "context":{},
  "inputs":[{"path":"brief.txt","text":"经授权的限定输入"}]
}
```

project 只允许 1–60 个英文数字、下划线/连字符；task 1–30000 字符。identity 的 owner/workspace/session/turn/command 必须由已认证应用上下文提供，不能让 LLM 任意生成归属。`inputs` 的路径是项目内相对路径；文本用 text，二进制可用 content_b64，总输入上限 8 MB；context 上限 2 MB；请求体上限 14 MB。plan 为原生只读执行，code 为实施与检查。

返回 HTTP 202，包含任务 `id`、状态及 `deduplicated`。幂等键由 owner/workspace/session/turn/command 组合导出；同键同载荷返回原任务，同键改载荷 409。重复请求复用 command_id；需求改变使用新 command_id。项目实际物理名可能添加隔离后缀，后续文件读取使用响应中的 project。

`resume_id` 只允许同账户/工作区/会话/逻辑项目且属于当前分支祖先的终态任务。响应 parent_task_id、branch_mode 表达 continue/fork 等分支行为。不要把工作台 project_id 与 Code project 直接当成同一字段。

### 状态和事件轮询

`GET /api/coder/tasks/{id}?offset=0` 返回：

```json
{
  "id":"24位十六进制",
  "project":"实际物理项目",
  "logical_project":"逻辑项目",
  "status":"queued",
  "result":"",
  "error":"",
  "session_id":"",
  "native_turn_id":"",
  "exit_code":null,
  "events":[],
  "next_offset":0,
  "event_count":0,
  "has_more":false,
  "verification":{},
  "execution":{},
  "model_resolution":{},
  "question":null,
  "cluster_jobs":[]
}
```

还保留 owner/workspace/tutor_session/tutor_turn、时间与分支字段。状态为 queued/running/waiting_input，终态 completed/failed/cancelled/interrupted。每次最多取 seq 大于 offset 的 100 条事件，下轮用 next_offset；has_more=true 时继续排空。events 保留原生结构，不能预设所有事件都有 text；常见信息在 `event.msg.type`。HTTP 任务接口没有独立 SSE 订阅端点，当前能力是持久结构化事件轮询。Tutor 原生适配器轮询后会将事件转发到正在进行的 Tutor turn，并发 coder_status。

`GET /api/coder/tasks` 只列 live 任务，实测为空；这不表示没有历史。需持久保存每次提交得到的 task_id。

waiting_input 且 question 非空时展示真实提问/选项，不自动假定用户已回答。`POST /api/coder/tasks/{id}/replies` 接收 `{question_id,answer,command_id,identity}`。相同回答命令可幂等复用；不同回答不能覆盖已答问题。取消使用 `POST /api/coder/tasks/{id}/cancel`、body `{identity:...}`；运行过程取消还会请求终止此任务登记的 cluster_jobs，不能推定已取消未登记的任意 Slurm 作业。

文件清单与读取：`GET /api/coder/projects/{实际project}/files`；带 `path=results/foo.json&format=text&start_line=1&line_count=180` 可定向读取。浏览器带 path 且非 text 时返回文件字节，最大 20,000,000 bytes。内部 API 还需 owner/workspace/session 等身份参数；读产物拒绝私有目录、符号链接和越界路径。

`verification` 来自 Code 写出的 verification.json，当前 native_runner 把其中检查标为 `self_reported_not_independently_verified`。completed、exit_code=0 和文件存在都不能替代科学参照/独立数值核验。

### 集群 MCP

现成 `research_compute(action,payload)` 通过 MCP streamable HTTP 提供 inventory/prepare/submit/status/read/assess/cancel/openpaso_schema。prepare 的 spec 包含 question/runtime/files/entrypoint/criteria/reference/limitations/resources；runtime 支持 python/paso/torch/openpaso/catalog。prepare 后保留 experiment_id，submit 返回真实 job_id；状态不明继续查同一个 experiment_id。assess 应用执行前声明的数值 criteria，不证明实验真值。

MCP 每次核对应用提供 owner_id，并限制到部署指定账户；专用 token 文件存在但未导出。cluster 控制子进程超时 65 秒；MCP 客户端通常预算 90 秒。可先 `tools/list` 与 inventory 验证通路，再在独立测试任务做 prepare/submit/status/read/assess。当前 Code native callback 另有已登记 cluster_job 路径，应沿实际模型工具使用，不以直接 sbatch 绕过登记。

## 3. 当前模型与搜索 provider

| 能力 | 当前配置 | 认证字段状态/实测范围 |
|---|---|---|
| Tutor 默认 LLM | gpt-6.1-sol，reasoning_effort=max；profile llm-profile-agent-setup / model llm-model-gpt61sol-max-study | key 存在；GET llm-options 可见；本次未额外发送计费推理 |
| 其他可选 LLM | gpt-6.1-sol 默认档、gpt-6.1-terra/high、另一 gpt-6.1-sol/max profile | 同一 Krill endpoint；配置存在 |
| LLM endpoint | https://api-slb.kbsfdxc.net/backend-api/codex；api_format=openai_responses、wire_api=responses | 不应按 chat/completions 协议直接拼接 |
| Code 模型 | gpt-6.1-sol，同上 endpoint | key 存在；健康探针成功；execution_selection 默认 max/500000，实际以 task.execution 为准 |
| Embedding | BAAI/bge-m3 / 1024；https://api.siliconflow.cn/v1/embeddings | key 存在；本次真实 RAG 查询成功 |
| 原生 search | duckduckgo | 无 API key；配置存在 |
| 文档解析 | MinerU cloud | api_token 存在；本次未重解析 |
| task/tts/stt/imagegen/videogen | 无配置 profiles | 不应在工作流假设可用 |

工作台账户 API 配置：独立 base_url/model 为空、api_key 未配置，`native_available=true`；流程应使用原生模型选择或现有适配器，不能假设工作台另有 OpenAI chat/completions Key。

`GET /research/api/search/sources` 实测：

- scholar_mcp、academic_web、crossref：configured=true。
- semantic（Semantic Scholar）、scholar（SerpApi）、wos：configured=false。
- 网页：DuckDuckGo 公共检索，configured=true；SerpApi 搜索 Key 不存在。
- journal_metrics（Clarivate Journals API）：configured=false；ROR 机构：configured=true。

configured 对 Scholar MCP 仅表示解释器或桥接配置存在，不能证明外部 Scholar 未限流/无需人工验证。auto 策略依次选已配置 WoS/SerpApi/Semantic Scholar，随后 Scholar MCP，最后 academic_web；自动失败时会明确标出 Crossref 降级。明确指定 source 不应暗中更换来源。题录与网页检索片段不是已读论文全文。

文献端点为 `GET /research/api/projects/{pid}/literature/search?q=...&source=scholar_mcp&limit=...`，来源列表为 `GET /research/api/search/sources`，网页为 `GET /research/api/search/web?q=...`。现有 Dify WebScraper 阅读端点为 `GET /research/dify/api/web-evidence?url=...`。应分别保留 requested_source/provider/status/errors，而非把所有空 items 当成无相关研究。

## 可执行验证与 Dify 接法

优先复用 `WorkbenchClient` 的已登录同源传输，不复制浏览器日常 cookies。下面代码读会话文件或 WORKBENCH_TOKEN，所有日志只记录结构与数量：

```python
import asyncio, json
from workbench_mcp.client import WorkbenchClient

async def main():
    client = WorkbenchClient()
    try:
        projects = await client.request("GET", "/research/api/projects")
        sources = await client.request("GET", "/research/api/search/sources")
        print({"project_count": len(projects["projects"]), "sources": sources})
        # 先由合法的项目绑定操作选定测试库，再查询。
        pid = "c0b9c547b07c401aa7fc7454b0104345"
        kb = "account:kb:氯-硫酸盐潜在数据"
        response = await client.request(
            "POST", f"/research/api/projects/{pid}/knowledge/search",
            json={"query":"chloride diffusion sulfate","mode":"semantic",
                  "knowledge_base":kb,"limit":2})
        result = response.get("result", {})
        assert not result.get("error_type") and not result.get("needs_reindex")
        print({"source":response.get("source"),
               "provider":result.get("provider"),
               "sources_count":len(result.get("sources", [])),
               "content_chars":len(result.get("content", ""))})
    finally:
        await client.close()

asyncio.run(main())
```

高强度验证的最短有效覆盖为：合法绑定与未绑定 KB 的 200/403；两种检索模式的非空真实来源与无匹配结果；断连/超时与空结果区分；Code 固定 command_id 的同载荷重试去重、改载荷 409；事件游标续读；waiting_input/replies；小型实际代码执行与文件回读；验证记录与原始数值结果对应。只在独立测试项目/会话执行会产生状态的用例。

Dify 联合检索可并行三支：选定 KB 的 semantic、限定文件范围的 keyword、真实 papers/web 来源。归一化时保留 `kind/title/text/url_or_source/page/chunk_id/provider/evidence`，不要直接混排不同评分。semantic 取 evidence_text（无此字段时 content）与稳定定位；keyword 保留 coverage/errors；网络保留题录、URL、来源和 verified 证据等级。去重使用库/文档/页/块或 DOI，不删除来源定位。

Code 是持久异步任务：提交节点只产生 task_id，后续轮询节点检查状态；waiting_input 转用户输入，终态再读产物与 verification。长任务不要依赖单次 Dify HTTP 节点一直等待。Tutor 原生 coder_run 已实现真实会话快照、分支与用户提问接续，优先让它承担需要交互的 Agent 编程任务，Dify 保存/展示稳定阶段。

## 代码证据定位

- 远端当前工作台：`/srv/research-workbench/source/server/knowledge_search.py`、`native_rag.py`、`native.py`、`storage.py`、`app.py`（项目绑定/API设置）、`literature_providers.py`、`search_mcp.py`。
- 原生知识库：`C:/Users/DEVELOPER/DeepTutor/deeptutor/api/routers/knowledge.py`（indexing-run/readiness/progress/SSE）、`deeptutor/multi_user/knowledge_access.py`、`services/workspace/knowledge.py`、`services/rag/pipelines/llamaindex/pipeline.py`。
- 运行 Code：`deeptutor-coder:/usr/local/lib/python3.12/site-packages/tutor_deepcode/`；worker.py 路由、protocol.py validate_task、store.py enqueue/_public/question、native_runner.py verification。
- 集群 MCP：`/srv/tutor-research-compute/app/compute_mcp.py`、`cluster_dispatch.py`；原生 Code 集群登记另由 tutor_deepcode/cluster.py 管理。
- 当前 MCP 工具包装：本项目 `bridge/workbench_mcp/tools/workspace_api.py` 与 `bridge/workbench_mcp/client.py`。

