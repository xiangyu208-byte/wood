param(
    [switch]$Gpu
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$composeArgs = @('compose', '-f', 'docker-compose.yml')
if ($Gpu) {
    $composeArgs += @('-f', 'docker-compose.gpu.yml')
}
$composeArgs += 'down'

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose 停止失败，退出码：$LASTEXITCODE"
}
