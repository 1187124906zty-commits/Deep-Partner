# 编码容器的集群连接

2026-10-29 已从真实编码容器通过SSH认证：用户 `cluster_user`，home `/work/home/cluster_user`，SSH别名 `research-cluster-xh5`。当前登录可能到login02/login04等不同节点，home共享；不使用节点/tmp传递后续连接需要的文件。

连接配置位于 `/home/coder/.ssh/config`，使用服务器本地生成的专用服务身份，其公钥在集群 `~/.ssh/authorized_keys` 受 `from="203.0.113.10",restrict` 限制。本机原有密钥未上传。私钥保存在持久化coder-home中，不读出到模型、日志或项目。HostKey已从本机已信任记录固定，StrictHostKeyChecking保持yes。

```sh
ssh research-cluster-xh5 'hostname; id -un; pwd'
scp script.py research-cluster-xh5:/work/home/cluster_user/<明确的项目路径>/scripts/
```

先读remote-research-cluster技能、CLUSTER_DATA.md、research-projects.json及实际远端研究状态。原有氯硫项目根 `/work/home/cluster_user/research-projects/chloride-sulfate-pino-bayes`，公共大数据根 `/work/home/cluster_user/research-projects/chatgpt-large-data-20261025`；这些路径已通过连接核对，不能把其他会话的新科学设想当作旧项目已完成内容。

调度参数已核对：account `cluster_user`、QOS `user_cluster_user`，CPU分区 `xhacnormalb`。这是接入时可见权限，提交实际任务前检查资源与用途。登录节点仅轻量操作；训练、求解、重编译、批量转换和后处理通过Slurm。复用 `/public/software/apps/anaconda3/2023.09/bin/python` 或技能中对应容器，实际任务先核对环境，不默认重装。

独立接入验证根 `/work/home/cluster_user/research-projects/deeptutor-integration`；不覆盖既有科研项目。完整状态以其 `research/STATE.md` 和 `/workspace/coder/cluster-validation/cluster-connection-verification.json` 为准。

真实验证：Slurm作业 `25047702` 在 `a04r07n07` 完成，COMPLETED、ExitCode0:0，Python3.11.5。周期一维扩散64点120步对傅里叶解析解的相对L2误差4.14236907700259e-6，质量误差1.1102230246251565e-16。输入通过编码容器SCP上传，作业实际运行后摘要经SCP回传并核对JobID；容器重建后的SSH/sacct回查亦通过。该算例是连接和调度测试，不是原氯硫科研模型的新增结果。
