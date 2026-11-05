# Deep Partner

Deep Partner 是一个科研工作流 App，组合 DeepTutor 会话与工具运行时、Research Workbench 项目与成果服务、Dify 交付流程，以及 SSH/Slurm 集群执行服务。

这个仓库首先用于审查四者之间的 **职责、调用链、状态所有权和恢复机制**。它包含工程源码、生产代码快照、部署脚本和第三方来源说明，不包含生产账户、API 密钥、研究数据库或私人项目材料。

**建议从 [架构审查入口](docs/ARCHITECTURE_REVIEW.md) 开始。**

## 工程目录

| 目录 | 内容 |
|---|---|
| [workbench](workbench) | 工作台后端、原工作台前端、统一前端、测试、MCP 客户端、模板与必要供应商资源 |
| [native/DeepTutor](native/DeepTutor) | DeepTutor 源码基线，叠加实际运行的 Python 源码和集群维护的前端源码 |
| [native/Dify](native/Dify) | Dify 1.18.0 官方源码；具体工作台接入与生产调整见 deployment |
| [deployment](deployment) | Dify 适配桥、原生扩展、运行时补丁、部署维护代码及工程文档 |
| [cluster](cluster) | 研究计算 MCP、集群调度、运行器与 Code 服务接入代码 |
| [integrations/codex](integrations/codex) | 项目工作流入口、本机工具桥、集群解析与仿真连接程序 |
| [desktop](desktop) | Windows Tauri/Rust 桌面承载端及 dp 命令行组件 |
| [docs](docs) | 架构审查说明、来源记录和公开快照范围 |

这是多个现有工程组成的源码快照，不是一个执行单条命令即可重建全部生产服务的安装包。历史运维脚本保留其原有路径约定；使用前需要配置运行路径、服务 URL、账户和集群资源。

## 审查任务

1. 逐条追踪“研究对话 → 工具调用 → 外部执行 → 结果入库”的真实调用链。
2. 分清原生 Turn、工作台 Job、Dify Workflow Run、交付记录和 Slurm Job 的事实来源。
3. 检查提交不明、重复请求、进程重启、服务离线和部分保存时的恢复行为。
4. 以代码与可复现测试为证据提出修改，不把历史说明中的“通过”当成本次验证结果。

审查导航与建议的首批故障测试见 [ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md)。

## 运行与验证

各组件依赖和测试保留在各自目录：

- 工作台 Python 依赖：[requirements.txt](workbench/requirements.txt)；测试：[tests](workbench/tests)。
- 工作台原界面：[web/package.json](workbench/web/package.json)。
- 统一界面：[unified-ui/package.json](workbench/unified-ui/package.json)。它复用 native/DeepTutor/web 组件，构建需设置 DEEPTUTOR_WEB_SOURCE 与 WORKBENCH_WEB_SOURCE；参见现有 Vite 配置。
- 桌面端：[Cargo.toml](desktop/Cargo.toml)。
- Dify：保留 [官方 README](native/Dify/README.md)、Docker 文件及许可证。

当前快照并未在一个全新环境内重新构建全部系统。历史验收记录与本次源码发布检查分别看待。

独立的 OpenHands 自托管工程环境说明见 [deployment/openhands](deployment/openhands)。

## 许可证与公开范围

各第三方组件保留原许可证，不以本仓库的名义重新授权。特别是 Dify 使用其自有附加条款的许可证；请阅读 [第三方来源说明](THIRD_PARTY_NOTICES.md)。

部署示例中的生产域名、IP 和个人路径已作示例化处理。真实凭据、下载论文、私人材料、运行数据库、虚拟环境和构建缓存未发布。详见 [公开快照范围](docs/PUBLICATION_SCOPE.md)。
