# ADR 007: Frequências do SatNOGS numa única consulta

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Consultar transmissores satélite a satélite gerava dezenas de requisições e lentidão (v1.9.7).

## Decisão
O app baixa a lista completa de transmissores uma vez e filtra localmente.

## Evidência
🟢 CONFIRMADO (commit 88b299d).

## Consequências
Atualizações de frequências dependem de uma resposta grande; precisa de tratamento de falha parcial.
