$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [ScriptBlock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Write-Host "== Testes automatizados =="
Invoke-Checked { .\.venv\Scripts\python.exe -m pytest -q }

Write-Host "== Lint Python =="
Invoke-Checked { .\.venv\Scripts\python.exe -m ruff check app tests scripts migrations }

Write-Host "== Sintaxe JavaScript =="
Invoke-Checked { node --check app\static\js\app.js }

Write-Host "== Varredura de segredos =="
Invoke-Checked { .\.venv\Scripts\python.exe scripts\scan_secrets.py }

Write-Host "== Auditoria de dependencias =="
Invoke-Checked { .\.venv\Scripts\python.exe scripts\audit_dependencies.py }

Write-Host "Security check completed"
