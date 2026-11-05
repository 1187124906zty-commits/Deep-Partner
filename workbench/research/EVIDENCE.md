# 工作台证据与来源

2026-11-02统一产品证据：前端Slurm25171485真实构建、35个共享源文件及导入图零类型错误、23测试。原生15单元与2集成通过；实际Tauri/WebView2与真实Codex CLI分别有运行记录。会话、同会话反馈、完成turn归属、Dify版本保存与回读、manifest认证/ETag/兼容性均有独立JSON。主回执位于 `D:/Development/询问/dify-research-deployment/reports/`：unified-ui-build、unified-ui-published、unified-feedback-live、unified-dify-turn-delivery、unified-delivery-evidence-revision、completed-native-identity-live、native-webview-verification和desktop-manifest-live。前端为本地源码/本地字体打包，未将在线页面变化称为手动前端升级。

本项目为软件工作台交付。两个科学案例用于验证资料、程序、图表、稿件和汇报的连续操作，不代表完成原论文全部训练复现。

ScanSci原生MCP单篇下载1711.10561、批次218277208ce2下载1711.10566、2001.04536、2010.08895、2111.03794、1910.03193，六篇均成功。PDF身份与页数实际核对，Part I和FNO原文已本地离线转换。Burgers方程及初边值依据1711.10561 PDF第5页式(3)；Darcy方程、系数分布和原421×421参考网格依据2010.08895附录A.3.2（PDF第14页）。

PINNs代码固定为maziarraissi/PINNs提交932f50a2d8ef4e80d1456bbae6887a73ff5166ef，MIT。Burgers参考数据256×100、t至0.99，初值与−sin(πx)最大差1.11e-16。FNO相关代码与小型数据固定为neuraloperator/neuraloperator提交a6648eeeb60fe0837f2d7d021517a945a159a0c8，MIT。当前darcy_test_16.pt是50×16×16，其中输入为torch.bool相位编码、目标为float32；未将其恢复为原始物理系数，也不将其等同于完整论文数据。初次绘图对正系数的断言揭示编码差别，已修正为直接展示存储编码。最后成功作业25086197。

官方Word模板：templates/manuscripts/source/provenance.json保存来源URL及格式；CIRP二进制DOC经现有LibreOffice转换为DOCX，保留源文件。审阅版保留原纸张和页边距、应用原字体规范，并明确单栏适配。导出检查发现继承的自动章节编号会重复，已显式关闭模板标题样式的编号并加入验证。Word/PDF公式为真实OfficeMath/公式字体，非截图；审阅Word包含原生ins/del/comments。

PPT源为用户D:/博士工作/组会/2026-9-23-组会-赵天宇.pptx（15页，4:3）。原母版、布局、主题XML保持，真实字体核对见verification/reference-ppt-style.json。两个示例各4页，实际渲染并展示参考数据图；预先整理的内容明确标注，与Paper2Slides模型规划结果区分。

NeoRead源码参考固定提交ccfb94df9f477381daf1a6aee27f77f660daeebe，阅读translation_batch.go、translation.go、selection_translation.go及prompts.go。未发现项目整体许可证，按其逐段对应、上下文、术语/数值/公式保留和仅输出协议的思路独立编写可编辑提示词。当前翻译保留Tiptap结构并检验ID；只替换文本和图片题名，不翻译代码或修改公式。

验证回执：server-acceptance.json（存储、审阅导出、真实渲染、母版）、translation-image-acceptance.json（结构、旧译稿保留、图片索引、WebSocket本机fixture）、translation-http-acceptance.json（OpenAI兼容本机HTTP队列两次调用，其中一次错误返回不覆盖译稿）、http-acceptance.json（实际部署API）、build.json（最终前端9项测试）、example-exports.json、example-knowledge-status.json。外部真实LLM翻译未通过：隔离QA账户没有获分配模型，预检会明确拒绝，不以预置译稿替代这项事实。


## Reader, output standards and figure interactions — 2026-11-01

- Native NeoRead source commit ccfb94df9f477381daf1a6aee27f77f660daeebe, installed web UI 0.9.5. Go 1.26.5 build Slurm 25086952: COMPLETED, 0:0. First compilation failed because compute nodes could not fetch public modules; modules were obtained from the official Go proxy and verified against the committed go.sum for an offline compilation.
- Actual figure capture Slurm 25087097: COMPLETED, 0:0; Matplotlib 3.11.2, reference-data-only scope. Artifacts are registered in each example's .workbench/figures, using the original plotting scripts and data.
- verification/figure-review-acceptance.json: 23 successful checks, including data invariance, PNG/PDF/SVG output, reference updates, stale writes, source-program reuse, multi-row grid layout and relative cell positions surviving regeneration.
- verification/reader-model-acceptance.json: 5 successful checks against a local HTTP fixture, including untouched native multimodal messages, native streaming output, private internal bridge authorization, figure style preview without silent saving and injected output standards. This is protocol evidence, not a real-model quality claim.
- Terra independently inspected the live DeepTutor chat, controls and theme CSS. Whole-workbench tokens match the existing cream/dark/snow/glass contract and deeptutor-theme key. Reading paper surfaces and VS code colors remain specialized. Full UI evidence will be saved after the final browser pass.

- Final native gateway acceptance: 6 checks, including a real POST reparse and the reparsed paper figure resolving to its original registered Matplotlib result. Source-only parser also publishes paper.md required by the native Go reparse and translation pipeline.
- Browser QA: real code split with syntax colors and line numbers; line 11 right-click menu; actual PPT page 3 with page-local annotation rail; manuscript image opens an embedded dock retaining the original PDF context; 2×1 grid and independent guide toggle; cell x offset preview. Screenshots: verification/render/code-reading.png, figure-inline-layout.png, slides-reading.png.

- Final frontend job 25088018: COMPLETED 0:0; TypeScript, 9 Vitest checks and Vite production output all passed.

## Quiet bilingual authoring and citations — 2026-11-01

- `verification/reference-acceptance.json`: 8 checks for stable citation identity, synchronized paragraph/bibliography/translation, old-version recovery, stale replacement rejection, model citation-number consistency and arXiv/year parsing.
- `verification/reference-http-acceptance.json`: 4 checks through an actual local HTTP model fixture for contextual citation proposals and explicit application; no external model call.
- `verification/authoring-export-acceptance.json`: 5 checks on an actual generated DOCX: citation labels, bibliography, 37% image width, right alignment, caption-before-image and editable math.
- `verification/translation-http-acceptance.json`: source -> translation and edited translation -> target both exercise the queued HTTP route; invalid provider output preserves the previous translation. 3 local fixture calls, zero external model calls.
- Browser: source and translated text show temporary red insertions, save clears decoration; saved main.json contains citation nodes but no temporary color metadata. `bilingual-editor-pending.jpg`, `bilingual-editor-after-save.jpg`, `bilingual-editor-saved.jpg` record actual UI. Final workbench reader has zero iframes and uses theme-aware PDF object colors; `adapted-reader-review.jpg`.
- Crossref live DOI query `10.1038/s42256-021-00302-5` returned Learning nonlinear operators via DeepONet based on the universal approximation theorem of operators; candidate metadata are not treated as full-text verification.

Final authoring production build: Slurm 25114340, COMPLETED 0:0; TypeScript, 11 Vitest checks and Vite pass. Static bundle received and installed by scripts/fetch_build.py. `verification/authoring-browser-acceptance.json` records 11 observed UI behaviors in the isolated QA workspace.

## Private moisture import and presentation confirmation — 2026-11-01

- `verification/moisture-import-acceptance.json`:234selected files,54references,16currentoriginalembeddedimagebyte matches,15source links,privateKB attached,noPPTplanorconfirmation.
- Capture Slurm25117043 COMPLETED0:0:Matplotlib3.11.2;15nativefigureobjects;42Python sources compile; no training. Installed plotting entry smoke Slurm25117631 COMPLETED0:0. Remote artifact is `imports/moisture/moisture-workbench.zip`; compute workspace `imports/moisture/workspace`, all under registered remote product root.
- Server `project/docs/runtime-figure-test.json`:15/15objectload+SVGchecks; source values untouched. Real manualadd_axes field figure13 checked3×4inference with unchanged bounds.
- `verification/presentation-acceptance.json`:26checks;all3neutralPPTXtemplates;no modelcall;actual8page synthetic stress decks pertemplate with complete text,bounds and overlap checks;13master/layout/theme parts preserved in Metropolis.
- Trusted-material test7passes:unregisteredbinaryreject,exactproject receipt,original artwork retained,source connection independent of byteequality,no automaticPPT,explicitsave synchronizesmanuscriptandretainsoldimage. Figure regression23passes;citation regression8passes.
- Frontend Slurm25116794 COMPLETED0:0:11Vitest+TypeScript+Vite. Actual owner UI verified35pagePDF,Dito-based sharedcomposer,Agent/notes toptabs and preserved drafts. A real native-model one-sentence Englishtranslation returned correctly; this does not validate full-manuscripttranslation quality.

Final frontend deployment: Slurm 25117967, COMPLETED 0:0, all 11 Vitest checks, TypeScript and Vite passed. The final template selector uses real content-page previews with a fixed header and confirmation footer. Source/translation UI retained; one real native-model sentence answer persisted after navigation and reload.

Source identity clarification: 20261003 is part of the archive directory name, not a frozen version date. The original archive README calls it earlier research material; selected training files include Oct7 and Oct12 revisions. Source extraction now carries 16 actual figure captions and 4 data tables, excluding 16 Word equation-layout tables while retaining all original manuscript content and raw table values.


Formal figure workspace completed2026-11-01. Final build25121599 COMPLETED0:0,16Vitest/TypeScript/Vite. Browser loaded index-U8cj2vl7.js at formal HTTPS origin, no-store and release2026.11.01-studio.15realMoistureplots pass main-cell/selection geometry without changing authored positions; plot13=8cells+4colorbars, insets/twin axes nested, unequal-row layouts preserved.23figure regressions,6shared-typography save/rerun checks and actual3Daxis+Arial resolution pass. RealReact undo loop red2/2 at25120946 then green2/2 at25121282 and full final build. Browser final nudge/undo returned saved state and normal figure switching. Responsive980/600 no page/toolbar/property horizontal overflow; dark/light checked and dark restored. Final actual axes/layout screenshots in verification/render. Tests/demo removed from active author UI/project, original scientific content retained. Heuristic twelve-area before/after review in verification/正式绘图界面复核.md and studio-ui-ratings.json. No manuscriptPPT plan, confirmation or export created.


Account alignment correction2026-11-01: user Edge807973009 was logged into existing task QA accountu_731b4f07a23742f0917ac6eb77df5df4 while the earlier privateMois-Net was inlocal-admin. Earlier real-user-account delivery claim was inaccurate. Both origins already served updated frontend; an inaccessible explicitprojectid silently fell back to a different visible project. Fixed initialProject resolution, added owned-project migration aliases and image deep links. Final build25122785 COMPLETED0:0,21Vitest/TypeScript/Vite. ActualEdge loadedindex-RoWpZHZJ.js, oldid alias canonicalized to05a893386c09449d88366cf6dfdc825f and openedresults/figure14.png directly. Formal materials imported from exact complete trusted server archive (local99MBtransfer failed and incomplete local file removed);54refs,16originalimages,15linkedplots,48resultfiles. NativeKB newly created under current account, last statusprocessing. Local-admin source project archived, source files preserved. CurrentEdge saved with wholefigure style panel open; screenshotverification/render/current-edge-workbench.jpg. New formalURL https://tutor.example.invalid/research/?project=05a893386c09449d88366cf6dfdc825f&area=code&file=results%2Ffigure14.png. Current owner/remote root recorded inmaterial-mapping.json. No model training orPPTgeneration. This correction supersedes prior delivery's account binding.


## 最新验收（覆盖旧的无模型/旧账户限制）— 2026-11-01

正式账户项目05a893386c09449d88366cf6dfdc825f，原稿rev8。前端Slurm25147301 COMPLETED0:0，34项Vitest、TypeScript与Vite通过；浏览器实际index-hp6cCQnR.js，Times New Roman/宋体，正文15.65pt行高，零KaTeX错误。

实际中文PDF16页；英文CAS原生预览20页；中文和英文Word各540个可编辑数学对象与16幅图片。逐式布局检查见`verification/user-issues/native/column-report.json`，其中CAS16个编号公式最小缩放1.0，零缺字符。原稿内容保持。实际PDF字体抽取确认obs/diff/out/ln/tanh和单位为正体，变量索引为斜体，向量为粗斜体。原生DOCX保留明确数学样式，渲染兼容层仅作用于临时文件。

本次重新阅读用户中文模板原文和分节参数；用字节比较确认原始DOC和CAS类/公共sty未改。适配器曾额外添加页眉行、继承正文行高，现已修正。原生几何与段落结构回归、实际PDF页眉/正文间隔检查通过。多行组适配设置在TYPOGRAPHY_PROFILE中明确列出，不包装成原期刊规定。

11种原生类/Word布局实际编译与PDF渲染通过。最终单栏公式、字体基线与数学样式、原生页眉、引用、撤销恢复、配额、图形保存和阅读模型协议检查均在隔离数据上运行；详细范围在final-acceptance中。早期只因只读输出目录失败的测试在可写运行目录重跑通过。

真实PDF英译中128/128段覆盖22页，176个受保护数学标记一致，209份源矢量资源存在；单栏和双栏PDF导出未翻译块0。真实中文PDF单页英译小样保留17个数学标记；修复了原生编辑API将阅读器操作提示词当作待改写正文的问题。该小样不能替代完整中文PDF的全篇译文验收。

真实相关文献第5版返回5篇期刊文献，3篇JCP、1篇CMAME、1篇Physics of Fluids。以在线题录与可用摘要作相关性判断，未经全文的结论不作为已核验事实。独立检索token和可靠IF/分区返回仍缺失；不编造。当前稿件PPT未生成。
