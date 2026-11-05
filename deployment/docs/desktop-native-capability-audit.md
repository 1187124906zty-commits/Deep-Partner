# 桌面 Rust 能力与共享 Web UI 迁移核查

核查日期：2026-11-02。桌面工程根目录：`D:/Development/电脑答疑/deeptutor-desktop`。只读参考：`D:/Development/电脑答疑/superba-source`。本次仅新建本报告，未修改工程源码、依赖、用户配置或服务端状态，未启动应用、登录生产服务、建立 SSH 隧道或运行安装程序。

## 结论

当前可运行的桌面应用为 **Rust + egui + wgpu/Direct3D 12**，不是 Tauri/WebView。工程中的 `tauri.conf.json`、`ui/`、旧 JS 测试仍在，但没有接入当前 Rust 启动流程。要求严格保持 DeepTutor 的 Claude 主题、字体、组件和动态，应让正式桌面壳运行与 Web 端同源的 UI 构建；继续复刻 egui 页面会持续产生第二套组件及交互实现。

Rust 本机核心可保留：HTTP/登录 Cookie、WebSocket 对话、DPAPI、共享目录、专用浏览器、Windows 截图与输入、本机 MCP、SSH 隧道已有可分离实现。需要补齐的主要是统一应用服务边界、WebView IPC、会话归属、真正的本机 CLI/任务生命周期和多设备连接。当前工程没有 `dp` CLI，也没有本机 Codex/Claude Code 执行适配器。

本机具备 Rust、Node、MSVC、Windows SDK、WebView2 和 NSIS 的基础构建条件；尚未通过正式 Tauri 构建验证。没有发现需要先安装整套开发环境的阻碍。

## 1. 实际启动和构建架构

| 文件/位置 | 已核验事实 | 对正式实现的含义 |
|---|---|---|
| `Cargo.toml:1` | 包 `deep-partner-desktop`，版本 `0.3.0`，Edition 2024；唯一声明的二进制 `deep-partner` 对应 `src/main.rs`；库名 `deeptutor_desktop` | 目前没有独立 CLI 二进制 |
| `Cargo.toml:18` | `eframe=0.37.0`、`egui=0.37.0`、`wgpu=30`、`egui_commonmark`；没有 `tauri`、`tauri-build`、`clap` | 旧 Tauri 配置不参与当前 Rust 构建；库默认也会带入 GUI 依赖 |
| `src/lib.rs:1` | 公布 `browser/cache/config/desktop/native/remote/schema/secure_store/service/transport/tunnel`；`desktop` 未做 feature 隔离 | 核心源码已经分模块，依赖图尚未隔离 |
| `src/main.rs:24` | 加载并保存 Config，创建 DesktopService 和 Tokio runtime；监听 `127.0.0.1:bridge_port`；最后 `eframe::run_native` (`:117`) | 运行时、工具桥、窗口生命周期集中在一个 main；可改成共享 AppState 后接 Tauri |
| `src/main.rs:48` | 本机端口绑定失败时直接跳过 router，不终止且没有报告绑定错误 | 第二实例可能有 UI 却没有自己的 bridge；增加 CLI 前需解决实例归属与连接检测 |
| `src/desktop/mod.rs:48` | `DesktopApp` 同时保存业务状态、RemoteClient、DesktopService、Tunnel、Tokio Handle、mpsc 收发器、egui Context | 关键混合层；不应把整个 DesktopApp 搬进 WebView IPC |
| `src/desktop/mod.rs:106` | `style()` 安装 Geist/Lora 和本机中文回退字体；`theme.rs` 用 Rust Palette 重绘主题；`layout.rs/forms.rs` 绘制组件 | 字体文件与部分色值可参考；不是 DeepTutor 原组件实现，无法据此保证严格 UI 一致 |
| `src/schema.rs:5` | `contract()` 用 `include_str!("../assets/backend-openapi.json")` 编译内嵌合同，`body_schema()` (`:57`) 生成原生业务表单 | 服务端新增合同不会自动进入旧客户端；不能承担服务端发布后实时更新的完整产品边界 |
| `package.json:1` | 无声明的前端依赖；dev=`cargo run`，test=`cargo test --all-targets`，build 调 `scripts/package-native.ps1` | 当前 npm build 不构建网页，不是共享 Web UI 的构建入口 |
| `build.rs:1` | 只用 `winresource` 编译图标/版本资源 | 尚无 `tauri_build::build()` |
| `scripts/package-native.ps1:1` | `cargo build --release`，复制 exe、字体许可，调用 `%LOCALAPPDATA%/tauri/NSIS/makensis.exe` 和 `installer.nsi` | 当前打包链可继续提供手动升级安装包，但迁移后要同步 Web 资产、CLI、依赖和版本 |

`tauri.conf.json` 是 Tauri v2 格式，但版本仍为 `0.1.0`，`frontendDist="ui"`，`app.windows=[]`，`withGlobalTauri=true`，只给名为 `shell` 的 webview `core:default` 权限。CSP 的 `connect-src` 只有 IPC，未包含业务 HTTPS/WSS 端点。`ui/app.js:4` 调用 `window.__TAURI__.core.invoke('desktop_command', {action,payload})`，`:119` 监听 `chat-event`。对现有 Rust 全文检索未找到 `desktop_command`、`#[tauri::command]`、`tauri::Builder` 或事件 emit 的实现；Cargo.lock 也没有 Tauri 包。因此不能只把现有配置打开就恢复正式桌面应用。

旧 `ui/` 为独立 HTML/JS/CSS 界面，有聊天、本机文件、设置等功能，不是当前 DeepTutor 共享组件的证明。`tests/app-flow.test.cjs` 在 JSDOM 中 mock `window.__TAURI__`；其通过也不能证明当前 Rust 与 WebView 已打通。`tests/ui.test.cjs` 同样主要检查旧 UI 的 DOM/脚本文本。

## 2. 可复用 Rust 核心与实际耦合点

下列模块的源码不依赖 egui/eframe，可迁入 core crate，或先通过 Cargo feature 从 GUI 依赖中分离。

| 能力 | 确切函数/位置 | 已有行为与迁移注意 |
|---|---|---|
| 连接与本机配置 | `src/config.rs:7` `Config`；`:42` `data_dir()`；`:53` `load()`；`:80` `validate()`；`:109` `save()`；`:120` `workspace_path()` | 默认服务 `https://tutor.example.invalid`、SSH 别名 `papers-research`、bridge/browser 端口 19388/19389；保存到 `%LOCALAPPDATA%/DeepPartner`，支持 `DEEP_PARTNER_HOME`/旧环境变量；继承旧 DeepTutorDesktop 配置与凭证；规范化路径后限制在共享目录内。load/save 会写目录，核查中未调用。主题和模型选择也在 Config，后续应区分 UI 偏好与本机配置。 |
| HTTP 和登录 | `src/remote.rs:22` `RemoteClient::new()`；`:41` `login()`；`:98` `api()`；`:158` `get()`；`:161` `upload()`；`:212` `download()`；`:229` `bootstrap()` | reqwest 登录；手动维护 `dt_token`、`__Host-dt_pair`、`__Host-dt_trusted` Cookie，内存会话；API 带服务端 Origin，multipart 上传与限定来源下载已实现。Cookie 在 Rust reqwest 内，WebView 不会自动获得同一登录态。 |
| 可信设备凭证 | `src/secure_store.rs:6` `protect()`；`:50` `save()`；`:54` `load()`；`remote.rs:82` `set_trusted()`；`:88` `trusted()` | Windows `CryptProtectData/CryptUnprotectData`，当前 Windows 用户范围，无 UI；用于可撤销 device credential。`bridge-token` 由 `main.rs:8` `token()` 单独生成并以普通文件保存，不能声称所有本机密钥均已 DPAPI 加密。 |
| 对话事件和控制 | `src/remote.rs:8` `EventSink`；`:280` `send()`；`:355` `control()`；`:365` `stream()` | WS `/ws` 协议 2.0，start_turn、reply/cancel 等控制透传、turn_id/seq 去重、resume_from，20 秒 heartbeat，中断后至多 3 次恢复。通过可注入 Arc callback 推事件，不绑定 GUI。单 RemoteClient 仅一个 outgoing 任务，非多任务引擎。`tool_result/thinking` 的字符串内容在发送 sink 前截至 1200 字符，完整 trace 不能从此 sink 重建。 |
| 工具服务 | `src/service.rs:26` `DesktopService`；`:38` `new()`；`:50` `status()`；`:53` `call()`；`:206` `tools()` | 17 个工具，启停 AtomicBool、CPU Semaphore、桌面操作串行 Semaphore、40 条 Activity。已支持文件列表/读取/搜索/写新输出文件、系统打开、浏览器、桌面输入。没有任意 shell/CLI 执行工具。 |
| 本机文件 | `service.rs:103` workspace_list、`:113` workspace_read、`:122` workspace_search、`:148` workspace_write；`config.rs:120` workspace_path；`src/cache.rs:32` TextCache 实现 | 读取/搜索限制共享目录，搜索跳过常见大型目录并设数量/字节上限；输出限定 `Deep partner Outputs`，拒绝覆盖。缓存按文件元数据失效并有字节预算。选目录、导入附件等 UI 流程尚不在独立服务内。 |
| 专用浏览器 | `src/browser.rs:31` `ensure()`；`:135` open、`:157` snapshot、`:168` click、`:177` type_text、`:197` screenshot、`:210` close；`:251` browser_executable | 启动本机 Edge/Chrome，专用 `DeepPartner/browser-profile`，CDP 端口和操作锁；不依赖 egui，也不是 WebView2 本身。保留该能力无须让模型控制产品 WebView。 |
| Windows 桌面 | `src/native.rs:13` screenshot、`:106` desktop_click、`:139` desktop_type、`:164` desktop_key | Win32 截图/输入；非 Windows 返回不支持。`system_info()` (`:5`) 的 rendering 文案写死 egui，迁移后应改为真实运行时信息。 |
| 本机 MCP | `src/transport.rs:12` router；`:32` mcp | Axum `/health`、`/test-page`、`/mcp`；JSON-RPC initialize/ping/tools/list/tools/call；4 MiB body limit、Bearer token，若请求带 Origin 仅允许旧 Tauri origin；GET /mcp=405、DELETE=204。它是工具 RPC，不是 UI 命令总线、通用事件订阅或多用户网关。 |
| SSH 通道 | `src/tunnel.rs:17` new、`:24` status、`:36` connect、`:137` disconnect；`:146` ssh | 启动隐藏 ssh.exe，enroll、反向 Unix socket 转发、activate；进程保活依赖 SSH；关闭时 kill/wait；可直接复用为现有机器的兼容连接适配器。 |

**仍在 egui 层的业务编排，需要提取：**

- `desktop/mod.rs:234` 在启动时 DPAPI load → set_trusted → `/api/quick-login/login`；`:310` `pump()` 处理登录、配对完成、保存 trusted 凭证；`:523` submit_login；`:537` submit_registration；`:766` remember 请求。将这些合并为 `AuthService`/应用服务后才能供 Web UI 和 dp 共用，避免在两种 UI 中各写一次。
- `desktop/mod.rs:246` `job()` 使用 mpsc 后调用 `egui::Context::request_repaint()`；`:1367` chat EventSink 同时发 mpsc 和 repaint。新壳只替换结果和事件适配器，RemoteClient 本身无需改成 Tauri 类型。
- `desktop/mod.rs:274` bootstrap 动态获取 capabilities/skills/personas/MCP/tools；`:927` download 和 `:939` open_artifact 混合系统对话框、远端下载、落盘和默认应用；`:1119/:1195` 选共享目录；`:1328` send_chat 组装业务 payload、附件 base64（单附件 20 MiB）并改 UI 状态。
- `desktop/layout.rs:700` logout_native 同时提交服务端 logout、清 Rust 内存 token、清 UI 状态、断 SSH。应定义一次可调用的会话退出/清理操作；目前 `RemoteClient::logout()` 只移除 `dt_token`，不会删除 DPAPI trusted 凭证。

## 3. dp / 其他 CLI、任务、事件、设备配对

**现有入口：** 只有 `deep-partner.exe`。`main.rs` 识别 `--verify-api`（从 stdin 读账号做接口核查）、`--bridge-only`（起本机 MCP 并永久等待）、`--benchmark-ui`、`--capture`、`--preview-page`。没有 help/子命令参数模型，没有 `dp`，也未发现 Codex 或 Claude Code 的本机进程执行实现。它不是一个现成的可扩充 CLI 引擎。

**“CLI 应用”页面含义：** `desktop/pages.rs:241` 指向 `/api/space/cli-apps/catalog`，说明文字为“管理安装在服务端的命令行工具”。该页面不代表已集成本机 Codex/Claude Code。

**任务和事件：** task-board 页面是服务端业务资源；RemoteClient 提供单次活动 turn 的流和控制。DesktopService Activity 只记录 tool/ok/elapsed_ms，最多 40 条、内存保存。未发现通用的本机 job registry、持久日志、任务 ID/退出码、子进程 stdout/stderr 流、PTY、CLI 会话恢复、共享事件总线。本机多进程 CLI 与窗口共享同一 bridge 也没有单实例发现协议。

**设备配对要区分两条链：**

1. 账户可信设备：已有 trusted cookie 的 DPAPI 保存和 quick-login 接口调用；`desktop/mod.rs:355` 有 pair/status → complete 处理，`:442` 有 tab==2 时每 3 秒 status 轮询。但全桌面源码检索只发现 `auth:pair` 的结果处理，没有发起 pair 的调用；现行 `layout.rs` 登录页是登录/注册两项。故只能确认有部分配对残留与可信设备登录功能，不能认定当前配对流程完整可用。
2. 本机工具通道：`Tunnel::connect()` 向固定 `sudo -n python3 /srv/deeptutor/migration/desktop_bridge_ctl.py enroll` 写 token，然后 `ssh -R /srv/deeptutor/data/system/desktop-bridge.sock:127.0.0.1:<port>`，再 activate。`scripts/desktop_bridge_ctl.py:31` enroll 拒绝已有活跃 socket，写单一 `desktop-bridge-token`，登记单一 `windows-desktop` MCP，还会更新已存在 workspace 的资源选择。`scripts/desktop_bridge_proxy.py:13` 经固定 Unix socket转发 JSON-RPC。它绑定现有 SSH 权限、路径、管理员激活和单连接，未提供按登录用户/device_id 隔离的产品化配对、撤销、在线选择和重连登记。

### superba-source 的有限可复用参考

`D:/Development/电脑答疑/superba-source/crates/superba-cli/Cargo.toml` 定义独立 `spb`，不依赖 GUI；`src/bin/spb.rs:5` 只调用 `superba_cli::main_with_args()`。`src/lib.rs:94` 的 `run(cli, Runtime, Output)` 让命令层只构建请求/输出结果；`superba-core/src/traits.rs:1003` 定义服务接口 `SwitchService`；GUI `crates/superba-gui/src/main.rs:22` 识别 CLI 调用并复用该命令引擎。可借鉴“core 服务 + 窗口适配器 + 独立 headless CLI”分层。它管理 Codex 的配置/启动/切换，是另一个产品；本次未审计其全部实现，也没有证据表明直接嵌入它就能执行 DeepTutor 任务或集成 Claude Code。无需引入整套 Superba GUI。

## 4. 本机必要环境与打包条件

以下为本轮只读命令实测，非旧验证材料推断：

| 条件 | 结果 |
|---|---|
| Cargo / Rust | `cargo 1.99.1`、`rustc 1.99.1`，活动工具链 `stable-x86_64-pc-windows-msvc`；命令位于 `C:/Users/DEVELOPER/.cargo/bin/` |
| Node / npm | Node `v24.14.1`、npm `11.17.0`；`C:/Program Files/nodejs/` |
| MSVC | vswhere 检出 VC.Tools.x86.x64 安装：VS 2022 BuildTools、VS 18 BuildTools、`C:/BuildTools`；检查到 `C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/14.44.35207` |
| Windows SDK | `C:/Program Files (x86)/Windows Kits/10/{Include,Lib}/10.0.26100.0` 存在 |
| WebView2 | EdgeUpdate 注册表记录 Runtime `155.0.4283.45`；`C:/Program Files (x86)/Microsoft/EdgeWebView/Application/155.0.4283.45/msedgewebview2.exe` 存在 |
| NSIS | 当前脚本实际引用的 `C:/Users/DEVELOPER/AppData/Local/tauri/NSIS/makensis.exe` 存在；不在 PATH 不影响此脚本 |
| Tauri | `cargo-tauri.exe` 未在 PATH 找到；本机 Cargo registry 缓存已有 `tauri-2.12.3`、tauri-build、runtime-wry 等包；缓存存在不能替代锁版本/编译/打包验证 |
| OpenSSH | `C:/WINDOWS/System32/OpenSSH/ssh.exe` 在 PATH；本次没有读取私钥、连远端或验证 papers-research 连接 |
| Codex | PATH 有 `C:/Users/DEVELOPER/AppData/Local/Programs/OpenAI/Codex/bin/codex.exe`；未运行其会话/配置命令 |
| Claude Code / dp | PATH 未找到 `claude`/`dp`；目标候选 `~/.local/bin/claude.exe`、`%APPDATA%/npm/claude.cmd`、`%APPDATA%/npm/dp.cmd`、`~/.cargo/bin/dp.exe` 均不存在。此结论限定于 PATH 和这些常见候选，不声称扫描了所有磁盘。 |
| 现有包 | `target/release/deep-partner.exe` 和 `dist/Deep partner.exe` 均 25,137,664 字节；`dist/Deep partner Setup.exe` 6,599,626 字节；打包脚本所需 `dist/使用说明.txt` 存在；时间为 2026-10-30 |

`verification/native-install.json` 记录 0.3.0 的旧安装成功；`native-delivery.json` 仍是 0.2.0。它们是历史证据，不能当作当前源码或未来 WebView 包已通过验收。现有 tests 包括 Rust HTTP/cookie/WS 本地模拟合同测试（`tests/remote_contract.rs:107`）、DPAPI roundtrip、共享目录边界与 egui 渲染测试；本轮未重跑测试或构建。

## 5. 共享 Web UI + Rust 核心的最小可维护实施路径

本节是基于上述事实的工程建议，不是已完成的实现。DeepTutor 前端与工作台源代码不在本次读取范围内，具体框架、静态打包/SSR约束、路由和现有 API helper 由主控核查后绑定。

1. **共享 UI 一个来源。** 桌面新壳消费与 Web 产品同源的组件、主题 CSS、字体与动画构建。新增平台 runtime/transport 适配层处理原生文件选择、外部打开、连接状态和 IPC；产品组件不复制成 `ui/app.js` 第二版本。将前端产物打包到安装包，前端升级按用户手动升级策略发布。
2. **保留并隔离 Rust 服务。** 最清晰的正式边界是小 Cargo workspace：core（现有 config/remote/secure_store/service/browser/native/transport/tunnel）、desktop（Tauri 壳）、dp（独立 headless CLI）。源代码复用重于改写；也可先用 optional GUI 依赖 + feature gate 完成相同隔离，但不能继续让 dp 无条件链接 egui/wgpu。`schema.rs` 是旧 egui 通用表单合同，不应作为共享 Web UI 的业务页面来源。
3. **提取一个应用服务对象。** 它拥有 Config、RemoteClient、DesktopService、Tunnel 和任务/事件状态；从 DesktopApp 提取可信登录/退出、附件、文件对话框结果、下载落盘。Tauri commands 和 dp commands 都调用这一层。`EventSink` 接 Tauri event/channel 或 CLI JSONL 输出；UI/终端适配器不出现在 core 模块类型中。
4. **明确一次会话归属。** 若共享 UI 的业务网络继续经 Rust transport，复用当前 reqwest Cookie 与 WS，给 Web UI API helper 一个原生实现；Web 浏览器版本仍用浏览器 transport。若改为 WebView fetch/WS，需正式实现 Cookie/session 与跨源适配，并减少 Rust 重复会话。不能假设 WebView 登录后 RemoteClient 自动登录。壳的构建源、IPC许可、CSP需按最终来源配置。
5. **服务端更新只更新服务端资源。** capabilities、skills、MCP、workflow 的目录/版本/声明式参数由服务端发布并通过 API 刷新；现有 bootstrap 只在登录/部分加载时取目录，尚无版本检查、更新通知或按刷新恢复的统一机制。新增轻量目录版本/ETag与刷新行为即可承接该政策。原生 Rust、前端组件/脚本及本机 CLI 适配器随手动安装包升级；不把远程网站页面自动变更当成本地前端手动升级的实现。
6. **新增本机 CLI 执行适配器与 dp。** Codex/Claude Code 检测、启动参数、cwd、认证复用范围、stdout/stderr 事件、取消、退出码必须有真实适配器；以 job_id、日志/事件、running/completed/failed/cancelled 等最少状态支持 UI 和 dp 的共同调用。当前只有单 turn 流和工具 activity，不足以替代进程任务。命令具体协议按安装的 CLI 版本核验后落地，不能由旧“CLI 应用”网页目录推断。
7. **连接先兼容再产品化。** 现有 SSH Tunnel 可以保留为本机兼容路径。面向其他设备，服务端按登录用户/device_id 登记出站连接、工具能力和撤销状态，窗口与 dp 连接同一实例；解决固定 socket/端口争用及失败可见性。不要求普通安装用户预先持有部署管理员 SSH/sudo权限。
8. **改打包链并验真实流程。** 更新 `Cargo.toml/Cargo.lock`、`build.rs`、`src/main.rs/src/lib.rs`、`tauri.conf.json`、前端构建脚本与 NSIS/安装包版本；新文件建议为 core 应用服务、Tauri IPC/事件适配器、`src/bin/dp.rs` 或 dp crate、CLI runner、job/event 类型。验证共享 UI 三种主题/字体/动态、登录/remember/logout、文件选择/上传/下载、本机工具、CLI流/取消/退出、目录更新和安装升级。旧 egui 截图或 mock Tauri JS 测试不能替代这些真实连接验收。

### 真实阻碍与可直接推进的部分

| 问题 | 影响 | 下一步可落地措施 |
|---|---|---|
| Tauri 运行壳缺失，配置版本与现行包不一致 | 没有能接共享 Web UI 的可运行入口 | 建正式 Tauri desktop crate，配置本地 UI 产物、窗口、commands/event，再接现有核心 |
| 共享前端的构建/SSR/API helper 未在本审计中核验 | 不能断言直接 frontendDist 指目录就可用 | 主控结合其前端核查选定静态产物或实际运行时；保留共享组件来源 |
| Rust/WebView 登录态不互通 | 可能出现页面登录但本机请求未认证，或维护两套退出状态 | 选定 transport 和会话所有者，并迁出 AuthService |
| 桥依赖固定 SSH 管理权限与单 socket | 换电脑、多设备、普通账户连接无法自动成立 | 服务端 device 登记与出站连接；旧 SSH 路径仅作兼容适配器 |
| dp/CLI runner/job 生命周期不存在 | 无法仅加按钮便交付 Codex/Claude Code 与 CLI | 用已安装 Codex 做真实适配验证，补 Claude Code 检测/安装策略与最小任务服务 |
| 服务端目录刷新与本机升级边界尚未实现 | 后端发版不等于已打开客户端自动知道；内嵌 OpenAPI仍旧 | 目录版本/刷新 + 明确静态 UI/原生版本，配套手动安装包 |
| 没有当前 Tauri 构建结果 | 环境齐全仅证明有条件编译 | 实现后运行实际锁版本构建、测试、安装与启动验证 |

## 读取范围与证据边界

读取了 `D:/Development/AGENTS.md`。在桌面根目录及两者父目录、报告目标目录检查了 AGENTS.md；除该工作区文件外未找到适用的额外文件。

桌面工程：完整读取 Cargo.toml、package.json、tauri.conf.json、build.rs、README.md、src/main.rs、src/lib.rs、config.rs、secure_store.rs、service.rs、transport.rs、remote.rs、tunnel.rs、打包脚本和 installer.nsi；读取 browser.rs 的启动及可执行文件定位代码并检索全部函数；对 native.rs、schema.rs、cache.rs 按导出函数/合同/边界定位；对 desktop/mod.rs 阅读状态定义、构造、任务/事件、登录/可信凭证、文件下载、设置、send_chat片段，并以全文件检索定位其余函数；对 layout.rs 读取登录 tab定位和 logout，theme.rs 读取 Palette/主题开头；pages.rs 读取 CLI/profile 等定义与关键路径。旧 ui/读取调用接口、事件和入口，未检查 vendor 实现。读取 Rust remote_contract 测试，以及两个 JS 测试的入口和关键断言。读取 desktop_bridge_ctl.py 的 enroll，检索activate等函数和路由；读取 proxy 完整代码。读取 verification/native-install.json、native-delivery.json；未读取历史生产账号材料、实际用户 token、用户 cookie、SSH 私钥和用户配置文件。

Superba：目录/AGENTS检查，Cargo workspace 清单及相关依赖、ARCHITECTURE.md（用于分层参考）、superba-cli Cargo/入口/lib前段、GUI main 入口，以及检索 SwitchService/CLI类型定义位置。未审计其余功能实现；不把架构说明中的产品版本事实外推到当前部署。

环境：仅执行目标命令 Get-Command、cargo/rustc/rustup/node/npm 版本、vswhere VC安装路径，以及限定的 WebView2注册表/可执行文件、MSVC/SDK、NSIS、CLI候选和目标工程产物目录检查。没有通盘扫描、网络探测或依赖安装。
