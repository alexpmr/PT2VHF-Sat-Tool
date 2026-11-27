# ADR 001: O app nunca transmite pelo rádio

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
O SAT Tool controla rádios por CAT apenas para sintonia (Doppler), modo e leitura. Um erro de software que acione PTT pode causar emissão indevida em faixa de satélite.

## Decisão
Nenhum driver envia comando de PTT/TX. Os drivers de `sat_tool/rigs.py` só escrevem frequência, modo e VFO/split; a leitura de estado é passiva.

## Evidência
🟢 CONFIRMADO pelo código dos drivers (ausência de comandos de TX) e pela regra R1 de `domain.md`.

## Consequências
Recursos que dependam de TX (beacon, telecomando) ficam fora de escopo; qualquer mudança exige ADR nova.
