param([string]$TaskName = "IT Self-Service Assistant")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $root "scripts\run_server.bat"
if (-not (Test-Path $launcher)) { throw "Launcher não encontrado: $launcher" }
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$launcher`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Inicialização automática do assistente interno de TI" -RunLevel Highest -Force
Write-Host "Tarefa '$TaskName' instalada. Configure a conta de serviço aprovada pela TI no Agendador de Tarefas."
