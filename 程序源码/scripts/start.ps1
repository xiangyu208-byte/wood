param(
    [switch]$Gpu
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '未找到 Docker，请先安装并启动 Docker Desktop。'
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '已由 .env.example 创建 .env，请在正式部署前修改数据库密码。'
}

$composeArgs = @('compose', '-f', 'docker-compose.yml')
if ($Gpu) {
    $composeArgs += @('-f', 'docker-compose.gpu.yml')
}
$composeArgs += @('up', '-d', '--build')

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose 启动失败，退出码：$LASTEXITCODE"
}

Write-Host "系统启动完成：http://localhost:$((Get-Content .env | Where-Object { $_ -match '^FRONTEND_PORT=' } | Select-Object -First 1) -replace '^FRONTEND_PORT=', '')"
