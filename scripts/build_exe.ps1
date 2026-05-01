param(
    [string]$Python = "python",
    [string]$BuildVersion = "",
    [string]$GitHubRepository = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BuildMetaPath = Join-Path $Root "src\vexnuvem_agent\_build_meta.py"
$BuildMetaBackup = $null

function Invoke-NativeCommand {
    param(
        [scriptblock]$Command,
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description falhou com codigo de saida $LASTEXITCODE."
    }
}

Push-Location $Root
try {
    if (Test-Path $BuildMetaPath) {
        $BuildMetaBackup = Join-Path $env:TEMP ("vexnuvem-build-meta-" + [guid]::NewGuid().ToString() + ".py")
        Copy-Item $BuildMetaPath $BuildMetaBackup -Force
    }

    Invoke-NativeCommand -Description "Atualizacao do pip" -Command { & $Python -m pip install --upgrade pip }
    Invoke-NativeCommand -Description "Instalacao das dependencias" -Command { & $Python -m pip install -r requirements.txt }
    $metadataJson = & $Python .\scripts\generate_build_metadata.py --version $BuildVersion --repository $GitHubRepository
    if ($LASTEXITCODE -ne 0) {
        throw "Geracao do metadata de build falhou com codigo de saida $LASTEXITCODE."
    }
    $metadata = $metadataJson | ConvertFrom-Json
    Invoke-NativeCommand -Description "Geracao dos assets de branding" -Command { & $Python .\scripts\generate_branding_assets.py }
    Invoke-NativeCommand -Description "Build do executavel com PyInstaller" -Command { & $Python -m PyInstaller --noconfirm --clean "VexNuvem Agent.spec" }

    Write-Host "Executavel gerado em dist/VexNuvem Agent/"
    Write-Host "Assets de branding gerados em build_assets/"
    Write-Host "Versao do build: $($metadata.build_version)"
}
finally {
    if ($BuildMetaBackup -and (Test-Path $BuildMetaBackup)) {
        Move-Item -Path $BuildMetaBackup -Destination $BuildMetaPath -Force
    }
    elseif (Test-Path $BuildMetaPath) {
        Remove-Item $BuildMetaPath -Force
    }

    Pop-Location
}
