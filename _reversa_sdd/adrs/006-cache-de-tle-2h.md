# ADR 006: Cache de 2 horas para TLE/OMM do CelesTrak

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
O CelesTrak limita requisições repetidas e bloqueia clientes abusivos.

## Decisão
Os elementos baixados ficam em cache local por 2 h; abaixo disso o app usa o cache; falha de rede cai para o último cache válido.

## Evidência
🟢 CONFIRMADO (`catalog.py`).

## Consequências
User-Agent ainda informa 1.3.0 (achado A6): deveria seguir a versão do app.
