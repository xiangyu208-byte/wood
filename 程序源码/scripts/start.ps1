param(
    [switch]$Gpu
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker was not found. Install and start Docker Desktop first.'
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Created .env from .env.example. Change the database passwords before deployment.'
}

$composeArgs = @('compose', '-f', 'docker-compose.yml')
if ($Gpu) {
    $composeArgs += @('-f', 'docker-compose.gpu.yml')
}
$composeArgs += @('up', '-d', '--build')

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE"
}

Write-Host "System started: http://localhost:$((Get-Content .env | Where-Object { $_ -match '^FRONTEND_PORT=' } | Select-Object -First 1) -replace '^FRONTEND_PORT=', '')"
