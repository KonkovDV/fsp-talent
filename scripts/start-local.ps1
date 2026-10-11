# Локальный запуск на Windows. Те же три шага, что у make demo.
# Из папки проекта:
#   powershell -ExecutionPolicy Bypass -File scripts\start-local.ps1
# Письма остаются в Mailpit (http://localhost:8025) и не уходят в Gmail.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'Docker не найден. Установите Docker Desktop, запустите его и повторите команду.'
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host 'Создан .env из примера. Править его не нужно.'
}

docker compose up -d --build --wait
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Demo data is loaded by the demo-seed service; --wait above already waited for it.

Write-Host ''
Write-Host 'Готово.'
Write-Host 'Сайт:      http://localhost'
Write-Host 'API:       http://localhost/docs'
Write-Host 'Письма:    http://localhost:8025'
Write-Host '           Код подтверждения лежит здесь, а не в Gmail.'
Write-Host 'Работодатель: hr@sibcode.demo'
Write-Host 'Кандидат:     fsp001@demo.talent'
Write-Host 'Пароль:       demo12345'
