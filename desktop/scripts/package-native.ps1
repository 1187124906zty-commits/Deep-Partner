param([ValidateSet('submit','status','fetch','package')][string]$Action = 'submit')
$ErrorActionPreference = 'Stop'
$taskBuilder = 'D:/Development/询问/dify-research-deployment/ops/cluster_native_build.py'
if (-not (Test-Path -LiteralPath $taskBuilder)) { throw '未找到集群构建入口，请按 docs/集群开发与界面恢复.md 检查路径' }
python $taskBuilder $Action
if ($LASTEXITCODE -ne 0) { throw '集群构建操作未完成，请查看上方具体输出' }
