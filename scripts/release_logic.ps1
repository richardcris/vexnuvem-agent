$ErrorActionPreference = 'Stop'

# Move para a raiz do projeto (pai de scripts/)
Set-Location (Split-Path $PSScriptRoot)

Write-Host ""
Write-Host "================================================"
Write-Host "  VexNuvem Agent - Publicar Nova Versao"
Write-Host "================================================"
Write-Host ""

try {
    # Le versao atual de pyproject.toml
    $toml = Get-Content 'pyproject.toml' -Raw
    $match = [regex]::Match($toml, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $match.Success) { throw "Versao nao encontrada em pyproject.toml" }

    $currentVersion = $match.Groups[1].Value
    $parts = $currentVersion -split '\.'
    $major = [int]$parts[0]
    $minor = if ($parts.Count -ge 2) { [int]$parts[1] } else { 0 }
    $patch = if ($parts.Count -ge 3) { [int]$parts[2] } else { 0 }

    Write-Host "Versao atual : $currentVersion"
    Write-Host ""
    Write-Host "Como deseja atualizar a versao?"
    Write-Host "  [1] Patch  $major.$minor.$($patch + 1)  (correcao ou melhoria pequena)"
    Write-Host "  [2] Minor  $major.$($minor + 1).0  (novo recurso)"
    Write-Host "  [3] Major  $($major + 1).0.0  (versao principal)"
    Write-Host "  [4] Manual  (digitar versao completa manualmente)"
    Write-Host ""
    $choice = Read-Host "Escolha (1/2/3/4, Enter = 1)"
    if (-not $choice) { $choice = "1" }

    switch ($choice) {
        "2" { $minor++; $patch = 0; $newVersion = "$major.$minor.$patch" }
        "3" { $major++; $minor = 0; $patch = 0; $newVersion = "$major.$minor.$patch" }
        "4" {
            $newVersion = Read-Host "Digite a versao completa (ex: 2.1.5)"
            if (-not $newVersion) { throw "Versao invalida." }
        }
        default { $patch++; $newVersion = "$major.$minor.$patch" }
    }

    Write-Host ""
    Write-Host "Nova versao: $newVersion"
    Write-Host ""

    # Atualiza arquivos de versao
    $utf8 = New-Object System.Text.UTF8Encoding $false
    Write-Host "Atualizando versao em pyproject.toml e __init__.py..."
    $toml = $toml -replace '(?m)^version\s*=\s*"[^"]*"', "version = `"$newVersion`""
    [System.IO.File]::WriteAllText((Join-Path (Get-Location) 'pyproject.toml'), $toml, $utf8)

    $initPath = Join-Path (Get-Location) 'src\vexnuvem_agent\__init__.py'
    $init = Get-Content $initPath -Raw
    $init = $init -replace '_BASE_VERSION\s*=\s*"[^"]*"', "_BASE_VERSION = `"$newVersion`""
    [System.IO.File]::WriteAllText($initPath, $init, $utf8)
    Write-Host "Versao atualizada para $newVersion."
    Write-Host ""

    # Exibe release notes
    $notesPath = '.github\release-notes.md'
    if (Test-Path $notesPath) {
        Write-Host "=== .github\release-notes.md ==="
        Write-Host ""
        Get-Content $notesPath | ForEach-Object { Write-Host $_ }
        Write-Host ""
        Write-Host "=== Fim das notas ==="
        Write-Host ""
        Write-Host "Edite .github\release-notes.md antes de continuar"
        Write-Host "se quiser alterar o texto que aparecera na release."
        Write-Host ""
    }

    # Mensagem de commit
    $commitMsg = Read-Host "Mensagem do commit (Enter = padrao)"
    if (-not $commitMsg) { $commitMsg = "chore: publica versao $newVersion" }

    Write-Host ""
    Write-Host "Commit : $commitMsg"
    Write-Host "Destino: origin/main"
    Write-Host ""
    $confirm = Read-Host "Confirmar publicacao? (S para prosseguir)"
    if ($confirm -notmatch '^[Ss]$') {
        Write-Host ""
        Write-Host "Publicacao cancelada."
        Read-Host "Pressione Enter para fechar"
        exit 0
    }

    Write-Host ""
    Write-Host "[1/3] Adicionando arquivos alterados..."
    git add -A
    if ($LASTEXITCODE -ne 0) { throw "Falha no git add" }

    Write-Host "[2/3] Fazendo commit..."
    git commit -m $commitMsg
    if ($LASTEXITCODE -ne 0) { throw "Falha no git commit. Verifique se ha algo para commitar." }

    Write-Host "[3/3] Enviando para o GitHub..."
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "Falha no git push. Verifique sua conexao e permissoes." }

    # Monta URL do repositorio
    $rawUrl = git remote get-url origin 2>$null
    $repoUrl = $rawUrl
    if ($repoUrl -match '^git@github\.com:(.+)\.git$') {
        $repoUrl = "https://github.com/$($Matches[1])"
    } elseif ($repoUrl -match '\.git$') {
        $repoUrl = $repoUrl -replace '\.git$', ''
    }

    Write-Host ""
    Write-Host "================================================"
    Write-Host "  Publicado com sucesso!"
    Write-Host ""
    Write-Host "  O GitHub Actions esta compilando o instalador."
    Write-Host "  Acompanhe em: $repoUrl/actions"
    Write-Host "================================================"
    Write-Host ""

    $openBrowser = Read-Host "Abrir pagina de Actions no navegador? (S/N)"
    if ($openBrowser -match '^[Ss]$') {
        Start-Process "$repoUrl/actions"
    }

    Write-Host ""
    Write-Host "Pronto. O instalador $newVersion sera publicado em alguns minutos."
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERRO: $_" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Pressione Enter para fechar"
