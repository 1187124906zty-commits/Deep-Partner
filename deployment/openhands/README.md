# OpenHands 自托管开发环境

本部署采用官方 npm 包 @openhands/agent-canvas 1.35.0，Node.js 24，
并使用 uv 启动 Agent Server 与自动化服务。服务通过 systemd 常驻。

它是 Deep Partner 的工程开发环境，处理工程副本；不接管 DeepTutor、
Dify、工作台或 Slurm 的生产状态与业务重试。

## 目录

- /srv/openhands/runtime：固定版本的 Agent Canvas npm 安装。
- /srv/openhands/tools：独立 Node.js 与 uv。
- /srv/openhands/projects/Deep-Partner：此公有仓库的开发副本。
- /srv/openhands/.openhands：设置、会话及自动化状态。
- /srv/openhands/cache：可重新下载的包缓存。
- /srv/openhands/private：访问密钥和模型配置，不进入 Git。

服务使用独立 openhands 账户，仅允许写入自身目录，并禁止访问现有生产项目、
数据库及凭据目录。开发环境中的 local runtime 表示在服务器服务账户的文件系统内执行；
它不代表为每次会话创建了独立 Docker 沙箱。

## 服务与入口

参考本目录的 systemd 单元和 Caddy 示例。入口使用已有域名上的独立 TLS 端口，
避免争用工作台的 /api 路由。Caddy 验证访问者后，转发到仅监听回环地址的
48000 端口；Agent Server、自动化端口不对公网发布。

密码散列和 LOCAL_BACKEND_API_KEY 必须在部署机器上生成，不使用仓库中的固定值。
模型连接通过 OpenHands 设置 API 保存，由其自身加密存储，不复制到源码。

    systemctl status openhands
    journalctl -u openhands -n 50 --no-pager
    systemctl restart openhands

## 更新

更新前记录当前版本，使用明确的新版本号安装 npm 包，重启并验证页面、
模型连接、已有会话和工程目录。不要在生产运行时自动追踪 latest。

上游操作说明：

- https://github.com/OpenHands/OpenHands
- https://github.com/OpenHands/OpenHands/blob/main/docs/SELF_HOSTING.md
- https://github.com/OpenHands/OpenHands/blob/main/docs/architecture.md

资源约束：这台服务器同时承载科研服务，适合单个开发 Agent。
构建和重计算沿用已有集群，不在本机服务进程中无界并发。
