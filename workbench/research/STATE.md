# 当前状态 — 2026-11-02

## DeepPartner 统一研究产品 0.4

网站 `/research/` 与内嵌前端的 Tauri/WebView2 桌面使用统一项目、会话、成果与反馈界面。生产前端源为 `D:/Development/deeptutor-coder-integration/frontend/web`，新共享壳为 `unified-ui/`；原生源为 `D:/Development/电脑答疑/deeptutor-desktop`。集群构建源映射为本项目 `src/unified-ui` 与生产 `frontend/src/web`，Slurm25171485 COMPLETED0:0，完整类型图零错误、23测试通过；最终静态包579文件。Web发布只重启工作台及必要bridge，没有重启Tutor。

原生15单元、2集成测试通过，dp独立worker与GUI共用任务核心；真实Codex0.164.0固定标记任务completed/exit0。实际WebView2启动、登录、远端Cookie不下发、持久任务读取和主题跨重启恢复有回执。Claude当前未安装，完整交互终端与公网通用设备配对未实现，现有个人SSH桥仅显式兼容连接。

真实UI会话 `unified_1793558921161_ab161e33` 已完成流式保存、刷新恢复和同会话论文反馈。真实Dify交付38ebe975c5184ef282ba59d5081d94b7关联反馈turn，工作流succeeded、回读与处理历史匹配、重复请求复用。附加评分指出精简核对回执证据不足，已补原始CLI事件、实际运行与会话身份作一轮定向修订；评分实际终态见独立回执，不作为软件发布成功的替代。

主说明和所有最新JSON回执在 `D:/Development/询问/dify-research-deployment/docs/DeepPartner0.4实际交付.md` 及相邻reports。安装包在原生源dist，版本0.4.0，最终元数据为其verification/native-0.4-artifacts.json。

## 最新：阶段评分与六种PPT用途（2026-11-02）

生产工作台已发布通用13阶段评分和六用途PPT规则。评审默认继承Tutor独立上下文，可单独配置OpenAI兼容接口；核心分项0–4且至少3，关键硬检查独立。评分绑定真实产物、来源与规则版本；PPT计划最多两轮定向修订，研究事实与科学选择交作者。当前私人模板已解析字号优先，回退有明确身份。其他阶段提供反馈与放行协议，独立物理、翻译或图表检查缺失时保留unknown。

145项后端、17项Dify交付桥接、12项MCP HTTP合同及42项前端测试通过。最新Slurm构建25170025完成0:0，正式资源index-BdC9D1Of.js。真实Tutor模型在隔离项目完成4项3/4、展示75、passed的评审；生产网站桌面与390px移动端新会话检查通过，未修改账户接口。更新ZIP39,913字节，37工具数不变，网站下载到新目录后实际quality_rubric/list/gate与context调用通过。原生Tutor未重启，隔离验证容器在确认无活动任务后已停止，证据保留。

三书1042页、451资产、11用途资料均已本地及集群真实存档，14个首选阅读层文件存在且资源引用可解析。首选阅读层进入本作者私人参考项目69c79a679648428aae6d8e06f4006f70（写作与汇报参考资料），原生KB=workspace:ws_1f64985a107540ec841c466019307d8a:kb:writing-presentation-references-20261102。LlamaIndex沿用已有BGE-M3，当前version-5、882节点，14输入逐份字节匹配且同次索引完成。关键词现在直接读取MD/文本源（每份最多2M字符，覆盖和截断明确），实检命中AWG3 word-of-mouth；原生语义检索返回Corpora2 PDF93的cell四义原段。发布MCP包也实检命中，访客401。

本批真实摄取评审首轮未放行，发现关键词预览截断和全来源版本证据不足；JSON证据定位已按RFC6901接通并实际检查存在性。更新证据按新输入链评审，四项均3/4、展示75、passed，review a6e95a56e19e530db0c007bbcf73e780；实时gate通过，旧评审stale保留。评分范围是摄取/追溯/检索，不是全文校订。回执 reports/native-quality-library.json、quality-native-ingestion-review.json、quality-native-ingestion-gate.json。S11选native_html避免MinerU交互正文遗漏；S04/S05原件未取，ALT独立。

本批MinerU三教材1042页和六用途原件按源页保留原始/自动恢复/局部原页补充。纯云样本存在串页与图示漏词，组合样本38关键锚点通过，全文页精度不能据此推断。完整归档目标是已核验集群quality-library/mineru-20261102；实际逐书完成和本地Markdown以任务报告为准。

主说明：D:/Development/询问/dify-research-deployment/docs/阶段评分与知识库实际接入结果.md。回执：该目录reports/quality-release-files.json、quality-production-ui.json、quality-tutor-live.json、quality-mcp-delivery.json。MCP本源回执mcp-package/reports/quality-delivery-validation.json。之前版本的完整37工具验证保留为历史范围，本次只复验新增协议与实际读取链。

## 最新：工作台 MCP、Dify 与整体检查

正式入口仍为 https://tutor.example.invalid/research/?project=05a893386c09449d88366cf6dfdc825f 。37 个任务工具已独立验证并注册到 Dify 应用 5c9d68ae-3847-4774-8e94-ecbfa9543e25。当前交付流程为 11 节点，每次实际调用账户、规则、处理记录三个 MCP 工具，其他工具按任务接入。实跑 ed8235c3-30dd-41c5-9140-22175341c384 全部成功，3.525 秒；文件回读、记录匹配、幂等重试、无效票据拒绝和当前草稿绑定复查通过。原生保存与 Dify 核验分别报告，不能以文件已保存掩盖后续流程失败。

正式包 mcp-package/dist/research-workbench-mcp.zip，38,057 字节。开发、全新、实际 ZIP 解压独立安装三套环境各 69/69，共 207 次调用，37 工具每轮均有成功覆盖。33 个返回文件与独立原生响应完整一致；三轮 3 个材料导入、3 个小稿件翻译 completed，QA 原稿恢复。网站下载与已验收 ZIP 字节一致，complete gate 通过。

Scholar-MCP 已真实安装，MIT，固定提交 c7bc58a730c44ddc6446690ca039b9d7f32d455a；工作台 Google Scholar 检索返回 10 条候选，全选通过。Crossref 保留为明确可选源及题录核验；WoS/JCR 未配置时明确显示。正式项目两个本机 ScanSci→集群验收→用户库任务均 completed。

完整 PDF 补测通过：独立原生、MCP 文献、MCP 阅读器分别在 191.372、232.543、194.060 秒完整取得同一 2,436,198 字节、16 页 PDF，全部字节一致。此前 45 秒窗口超时保留，以 verification/workspace-pdf-full-transfer.json 为补充完成证据。

前端 Slurm 25164817 COMPLETED 0:0，TypeScript、40 项 Vitest、Vite 通过。正式资源 index-bbPS919k.js、index-CLqCOViI.css 已发布，大小与构建相符。手机文献标题隐藏修复已在正式 390 px 页面实看；程序目录五列宽度及阅读时名称导航已修正、构建、发布。最后桌面实看因本机界面会话“系统找不到指定路径”失效未完成，不能记为所有页面所有断点视觉验收通过。

完整逐项结果与限制见 verification/工作台与Dify交付验收.md 。安装包独立回执为 mcp-package/reports/delivery-validation.json，网站回执为 verification/system-delivery-acceptance.json。本次未重写正式研究稿的科学内容、未生成其 PPT、未训练模型。

## 历史阶段记录：以下状态由上面的最新记录补充或替代

正式工作台：https://tutor.example.invalid/research/?project=05a893386c09449d88366cf6dfdc825f

原始用户问题文档的15项修改及验收范围见 `research/USER_ISSUES.md`；固定模板依据与适配边界见 `research/TYPOGRAPHY_PROFILE.md`。当前实际账户已核实，源稿版本8，中文原稿选择用户提供的《西北工业大学学报》模板，英文译稿保留Elsevier CAS适配。原稿科学内容未因本次排版和软件测试改变。

最终前端构建Slurm25147301为COMPLETED 0:0：TypeScript、34项Vitest及Vite通过；正式网页实际载入index-hp6cCQnR.js。正文Times New Roman/宋体、10.5pt，行高15.65pt；数学数组左对齐列10处，右对齐列0处，KaTeX错误0。正式后端使用任务自有容器，未通过部署脚本重启DeepTutor。

本地及正式服务器已保存中文Word、中文PDF、英文可编辑Word、英文CAS原生PDF。中文PDF16页；英文CAS20页；两份Word均保留540个原生OfficeMath对象、16幅图片。16个编号公式在CAS中未触发缩小。中文PDF不存在空公式占位符、替换字或渲染指令残留，公式不跨双栏中缝。

排版修复涵盖正体缩写、粗斜体向量、变量下标、函数和单位、行内基线、单栏内断行、组内行距与编号。页眉复用原有段落，移除额外换行，并保留页眉自己的单倍行距；页边距与页眉距顶端不改。原始DOC、CAS的cls/sty与用户原包一致，适配器与模板源文件分开。

真实PDF英译中已完成22页128段，176个行内数学对象标记全部保留；单栏12页、双栏7页导出未翻译块为0。真实中译英PDF验收范围为单页小样，17个数学对象标记保留；完整中文PDF尚未做全篇英文验收。原稿到英文稿的194段翻译及中英文Word、CAS预览是另一条已完成流程。

相关文献缓存第5版已返回5篇真实期刊文献：JCP3篇、CMAME1篇、Physics of Fluids1篇，按年份排序。理由区分题录/摘要范围；没有编造影响因子或分区。用户独立检索token未提供，当前使用Crossref；IF/分区获取未核验时按实际状态显示。

原PDF与公式矢量、多用户文件归属、2GiB配额、撤销与历史恢复、图形当前编辑上下文、保存后撤销、批注与追溯、统一快捷键均保留。当前稿件没有生成PPT。软件验证不代表新的模型训练、物理结果验证或论文结论审查。

最终回执：`verification/user-issues/final-acceptance.json`。图像：`verification/user-issues/native/chinese-equation-page-4.jpg`及`verification/render/typography-current-edge.png`。正式本地输出文件位于`verification/user-issues/native/`，只交付当前有效版本。
