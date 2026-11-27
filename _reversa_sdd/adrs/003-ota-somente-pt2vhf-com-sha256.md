# ADR 003: Atualização OTA só por www.pt2vhf.com com SHA-256

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Regra do mantenedor: downloads e atualizações oficiais só pelo site; GitLab aposentado; GitHub Releases só como origem dos arquivos do CI.

## Decisão
`update.php?product=sat` informa versão, URL e SHA-256; o cliente baixa do pt2vhf.com, confere o hash antes de instalar e conta o download uma única vez em `download.php`. OTA automático vem ligado por padrão e é configurável.

## Evidência
🟢 CONFIRMADO (`sat_tool/updater.py`, commits a343ea9, d4bea75, cccd7da).

## Consequências
Publicar versão exige `updates.json` com tamanho e SHA-256 corretos; um hash errado bloqueia a atualização nos clientes.
