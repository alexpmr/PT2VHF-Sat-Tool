# ADR 009: Rotor sempre inicia em DESLIGADO

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Mover a antena sem o operador perceber, ao abrir o app, pode danificar cabos ou o rotor.

## Decisão
Ao iniciar, o modo do rotor é sempre Desligado; Automático e Manual exigem ação do operador.

## Evidência
🟢 CONFIRMADO (commit 5297007 e `app.py`).

## Consequências
Pendente com o Alex: posição real da antena em leituras de flip (AZ 140° EL 175°).
