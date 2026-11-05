# Deep Partner 管理员入口与系统架构

这是同一站点内独立增加的免登录管理员入口。原站点的账户认证、注册申请与原工作台入口保持原有行为。

- 管理员工作台：https://tutor.example.invalid/admin/
- 无需执行脚本的实际界面审阅：https://tutor.example.invalid/admin/review
- 实际页面可见文字与截图链接：https://tutor.example.invalid/admin/review.md
- 可直接读取的本文：https://tutor.example.invalid/admin/architecture.md
- API 定义：https://tutor.example.invalid/admin/research/api/schema
- 现有研究工作流与工具集成项目：https://tutor.example.invalid/admin/research/?project=c37b9168a0db40e3b258c9c03cd56697&view=overview
- 原工作台：https://tutor.example.invalid/research/

## 请求链路

浏览器或外部工具
  → Caddy HTTPS 入口
  → /admin/*：独立管理员网关
  → 原生 DeepTutor 账户服务、Research Workbench、既有工作流服务

原 /research/*、/api/*、/login、/register 仍使用原路由和原认证。管理员网关仅处理 /admin/*。它在服务器端登录现有管理员账户，并在转发请求时带入该账户身份；不会向浏览器下发管理员登录 cookie 或 token。管理员入口内的前端资源和接口地址被映射至 /admin/*，原前端文件保持原样。

## 应用组成

1. 统一前端：项目侧栏、研究对话、项目概览、工作流、文献与知识库、程序和稿件等成果视图。网站和桌面客户端共用该前端体系。
2. DeepTutor 原生服务：身份与工作区、会话与持久化回合、模型设置、工具与能力调度、实时 WebSocket。
3. Research Workbench：项目材料、文献、项目知识、知识图谱、稿件和演示文稿、工具工作流及执行回执。每个项目绑定原生工作区和账户所有者。
4. 专用工作流服务：类型化的研究流程、文献上传与集群解析、下载 worker 回执；沿用现有路由和运行实例。
5. Dify 交付适配：既有的证据读取、交付与版本保存流程，由原适配器承担。
6. 集群执行：已配置的 SSH 与 Slurm、计算节点解析和求解、远端原始结果及项目归档。管理员入口不会另建求解环境。

## 可读取的接口

- /admin/api/auth/status：管理员网关内的原生身份状态。
- /admin/research/api/bootstrap：当前身份与项目列表。
- /admin/research/api/projects：当前管理员名下项目。
- /admin/research/api/schema：工作台全部 API 的 OpenAPI 定义。
- /admin/research/api/standards：产物规范与集成契约。
- /admin/research/api/projects/{project_id}/agent-context?task=code：具体项目的代码任务上下文；其他 task 以接口定义和项目规范为准。

这些接口读取当前服务的实际数据。架构说明概括已部署模块，实际端点、字段和方法以 schema 为准。

## 管理员入口的权限

这是开放的管理员工作区入口，具有现有管理员账户的操作权限，并可访问该账户名下的项目与资料。它适合此次需要的直接访问与架构查看。原入口的登录限制仍然生效。

## 部署位置

- 管理员网关独立容器：deep-partner-admin，监听服务器回环地址 127.0.0.1:47918。
- 网关和架构说明：/srv/deep-partner-admin/。
- Caddy 独立路由：/etc/caddy/deep-partner-admin.caddy。
- 原生账户配置：保持 enabled=true，不修改原生个人资料接口。
- 前端资源：只读挂载当前正式前端，按管理员路径提供，不覆盖原发布文件。
