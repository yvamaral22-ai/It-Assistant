param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceAccount
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dataPath = (Resolve-Path (Join-Path $root "data")).Path
if (-not $dataPath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "O diretório de dados não pertence ao workspace esperado."
}

try {
    ([System.Security.Principal.NTAccount]$ServiceAccount).Translate(
        [System.Security.Principal.SecurityIdentifier]
    ) | Out-Null
} catch {
    throw "A conta de serviço '$ServiceAccount' não foi encontrada."
}

Write-Host "Restringindo dados a $ServiceAccount, Administradores e SYSTEM..."
& icacls $dataPath /inheritance:r /grant:r `
    "${ServiceAccount}:(OI)(CI)M" `
    "*S-1-5-32-544:(OI)(CI)F" `
    "*S-1-5-18:(OI)(CI)F" /T /C
if ($LASTEXITCODE -ne 0) { throw "Falha ao proteger o diretório de dados." }

$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
    & icacls $envPath /inheritance:r /grant:r `
        "${ServiceAccount}:R" `
        "*S-1-5-32-544:F" `
        "*S-1-5-18:F"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao proteger o arquivo .env." }
}

Write-Host "Permissões locais endurecidas com sucesso."
