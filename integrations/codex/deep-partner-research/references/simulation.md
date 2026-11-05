# 仿真程序路由

实际入口为 `partner_research(kind="simulate")` 或 `dp workflow run`，并绑定已有项目。仿真不依赖单独的验证技能进入模型上下文。程序负责准备、提交、监控、结果核验及归档；未闭合的物理条件由上游文献或代码准备阶段补齐。

请求为 `kind=simulate`，用 `input_paths` 列出本次需要上传的项目文件。`simulation` 支持：

- `engine=python`：`entrypoint` 必须属于 `input_paths`；`arguments` 为参数数组。
- `engine=openpaso_mcp`：`tool_steps` 为真实工具名和 `arguments`，作业在计算节点完成 MCP 初始化、发现和调用；不伪造工具要求的评审或放行记录。
- `runtime=paso|dune|torch`：使用现有集群 wrapper，不安装新求解器。默认 paso。
- `resources`：`cpus/memory_mb/walltime_seconds`，默认 2/4096/600。
- `summary_path`：求解脚本写出的 JSON 摘要，默认 `results/summary.json`。
- `expected_outputs`：必须存在的原始结果相对路径列表。
- `checks`：预先指定的结果检查，每项有 `field/op/value/atol/unit/basis`。`op` 支持 finite、true、le、ge、close。
- `validation_basis=theoretical|experimental|calibration|unspecified`，`physics` 保存方程、单位、边界、初值和参照定义。

示例：

```json
{
  "kind": "simulate",
  "input_paths": ["src/solve.py", "configs/case.json"],
  "simulation": {
    "engine": "python",
    "runtime": "paso",
    "entrypoint": "src/solve.py",
    "arguments": ["configs/case.json"],
    "resources": {"cpus": 2, "memory_mb": 4096, "walltime_seconds": 600},
    "summary_path": "results/summary.json",
    "expected_outputs": ["results/summary.json"],
    "validation_basis": "theoretical",
    "checks": [{"field": "max_error", "op": "le", "value": 0.01, "basis": "已有理论参照及预定精度"}]
  }
}
```

提交后读取 `status`；中断后使用原 `run_id` 的 `resume`。已有 Slurm ID 接续查询，不重新提交。执行、数值检查和实验验证分别记录；零退出码不能自动称为实验验证。原始大结果留在回执指定的集群目录，项目保存 `results/simulations/<run-id>/{request.json,result.json,report.md}`。
