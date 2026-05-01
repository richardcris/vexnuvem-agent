param(
    [string]$Python = "python",
    [switch]$SkipExeBuild,
    [string]$BuildVersion = "",
    [string]$GitHubRepository = "",
    [string]$OutputBaseFilename = ""
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

function Get-InnoSetupCompiler {
    $fromPath = Get-Command iscc -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $candidates = @(
        (Join-Path $Root ".tools\Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    return $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

Push-Location $Root
try {
    $installerScript = Join-Path $Root "installer\VexNuvem Agent.iss"
    if (Test-Path $BuildMetaPath) {
        $BuildMetaBackup = Join-Path $env:TEMP ("vexnuvem-installer-build-meta-" + [guid]::NewGuid().ToString() + ".py")
        Copy-Item $BuildMetaPath $BuildMetaBackup -Force
    }

    $metadataJson = & $Python .\scripts\generate_build_metadata.py --version $BuildVersion --repository $GitHubRepository
    if ($LASTEXITCODE -ne 0) {
        throw "Geracao do metadata de build falhou com codigo de saida $LASTEXITCODE."
    }
    $metadata = $metadataJson | ConvertFrom-Json
    $resolvedVersion = [string]$metadata.build_version
    $resolvedRepository = [string]$metadata.github_repository
    $resolvedOutputBaseFilename = if ($OutputBaseFilename) { $OutputBaseFilename } else { "VexNuvem-Agent-Setup-$resolvedVersion" }

    if (-not $SkipExeBuild) {
        Invoke-NativeCommand -Description "Build do executavel" -Command {
            & powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -Python $Python -BuildVersion $resolvedVersion -GitHubRepository $resolvedRepository
        }
    }
    else {
        Invoke-NativeCommand -Description "Geracao dos assets de branding" -Command { & $Python .\scripts\generate_branding_assets.py }
    }

    $isccPath = Get-InnoSetupCompiler
    if (-not $isccPath) {
        throw "Inno Setup 6 nao encontrado. Instale o compilador ISCC.exe e rode o script novamente."
    }

    Invoke-NativeCommand -Description "Build do instalador com Inno Setup" -Command {
        & $isccPath "/DAppVersion=$resolvedVersion" "/DOutputBaseFilename=$resolvedOutputBaseFilename" $installerScript
    }
    Write-Host "Instalador gerado em dist/installer/"
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