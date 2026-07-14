param([string]$TaskName = "IT Self-Service Assistant - Backup")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\backup_database.py"
if (-not (Test-Path $python)) { throw "Ambiente virtual não encontrado: $python" }
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Backup diário do banco do assistente de TI" -RunLevel Highest -Force
Write-Host "Tarefa de backup instalada para 02:00. Revise a conta e o destino conforme a política da empresa."
