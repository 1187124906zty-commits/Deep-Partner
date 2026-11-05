# 工作台阶段评分：现有实现调查与最小接入建议

调查日期：2026-11-02。范围：本机 `D:/Development/research-workbench` 当前源码、其 `vendor/paper2slides`、MCP 工具契约和 Dify 交付桥接；另核对 HKUDS 官方源码。仅作静态读取和公开官方源码核验，未启动模型、未运行生成、未部署，也未把已有测试脚本当作本轮实际执行结果。

## 1. 已确认的结论

**工作台当前实际集成的 HKUDS/Paper2Slides 没有“每阶段质量打分—按分数修订—复评”的实现。** 它提供内容规划、四阶段流水线、检查点与从指定阶段重跑。工作台另行实现可编辑 PPT 输出及有限的版面/渲染硬校验。将这些现有能力描述成已有评分体系会误导后续实施。

用户希望“每个阶段输出都有类似 paper2slides 的评分过程”，可以落实为独立的阶段产物质量评审层；这部分需要新增。可直接复用现有任务、文件版本、批注、回执与处理历史，不必复制整个 Paper2Slides 流水线，也不必先替换工作台架构。

## 2. 项目身份与版本证据

| 对象 | 实际身份/核验结果 | 证据 |
| --- | --- | --- |
| 工作台 | 研究工作台，复用 DeepTutor 账户、原生工作区、知识库与会话；该本机目录没有 `.git`，不能给出自身提交号 | [README.md](D:/Development/research-workbench/README.md)、[server/integration.py](D:/Development/research-workbench/server/integration.py) |
| 当前输出标准 | `VERSION='2026-11-01'`；按 `code/paper/translation/literature/slides/review/figure` 注入相关约定 | [server/standards.py](D:/Development/research-workbench/server/standards.py) |
| 本地 Paper2Slides 集成 | 显式导入本仓 `vendor/paper2slides` 的 `ContentPlanner`；planner 标签为 `HKUDS/Paper2Slides ContentPlanner` | [server/slides.py](D:/Development/research-workbench/server/slides.py) 的 `plan_with_paper2slides`，第199行；[server/app.py](D:/Development/research-workbench/server/app.py) 的 `generate_plan`，第1228行 |
| 官方参照版本 | `HKUDS/Paper2Slides`，`main` 提交 `0785051d1f52814097e94c44751e3f12b83f7c8a`，提交时间 `2026-05-20T09:08:05Z`；这是本轮查询得到的官方当前版本 | [官方固定提交](https://github.com/HKUDS/Paper2Slides/tree/0785051d1f52814097e94c44751e3f12b83f7c8a)、[官方提交API](https://api.github.com/repos/HKUDS/Paper2Slides/commits/0785051d1f52814097e94c44751e3f12b83f7c8a) |
| 版本一致性范围 | 本地 `core/pipeline.py`、`core/state.py`、`generator/content_planner.py`、`core/stages/plan_stage.py`、`core/stages/generate_stage.py` 与上述官方提交逐内容一致，比较时统一换行。未据此声称整个 vendor 未改动 | 本轮从固定提交读取原始文件并直接文本比较 |
| 已知本地改动 | `generator/image_generator.py` 增加 `re` 和从 Markdown data URL 解码图像的兼容处理；差异中没有评分或评审逻辑 | [本地 image_generator.py](D:/Development/research-workbench/vendor/paper2slides/generator/image_generator.py)、[官方同文件](https://github.com/HKUDS/Paper2Slides/blob/0785051d1f52814097e94c44751e3f12b83f7c8a/paper2slides/generator/image_generator.py) |
| `D:/Pi/Data/research-tools` | 当前直接子目录是 `ppt-master`、`ppt-master-installation`、`scansci-pdf`；未找到另一份 Paper2Slides 安装 | 本轮目录清单与限定文本检索；不推断整个磁盘不存在其他副本 |

仓库没有 Paper2Slides 来源提交清单或独立版本号；因此准确的表达是“本地关键模块与指定官方提交一致，并有已知图像响应兼容补丁”，不能将其包装成已完整锁定版本的发布包。

## 3. Paper2Slides 实际怎样工作

官方与本地共用的 `STAGES` 是 `rag → summary → plan → generate`。`run_pipeline` 在每阶段调用前保存 `running`，调用无异常则保存 `completed`，异常则 `failed` 并退出当前循环。`detect_start_stage` 根据检查点文件是否存在选择恢复位置。这是执行状态和恢复机制，不对产物内容给分。[本地状态实现](D:/Development/research-workbench/vendor/paper2slides/core/state.py)、[本地流水线实现](D:/Development/research-workbench/vendor/paper2slides/core/pipeline.py)、[官方固定版本流水线](https://github.com/HKUDS/Paper2Slides/blob/0785051d1f52814097e94c44751e3f12b83f7c8a/paper2slides/core/pipeline.py)。

| 可能被误认为评分的行为 | 实际实现 | 是否属于质量评分/修订 |
| --- | --- | --- |
| 规划产生结构化幻灯片 | LLM 输出 JSON，解析为 `ContentPlan/Section`；包含标题、正文、图表引用与 metadata | 否。没有分项得分、权重、总分或评价报告 |
| 规划解析失败 | 上游返回最小 fallback sections；工作台覆写为抛错，且拒绝空正文 | 格式与非空校验；没有内容评审 |
| 图像生成最多重试3次 | 处理接口异常、缺少返回图像等失败 | 传输/响应重试；没有将低质量图片反馈给模型 |
| iterative single-image generation | 逐页生成；第2页作为后续页的风格参考，可并行生成后续页 | 风格条件传递；不是评审后修订 |
| `--from-stage` 和检查点复用 | 用户或调用者明确选择从某阶段重新执行 | 手动/程序化重跑；没有按得分自动选择修订 |

对应源码：[ContentPlanner](D:/Development/research-workbench/vendor/paper2slides/generator/content_planner.py) 第79、111行起；[ImageGenerator](D:/Development/research-workbench/vendor/paper2slides/generator/image_generator.py) 第180、432、535行附近。官方树本轮共120项，未出现 evaluator/scorer/critic/quality/refine 命名模块；结合实际流水线与生成器代码，未发现内建评分维度、评分尺度、加权聚合、质量阈值、评分驱动修订回路或逐轮得分持久化。

### 3.1 同名/派生项目 paper2ppt：已核对其实际评分源码

用户所说的“类似 paper2slides 的评分”也可能泛指独立派生项目 [celestial-micha/paper2ppt](https://github.com/celestial-micha/paper2ppt)。其 Python 包仍叫 `paper2slides`，容易混淆。**它与当前集成的 HKUDS/Paper2Slides 是不同实现。** 本轮核对到它的 `main` 固定提交 `fc8a91495346d29dfb72df35fbefb5832d6d99e6`，时间 `2026-07-02T14:42:16Z`；以下结论来自该提交源码，不仅来自 README，也不表示本地已安装或本轮运行过它。[固定提交](https://github.com/celestial-micha/paper2ppt/tree/fc8a91495346d29dfb72df35fbefb5832d6d99e6)。

该项目有三套需要区分的机制：生成阶段的布尔 QA 与局部修订、非视觉审计的严重度罚分、DeckIR 通用 scorecard。它们不是一套共同的“LLM给分后自动重做”协议。

### 3.2 生成阶段：确定性 QA → 局部压缩修订

`text_pptx_workflow._render_node()` 渲染原生 PPTX 后调用 `inspect_pptx_layout()` 与 `evaluate_presentation_spec()`，生成 `layout_qa.json`。这一步不读取 universal scorecard 总分，也不调用 LLM 进行打分。[text_pptx_workflow.py，第396行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/generator/text_pptx_workflow.py#L396)。

检查覆盖空页/空标题/空表/空组件、无意义占位、截断省略号、布局类型与图表不匹配、point 的 claim/detail/evidence 是否填写、metric 的标签/数值、PPTX 对象边界与文本容量风险。**实现并非语义事实核验**，例如 evidence 只查非空；缺 evidence 会记录 warning，但 `_is_severe_warning()` 没有 `missing evidence`，因此它本身不会使 `passed=false`。同样，claim/detail 相同、metric 看起来非数值等告警未必触发阻断。严重性由告警字符串是否含固定 marker 决定。[pptx_qa.py，第32、80、123、203行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/generator/pptx_qa.py#L80)。

`qa_passed=false` 且修订次数小于 `PPTX_QA_MAX_REPAIR_ATTEMPTS` 才进入 `_qa_repair_node()`，默认上限2次；通过或达到上限都会转到讲稿生成，**达到上限并不保证 QA 已通过**。修订只处理 `failed_slides`（或从告警解析出的页码），按固定规则压缩标题/takeaway、限制 point/metric 数量、压缩表格/图注并规范布局，再渲染复评。此处没有重新请求 LLM 按评价重写；实际修改有截取条目和图块的行为，不能直接照搬到要求完整保留科研证据的阶段。[同工作流，第431–501行](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/generator/text_pptx_workflow.py#L431)。

### 3.3 非视觉审计：七类问题的严重度罚分

`inspect_pptx_nonvisual()` 直接读取 PPTX 元数据，检查对象/容器边界、估算文字容量、字体、图表适配、重叠、对齐与样式规则；结果明确标记 `rendering_used=false`、`vision_model_used=false`。规则包含 `global/style_aware`、适用 style_scope、repair_mode、confidence 等元数据，因此部分规则只适用于特定冻结样式。[nonvisual_audit.py，第178行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/nonvisual_audit.py#L178)。

它的七个维度是 content、evidence、layout、typography、component_fit、style、repair_risk。`_summarize_findings()` 按维度累加罚分：high=12、medium=6、low=2，维度得分为 `max(0, 100−该维度罚分之和)`。这是缺陷计数模型，不是学习得到或经实测标定的质量概率；相同缺陷率的大型稿件也可能因总缺陷更多得分更低。[同文件，第1962行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/nonvisual_audit.py#L1962)。

### 3.4 通用 scorecard：九维、0–100、等权平均

`pptx_intake.write_pptx_intake_bundle()` 将可编辑 PPTX 转成 DeckIR，可附加非视觉 audit、repair log，以及 summary/plan/spec 检查点对齐；保存 `deck_ir.json`、`universal_scorecard.v0.json` 和可选的 audit/alignment/repair snapshot。它可接收外部生成的原生 PPTX，适合作为独立评审入口。[pptx_intake.py，第101行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/universal/pptx_intake.py#L101)。

`deck_ir.score_deck_ir_v0()` 的真实单项计算如下。所有数值分最终夹到0–100并保留1位小数；confidence 为实现中的固定/条件常量，并非校准后的可靠性测量。[deck_ir.py，第140–524行](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/universal/deck_ir.py#L140)。

| 维度 | 真实评分信号/计算概要 | 主要限制 |
| --- | --- | --- |
| editability | 从100起，栅格面积最多扣55；原生文字最多加15、原生对象比例最多加10；有图片但原生文字少于250字符再扣20 | 衡量可编辑信号，不判断科学内容 |
| content_fidelity | 有检查点：`20+32×关键词覆盖+30×标题覆盖+18×章节覆盖`；无检查点：42起，按词量/证据页/metric页加分，上限72 | 实现明确未做 claim 级语义匹配；无来源也会产生代理分 |
| narrative_structure | 35起；六类页面角色覆盖最多加45，未知角色/角色过度重复扣分，封面/结尾分别加8/7 | 推断角色和节奏，不核验真实论证链 |
| evidence_grounding | 38起；图片/表/类数值文字密度最多加32，图注最多加18，类似来源文字加8；有检查点时取当前分与引用覆盖公式较大者 | 有“证据对象”不等于论断获支持；取 max 可能让结构代理分盖过低覆盖 |
| layout_geometry | 82起；安全区违规最多扣32；平均占用率<0.18扣15，>0.92扣20；audit 的layout问题数最多扣45 | 元数据/估算，不是实际渲染视觉验收 |
| typography | 无audit为null；有audit从100起，按typography问题、低字号、估算溢出分别限额扣分 | 依赖规则覆盖，不证明实渲染可读 |
| visual_design | 45起，奖励角色/布局签名多样性、字体数2–6、颜色数3–12，惩罚过多字体/颜色和style问题 | 代码明确是启发式代理；status虽写human_calibrated，本次并未证明对当前产物完成人工校准 |
| repairability | 无log为null；少于2轮固定50；否则从48起按total/high/medium问题减少加分；停滞扣14 | 衡量告警变化；减少告警可能由删减内容造成，需要额外完整性检查 |
| human_preference | 始终null，状态pending_human_feedback | 刻意不从机器信号推断人的偏好 |

总分是所有**非null机器维度的算术平均**，没有额外权重；human_preference 不参加。每项有 score/confidence/status/signals/notes。缺失 typography 或 repairability 时平均维度数会改变，所以不同输入证据范围的总分不能直接当作同等充分的评分比较。`_scorecard_findings()` 将单项<45标high、45–<65标medium；这不是“overall达到某阈值就自动通过”。[deck_ir.py，第169–202、539行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/universal/deck_ir.py#L169)。

检查点对齐的 phrase coverage 只需原短语直接出现在整套PPT文本中，或非停用词 token 重合比例≥0.42。它不要求证据出现在正确页面，也不识别否定、数值条件或因果方向，因此不能把 content_fidelity/evidence_grounding 分数解释为研究正确性已验证。[content_alignment.py，第56、234行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/universal/content_alignment.py#L234)。

### 3.5 阈值与停止条件属于不同使用场景

**种子模板 gate：** `evaluate_template_gate()` 默认要求 editability≥90、typography≥60、layout_geometry≥50、visual_design代理≥65、evidence_grounding代理≥55，栅格面积比例≤0.08；还要求必要角色和至少6种layout signature。content_fidelity<70只给warn，因为这是probe；human preference待评也只给warn；数值维度缺分时同样warn。无fail但有warn返回 `pass_with_warnings`。这些是模板试验阈值，不能直接拿来决定科研阶段是否通过。[template_gate.py](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/seed_pipeline/template_gate.py#L8)。

**六路风格试验的有限迭代：** 默认max_iterations=3、patience=2、top_k_repairs=3；最少执行 `min(2,max_iterations)` 轮。停止判断依次检查无high/medium问题、出现repair_risk、连续无改善达到patience、轮数上限。其blocking score是 `100×high+20×medium+low`，越低越好，与九维总分不是一回事。[sixway.py，第54、346、1162行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/sixway.py#L1162)。

这里还存在实现边界：`_materialize_proposal_route()` 先按iteration/repair_mode渲染，之后才从上一轮findings生成top-k“planned repairs”文字写入日志；`_render_proposal_pptx()` 并不接收这些findings或动作。渲染器主要按“首轮/后续轮”切换预设字号、词数、框高等。因此源码证明了审计与停止闭环，但该路线的日志不能证明实际执行了逐条top-k诊断驱动修订。结束时复制的是最后一轮产物，并未按best_score恢复最佳轮次。[sixway.py，第356–405、487、629行起](https://github.com/celestial-micha/paper2ppt/blob/fc8a91495346d29dfb72df35fbefb5832d6d99e6/paper2slides/benchmark/sixway.py#L356)。

### 3.6 可借鉴与本轮未测范围

可复用的设计思想是“统一产物表示→可定位问题与检查→分项得分及证据范围→受影响对象修订→逐轮记录与停止原因”，以及将pending human、partial、needs_checkpoint等状态显式保存。应改进其薄弱处：专业正确性需要真实证据检查，缺失关键依据应阻断相应判断；分数聚合应显示覆盖率；修订动作要真正绑定问题与变更，且验证没有丢失原有证据。

本轮未安装该项目、未执行其scorecard/benchmark、未验证其模型调用/修订成功率，也未逐条审查2573行非视觉规则的数值精度。已确认的是指定提交的接口、公式、分支和停止逻辑；未确认的是分数与人类判断/科研质量的相关性，以及迁移到当前工作台数据后的有效性。不能将已有源码当作评分效果已获证明。

## 4. 工作台当前真正已有的检查与阶段接口

### 4.1 PPT 路径与硬校验

当前路径为：确认模板/受众 → 读取真实模板 → `ContentPlanner.plan()` → `slides/plan.json` → `make_deck()` → LibreOffice 转 PDF → `verify_rendered()` → 成功后替换当前导出并写 `slides/verification.json`。[server/app.py](D:/Development/research-workbench/server/app.py) 第1038、1228、1284行起。

`layout_sections()` 会估算文字容量、限制标题为两行、验证 Figure/Table 引用存在、按图表或正文容量拆页；过宽表格会要求先选择关键列。正文通常限制为20–24pt，标题28–40pt。该过程保留正文和引用，不是对叙事、证据充分性或美学进行评分。[server/slide_quality.py](D:/Development/research-workbench/server/slide_quality.py) 第34行起。

`verify_rendered()` 实际检查 PDF 页数、预期文字是否出现在文本层、文字是否出界、文字行重叠、正文与非装饰图片的重叠。失败则抛出具体页码问题；成功返回 `complete_visible_text/page_bounds/text_line_overlap/content_text_image_overlap` 等布尔结果。[同文件](D:/Development/research-workbench/server/slide_quality.py) 第74行起。

这些检查有实用价值，也有明确边界：文字层完整不代表语义正确，几何不重叠不代表图表易读或视觉层次良好；没有检测图片内坐标/图例字号，也没有证明研究论断得到原文支持。`slides/verification.json` 应继续称“渲染/结构验证”，不能直接改名为“质量评分”。

`tests/planner_acceptance.py` 验证实际 planner 与本地 API fixture 的契约、空/无效模型输出的拒绝，明确 `external_model_calls=0`。`tests/presentation_acceptance.py` 使用合成材料验证确认设置、模板来源、拆页、可编辑表格、字号和真实渲染；它们属于功能/输出可靠性测试，不是生成内容质量标定。本轮只阅读了这些脚本，未重跑。[planner 验收源码](D:/Development/research-workbench/tests/planner_acceptance.py)、[presentation 验收源码](D:/Development/research-workbench/tests/presentation_acceptance.py)。

### 4.2 全工作台可复用接口

| 接口/模块 | 当前实际能力 | 对阶段评分的用途与限制 |
| --- | --- | --- |
| `GET .../agent-context?task=...`；`standards.context()` | 当前项目、任务标准、技能原文、当前产物路径、回执协议 | 可复用评审上下文；目前不返回 rubric、评审状态或得分 |
| `Store.job/set_job/jobs`；`GET .../jobs` | 异步 `kind/status/stage/result/error`；result 可存结构化 JSON | 可承载评审任务；`stage` 当前是展示文案，缺少稳定 stage_id/阶段产物契约，不能靠文案识别科研阶段 |
| `manuscript/main.json` | 可编辑结构、递增 revision、翻译源版本与 stale 状态 | 能将稿件评审绑定版本；输入改变应使旧评审过期 |
| `slides/plan.json` | section id、文字、图表引用及确认设置 | 可以按稳定页 ID 定位修改；当前 PUT 只验证 sections 为 list，并没有独立 revision/CAS，评分若直接覆盖或只绑定标题不可靠 |
| 文件读写与 `expected_modified` | 当前项目文件、修改时间、可恢复替换与历史差异 | 可绑定程序/报告等产物版本，利用现有冲突检测 |
| `annotations` + `locator` | paper/literature/code/slides/image 区域；引用、页码/对象/原文定位；open/submitted/resolved/deleted | 可将评审意见定位到具体对象；目前是问题记录，没有分项分数和 stage 输出实体 |
| `POST .../agent-receipt` | 检查问题属于本项目，产物路径存在；记录 question_ids/artifacts/validation/limitations，可据调用参数标记 resolved | 可复用交付关联；服务器不重新执行 validation，不能据 `recorded=true` 认定评审结论已被独立验证 |
| `review_events` + `GET .../review-history` | 不可变新增事件与当前批注，接口返回最近300条事件 | 可先用事件关联评审记录；若需完整逐轮记录，应使用独立评审文件/索引，不依赖最近300条窗口 |
| `models.complete(..., structured=True, task=...)` | 已配置 API 或账户原生模型，统一输出标准；可要求 JSON | 可复用评审模型传输；目前没有 evaluator 协议，亦不验证分数范围/证据定位/聚合一致性 |
| MCP `workbench_review(action='receipt')`、`workbench_jobs` | 暴露相同回执与任务状态 | 可先不增加 MCP 工具种类；但严格结构、评分读取和运行控制最终应有明确参数/操作 |

实现来源：[standards.py](D:/Development/research-workbench/server/standards.py)、[storage.py](D:/Development/research-workbench/server/storage.py)、[annotations.py](D:/Development/research-workbench/server/annotations.py)、[models.py](D:/Development/research-workbench/server/models.py)、[app.py](D:/Development/research-workbench/server/app.py)、[MCP 参数文档](D:/Development/research-workbench/mcp-package/TOOL_REFERENCE.md)。

### 4.3 Dify 检查不等于质量评审

当前11节点图读取项目和规则，核对账户/规则原文/版本，写入或登记真实产物，回读，再核对本次回执与原生历史的项目、所有者、时间、产物和 validation 相等。`workflow_receipt` 还区分产物已保存与 Dify 终态是否成功、历史是否核验。它解决“确实保存到当前项目并且有真实处理记录”的问题。[configure_workflow.py](D:/Development/research-workbench/integrations/dify-bridge/configure_workflow.py)、[delivery.py](D:/Development/research-workbench/integrations/dify-bridge/delivery.py)。

交付桥接将额外 validation 标为 `reported_by='agent'`；回读校验和历史匹配不能证明这些声明对应的科学计算或内容评价正确。源码中没有阶段 rubric、维度打分、加权总分或低分回修节点。应保留现有完整性核验，在其旁边新增内容质量评审。

## 5. 最小接入方案（以下为新增建议，非现有能力）

### 5.1 评审对象与触发位置

每个阶段先声明其**真实输出、用途、输入来源和完成标准**，输出成功保存后建立一个评审对象。建议至少记录 `project_id/stage_id/artifact_refs/input_refs/rubric_id/rubric_version/evaluator/review_status/created`。产物引用携带稿件 revision、文件 modified 或明确的快照标识；PPT 页意见另带 section id。没有产物或模型不可用时记为 `not_reviewed/evaluation_failed`，不填默认高分，也不把整个科研阶段标记为已通过质量评审。

建议采用以下最小阶段评审合同；它适用于确定性评审、模型判断或人工复核，不将三者的证据强度混为一谈。字段为新增设计，当前API尚未实现。

| 字段组 | 最小内容 | 用途 |
| --- | --- | --- |
| 标识与链路 | `schema_version, review_id, project_id, stage_id, stage_run_id, parent_review_id, round` | 区分阶段/执行/复评，并串联逐轮变化 |
| 本轮任务 | `question, intended_use, claim_scope` | 评分只针对承诺回答的问题及用途 |
| 版本绑定 | `artifacts[{path,revision或modified,locator}], input_refs[...]` | 定位真实输出与原始证据，检测过期 |
| 规则版本 | `rubric{id,version,dimensions,weights,gates}` | 复评与跨模型比较有共同标准 |
| 评审来源 | `evaluator{kind,model或tool,version}, created` | 区分deterministic/model/human，避免保存密钥 |
| 实际检查 | `checks[{id,status,measurement,evidence_ref,performed_by}]` | 保存硬检查与原始测量；未执行明确not_run |
| 分项判断 | `dimensions[{id,score或null,max,confidence,status,reason,evidence_refs}]` | 数字可解释且可回查，缺证不自动补分 |
| 定位问题 | `issues[{id,severity,artifact_ref,locator,reason,requested_change}]` | 真正驱动后续修改，定位到句段/页/对象/文件 |
| 服务端聚合 | `overall, scored_dimensions, missing_dimensions, decision` | 明确聚合范围与通过/需修订/缺证/评审失败 |
| 修订交接 | `revision_request{issue_ids,changes_required}, stop_reason, limitations` | 负责产物的执行器返回实际变更、检查和剩余项 |

`confidence` 应说明来源；初版如没有校准，不要展示成统计置信概率。服务端计算分数和决策，模型只提交带证据的分项建议。复评对照同一rubric的新产物版本，同时记录受影响的检查，避免仅修改分数或仅增加日志。

最小代码接入面可限制为新 `server/stage_reviews.py`、少量 app 路由/任务钩子和前端评审显示，复用 Store、当前模型传输与历史；不改 vendor。先在 `slides-plan`、`slides-export` 和 Dify 产物提交三个有明确输出的节点挂接，再把同一接口用于文献综述、方法方案、仿真结果和稿件。这里的“阶段”应对应产物交付节点，避免给下载重试、排版进度或每个 HTTP 请求评分。

### 5.2 评分维度与聚合

通用骨架可用0–5分，每个 rubric 给出具体的1/3/5分锚点；`null` 表示证据不足或不适用，必须附原因。每项得分需要 `reason + evidence_refs + issues + suggested_changes`，不能只返回一个总分。下表是待校准的起始方案，权重不是从 Paper2Slides 复制而来。

| 维度 | 起始权重 | 应评什么 |
| --- | --- | --- |
| 对阶段问题的回答程度 | 25% | 是否交付本阶段应回答的问题，是否遗漏关键条件 |
| 证据与来源对应 | 25% | 论断是否有真实来源/数据支撑，是否保留可回读定位 |
| 专业正确性与论断边界 | 25% | 原理、方程、数值、单位、适用范围与不确定性是否表达正确 |
| 组织与可读性 | 15% | 推理联系、表述、图表与对象布局是否支持读者理解 |
| 后续可用性 | 10% | 输入输出、可复现条件、可编辑性、接口和交接是否足够 |

总分可由服务端按适用维度计算 `100 × sum(w_i × s_i/5) / sum(w_i)`，保留逐项分数、证据覆盖比例与缺证维度。不能把模型自行给出的 overall 直接当作权威总分。关键维度缺少证据时显示“待补证据/无法完成评审”，不只靠其余维度归一化掩盖缺口。

不同阶段应替换具体锚点：文献输出看覆盖、反证和来源范围；方案看机制/实现/可验证性；计算结果看基准、守恒、收敛与适用范围；稿件看论断与证据、论证和表达；PPT 同时看内容叙事与渲染视觉。仿真正确性所需实际检验必须由工具执行，语言模型对报告“看起来合理”的评分不能代替残差或基准证据。

### 5.3 与硬约束分开，并形成有界回路

保留 `hard_checks` 和 `quality_review` 两部分。结构无效、产物缺失、越界丢字、实际执行失败等仍由确定性检查报告；高内容得分不能抵消这些失败。可以先评可读的有效部分以给出修改意见，但最终是否可推进应同时看硬检查、关键质量维度与证据是否足够。未经运行的项目仅评价方案/文本，不评价运行性能。

建议流程：

1. 保存本轮阶段产物及版本，运行该阶段已有实际检查。
2. 评审器读取本轮产物、适用标准、原始证据和检查结果，生成结构化分项评审。
3. 服务端验证返回结构、分数范围、引用能否定位，计算总分；展示问题位置和下一次应改什么。
4. 低分/关键问题交回负责产物的执行器，仅修订受影响部分；通过现有写入接口保留旧版与修改原因。
5. 对新版本重跑受影响检查和评审，保存 `parent_review_id/round/before/after`。新输入使依赖旧输入的评审过期。
6. 默认最多2轮自动修订；仍有关键问题或改善停滞时交还主控重新判断，显示未解决项，不伪装通过。评审失败也不覆盖当前最近一次成功交付。

初版可将完整 JSON 保存于 `.workbench/stage-reviews/<review_id>.json` 并在 `review_events` 记录 `stage.reviewed` 索引，任务 result 返回 review_id/path。**当前 agent-receipt 只拣选四个已知字段，不会保存任意新增顶层 score 字段**；实现时应明确扩展协议或将评审文件作为实际产物/validation 的证据引用，不能只给调用参数偷偷增加 score。

## 6. 有界验收建议

首轮实施至少用以下几类不同状态验证真实行为，而不需要立即进行大规模模型评测：

- 有效产物得到分项评分、证据定位与服务端一致总分；界面能读到对应版本。
- 硬检查失败且评分很高时仍显示不可推进；缺证维度不会被默认满分填补。
- 修改稿件/文件后旧评审标为过期，不能用于新版本自动通过。
- 低分只修受影响对象，并保存前后版本、分项变化与剩余问题；达到轮数上限停止自动回修。
- 评审模型失败、返回无法解析、引用不存在或分数越界时，保留当前产物并明确评审未完成。
- Dify 流程成功、保存回读成功、模型评审通过三个状态分别保留，回执不把 agent 自报检验升级为独立实验证据。

这能实现用户所要的阶段评分和修订过程，同时保留当前工作台已有的真实产物、可恢复修改和硬验证能力。
