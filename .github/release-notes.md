<!--
Edite este arquivo antes de publicar a proxima versao.
O workflow substitui automaticamente:
- {{VERSION}}
- {{TAG}}
- {{REPOSITORY}}
- {{COMPARE_URL}}
-->

## Novidades desta versao

- Secao de Servidores FTP agora e protegida por senha de desenvolvedor: os botoes Novo Servidor, Editar e Remover so funcionam apos autenticacao.
- Secao de Monitoramento Remoto (API Base44) tambem e protegida por senha de desenvolvedor: os campos ficam completamente ocultos ate que a senha seja informada.
- Ao bloquear ou salvar, os campos de endpoint e token da API sao limpos da tela para que as informacoes nao fiquem expostas.

## Melhorias

- Processo de atualizacao automatica corrigido: o app agora reabre corretamente apos instalar a nova versao.
- Eliminado o loop infinito de download quando o instalador nao concluia a atualizacao.
- O script de atualizacao aguarda o processo encerrar completamente antes de rodar o instalador, evitando conflito de arquivos em uso.
- Script de build local detecta automaticamente o ambiente Python (`.venv`) sem precisar de caminho fixo.

## Correcoes

- Corrigido o problema em que o app nao reabria automaticamente apos a atualizacao silenciosa.
- Corrigido o loop onde, ao abrir o atalho da area de trabalho, o app voltava a baixar e instalar a mesma versao.
- Corrigido o caminho Python hardcoded no script de build local que impedia gerar instalador em outras maquinas.

**Comparacao completa:** {{COMPARE_URL}}