<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O atualizador automatico agora deixa de esperar indefinidamente o encerramento do processo antigo antes de rodar o setup da nova versao.
- Isso evita o ciclo em que a notificacao de update aparecia, o app sumia, mas ao abrir de novo ele continuava na versao anterior e tentava atualizar outra vez.

## Melhorias

- O launcher de atualizacao agora segue para o instalador mesmo que o encerramento do processo antigo demore alem do esperado.
- O fluxo continua usando a instalacao padrao e a atualizacao do atalho da area de trabalho para manter a troca da versao mais confiavel.

## Correcoes

- Corrigido o bloqueio do launcher que podia ficar preso aguardando o PID do app antigo e impedir a execucao do setup silencioso.
- Corrigido o comportamento em que a mesma versao antiga voltava a abrir e reiniciava o ciclo de atualizacao apos a notificacao de upgrade.

## Observacoes

- Depois de atualizar para a 1.0.12, use o mesmo icone da area de trabalho e confirme se o app volta ja na nova versao, sem reiniciar o ciclo de update.

**Comparacao completa:** {{COMPARE_URL}}