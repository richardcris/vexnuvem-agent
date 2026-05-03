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
    $minor = [int]$parts[1]
    $curBase = "$major.$minor"

    Write-Host "Versao atual : $currentVersion (o patch sera o numero do run do GitHub)"
    Write-Host ""
    Write-Host "Como deseja atualizar a versao?"
    Write-Host "  [1] Manter  $major.$minor  (so patch muda pelo run do GitHub)"
    Write-Host "  [2] Minor   $major.X  (incrementar minor)"
    Write-Host "  [3] Major   X.0  (nova versao principal)"
    Write-Host "  [4] Manual  (digitar major.minor manualmente)"
    Write-Host ""
    $choice = Read-Host "Escolha (1/2/3/4, Enter = 1)"
    if (-not $choice) { $choice = "1" }

    switch ($choice) {
        "2" { $minor++; $newBase = "$major.$minor" }
        "3" { $major++; $minor = 0; $newBase = "$major.$minor" }
        "4" {
            $newBase = Read-Host "Digite a nova versao base (ex: 2.1)"
            if (-not $newBase) { throw "Versao invalida." }
        }
        default { $newBase = "$major.$minor" }
    }

    Write-Host ""
    Write-Host "Nova versao base: $newBase.<run>  (patch definido pelo GitHub Actions)"
    Write-Host ""

    # Atualiza arquivos se a base mudou
    $utf8 = New-Object System.Text.UTF8Encoding $false
    if ($newBase -ne $curBase) {
        Write-Host "Atualizando versao em pyproject.toml e __init__.py..."
        $toml = $toml -replace '(?m)^version\s*=\s*"[^"]*"', "version = `"$newBase.0`""
        [System.IO.File]::WriteAllText((Join-Path (Get-Location) 'pyproject.toml'), $toml, $utf8)

        $initPath = Join-Path (Get-Location) 'src\vexnuvem_agent\__init__.py'
        $init = Get-Content $initPath -Raw
        $init = $init -replace '_BASE_VERSION\s*=\s*"[^"]*"', "_BASE_VERSION = `"$newBase.0`""
        [System.IO.File]::WriteAllText($initPath, $init, $utf8)
        Write-Host "Versao atualizada para $newBase.0 nos arquivos locais."
        Write-Host ""
    }

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
    if (-not $commitMsg) { $commitMsg = "chore: publica versao $newBase" }

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
    Write-Host "Pronto. O instalador $newBase.<run> sera publicado em alguns minutos."
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERRO: $_" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Pressione Enter para fechar"
