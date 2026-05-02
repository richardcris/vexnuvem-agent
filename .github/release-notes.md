<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O processo de atualizacao agora força a instalacao na pasta padrao do VexNuvem Agent, evitando que o setup reaproveite um caminho antigo e deixe a maquina abrindo a copia errada depois do update.
- O fluxo de upgrade tambem passa a recriar o atalho da area de trabalho para apontar para a versao instalada correta apos a atualizacao.

## Melhorias

- Atualizacoes silenciosas agora executam o instalador com a pasta instalada padrao e com a tarefa de atalho da area de trabalho habilitada.
- Quando a atualizacao e aberta manualmente, o setup ja inicia apontando para a pasta instalada correta do agente.

## Correcoes

- Corrigido o ciclo em que a maquina instalava a nova versao, mas continuava abrindo uma copia antiga e oferecendo update de novo.
- Corrigido o fluxo que podia manter o atalho do desktop apontando para uma instancia desatualizada apos a instalacao.

## Observacoes

- Depois de atualizar para a 1.0.10, teste o mesmo atalho da area de trabalho usado antes para confirmar que ele abre a instalacao atualizada sem voltar para o ciclo de update.

**Comparacao completa:** {{COMPARE_URL}}