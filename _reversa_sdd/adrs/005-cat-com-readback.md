# ADR 005: CAT confirma a frequência por leitura de volta

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Rádios diferentes aceitam comandos silenciosamente ou com atraso; Doppler sem confirmação acumula erro.

## Decisão
Após escrever, o driver lê a frequência quando o protocolo permite e só atualiza o estado interno com o valor lido; a correção Doppler tem limiar mínimo para não inundar a serial.

## Evidência
🟢 CONFIRMADO para o TS-2000 (`cat.py`) e 🟡 INFERIDO para os demais drivers (`rigs.py`); ICOM/Kenwood/WiSpDDE sem teste em hardware real.

## Consequências
Drivers novos devem implementar leitura; rádios sem leitura ficam marcados como não confirmados.
