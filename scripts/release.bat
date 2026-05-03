@echo off
setlocal EnableDelayedExpansion

echo.
echo ================================================
echo   VexNuvem Agent - Publicar Nova Versao
echo ================================================
echo.

REM --------------------------------------------------
REM Le a versao atual de pyproject.toml via PowerShell
REM --------------------------------------------------
for /f "delims=" %%v in ('powershell -NoProfile -Command ^
    "(Get-Content pyproject.toml) | Where-Object { $_ -match '^version\s*=' } | ForEach-Object { ($_ -split '=',2)[1].Trim().Trim('\"') } | Select-Object -First 1"') do (
    set CURRENT_VERSION=%%v
)

if "!CURRENT_VERSION!"=="" (
    echo ERRO: Nao foi possivel ler a versao de pyproject.toml.
    pause
    exit /b 1
)

REM Separa major e minor (patch e gerado pelo numero do run do GitHub Actions)
for /f "tokens=1,2 delims=." %%a in ("!CURRENT_VERSION!") do (
    set VER_MAJOR=%%a
    set VER_MINOR=%%b
)

echo Versao atual : !CURRENT_VERSION! (o patch sera o numero do run do GitHub)
echo.
echo Como deseja atualizar a versao?
echo   [1] Manter  !VER_MAJOR!.!VER_MINOR!  (so patch muda pelo run do GitHub)
echo   [2] Minor   !VER_MAJOR!.X  (incrementar minor)
echo   [3] Major   X.0  (nova versao principal)
echo   [4] Manual  (digitar major.minor manualmente)
echo.
set /p VER_CHOICE=Escolha (1/2/3/4, Enter = 1): 
if "!VER_CHOICE!"=="" set VER_CHOICE=1

if "!VER_CHOICE!"=="2" (
    set /a VER_MINOR=!VER_MINOR!+1
    set NEW_BASE=!VER_MAJOR!.!VER_MINOR!
)
if "!VER_CHOICE!"=="3" (
    set /a VER_MAJOR=!VER_MAJOR!+1
    set VER_MINOR=0
    set NEW_BASE=!VER_MAJOR!.!VER_MINOR!
)
if "!VER_CHOICE!"=="4" (
    set /p NEW_BASE=Digite a nova versao base (ex: 2.1): 
    if "!NEW_BASE!"=="" (
        echo Versao invalida.
        pause
        exit /b 1
    )
)
if "!VER_CHOICE!"=="1" set NEW_BASE=!VER_MAJOR!.!VER_MINOR!

echo.
echo Nova versao base: !NEW_BASE!.^<run^>  (patch definido pelo GitHub Actions)
echo.

REM --------------------------------------------------
REM Atualiza pyproject.toml e __init__.py se mudou
REM --------------------------------------------------
set OLD_BASE=!VER_MAJOR!.0
REM Compara a base atual com a nova (usando apenas major.minor)
for /f "tokens=1,2 delims=." %%a in ("!CURRENT_VERSION!") do set CUR_BASE=%%a.%%b

if not "!NEW_BASE!"=="!CUR_BASE!" (
    echo Atualizando versao em pyproject.toml e __init__.py...

    powershell -NoProfile -Command ^
        "$content = Get-Content 'pyproject.toml' -Raw; $content = $content -replace 'version\s*=\s*""[^""]*""', 'version = ""!NEW_BASE!.0""'; Set-Content 'pyproject.toml' $content -NoNewline"

    powershell -NoProfile -Command ^
        "$content = Get-Content 'src\vexnuvem_agent\__init__.py' -Raw; $content = $content -replace '_BASE_VERSION\s*=\s*""[^""]*""', '_BASE_VERSION = ""!NEW_BASE!.0""'; Set-Content 'src\vexnuvem_agent\__init__.py' $content -NoNewline"

    echo Versao atualizada para !NEW_BASE!.0 nos arquivos locais.
    echo.
)

REM --------------------------------------------------
REM Exibe as notas da proxima versao
REM --------------------------------------------------
echo === .github\release-notes.md ===
echo.
type ".github\release-notes.md"
echo.
echo === Fim das notas ===
echo.
echo Edite .github\release-notes.md antes de continuar
echo se quiser alterar o texto que aparecera na release.
echo.

REM --------------------------------------------------
REM Pede mensagem de commit
REM --------------------------------------------------
set /p COMMIT_MSG=Mensagem do commit (Enter = padrao): 
if "!COMMIT_MSG!"=="" set COMMIT_MSG=chore: publica versao !NEW_BASE!

echo.
echo Commit : !COMMIT_MSG!
echo Destino: origin/main
echo.
set /p CONFIRM=Confirmar publicacao? (S para prosseguir, qualquer outra tecla cancela): 
if /I not "!CONFIRM!"=="S" (
    echo.
    echo Publicacao cancelada.
    pause
    exit /b 0
)

echo.

REM --------------------------------------------------
REM git add + commit + push
REM --------------------------------------------------
echo [1/3] Adicionando arquivos alterados...
git add -A
if errorlevel 1 (
    echo.
    echo ERRO: Falha no git add.
    pause
    exit /b 1
)

echo [2/3] Fazendo commit...
git commit -m "!COMMIT_MSG!"
if errorlevel 1 (
    echo.
    echo ERRO: Falha no git commit. Verifique se ha algo para commitar.
    pause
    exit /b 1
)

echo [3/3] Enviando para o GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo ERRO: Falha no git push. Verifique sua conexao e permissoes.
    pause
    exit /b 1
)

REM --------------------------------------------------
REM Sucesso - tenta abrir a pagina de Actions
REM --------------------------------------------------
echo.
echo ================================================
echo   Publicado com sucesso!
echo.
echo   O GitHub Actions esta compilando o instalador.
echo   Acompanhe o progresso em:
echo.
for /f "tokens=*" %%u in ('git remote get-url origin 2^>nul') do (
    set RAW_URL=%%u
)

REM Converte URL SSH (git@github.com:user/repo.git) para HTTPS
set REPO_URL=!RAW_URL!
if "!REPO_URL:~0,15!"=="git@github.com:" (
    set REPO_URL=https://github.com/!REPO_URL:~15!
)
REM Remove .git do final
if "!REPO_URL:~-4!"==".git" set REPO_URL=!REPO_URL:~0,-4!

echo   !REPO_URL!/actions
echo ================================================
echo.

set /p OPEN_BROWSER=Abrir pagina de Actions no navegador? (S/N): 
if /I "!OPEN_BROWSER!"=="S" (
    start "" "!REPO_URL!/actions"
)

echo.
echo Pronto. O instalador !NEW_BASE!.^<run^> sera publicado automaticamente em alguns minutos.
echo.
pause
exit /b 0
