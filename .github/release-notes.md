<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- O sistema de atualizacao agora identifica corretamente a release mais recente publicada no GitHub, evitando respostas stale do endpoint antigo.
- As notas exibidas em "Novidades desta versao" passaram a ser definidas por este arquivo e publicadas automaticamente na release {{VERSION}}.

## Melhorias

- O workflow de release monta automaticamente o link de comparacao entre a versao anterior e a atual.
- O script local de build do executavel agora funciona mesmo quando versao e repositorio nao sao informados manualmente.

## Correcoes

- Corrigida a verificacao de atualizacoes para buscar a release mais recente pela lista de releases publicadas.
- Corrigida a chamada para gerar metadados de build no script `scripts/build_exe.ps1`.

## Observacoes

- Antes da proxima publicacao, edite este arquivo para atualizar os itens acima com as novidades da nova versao.

**Comparacao completa:** {{COMPARE_URL}}