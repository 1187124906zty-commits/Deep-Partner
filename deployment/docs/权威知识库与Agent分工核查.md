# 权威知识库、Skill 与 Agent 的分工核查

日期：2026-11-02。范围：现有研究工作台源码、服务器实际配置、本地写作教材及已有页段提取。没有修改生产配置、替换私人模板或批量上传教材。

用户的分层认识成立：系统性领域知识和明确约束需要有稳定来源，skill 负责按任务选择和调用，模型与工具执行并审查。需要补充的是，Agent 是将模型、工具、任务状态、权限、记忆与反馈组织成执行循环的系统；LLM 是其中负责理解与判断的模型。确定条件可以由程序执行，语义和视觉问题需要模型结合材料判断。生成完成、自查通过和成果验收分别记录。

## 实际已有的工作台基础

服务器 `/srv/research-workbench/source` 中的现用 PPT catalog 版本为 `2026-11-01`，与本地对应目录一致：

- 视觉模板：Beamer Default、Beamer Madrid、Metropolis，均记录来源与适配身份。
- 用途配置：组会讨论、学术报告、项目汇报、开题报告、学位论文答辩、文献研读。
- 公共模板的当前布局默认：16:9、13.333333 × 7.5 in、0.7 in 边距；标题32 pt、封面38 pt、正文24 pt、最低正文20 pt、图注14 pt、行距1.18；西文 Arial、中文微软雅黑；标题最多两行、每页最多一个完整图表。

以上是当前产品默认与适配配置，不是所有用户模板、汇报或期刊的通用硬要求。

对应本地文件：

- `D:/Development/research-workbench/templates/presentations/catalog.json`
- `D:/Development/research-workbench/server/presentation_catalog.py`
- `D:/Development/research-workbench/server/slides.py`
- `D:/Development/research-workbench/server/slide_quality.py`

工作台还已有 `server/standards.py`：以 `vendor/workbench-skills/OUTPUT_STANDARD.md` 提供产品规范，按 code/paper/slides 等任务路由技能，把规范材料放入项目 `.workbench/standards`，并通过 context 与回执关联产物。现有 corpus rulebook 也要求保留连续上下文、实际审读范围与候选状态。

这些是可以整合的真实基础。MCP 的研究与语料工具未提供 PPT 风格配置读取，因此本轮补充检查了源码，并通过已有 SSH 对服务器实际配置做只读核对。没有把 MCP 返回的项目清单解释为用户已选定某个项目。

## 目前还存在的具体缝隙

1. **默认值与私人模板可能冲突。** `slide_quality.py::layout_sections` 对标题使用28–40 pt、正文20–24 pt的 clamp；`presentation_catalog.py::generation_context` 也直接写入正文20–24 pt等指令。它们适合作为当前公共模板策略，严格私人模板任务需要以实际模板条件决定，并明确可调整项。这是代码检查所得，不是已执行所有私人模板的结论。
2. **解析中的回退与源事实需要分开。** `slides.py::shape_info` 在未读到显式字体时回退到 Times New Roman/微软雅黑，且 palette 从 theme1.xml 读取。必须进一步处理主题/母版/版式继承、多主题与局部覆盖；回退值不能表示已从原件读出该字体。
3. **已有渲染检查的覆盖有限。** `verify_rendered` 检查页数、文本是否出现、越界和部分重叠。它没有独立证明所有字体、主题、母版对象与原件一致，也不证明内容完整或科学结论成立。
4. **稿件有真实模板与排版检查，仍需规则目录统一。** 当前服务器登记10项稿件版式，含通用版式、用户原生 Word、官方 Word 与 LaTeX到Word适配。模板 provenance 已保存原件来源和部分排版事实；期刊预览使用实际类文件，缺字时拒绝发布预览。全面稿件验收还需覆盖当前适用的样式、字体、引文、图表、参考文献、公式与页布局，不能把编译成功当成全部合规。

## 实际找到的写作教材

| 原件 | 已确认身份与用途 | 本轮实际阅读范围 |
|---|---|---|
| `C:/Users/DEVELOPER/Downloads/2nd-科研写作-Science research writing for non-native speakers of English.pdf` | Hilary Glasman-Deal，Science Research Writing，第2版；本机PDF385页。可用于章节功能、语言选择、因果方向与主张确定程度 | 复用现有提取，读PDF213、214、295、296、318；原页渲染核对PDF213（印刷184页） |
| `D:/BaiduNetdiskDownload/PFC2D/Academic Writing for Graduate Students Essential Tasks and Skills.pdf` | John M. Swales、Christine B. Feak，Academic Writing for Graduate Students，第3版，2012；本机PDF430页。可用于信息流、数据评论、主张限定与修辞任务 | 读PDF41、42、171、172；原页渲染核对PDF42（印刷32页） |
| `D:/WECHAT/xwechat_files/wxid_bybr0emq5bzg22_ef18/msg/file/2026-10/Academic_Writing_with_Corpora.pdf` | Tatyana Karpenko-Seccombe，Academic Writing with Corpora，第2版，2025；本机PDF227页。可用于搭配、KWIC语境、义项及领域用语 | 读PDF88–93；原页渲染核对PDF93（印刷70页） |

现有提取位于 `D:/Development/skill开发/writing-framework-rebuild-20261014/sources/{srw2,awg3,corpora2}/`。本轮原件页数与其 metadata 一致；Science Research Writing 有原提取的字形恢复说明，因此同时核对了原页。没有重新全文审读三本书。

`Academic Writing with Corpora` 的本轮页段展示同一词 cell 在不同领域的不同义项，并用语料比较 adapt/adopt。`Science Research Writing` 区分因果方向、关联措辞与确定程度。`Academic Writing for Graduate Students` 说明信息承接，并给出被动结构适合当前上下文的例子。这些材料适合成为带条件与案例的表达知识，不能转成统一词语替换、句长上限或一律主动语态的制度。

原件与渲染核查记录：`reports/authority-source-checks/book-checks.json`。已有 academic-writing-guide 来源说明已使用前两本；工作台 writing guide 也已有术语义项、语料上下文和确定程度指导，值得复用。

## 权威如何建立

权威来自明确的适用范围、来源、版本和确认状态，而不是“放进知识库”这个动作。建议统一管理、分别取用下列材料：

| 内容 | 条目应保留什么 | 如何使用 |
|---|---|---|
| 用户/项目明确模板与要求 | 归属、模板版本、对象/样式定位、允许变动、确认状态 | 当前任务逐项执行与检查 |
| 官方期刊或学校规范 | 官网、日期、文章类型、阶段、原条款、有效版本 | 按实际适用条件作为要求 |
| 产品默认配置 | 来源配置、版本、选择条件、覆盖关系 | 未被更具体要求替换时使用 |
| 教材、语料与视觉范例 | 原文定位、连续语境、释义、例外和迁移条件 | 按当前表达任务检索并判断 |
| 模型推断与新提议 | 生成依据、未知、候选状态与验证需求 | 不自动成为正式规则 |

同一系统可以同时保存结构化规则和全文/语料索引。硬约束按任务条件完整枚举，正文例文按语义或关键词检索；不能让一次RAG的top-k是否命中决定哪些强制要求存在。规则选定后形成任务快照，生成和检查使用同一版本。

遇到用户模板、官方要求与默认值冲突时，记录具体冲突，继续无冲突工作，必要时由作者决定目标。书籍与已发表论文的知识保留条件，不能获得覆盖明确用户要求的权限。个人教材和机构材料的访问归属继续由实际账户与授权范围控制。

## 路由与检查怎样执行

以“按用户模板做文献报告”为例：

1. Tutor 恢复报告对象、目的和源材料，绑定所选模板及任务版本。
2. Skill 选择论文读取、模板解析、制作和检查能力，并取得全部适用硬要求。
3. 工具读取母版/版式/主题与文本对象，保留源定位、解析不确定性与回退身份。
4. 模型依据论文组织内容；制作工具输出原生可编辑文件。
5. 程序核对字体声明、尺寸、对象关系、内容存在等可计算条件；渲染与视觉审读检查呈现，语义审读核对图证和主张。
6. 依据实际失败项修订，回传产物版本、规则版本、检查证据与未验证项。

这套职责可以继续由 Tutor 提供文本，Codex/本机 worker/文档工具执行需本机环境的步骤。检查可以使用不同工具和独立模型视角，但不能只凭生成模型自评得到“严格合规”。

## 本轮落地材料与边界

新增 `quality-knowledge/source-registry.json` 与 `rule-seeds.json`，以实际来源建立源索引和规则样例，保留产品默认与教材指导的不同身份；`runtime_enabled=false`，尚未接管生产规范。

更新 `workbench-deliverable-quality/SKILL.md`，让任务优先取得适用规则、模板profile与术语记录，具体数值与义项回到知识目录；skill 保留路由、必要步骤与恢复条件。原四份分支仍解释如何执行，不在其中复制全部书籍细节。

后续接入应扩展现有 standards、模板catalog与corpus rulebook，避免再平行建立一套互相争夺权威的规则系统。最先验证用户模板高于产品默认时是否确实按模板执行，再逐项覆盖手稿格式和术语语境。该文是核查与接入设计，没有宣称上述缺口已经修复。

可核对的书目：[University of Michigan Press第3版页面](https://press.umich.edu/Books/A/Academic-Writing-for-Graduate-Students-3rd-Edition2)。其余两书的本轮内容依据本地原件；出版社页面访问受限，没有将未获取的网页作为正文证据。
