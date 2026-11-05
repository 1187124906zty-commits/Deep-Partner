# DeepPartner 0.4 实际交付

更新：2026-11-02。本文件说明正式实现、实际验收和适用范围。安装程序的最终大小、前端作业号与回执以文末 JSON 为准。

最终前端作业25171485，COMPLETED/0:0，完整类型检查零错误、23项测试通过。实际Tauri/WebView2和网站均已复查通过；最终安装包17,534,916字节，主程序41,405,952字节、独立dp1,769,472字节，实际文件/产品版本0.4.0。总回执为 `reports/unified-product-acceptance.json`。

入口为 [统一研究空间](https://tutor.example.invalid/research/)。桌面使用同一个前端构建，直接内嵌到 Tauri/WebView2 程序；不在线加载网站前端。现有 Tutor 账户、项目、会话、知识库、文件和稿件继续使用原服务。工作台与 Dify bridge 的发布没有重启原生 Tutor 服务。

## 现在的使用过程

侧栏选择项目和会话。中央在“对话”“成果”之间切换，宽屏可并排查看。成果区包含文献、程序、论文、PPT、修改记录与历史恢复。对话提出任务、显示流式回复和可展开执行活动；成果区用于查看、编辑、批注和回送问题。

论文“问 Agent”、普通批注及图形反馈进入当前项目的原生会话。图形请求携带实际截图、选中对象、当前未保存样式和版本；后端验证编辑会话和 revision。批注保存实际 session、turn 和 operation 身份，不再为嵌入视图维护另一份审查聊天。自动附带的材料与规则可以展开查看，原始会话和复制内容保留。

普通设置保留外观、界面语言、输出语言、账户和本机工具。模型与服务管理保留在已有管理员入口。中小学课程、练习和掌握路径不进入研究产品导航；通用研究阅读、提问、检索、可视化、技能和连接器仍能按任务使用。评分配置入口在嵌入视图收起，阶段评分仍由服务端工作流和工具执行。

视觉直接复用生产 DeepTutor 1.7 的 ChatWorkspace、ChatRuntimeRoot、消息与工具活动、MotionProvider、主题 CSS/Tailwind 和页面自定义。Geist、Lora 及字体许可随前端打包，修复原 Lora 服务器磁盘路径导致的 404。工作台业务处于同一 React 树中，没有 iframe 或第二套应用侧栏。

## 更新边界

| 改动 | 生效方式 | 是否升级桌面前端 |
|---|---|---|
| 已接入 Dify 流程的提示、节点、模型及兼容的内部编排 | 在 Dify 发布；后续调用服务器当前已发布流程 | 通常不需要 |
| Tutor 服务端技能与规则 | 在相应服务部署；新任务读取当前规则 | 协议兼容时不需要 |
| 远程 MCP 实现或工具 schema | 部署工具，并刷新实际使用方的注册/schema 缓存 | 已有通用工具协议兼容时不需要 |
| 本机 Codex/Claude 的技能和 MCP | 由本机 CLI 的实际配置与安装管理 | 不能仅靠 Dify 发布同步 |
| 新界面、破坏事件协议的改动、新本机适配器或 Rust 功能 | 重新构建并手动安装桌面版本 | 需要 |

这里的“联网同步”是发现并调用服务器已发布能力；桌面不下载执行远程前端脚本，也不复制一套 Dify 运行引擎。已开始的任务保留实际运行身份，兼容服务端变更用于新任务。发布者需要维护稳定的输入输出和事件协议。

`/research/api/desktop/manifest` 在启动、恢复联网、窗口恢复焦点和一分钟间隔刷新，提供协议、前端要求、原生能力和规则版本。实际 HTTP 验证包括未登录 401、当前 0.4.0/2.0 兼容、未变化 ETag 返回 304、旧版本提示手动升级。工作流发布版本没有运行时取证时保留 unknown，不把声明当作实时健康证明。不兼容时阻止新 turn/regenerate，已有任务仍可恢复、取消和回复人工问题。

## 本机 CLI 与 dp

桌面“本机任务”真实检测本机 Codex/Claude，指定工作目录后启动任务，显示增量事件、最终状态及取消。任务由独立 worker 执行，窗口关闭后不依赖 WebView 存活。已有任务可重新选择，日志保存在当前 Windows 用户的 `%LOCALAPPDATA%/DeepPartner/jobs`。

`dp.exe` 与主程序放在同一目录，可使用：

```powershell
& 'D:/Development/电脑答疑/deeptutor-desktop/dist/dp.exe' doctor --json
& 'D:/Development/电脑答疑/deeptutor-desktop/dist/dp.exe' task run --engine codex --cwd 'C:/Research' --prompt '检查当前项目' --json
& 'D:/Development/电脑答疑/deeptutor-desktop/dist/dp.exe' task status TASK_ID --json
& 'D:/Development/电脑答疑/deeptutor-desktop/dist/dp.exe' task events TASK_ID --after 0 --jsonl
& 'D:/Development/电脑答疑/deeptutor-desktop/dist/dp.exe' task cancel TASK_ID
```

桌面、dp 与五个 MCP CLI 工具共用一个 JobManager。此次检测到 Codex CLI 0.164.0；真实任务返回 `DEEP_PARTNER_CLI_OK`，有提供方完成事件、退出码 0 和持久 completed 状态。Claude Code 当前未安装，界面明确显示未检测到，没有声称已认证或实跑。

首版使用官方的[Codex非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)与[Claude Code print/结构化输出](https://code.claude.com/docs/en/headless)适配，尚未提供完整终端和 app-server 交互审批窗口。现有个人 SSH 工具桥可显式连接；它使用当前部署所有者的已有配置，不是公网普通用户的通用设备配对与任务领取服务。没有自动登记 SSH 或向其他账户分发本机能力。

## 已完成的实际核对

- 真实网站：项目、会话和五类成果面板均能打开，桌面与 390 px 页面无脚本错误或横向溢出；字体实际加载。
- 真实 Tutor：新界面发送任务，保存真实流式事件与回答；刷新后恢复原会话。论文区反馈返回新的 turn，仍保留同一 session，实际回答和批注身份均可回读。
- 实际桌面 exe：通过 Tauri 的真实 WebView2 调试连接检查内置 UI，登录、项目、本机工具和已有任务可用，页面保持本机地址；远端 Cookie 不进入 WebView 存储。
- 本机偏好：主题和语言由本机文件保存；随机端口改变并重启后深色选择恢复。已有 DPAPI 可信设备恢复原 quick-login 启动流程；新资料目录不创建信任记录，撤销、离线和超时回到正常登录。
- 原生：进程树取消、worker 独立运行、持久状态与日志、提供方语义失败、Origin、Cookie 与 HTTP/WS 合同均有测试。Windows 原生构建在本机执行；共享前端构建在 Slurm 执行。
- 后端：当前账户及工作区会话归属、完成 turn 身份、批注与回执关联、真实 Matplotlib 图形快照和未保存草稿、版本冲突及 manifest 有定向测试；Dify 交付与旧载荷兼容测试通过。

这些证据验证软件链路，不替代用户真实科研任务的数值、文献或排版质量判断。原生下载的代理响应与附件头经过测试，保存对话框已接入；此次没有借助原生界面自动化完成一次人工选择保存路径。安装包已生成，实际运行的是打包后的主程序；没有静默替换用户已有安装目录。

附带的软件核对说明也实际触发了评分。首轮指出简短说明缺少可读原始记录；补入本机提供方完成事件、Dify回执和会话身份后，一轮复评为62.5、核心项2/2/3/3，仍为needs_revision。评审进一步指出部分UI恢复和重复请求的材料仍是摘要/布尔记录，不能独立复核全部断言。本次保留这个结果，没有覆盖为通过，也没有继续为了分数循环改稿。该评分绑定具体核对说明及其输入，不是对安装包功能测试作出的结论。实际Dify保存、文件回读、同会话UI与本机执行的直接回执分别保留。

## 产物与证据

正式安装包：`D:/Development/电脑答疑/deeptutor-desktop/dist/Deep partner Setup.exe`。

主程序与独立 CLI：`D:/Development/电脑答疑/deeptutor-desktop/dist/Deep partner.exe`、同目录 `dp.exe`；使用说明为同目录 `使用说明.txt`。

源框架：[DeepPartner统一产品框架.md](DeepPartner统一产品框架.md)。前端源：[unified-ui/README.md](D:/Development/research-workbench/unified-ui/README.md)。原生源：[desktop/README.md](D:/Development/电脑答疑/deeptutor-desktop/README.md)。

最终回执：`reports/unified-ui-build.json`、`reports/unified-ui-candidate.json`、`reports/unified-ui-published.json`、`reports/unified-stream-live.json`、`reports/completed-native-identity-live.json`、`reports/native-webview-verification.json`、`reports/desktop-manifest-live.json`、`reports/unified-product-release.json`。原生打包元数据为桌面源目录 `verification/native-0.4-artifacts.json`，测试与打包日志在同目录。
