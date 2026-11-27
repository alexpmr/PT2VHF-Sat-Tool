# ADR 008: Painel web na LAN protegido por PIN

**Status:** aceita (retroativa, extraída pelo Reversa em 27/11/2026)

## Contexto
Acesso pela LAN (como no APRS Client) expõe controle do rádio e rotor a outros dispositivos.

## Decisão
O servidor (`LocalStatusServer`, porta 8094) escuta só em localhost por padrão; o modo LAN aceita apenas clientes de redes privadas (`client_allowed`). Ações de controle exigem PIN (hash com sal) e passam por `validate_control`, que recusa qualquer ação ligada a TX.

## Evidência
🟢 CONFIRMADO (`web_ui.py`, commit 26a2e0c).

## Consequências
Achado A5: sem checagem de Host em modo localhost, há risco de DNS rebinding.
