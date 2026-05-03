$ErrorActionPreference = 'Stop'

# Move para a raiz do projeto (pai de scripts/)
Set-Location (Split-Path $PSScriptRoot)

Write-Host ""
Write-Host "================================================"
Write-Host "  VexNuvem Agent - Gerar Instalador Local"
Write-Host "================================================"
Write-Host ""

try {
    # Le versao atual de pyproject.toml
    $toml = Get-Content 'pyproject.toml' -Raw
    $match = [regex]::Match($toml, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $match.Success) { throw "Versao nao encontrada em pyproject.toml" }

    $currentVersion = $match.Groups[1].Value
    $parts = $currentVersion -split '\.'
    $parts[-1] = [string]([int]$parts[-1] + 1)
    $newVersion = $parts -join '.'

    Write-Host "Versao atual  : $currentVersion"
    Write-Host "Nova versao   : $newVersion"
    Write-Host ""

    # Atualiza pyproject.toml
    $toml = $toml -replace '(?m)^version\s*=\s*"[^"]*"', "version = `"$newVersion`""
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) 'pyproject.toml'), $toml, $utf8)

    # Atualiza __init__.py
    $initPath = Join-Path (Get-Location) 'src\vexnuvem_agent\__init__.py'
    $init = Get-Content $initPath -Raw
    $init = $init -replace '_BASE_VERSION\s*=\s*"[^"]*"', "_BASE_VERSION = `"$newVersion`""
    [System.IO.File]::WriteAllText($initPath, $init, $utf8)

    Write-Host "Gerando instalador versao $newVersion..."
    Write-Host ""

    & "$PSScriptRoot\build_installer.ps1" `
        -Python "c:/Users/richa/OneDrive/Desktop/Novo agente/.venv/Scripts/python.exe" `
        -BuildVersion $newVersion

    if ($LASTEXITCODE -ne 0) { throw "build_installer.ps1 falhou com codigo $LASTEXITCODE" }

    Write-Host ""
    Write-Host "================================================"
    Write-Host "  Instalador gerado com sucesso!"
    Write-Host "  dist\installer\VexNuvem-Agent-Setup-$newVersion.exe"
    Write-Host "================================================"
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERRO: $_" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Pressione Enter para fechar"
