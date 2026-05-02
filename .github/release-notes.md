<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O atualizador agora distingue a instalacao oficial de uma copia portatil do executavel, evitando fechar o app sem concluir a troca quando a atualizacao for detectada fora do caminho padrao.
- Campos de FTP copiados com Enter extra agora sao normalizados antes da conexao, reduzindo falhas durante o envio do backup.

## Melhorias

- Em instancias abertas fora da instalacao padrao, o check manual de update passa a abrir o instalador normalmente, sem encerrar a sessao atual do agente.
- O upload FTP remove `\r` e `\n` finais comuns de copia e cola em host, usuario, senha e diretorio remoto.

## Correcoes

- Corrigido o fluxo que entrava em loop de atualizacao quando o app era aberto por uma copia portatil em vez da versao instalada em `%LOCALAPPDATA%\Programs\VexNuvem Agent`.
- Corrigida a falha `an illegal newline character should not be contained` causada por quebras de linha invalidas em configuracoes do FTP.

## Observacoes

- Se voce estiver usando uma copia portatil, conclua a instalacao aberta pelo setup e depois passe a iniciar o agente pela versao instalada.

**Comparacao completa:** {{COMPARE_URL}}