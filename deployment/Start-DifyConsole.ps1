$ErrorActionPreference = 'Stop'
$consoleUrl = 'https://tutor.example.invalid/dify/apps'
$status = Invoke-RestMethod -Uri 'https://tutor.example.invalid/dify/console/api/setup' -TimeoutSec 20
if ($status.step -ne 'finished') {
    throw 'Dify has not finished initialization.'
}
Write-Output "Dify console: $consoleUrl"
Start-Process $consoleUrl
