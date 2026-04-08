Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Virtual environment belum ada. Jalankan: py -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "Menjalankan dashboard di http://127.0.0.1:8000/" -ForegroundColor Green
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

