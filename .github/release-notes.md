<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O agente agora preserva o token da API nas configuracoes e consegue autenticar chamadas de monitoramento remoto quando a integracao exigir Bearer token.
- Esta atualizacao tambem melhora o fluxo de instalacao automatica, reabrindo a versao instalada ao final do setup silencioso.

## Melhorias

- O campo "Token API" ficou visivel em `Configuracoes > Monitoramento remoto`, evitando que ambientes novos fiquem offline por falta de autenticacao.
- O launcher de atualizacao agora prioriza a reabertura do executavel instalado em `%LOCALAPPDATA%\Programs\VexNuvem Agent`.

## Correcoes

- Corrigido o envio do cabecalho `Authorization` para endpoints Base44 `.../functions` quando houver token configurado.
- Corrigido o salvamento das configuracoes para nao apagar o token da API ao testar ou salvar a tela de monitoramento remoto.

## Observacoes

- Depois de atualizar, confirme na outra maquina se o endpoint e o token da API continuam preenchidos em `Configuracoes > Monitoramento remoto`.

**Comparacao completa:** {{COMPARE_URL}}