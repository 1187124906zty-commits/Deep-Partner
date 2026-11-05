# DeepTutor 统一研究产品前端源核查

核查日期：2026-11-02。范围：只读检查现有 DeepTutor Web 源码、前端构建入口、匿名公开静态资源；未读取凭据、未调用模型、未修改产品源码或配置。本文只记录前端事实与据此提出的集成建议，不对工作台后端或 Rust 桌面端实现作判断。

**生产源纠正与实施基线（后续核查）：** 下文初轮读到的 `C:/Users/DEVELOPER/DeepTutor/web` 是本机1.6.15安装源码，不能作为现网1.7的版本基线。协调方随后核实生产实际使用 `D:/Development/deeptutor-coder-integration/frontend/web`；集群对应 `/work/home/cluster_user/research-projects/deeptutor-integration/frontend/src/web`，并有会话恢复/缓存补丁。正式 `research-workbench/unified-ui` 的所有 canonical 导入均直接指向这一生产源，未复制旧版状态机。生产新增 `ChatRuntimeRoot`、PageCustomizationProvider 和 classic/modern布局样式也已纳入统一入口。以下1.6.15文件定位是初轮调查记录；正式构建以生产源和实际编译为准。

## 1. 可复用的真实工程与部署关系

**现有完整 Web 工程是 `C:/Users/DEVELOPER/DeepTutor/web`。** 它是 Next.js App Router 应用，源码树包括 `app`、`components`、`features`、`shared`、`context`、`contracts`，并非仅 Python 安装目录。其 `package.json` 声明 Next 16.2.3、React 19、Tailwind CSS 3.4.17、framer-motion 12.24、lucide-react；没有 shadcn/Radix/Ant Design 这类外部基础组件包。基础组件由项目自己的 `shared/ui` 实现。

核查时本地仓库 HEAD 为 `a31d826`，提交日期 2026-10-19，提交标题 `release: v1.6.15`。这是源码版本标识，不能单独证明现网部署提交与其完全相同。

`D:/Development/电脑答疑/deeptutor-desktop/README.md` 明确当前 0.3.0 使用 Rust、egui、wgpu 绘制，默认连接 `https://tutor.example.invalid`；其 `package.json` 的 `npm run build` 调用原生打包脚本。这个目录不是现有 Next Web 前端的源码入口，不宜从这里提取 Web 主题或聊天组件。本文没有阅读其 Rust 源码。Android 研究目录内还有 `research/deeptutor-review/official-source/web` 副本，本轮不将研究副本作为正式实施基线。

Web 的部署链在源文件中是明确的：

- `web/next.config.js:98` 允许 `DEEPTUTOR_NEXT_DIST_DIR`，默认输出 `.next`；`:116` 使用 `output: "standalone"`。
- `web/scripts/build.mjs:58` 检查 standalone `server.js`，并把静态文件和 `public/` 拷入 standalone 运行目录。
- 项目根 `Dockerfile:170` 将 `web/.next/standalone`、`.next/static` 和 `web/public` 组合到运行镜像。
- 根 `README.md:447` 说明浏览器仅访问前端 3782，Next 代理转发 `/api/*`、`/ws/*` 到 FastAPI 8001；`web/proxy.ts:64` 是前端代理入口。因此正式融合可复用同一 Next 壳和同源代理模式。

匿名访问现网首页得到 `200`，最终地址为 `https://tutor.example.invalid/login?next=%2Fchat`，标题为 DeepTutor。公开 CSS `/_next/static/css/7a1738f92fd29264.css` 同时包含本地主题值 `#fdfcf9`、`#b0501e`、`#1a1918` 和 `--viewer-dur`。另一份 `/_next/static/css/ccd10301bc7b8f84.css` 含 Geist、Lora 字体声明。这支持现网使用该设计体系，但尚未核现网完整部署 commit。

**现网资产暴露的编译路径提示远端整合工程可能是 `/work/home/cluster_user/research-projects/deeptutor-integration/frontend`。** 这是由字体 URL 推断的路径，本轮未用远端文件访问验证，不能当作已经确认的远端目录事实。

## 2. 主题、字体、基础组件与动效的确切来源

所有以下路径均相对 `C:/Users/DEVELOPER/DeepTutor/web`。

| 要素 | 源文件 | 实际实现与复用要求 |
| --- | --- | --- |
| 配色语义 token | `app/globals.css:73` | 四族主题的背景、正文、card、popover、primary、secondary、muted、accent、border、input、ring、overlay、success/warning/info、raised surface 与阴影；应直接复用整套 token。 |
| Claude 风格奶油主题 | `app/globals.css:87` | `:root`：背景 `#fdfcf9`、正文 `#1c1816`、主色 `#b0501e`、secondary `#f5f2ea`、muted `#f1ede2`、次要文字 `#6d645a`、border/input `#e6decc`、card/popover 白色。源码注释明确 Inspired by Claude's chrome。对应 theme id 是 `light`。 |
| 暖黑主题 | `app/globals.css:130` | `.dark`：背景 `#1a1918`、正文 `#e8e4de`、card `#242220`、primary `#d4734b`、muted `#2a2725`、次要文字 `#9b9590`、border/input `#3a3634`。 |
| 主题初始化和持久化 | `components/ThemeScript.tsx`；`lib/theme.ts` | key `deeptutor-theme`，在 hydration 前设置 class；当前没有存储偏好时，亮色系统默认 `snow`（白底蓝色），暗色系统默认 `dark`。要交付奶油风格，应将研究产品初始偏好明确设为 `light`，并同步初始化脚本与客户端 fallback。 |
| 字体声明 | `app/layout.tsx:2` | `next/font/google` 加载 Geist、Lora，`display: swap`，变量为 `--font-sans`、`--font-serif`。本地 `public` 未发现独立字体资产目录；这些字体由 Next 构建生成，而不是从桌面端字体文件加载。 |
| 字体栈和颜色工具类 | `tailwind.config.js:35` | sans：Geist、PingFang SC、Hiragino Sans GB、Microsoft YaHei、Noto Sans SC；serif：Lora、Songti SC、STSong、Noto Serif SC、Source Han Serif SC、SimSun、Georgia。中文依赖系统回退，未见随本地 Web 工程分发的 CJK 字体包。颜色工具类通过 `color-mix` 支持 token 与透明度，必须一起复用，避免 `/55` 等工具类失效。 |
| 基础 UI | `shared/ui/` | `Button`、`IconButton`、`Dialog`、`Field`、`Tooltip`、`InlineAlert`、`StatusChip`、`Skeleton`、`EmptyState`；`styles.ts` 用 clsx + tailwind-merge。Button 已提供尺寸、状态、focus ring、120ms 快速过渡。 |
| 页面版式 | `components/layout/FeaturePage.tsx`；`app/globals.css:5` | PageContainer、FeaturePage、PageHeader、pageActionClass、pageGridClass；正文容器查询控制列数，标题使用 serif、27/30px。适用于研究工作台审查页，沿用同一尺寸规则。 |
| 全局细节 | `app/globals.css:309`、`:355`、`:435` | motion-fast/base/slow 分别 120/180/240ms；surface-card、muted-chip、raised surface；`.prose` 为 16px serif，并包含代码、公式、表格、引用与列表样式。 |
| Motion 加载 | `components/common/MotionProvider.tsx`、`motion-features.ts` | LazyMotion 按需加载 domMax；根 `app/layout.tsx` 包裹共享 MotionProvider。 |
| CSS 动效 | `app/globals.css:753` | fade-in 350ms；overlay-in 160ms；pop-in 200ms；breathing 1.8s；trace detail-in 180ms；live dot 1.25s；turn-flash；资源 chips 进出。保留 reduced-motion 规则。 |
| 侧预览联动 | `app/globals.css:987`；`components/chat/preview/FilePreviewDrawer.tsx` | `--viewer-dur: 300ms`、`cubic-bezier(0.32,0.72,0,1)`；chat-preview-shell 的挤压与预览面板滑动共享曲线和时长。 |
| 工作状态动画 | `components/activity/ActivityOrb.tsx`；`vendor/thinking-orbs/` | 真实 canvas orb 引擎与预设，不是单一 CSS spinner；18px 展示框、20px preset、3倍 supersampling；`hooks/usePickerOpen.ts` 控制弹层打开时暂停。`features/chat/trace/ActivityOrb.tsx` 映射思考、计划、探索、工具、回答等阶段。 |

### 已确认的现网字体缺陷

现网的字体 CSS 把服务器绝对路径写进浏览器资源 URL，例如：

```text
Geist: /work/home/cluster_user/research-projects/deeptutor-integration/frontend/fonts/22a5144ee8d83bca-s.p.woff2
Lora:  /work/home/cluster_user/research-projects/deeptutor-integration/frontend/fonts/5c0c2bcbaa4149ca-s.p.woff2
```

本轮匿名 HEAD 请求 Lora 的上述 URL 返回 **404**；另一 Lora 分包 `08aedeceaf1dcd57-s.woff2` 也返回 **404**。这已经足以证明至少这些字体声明不能正常加载。尚未对每个字体分包逐一检查，不声称全部字体请求都失败。

正式集成应恢复浏览器可访问的字体 URL，复用 Next 正常生成的 `/_next/static/media/...`，或把已授权字体资源放到公开 `/fonts/...` 并使用正确的 local font 声明。不能把服务器磁盘绝对路径作为 CSS URL。视觉验收需核对浏览器实际加载字体，不能仅检查 CSS 中出现 Geist/Lora 字样。

## 3. 聊天、DeepPartner 与执行呈现中可共享的内容

**已有共享关系，应该在此基础上接工作台，而非另做聊天窗口。**

| 用途 | 实际源组件/模块 | 复用边界 |
| --- | --- | --- |
| 会话整体 | `features/chat/components/ChatWorkspace.tsx` | 已整合消息、输入、资源、会话标题、侧预览；正文宽 960px，初始欢迎标题 serif 40px；保留该布局与控制器。 |
| 输入与发送/停止 | `components/chat/home/ChatComposer.tsx`、`ChatComposer.module.css`、`ComposerInput.tsx` | 26px 圆角输入表面；初始宽768、会话宽960；650ms宽度过渡；附件拖放、发送与停止状态、资源栏、容器查询工具栏。ModelSelector 在 `ChatComposer.tsx:1392`，是研究版简化模型前台的明确裁剪点。 |
| 消息列表与文件 | `features/chat/messages/ChatMessageList.tsx` | AssistantMessage、UserMessage、GeneratedFileCards、消息操作、过程折叠、延迟载入 trace；可保留完整消息呈现，按研究场景过滤教育专用卡。 |
| 平滑 Markdown 和模型思考折叠 | `components/common/AssistantResponse.tsx`、`MarkdownRenderer.tsx`、`ModelThinkingCard.tsx`、`hooks/useSmoothStreamText.ts` | AssistantResponse 已共享使用；存在 ReadingContext 依赖，拆取时需保留 provider 或做兼容注入，不能直接复制单文件后去掉依赖。 |
| 工具/推理概要/研究阶段 | `features/chat/trace/TracePresentation.tsx` | `CallTracePanel`（1200）、`StreamingStatus`（1519）、`TraceFlow`（1657）、`NestedTraceFlow`（1680）、`AssistantActivity`（1762）、`ResearchStagePanel`（1951）；summary/raw 分层、工具配对、状态、人读标签已有逻辑。 |
| 工作台可复用的活动基元 | `components/activity/` | ActivityHeader、ActivityStack、ActivityRow、ActivityFold、ActivityDetailGrid、StatusDot、ActivityOrb；适合承载工作台真实审查事件与状态。 |
| 执行 transcript 与材料预览 | `components/chat/home/SubagentRunTranscript.tsx`、`SubagentTabBody.tsx`、`ConsultationTabBody.tsx`、`SessionViewerPanel.tsx`、`SessionActivityPanel.tsx`、`ChatViewerBridges.tsx` | 已有执行详情、文件tab、会话工具/引用/材料索引，可为研究任务、证据、审查结果提供同样的右侧面板。 |
| 正常聊天状态与恢复 | `features/chat/ChatRuntimeProvider.tsx`、`ChatStateAdapter.tsx`、`transport/UnifiedTurnClient.ts`、`transport/TurnRuntimeClient.ts` | 默认 `/ws`；连接恢复、顺序事件、缺口处理、resume cursor、取消命令和用户输入确认；必须连同 contracts/generated 与 parse 层保持合同一致。 |
| 伙伴会话 | `components/partners/PartnerChat.tsx`、`PartnerComposer.tsx` | WS `/ws/partners/{id}`。文件开头明确说明 stream_event 为统一 StreamEvent，直接复用 `AssistantActivity`；流式回答复用 `lib/stream.ts` 的 append/retraction/recompute 规则。伙伴会话与普通 chat 已共享渲染，不应分成两套设计。 |
| 伙伴群组 | `components/partners/group/PartnerGroupChat.tsx`、`GroupRound.tsx`、`GroupSidePanel.tsx`、`InvocationCard.tsx` | 可保留群组讨论及已有批准/拒绝后续讨论的交互。该审批卡合同面向伙伴追问，不能仅改标题就当成工作台的科学审查批准。 |

执行/审查融合需要一个明确的展示适配层：工作台事件可以转换成 Activity 基元接受的 label、status、duration、summary、details；只有真正符合 DeepTutor turn 协议的数据才能进入原有 StreamEvent/TraceFlow。不要用假造的 chat trace 替代工作台记录，也不要为了统一外观绕过原来的取消、恢复与用户回复命令。

## 4. 导航和设置的研究版裁剪点

当前导航权威列表在 `components/sidebar/nav-entries.ts:37`，实际是 Home(`/chat`)、Partners、Personalized Learning(`/learning`)、Learning Space(`/space`)、Task Board(`/kanban`)、Co-Writer、My Agents。`SidebarNav.tsx` 支持重排和 More 折叠；`SidebarShell.tsx` 统一历史、工作区、底部账户设置；`AppShell.tsx` 提供768px断点的桌面侧栏与移动抽屉。`hooks/useSidebarResize.ts` 默认220px，范围220–480px；collapsed rail 在 SidebarNav 中为60px。

研究产品可保留 Chat、Partners、任务、Co-Writer、Agents，将工作台审查作为同一导航中的正式研究模块。`/space` 可用研究资料/资源的名称与内容子集承载，既有 `lib/space-items.ts` 已明确拆为历史、智能体、笔记本、题库、人格、技能。

前台可隐藏的教育入口包括：

- `/learning` 的课程/掌握式学习入口，以及 Space 中 `/space/questions` 题库。
- 能力菜单中的 `deep_question`（Quiz）、`course_study`、`mastery_path`；视研究产品需求处理 math_animator/视频课程类入口。权威能力展示在 `features/capabilities/presentation.tsx`，目录加载在 `useCapabilityCatalog.ts`。
- `MasteryQuestionCard`、`MasteryHandoffCard`、`MasterySourcePresentation`、`CoursePill`、`CourseHandoffCard` 这些教育专用消息/资源卡的常规入口。
- 设置中的 learner-profile、progress、guardian、video-learning。这些都可从研究版导航和搜索结果中过滤，底层模块继续保留。

**不要把所有带 Questions 或 Reading 名称的能力一起隐藏。** `ask_questions` 是一般性的补全上下文，研究对话仍可用；沉浸阅读、书籍/文献、知识库、笔记本也可以服务科研。`deep_solve` 是通用问题求解，不等于中小学入口。建议按产品使用目的建立研究版显示列表，而不是按关键词删目录。

设置的分组入口为 `features/settings/navigation/settings-pages.ts:13`；所有叶项和 alias 在 `settings-nav.ts`，访问显示在 `settings-access.ts`。常规研究前台可保留常规/语言、外观、工作区、会话、记忆、用量、归档；提供方、language models、task models、embedding、search、voice、multimodal、各 CLI agent 的模型/推理强度/运行参数放入明确的管理或高级入口。`settings-nav.ts` 中已经有 adminOnly、learnerOnly、guardianOnly 语义，可复用其机制，并加研究产品的显示规则。

需要同时过滤设置目录、设置搜索、能力选择器、欢迎建议和会话资源选择器；只从侧栏删一项不能完成前台简化。`ChatComposer` 中保留简短执行智能体/默认模型摘要即可；其 `AgentSelector` 保留对真实连接智能体的选择，详细服务设置继续使用现有管理页面。

现有 `navVisibleUnderPolicy` 是学习账户访问策略，学习策略会隐藏 Partners/Agents 这类没有对应 surfaces 的项目。研究产品不宜借用 learner preset 来获得精简导航；应提供独立的产品显示规则，同时沿用原有权限判断。

## 5. Web 端统一壳的实施合同建议

1. 以现有 Next 工程作为壳，继续使用根 layout 的字体变量、ThemeScript、MotionProvider、I18nClientBridge、ToastViewport、AppShellProvider。研究审查页进入相同 AppShell；页面内部使用 FeaturePage 与 shared/ui。
2. 保留 SidebarShell、WorkspaceSidebar、ChatRuntimeProvider 的会话生命周期。`app/(workspace)/layout.tsx` 将 runtime 放在页面上方，专门处理 `/chat` → `/chat/<id>` 时保持已打开材料与运行状态，这一层级不应被新的路由壳打断。
3. 直接共享 globals.css、tailwind.config.js 的颜色/字体规则、activity 组件、聊天输入和消息呈现。通过产品导航与能力显示配置收敛入口，不重写一套近似配色和圆角。
4. 将工作台的证据、审查、任务记录以真实资源打开到已有 SessionViewerPanel/文件预览交互中；深度状态可以使用 Activity 基元，但事件字段与审查动作需接真实工作台合同。
5. 交付时至少核对奶油与暗色主题、实际加载的 Geist/Lora、中文回退、768px抽屉、聊天与右侧材料同屏、流式更新与停止、工具过程折叠、重新连接后继续会话，以及被隐藏入口不会出现在目录/搜索/欢迎建议中。保留现有 `tests/design-token-parity.test.ts` 的语义 token、focus 与 reduced-motion 检查。

本轮仅形成源核查与实施边界，没有构建或运行修改后的产品。因此以上“可以复用”指已经读到现成实现或现存共享导入，不代表新的研究工作台融合已经完成。

## 6. 本地 Tauri 静态打包的最小复用接缝

补充约束：桌面前端必须随安装包本地提供、手动升级；不加载远程页面、不使用 iframe。为此只增加 Next 的 `/research` 页面只能解决 Web 统一，不能直接成为桌面静态包。

已按协调方提供的路径只读核对 `D:/Development/research-workbench/web` 的顶层入口。它确实是 Vite 6.4.1 / React 19，依赖包括 Tiptap、KaTeX、lucide；没有 Tailwind、framer-motion、i18next、react-markdown 等 DeepTutor 呈现依赖。`vite.config.ts` 的 base 为 `/research/`，build 输出 `../static`；`src/main.tsx` 载入多个工作台 CSS 文件。`src/App.tsx` 自己拥有完整 sidebar、header、区域切换、jobs/toast/modal，并在侧栏提供跳转 `/chat` 的 DeepTutor 链接。因此直接把整个 Workbench App 放到另一个产品壳里，会形成两套导航；应先把它的业务内容与外层框架分开。

### 6.1 实际依赖边界

当前源码没有名为 `ChatHome` 的文件；完整聊天入口是 `features/chat/components/ChatWorkspace.tsx`，完整消息视图是 `features/chat/messages/ChatMessageList.tsx`。这些名字应作为实施中的确切基线。

| 模块 | 已核到的框架/上下文依赖 | Vite 复用判断 |
| --- | --- | --- |
| `ChatWorkspace.tsx` | 直接 import `next/navigation` 的 useSearchParams、`next/dynamic`、`next/link`；`controllers/useChatRouteSession.ts` 直接 useParams/useRouter；还用 ChatStateAdapter、AppShell、QuizFollowup、Geogebra、资源复用上下文，以及资料/模型/任务 API。 | 不是可零修改导入 Vite 的独立组件。保留其页面编排源码，通过小型 host 接口替换路由和动态加载即可继续复用；不能把它描述成几个纯 UI 文件。 |
| `ChatRuntimeProvider` / `ChatStateAdapter` | 核到的顶层源码没有 Next import；是 React context、协议/状态机、存储、API、WebSocket 客户端。provider 通过 process.env.NODE_ENV 做开发检查。 | 可跨宿主复用。需要提供相同 React runtime、API/WS/存储适配与 process 环境处理，不需要 Next 服务端。 |
| `ChatMessageList.tsx` | 顶层 Next 依赖是 `next/dynamic`；props 接受消息、streaming、事件和 callbacks；调用语音 API、伙伴草稿等业务模块，并动态加载教育与可视化卡。 | 可复用现有消息组件；将 lazy loader 换为共享 React.lazy/Suspense 实现，教育卡通过明确 feature slot/filter 处理。不是重新写消息气泡。 |
| `TracePresentation.tsx` | 本文件无 Next import、无 chat runtime context；接受 StreamEvent；依赖 React、i18n、MarkdownRenderer、activity 基元与 trace selectors/model。 | 是最清楚的可共享呈现接缝；MarkdownRenderer 下游的 next/dynamic 需要先拆除。 |
| `ModelThinkingCard.tsx` | 本文件仅 React、lucide、react-i18next、MarkdownRenderer；其工作是展示模型明确输出的 think 区块，与工具摘要有不同输入合同。 | 可共享，最小修改在下游 Markdown loader，而不在卡片结构。 |
| `MarkdownRenderer` / `RichMarkdownRenderer` | 都用 next/dynamic；Rich 动态加载 Mermaid、RichCodeBlock、GeogebraOpenCTA；RichCodeBlock 读取 AppShellContext 的代码主题、行号和换行；GeoGebra CTA 读取 GeogebraTabContext。 | 用 React.lazy/Suspense 保留原渲染实现，代码显示偏好和打开图形动作通过共享 provider/host port 提供。不能只带走最外一层 renderer。 |
| `AssistantResponse` | 平滑文本 hook、Markdown、ModelThinkingCard、ReadingContext。ReadingContext 本身是普通 React，默认 context 提供 material=null 和空操作。 | 单纯文字呈现可在默认 context 下运行；要保留文献定位点击和阅读工具同步，应一并保留/接入 ReadingProvider。其 rich code 下游仍需要 AppShellProvider。 |
| `ChatComposer.tsx` | 本文件无 Next import；主要由 props 驱动，但会读取 TaskBoard store、伙伴和群组 API、录音 hook。其 PartnerSelector、PartnerGroupSelector、KnowledgeSelector 使用 next/link。 | 结构和输入交互可共享；把 link 及 API/store 适配到宿主，保留本组件与 CSS module。`StandaloneComposer` 已提供另一个宿主的状态封装，但本身仍用 next/dynamic，并非现成 Vite 版本。 |
| `components/activity`、`shared/ui` | 主要为 React/DOM、lucide、少量 i18n；ActivityOrb 使用 vendored canvas 和 DOM MutationObserver。 | 可直接形成公共 UI 模块；带入其样式、Tailwind扫描范围、必要hooks和vendor源。 |

`"use client"` 在 Vite 中只是指令字符串，不是阻碍。真正阻碍是 Next imports、缺少依赖/生成样式、API 与认证同源假设；字体加载则来自根 layout，而不是聊天组件内部。

### 6.2 应提取的最小共享模块与宿主接口

建议建立一个**由现有源码提取的共享 React 客户端模块**，两个入口消费同一份实现：Next Web 入口和 Vite/Tauri 入口。先做以下必要边界，不需要重建聊天产品：

1. **设计源**：以 DeepTutor `app/globals.css`、`tailwind.config.js`、`components/common/MotionProvider.tsx`、`components/activity` 和 `vendor/thinking-orbs` 为 canonical。共享模块构建其样式，或让 Vite 使用相同 Tailwind3配置并扫描共享源码。当前 Workbench 只有 tutor-theme token 副本和手写 tutor-ui.css，单复制聊天 TSX 不会生成其 Tailwind 类。
2. **字体源**：canonical 是 DeepTutor `app/layout.tsx` 声明的 Geist / Lora 与 Tailwind CJK回退栈；Vite用本地 WOFF2资产重新声明相同变量。已核 Workbench `src/fonts` 有 Geist-Variable.woff2 和 STIX，**没有 Lora**；STIX是论文/公式字体，不能代替壳的 Lora。字体资产应随桌面包发出。Next/font 本身留在 Next 入口，不能导入 Vite；修复现网绝对路径404问题。
3. **导航 port**：提供 sessionId、query、push/replace 和 Link。Next adapter 使用现有 hooks；Vite adapter 使用统一 shell 的 router/state。现有 `lib/workspace-scope.ts` 已有 `registerWorkspaceNavigator`，可沿用其注册点和 dt_workspace语义；只需把 `useChatRouteSession`、useSearchParams、Link等宿主入口抽出来，不需要模拟一套完整 Next router。
4. **lazy loader**：共享呈现层用 React.lazy/Suspense；Next Web 可消费同一份模块。无需给 Vite带入 next/dynamic runtime，也不应把 `next/*` 全局替换成无行为假模块。
5. **transport port**：抽在现有 `shared/api/client.ts`、WS socket factory 与 Workbench `src/api.ts` 的宿主边界。当前 DeepTutor apiUrl/wsUrl 经 scopedUrl返回同源路径；Workbench请求固定 `/research/api`、credentials same-origin，401跳远端 `/login`。在 Tauri本地源下这些路径不再天然指向生产服务器，必须接到已核验的桌面 RemoteClient/认证桥，覆盖HTTP、WS、上传下载及登录跳转；仅改URL前缀不足以保留会话。此处未读取Rust，也未宣称现有桥已覆盖所有流量类型。
6. **上下文和页面内容**：保持一个 AppShellProvider / ChatRuntimeProvider / ReadingProvider、共享 i18n 和 MotionProvider，放到统一产品主入口之上。将 Workbench `App.tsx` 的业务区（Library、Files、PaperWorkspace、Slides、StageQuality等）作为内容视图放进同一个壳；保留其API、保存回调和审查业务。移除它的第二套sidebar/header，而不是把整个 App包入聊天页面。

### 6.3 哪个方案实际更小

**只交付 Web：** 在已有 Next增加 research主路由，并导入工作台业务组件，是较小改动，因为大部分 DeepTutor壳和聊天不用迁移。

**同时交付要求的本地静态桌面：** 先提取上述共享 React呈现/运行模块、让 Vite作为本地统一入口，是总改动较小的路线。核心是复用 ChatWorkspace / ChatMessageList / TracePresentation / ChatComposer源码并增加宿主适配；不重写聊天视图。Next的 middleware代理、服务端ThemeScript、动态会话路由与standalone server不能直接装进静态文件包。先在Next完成全部融合、再另做静态导出，仍要重新处理这些同样的边界，重复工作更多。

因此建议的最小实现次序是：共享设计与活动呈现 → 让现有消息/输入在Vite宿主渲染 → 接同一聊天runtime与桌面transport → 将工作台业务区放入同一壳 → Next入口消费同一共享模块。若首阶段需要较快验证网页融合，可先加Next路由验证交互，但应从开始就沿用同一个共享模块，不能把临时网页集成当作已完成桌面打包。

以上是基于实际顶层imports和配置得到的接缝判断，未执行构建迁移；不能用它宣称所有传递依赖已经通过Vite编译。
