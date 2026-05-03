@echo off
setlocal EnableDelayedExpansion

echo.
echo ================================================
echo   VexNuvem Agent - Publicar Nova Versao
echo ================================================
echo.
echo Este script faz commit das suas alteracoes e
echo envia para o GitHub, disparando o build e a
echo publicacao automatica do instalador.
echo.

REM --------------------------------------------------
REM Verifica se ha alteracoes no repositorio
REM --------------------------------------------------
git status --short
echo.

set HAS_CHANGES=0
for /f "delims=" %%l in ('git status --porcelain 2^>nul') do (
    set HAS_CHANGES=1
    goto :check_done
)
:check_done

if "!HAS_CHANGES!"=="0" (
    echo Nenhuma alteracao encontrada.
    echo.
    echo Se quiser re-publicar sem mudancas de codigo, use:
    echo   git commit --allow-empty -m "chore: re-publicar versao"
    echo   git push origin main
    echo.
    pause
    exit /b 0
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
if "!COMMIT_MSG!"=="" set COMMIT_MSG=chore: publica nova versao do agente

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
echo Pronto. O instalador sera publicado automaticamente em alguns minutos.
echo.
pause
exit /b 0
