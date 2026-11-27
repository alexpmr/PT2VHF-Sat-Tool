# ADR 002: Rede, TLE e E/S serial fora da thread da interface

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Downloads (CelesTrak, SatNOGS, OTA), cálculos de passagens e consultas seriais travavam a janela PySide6 (histórico: v1.8.0 'TLE em segundo plano').

## Decisão
Trabalhos demorados rodam em `threading.Thread`/workers e devolvem resultado à interface por sinais Qt ou `QTimer`; a GUI só é tocada na thread principal.

## Evidência
🟢 CONFIRMADO (commit d058788 e padrão de workers em `app.py`).

## Consequências
Toda nova integração de rede ou serial deve seguir o mesmo padrão; achado A1 (gravador do SDR fora do lock) mostra o risco de estado compartilhado entre threads.
