<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O agente agora envia um heartbeat automatico para a Base44 ao abrir e durante a execucao, fazendo o cliente aparecer como `online` no painel remoto.
- Esta atualizacao tambem mantem a correcao do token da API e melhora o fluxo de instalacao automatica, reabrindo a versao instalada ao final do setup silencioso.

## Melhorias

- O campo "Token API" ficou visivel em `Configuracoes > Monitoramento remoto`, evitando que ambientes novos fiquem offline por falta de autenticacao.
- O app renova o status remoto periodicamente sem depender da execucao de um backup completo.
- O launcher de atualizacao agora prioriza a reabertura do executavel instalado em `%LOCALAPPDATA%\Programs\VexNuvem Agent`.

## Correcoes

- Corrigido o envio do cabecalho `Authorization` para endpoints Base44 `.../functions` quando houver token configurado.
- Corrigido o salvamento das configuracoes para nao apagar o token da API ao testar ou salvar a tela de monitoramento remoto.
- Corrigido o fluxo que deixava `last_connection` nulo e mantinha o cliente como `offline` em maquinas novas sem backup executado.

## Observacoes

- Depois de atualizar, abra o agente na outra maquina e aguarde alguns segundos para o heartbeat inicial atualizar o status remoto.

**Comparacao completa:** {{COMPARE_URL}}