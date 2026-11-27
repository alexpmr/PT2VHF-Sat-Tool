# ADR 004: Migrações de configuração aplicadas uma única vez

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Mudanças de padrão (ex.: LUČA-1, HADES-E2, IO-86) não podem reverter escolhas do usuário a cada abertura.

## Decisão
`config.py` guarda marcadores de migração já aplicada; cada migração roda uma vez e respeita valores já alterados pelo usuário.

## Evidência
🟡 INFERIDO a partir de `config.py` e dos commits v1.9.6/v1.9.7.

## Consequências
Nova migração precisa de chave própria; achado A4 (JSON corrompido impede a abertura) afeta este fluxo.
