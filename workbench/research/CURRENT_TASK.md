# 当前任务 2026年11月1日

## 最新交付与剩余验证范围

当前用户请求已扩展为：完整整理工作台、Google/WoS 类检索、MCP 打包并注册到指定 Dify、整体 UI 和工作流验证。MCP 正式包已在 `mcp-package/dist/research-workbench-mcp.zip` 生成并独立验收，37 工具、三套环境各 69/69；已同步网站下载。Dify 37 工具注册、11 节点实跑和无效票据拒绝通过。完整 PDF 原生与两条 MCP 路径补测通过。

最新前端构建 25164817 COMPLETED 0:0，40 项 Vitest、TypeScript、Vite，通过并发布 index-bbPS919k.js/index-CLqCOViI.css。手机文献标题隐藏、程序时间列重叠及阅读时元数据挤占已修正。手机正式页面已实看；程序目录最后一轮桌面实看因本机界面工具无法重建会话而待补，不记为全页面视觉验收通过。

继续时读取 `research/STATE.md` 与 `verification/工作台与Dify交付验收.md`。先前排版和示例中的旧版文件/作业状态只作为历史过程，不能覆盖当前通用模板、当前账户及 MCP/Dify 交付状态。本次未修改正式稿科学内容或生成 PPT。

## 下列为任务演进记录

用户最新要求：中文排版参考 `C:/Users/DEVELOPER/Downloads/写作范例.doc`，检查并修正公式。沿用当前工作台及先前15项软件修正；实际当前账户项目为05a893386c09449d88366cf6dfdc825f。

参照已核对：文件为《力学进展》2015年写作范例；单栏，宋体/Times New Roman五号，原生公式对象为Cambria Math，网格行距15.6pt，变量斜体，向量/矩阵黑斜体，说明性下标、函数、单位正体，公式编号在右侧。该文件仅作为本次排版参照，未据其内容将研究稿改为综述。

当前实现：新增chinese-mechanics模板和本地期刊条目，原始DOC保留；导出器保留脚本字母ℛ/𝒥/ℒ等，标准函数和arg min使用正体运算符；Cambria Math的首级上下标比例73%来自实际字体MATH表。单栏为默认，双栏为适配选项。

实际查出的另一个缺陷：正文固定行距会把插图裁成单行。已修复图片段落的自动高度，并使新范例正文按15.6pt最小行高容纳行内数学。测试以真实渲染的蓝色图像面积识别裁切，不能再仅靠图片数量宣布版面成功。

前端Slurm25149416已经COMPLETED0:0，35项Vitest/TypeScript/Vite；新前端index-C4gJWxLy.js及index-DNyL5cCH.css已传到正式网站。后端文件已更新，尚需完成最终渲染、逐页视觉检查，随后重启任务自有research-workbench服务并将当前稿的模板由chinese改为chinese-mechanics。源稿目前revision8，正文未改动。

正在执行的最终服务端检查包括authoring_export_acceptance、native_header_spacing_acceptance、verify_writing_example、该模板缩略图。测试必须设置WORKBENCH_TEST_OUTPUT到可写runtime-home路径。原生公式540个、原始图片16幅；插图完整显示后的中间稿27页，最后增加最小行高后页数以最终报告为准。

本地current-pages和chinese.docx/pdf目前仍是较早的19页检查版，不能交付为最终结果。应用端当前候选文件为manuscript/exports/中文稿-力学进展写作范例.docx及.pdf。最后下载完整新文件后覆盖本地verification/user-issues/native/chinese.docx和chinese.pdf，并逐页检查。

下载通过已授权的Edge工作台原生下载可以完成；SCP大文件下载180秒超时，本机旧QA代理47901已停止。不得导出或重放用户浏览器cookies。已创建检查用Edge标签807973279，真实工作台原标签807973009；二者都在browser3。小型SCP代码上传仍正常。

逐页视觉检查补充：1—16页的公式与图像已经检查，随后发现表2/表3的两层合并表头在PDF中被拆成纵向文字。已定位为Pandoc TableHead只收一行，rowspan跨到TableBody后被丢弃；正在保留全部跨行表头并做实际PDF同一行坐标回归。最终页数与文件仍待这项修复后的最终渲染，不交付前述27页候选版。

## 新增用户反馈与执行范围
中文数学字母应使用新罗马；文献库、记录和引用详情布局重排，模仿Zotero宽字段与完整条目；去掉引用详情下重复的检索框；图片Agent应在画布右侧，不能挤到下方造成大面积空白；相关研究不能回填原文自身或混入旧搜索结果，默认近五年，标实际来源并接入Google Scholar/WoS可配置服务。当前Crossref是实际源，Semantic Scholar Token未配置。用户截图中的1980条目是按当前DOI查找返回的原文，显示在相关研究下面；实际ref33缓存有2021/2013/2001等旧候选，需要时间窗口。正文当前revision9，仅模板选择改变。此前26页Cambria Math文件是已核验排版版本，接下来按用户新要求生成Times字母版本。

## Taste 合并改版进行中
用户在2026-11-01补充用https://www.tasteskill.dev/与frontend-design互补。已安装并读取Taste v2主技能，采用应用界面builder/framed-sheet，保留品牌字体/主题；网站列出的旧redesign子技能在当前上游不存在，未影响主技能使用。本轮新增workbench-design.css统一引用/文献库/历史/图片Agent侧栏；文献库“全部”应包含54题录与2PDF并按attachment去重（原只显示2文件）。引用改dl宽字段，重复DOI查找默认折叠，近期推荐默认近5年并显示实际来源。新增可配置WoS Starter/Scholar SerpApi，当前真实配置仍Crossref，未声称实测授权API。服务端mock9检查通过。Slurm前端25153865运行中。新的TimesNewRoman字母公式导出测试和实际稿件渲染正在服务器运行，等待回执。

## 联网与批量下载扩展
用户新要求：把模板检索、文献搜索/下载、相关研究、期刊IF/分区接口做完整。下载流明确为用户本机ScanSci→已核验research-cluster-xh5→所属用户文件夹；前端点选和全选批量下载，不再依赖手输DOI。须保留前面Taste、引用、记录、字体修复并交付正式网页。当前前端25155955已提交最终布局检查，暂未fetch。

## 通用模板与作者信息
用户要求默认通用预览，需特定期刊再联网查指南/下载模板。力学进展2015范例与当前发表版不符，不能用作默认期刊标准。账户记录单位、邮箱、姓名；预览联网核验相关信息，显示真实作者资料和预览日期，不造卷期/正式出版日期。

## 2026-11-01 13:11 UTC · 当前交付
用户要求系统整理整个工作台、Google/Scholar搜索、MCP工具包与整体UI检查。37个任务工具/92个原操作已按原API执行、实现；开发检查59项通过。独立验证代理mcp_verify_workspace、mcp_verify_authoring运行中，须在模块通过后整合真实stdio、清洁安装与解压交付。包路径mcp-package/dist/research-workbench-mcp.zip。共享client/auth入口已实现，私有QA会话仅外部文件。集群前端25160901 COMPLETED0:0，回传1975239字节包遇到SFTP/SSH慢，当前fetch_build通过SSH300秒超时重传。要部署正式静态文件并浏览器重新加载；旧页面仍是旧布局，不能当新版验收。前面FNO/PINO两份PDF已完成ScanSci→集群→用户库。正式稿件05a893386c09449d88366cf6dfdc825f只读UI；验证项目15289d1656da4c9f8b408609c83cc331(workspace)/4959b9a67b324c0eb69ab9c67ee897cb(authoring)。
