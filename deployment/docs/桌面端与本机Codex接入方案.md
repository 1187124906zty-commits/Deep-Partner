# 桌面端、本机 Codex 与工作流接入方案

核查日期：2026-11-02（北京时间）。本文件记录本地代码核查、只读协议实测与建议。桌面任务运行时和下列 `dp` 命令尚未实现。

建议沿用现有 Deep partner 的 Rust 原生客户端，并增加独立运行的本机任务进程和专属 CLI。服务器中的工作流提交有身份的任务，本机主动领取，调用本地 Codex 或 ScanSci，随后回传事件、文件和来源记录。服务器保存共享项目状态，集群保存已验收的大文件并承担计算。

## 本地工程的实际情况

| 工程 | 已核实的实现 | 建议复用或参考 | 必须补齐的部分 |
|---|---|---|---|
| `D:/Development/电脑答疑/deeptutor-desktop` | 当前 Cargo 使用 egui/eframe 0.37、wgpu 30、Tokio、reqwest、Axum；已有原生登录、会话、资料、工具桥、DPAPI 凭证与安装脚本 | 作为主工程，沿用界面、远程客户端和本机工具实现 | 持久任务队列、Codex 适配、CLI、按用户设备绑定的任务通道、可续传交付 |
| `D:/Development/电脑答疑/superba-source` | Rust workspace；`superba-gui` 使用 egui/eframe；`superba-cli` 提供 `spb`，GUI 也可把子命令交给同一命令引擎 | 参考核心库与多入口共用实现、JSON 输出、退出码、进程识别和凭证存储 | 其会话模块主要服务于 Codex provider 迁移，不能作为研究项目存储直接接入；这里没有发现可直接替代研究任务运行时的现成实现 |
| 当前 `tenant-storage/operator_download_worker.py` | 设备领取下载作业，直接调用原 ScanSci Python 下载入口，验证 PDF，上传集群并回传归属用户 | 作为首个本机能力适配器的基础；保留原 ScanSci 机构会话 | 目前 SSH、集群路径和运行环境有本机运维假设，需要改成受用户配置与授权约束的设备能力 |

`deeptutor-desktop` 中仍存在 `tauri.conf.json`，但当前 Cargo、main.rs 和 README 表明运行界面已是 egui。早先称它是 Tauri 壳不准确。

旧 `src/tunnel.rs` 使用管理员 SSH、远端 `sudo` 登记与固定的 `/srv/deeptutor/data/system/desktop-bridge.sock`。这可供现有个人环境使用，公网多用户版本应改用各账户的设备配对和任务领取接口。注册用户不需要取得服务器 SSH 权限。

## 本轮真实验证

运行了 `ops/probe_local_codex.py`，结果保存在 `reports/local-codex-discovery.json`：

- 本机 Codex CLI：`0.164.0`。
- 实际启动独立 app-server 子进程，以 stdio 完成 `initialize` → `initialized` → `skills/list`。
- 为 `D:/Development/询问` 发现 163 条技能记录，包括禁用记录；发现错误为空。
- CLI 配置中 `scansci-pdf`、`research-workbench` 等 MCP 为启用状态；这项检查只读取配置，没有证明 MCP 当下已连接成功。
- 旧的两个 `scansci-pdf` 技能记录仍为禁用状态；`scansci-sort` 与 `scansci-browser-persistence` 为启用状态。MCP 启用与同名技能启用是两个独立条件，不应自动修改用户现有选择。
- 未创建模型 turn、未下载论文、未修改 CLI 配置。这轮没有验证完整桌面到下载再到交付的闭环。

可复现命令：

```powershell
python -X utf8 ops/probe_local_codex.py --cwd 'D:/Development/询问' --output reports/local-codex-discovery.json
```

## 建议的职责与连接

连接图源文件和预览位于 `figures/desktop-local-agent.mmd` 与同名 Markdown/PNG。

1. Tutor 持有研究任务、问题和阶段判断。Dify 负责可见编排、触发、等待和协调。本机 Codex 接到有范围的子任务，交回证据与产物。
2. 桌面端展示设备、任务、文件、技能与人工操作入口。本机任务进程独立运行，关闭窗口后可继续；退出整个本机进程或休眠时，云端应明确显示设备离线。
3. 本机任务进程主动通过 HTTPS 长轮询领取任务、上报心跳和进度。可以以后再增加 WebSocket，第一版不依赖本机公网端口或用户服务器 SSH 权限。
4. Codex 使用 stdio 接入。专属 CLI 与桌面共用核心库，再通过本机 IPC 连接任务进程，避免两个入口各自启动相同任务。
5. ScanSci 继续管理它自己的专用浏览器与机构会话。需要认证时，桌面展示 `waiting_for_user`，用户在原浏览器完成后继续原任务；不导出浏览器 cookies。
6. 文件经当前归属检查、配额预留和接收回读后进入项目。集群使用现有归档/存储通道或受限传输凭证，普通用户不继承运营者 SSH 私钥。

## 为什么优先 app-server

OpenAI 官方把 app-server 定位为产品深度集成入口，支持会话、事件和交互；本机已验证其 stdio 握手与技能发现。桌面端可使用 `thread/start`、`thread/resume`、`turn/start` 与 `turn/interrupt`，并响应协议中的审批和用户输入请求。应固定已验收的 CLI 版本及协议；官方目前仍将 app-server 命令及 WebSocket transport 标记为 experimental，不能将本次探针当作生产可靠性证明。[官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)

短作业可用 `codex exec --json` 和 `--output-schema`；长会话与人工接续优先共用 app-server。两种路径均应记录真实会话身份，不分析终端自然语言来判断成功。[官方非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)

任务要求指定技能时，先发现技能并校验启用状态，再发送 `$skill-name` 文本及明确的 skill path 输入。技能描述执行方法，MCP/脚本提供实际能力；文件、Python 环境、机构授权和工具连接仍须验证。插件可同时分发技能与 MCP 配置，但产品应展示实际安装与可用状态。[官方技能说明](https://learn.chatgpt.com/docs/build-skills)

## 专属 CLI 的首版接口提议

暂用 `dp` 作为名称。以下都是接口设计，尚未安装或实现。

| 命令 | 用途 |
|---|---|
| `dp doctor --json` | 检查版本、登录、工作目录、所需技能与工具可用状态 |
| `dp device pair` | 将当前本机设备绑定到已登录工作台账户 |
| `dp worker run` | 运行本机任务进程，领取任务、恢复事件与上传记录 |
| `dp task submit --request task.json --json` | 提交受项目与设备权限约束的任务，立即返回任务身份 |
| `dp task status TASK_ID --json` | 查询同一任务 |
| `dp task events TASK_ID --after CURSOR --jsonl` | 按游标读取进度 |
| `dp task cancel TASK_ID` | 取消原任务并核对最终状态 |
| `dp artifact upload --task TASK_ID --path FILE --json` | 向绑定项目上传产物，返回实际接收回执 |

第一版沿用现有 Rust library，增加桌面和控制台两个 binary。共享任务模块中放 Codex、ScanSci 和上传适配器，先不拆成大量 crate。按来源显示执行、下载、传输与验收事件；stdout 输出机器可读结果，诊断信息走 stderr。鉴权令牌由凭证存储提供，不作为命令参数。

Codex 可通过 `dp` 读取任务材料、调用确定的工具动作与交付成果；云端 Tutor/工作流经任务网关把本机子任务交给 Codex。两方向均绑定同一任务身份，子任务不能在不知道父任务的情况下再次提交相同研究目标，避免递归调度。

## 任务与恢复约定

每个任务携带 `command_id`、`parent_run_id`、项目与设备身份、能力、输入版本、技能引用、截止条件；服务端从已认证账户决定 owner。任务进程将逻辑项目映射到已配对账户自己的本机目录，并保存 `task_id` ↔ Codex `thread_id/turn_id` 的关系。

持久化状态可用 `queued → running → waiting_for_user → uploading → verifying → completed`，另有 `failed/cancelled`。长任务先返回受理身份；论文在本机下载完毕还不能标记项目交付完成。

本机 SQLite 放本机磁盘，用于队列、进程身份、事件与待传清单；服务端持久状态保存共享项目事实与已接收成果。Codex 会话是执行记录，不能单独替代项目长期记忆。账户切换须切换设备权限和目录映射；Codex 身份、工作台身份与机构身份分别配置。

重复 command_id 复用原任务，冲突载荷拒绝执行。心跳失联后优先核对原任务与产物，不直接重提模型作业。对于任意模型工具动作，应用级去重不能承诺所有副作用“恰好一次”；下载、上传和成果登记应各自具备可核对的身份与恢复点。

## 第一个完整验收场景

用一个真实用户、一个项目、一台配对设备完成：工作流提交 DOI → 本机领取 → 读取指定技能并调用原 ScanSci → 在需要时等待用户认证 → 验证论文身份与 PDF → 上传指定用户空间/集群 → 回读 → 返回来源、文件和配额回执 → Tutor 继续研究。

同时验证重复提交、关闭桌面窗口、设备离线与重连、上传中断、配额不足、撤销设备和取消任务。检查是否复用原任务、是否交付给正确用户，以及用户等待是否真实可接续。下载链通过后，再沿用同一接口接入代码执行、论文、图表和 PPT。确定的下载和上传动作直接调用已有实现，只有需要理解与判断的步骤才启动 Codex。
