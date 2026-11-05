---
name: research-compute-validation
description: 用真实计算检验研究方法、数值程序或可证伪结论；连接 DeepTutor、DeepCode、Slurm 与 openPASO，返回原始证据、误差和适用范围。
tags: [research, compute]
---

# 以计算检验研究

Tutor根据对话和资料形成研究思路，解释目标与约束，通过research_code把实施交给Code Agent。Code负责程序、数据处理、计算、数值检查和产物整理；本技能的计算步骤主要由Code执行。Tutor先读交接摘要，需要时再定向检索原始证据，继续与用户讨论研究意义和下一步。L3保存条件明确的经验，项目和计算记录保存原始证据。

## 形成可运行的检验

读取当前项目资料与相关原代码，确定控制方程、单位、边界/初始条件和目标量。选择与当前问题匹配的解析解、制造解、独立参考实现或实验数据；说明它是理论核验、校准还是独立实验比较。机器学习任务同时说明替代的计算环节、数据划分与泛化变量。

在观察结果前指定指标和接受依据。针对可能的错误安排最小对照，例如错误算子即使线性残差很小也应被解析误差或网格趋势识别。数值精度按目标结论确定，不固定要求每个任务重复相同检查。

## 调用计算接口

1. `inventory` 查询当前集群资源策略和已有运行时。计算均通过 Slurm，登录节点负责控制。当前接口支持 1–4 CPU、512–8192 MB、1–15 分钟；更大计算先说明所需资源并调整正式资源策略。
2. `prepare` 固定一轮实验的源文件、运行时、判据和参照。`spec_json` 包含 question、runtime、files、entrypoint、criteria、reference、limitations 与 resources。返回的 experiment_id 是后续操作的唯一身份。
3. `submit` 提交同一实验。返回 Slurm job_id 只表示已提交；`status` 查询真实状态和执行回执。排队或运行时保留当前 ID，按合理间隔查询；需要继续讨论时交付当前状态，后续从同一 ID 恢复。`cancel` 只控制该实验登记的作业。
4. 程序将实测标量写入 `outputs/metrics.json` 的 `metrics` 对象，原始表和场数据另外保存在 outputs。`assess` 核对 Slurm 终态、进程退出和运行前判据，并生成 `outputs/assessment.json` 与 `.md`；`read` 回读必要原始表、日志和评估。指标缺失或执行失败不算通过。
5. 回到研究问题解释结果，保留反例与未知。数值指标由实验程序产生，MCP 只做执行核对和确定的比较；程序可能含错，参考可能不独立，均需根据来源和对照判断。`NUMERICALLY_CHECKED` 不等于真实材料机制或实验已经证实。

标准 Python 运行时用 `python`；已有科学计算环境用 `paso`；PyTorch 用 `torch`。entrypoint 是 supplied files 中的 .py 文件，arguments 是字符串数组。脚本当前工作目录是该实验根，输入文本放普通相对路径，输出放 outputs/。大数据保持远端，只回读必要摘要。

criteria 每项为 `{name, metric, op, threshold, unit}`；op 可用 lt/le/gt/ge/eq；metric 对应输出 metrics 对象中的键。例如二阶预期可用 `{"name":"L2收敛阶","metric":"l2_rate","op":"ge","threshold":1.8,"unit":"1"}`，阈值必须来自该算例的精度用途与理论依据。

## openPASO

复用已有 `/work/home/cluster_user/opensource/openpaso`。先运行 `runtime=openpaso_catalog` 的有限作业，再用 `openpaso_schema` 读取该作业实际记录的工具名与 schema。`runtime=openpaso` 使用 `{openpaso:{tool,arguments}}` 执行该工具，并保存原始 MCP 返回。元数据 available 只表示发现，不等于所有后端已完成当前问题的验证。实际求解、网格和后处理都在分配到的计算节点中进行。

已知平台通路不需要再通过旧的通用 SSH/cluster_job 入口。DeepCode 通过已配置的 research-compute MCP 使用同一套 prepare/submit/status/assess；该连接的凭据由计算服务持有，模型使用实验接口；集群接入网关的 SSH 限制并非安全沙箱，执行的是受信科研代码。

## 反馈到工作台

将问题、预先判据、实际作业状态、主要数值、原始文件位置、比较解释和局限写入当前项目。使用 `research_workbench` 取得真实保存回执；计算记录与工作台保存分别报告。较长任务保留 experiment_id 和 job_id，下一轮先查询既有状态再决定后续有限计算。

## Code交接格式

读取工具自动携带的research_project上下文、当前对话约束和inputs清单；在工作目录src/整理正式程序，data/记录数据及远端来源，results/保存结果与评估，docs/code-handoff.md给Tutor简短交接。按当前工作台技能规则调整具体结构，保持同一项目的已有文件。完成时写research-handoff.json，含schema_version=1、当前真实task_id、artifacts[{path,summary}]、validation和limitations；列出实际需要写回工作台的文件。应用按版本规则发布清单并取得保存回执，Tutor不需要重复执行整套验证。大数据保留远端，用可回查的清单关联。
