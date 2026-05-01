# VexNuvem Agent

VexNuvem Agent e um software desktop em Python para backup automatico e manual, com interface moderna em PySide6, envio via FTP com failover, compressao inteligente, historico local e integracao com API de monitoramento.

## Recursos

- Dashboard com status ao vivo, metricas e disparo manual de backup.
- Cadastro de arquivos e pastas com filtros por extensao, incluindo `.FDB`, `.SQL` e `.ZIP`.
- Agendamento por horario fixo, intervalo de horas ou dias especificos da semana.
- Compressao inteligente em `.zip`, evitando recompressao pesada para arquivos ja compactados.
- Upload FTP para varios servidores com failover automatico e retentativas.
- Credenciais criptografadas localmente com `cryptography` e chave persistida no `keyring` quando disponivel.
- Historico em SQLite com tamanho, horario, status e detalhes de erro.
- Envio opcional de eventos para API REST tipo Base44 e consulta de status remoto por `agent_id`.
- Verificacao automatica de atualizacoes ao abrir o app usando GitHub Releases.
- Modo em segundo plano via bandeja do sistema.
- Monitor anti-ransomware em tempo real nas pastas protegidas, com alerta de atividade suspeita e disparo opcional de verificacao rapida do Microsoft Defender.

## Estrutura

- `main.py`: ponto de entrada rapido.
- `src/vexnuvem_agent`: pacote principal da aplicacao.
- `scripts/build_exe.ps1`: geracao de executavel com PyInstaller.

## Instalacao

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Execucao

```powershell
python main.py
```

## Build do executavel

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

O executavel sera criado em `dist/VexNuvem Agent/`.
O build agora gera automaticamente os assets de branding em `build_assets/` e aplica a logo como icone do executavel.

## Build do instalador

O instalador do Windows usa Inno Setup 6.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1 -Python .\.venv\Scripts\python.exe -BuildVersion 1.0.1 -GitHubRepository usuario/repositorio
```

Se o Inno Setup nao estiver instalado, o script interrompe com uma mensagem pedindo a instalacao do `ISCC.exe`.
O instalador sera criado em `dist/installer/` com a logo aplicada no assistente e no atalho do programa.

## Atualizacoes automaticas

- O app consulta a release mais recente do GitHub ao abrir, compara a versao instalada e avisa quando existe um instalador novo.
- No app instalado pelo setup, quando existir uma versao mais nova o agente baixa o instalador, fecha a versao atual e aplica a atualizacao silenciosamente.
- Configure em "Atualizacoes automaticas" o repositorio no formato `usuario/repositorio`.
- Se o repositorio GitHub for privado, configure tambem um token pessoal com permissao `Contents: Read` para consultar a release e baixar o instalador.
- Se o build for publicado pelo workflow do GitHub, esse repositorio pode ser embutido automaticamente no executavel.

## Workflow GitHub

- O arquivo `.github/workflows/release.yml` publica uma nova release a cada push na branch `main`.
- O workflow gera uma versao no formato `MAJOR.MINOR.RUN_NUMBER`, monta o instalador no Windows e anexa o `.exe` da instalacao na release.
- Edite o arquivo `.github/release-notes.md` antes de publicar a proxima versao para definir o texto que aparecera em "Novidades desta versao" apos a atualizacao.
- O upload da release usa o `GITHUB_TOKEN` padrao do Actions, entao nao precisa criar segredo extra para publicar.
- Para esse workflow funcionar no GitHub, este projeto precisa estar na raiz de um repositorio proprio, com a pasta `.github/workflows` versionada nesse mesmo repo.

## Primeiro push no GitHub

- Esta pasta agora pode ser usada como um repositorio Git independente.
- O remote `origin` esperado e `https://github.com/richardcris/vexnuvem-agent.git`.
- Se esse repositorio continuar privado, gere um token de leitura no GitHub e informe-o no app em `Configuracoes > Atualizacoes automaticas > Token GitHub`.
- Crie esse repositorio vazio no GitHub e depois publique com:

```powershell
git add .
git commit -m "Initial VexNuvem Agent release setup"
git push -u origin main
```

- Depois do primeiro push na branch `main`, o workflow de release passa a gerar e publicar automaticamente o instalador nas Releases.

## Persistencia local

O VexNuvem grava dados em `%APPDATA%\VexNuvem`:

- `config.json`: configuracoes da instalacao.
- `history.sqlite3`: historico de execucoes.
- `archives/`: backups compactados locais.
- `logs/`: logs rotativos da aplicacao.

## Observacoes

- Configure pelo menos um servidor FTP valido antes do primeiro backup.
- A integracao com a API e opcional. Informe o endpoint base, por exemplo `https://SUA_URL/api`.
- Para apps Base44 Functions, tambem e aceito um endpoint como `https://SEU_APP.base44.app/functions`.
- Em REST generico o agente usa `POST /backup` e `GET /status/{client_id}`.
- Em Base44 Functions o agente tenta `POST /receiveBackup` e `GET /clientStatus` com `client_id` como parametro, com fallback para formatos proximos.
- Cada instalacao recebe um `Client ID` unico automaticamente no primeiro uso.
- A protecao anti-ransomware e uma camada defensiva de monitoramento e resposta. Ela ajuda a detectar sinais tipicos de criptografia maliciosa e pode acionar o Microsoft Defender, mas nao substitui um antivirus completo do sistema.
