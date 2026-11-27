# Permissões — PT2VHF SAT Tool

> Reversa (Detetive), 27/11/2026. Não há contas de usuário. Os "papéis" são de onde vem a ação. 🟢

| Ação | Operador na janela | Navegador local (127.0.0.1) | Navegador na LAN (chave/cookie) | Navegador na LAN sem chave | IP público |
|---|---|---|---|---|---|
| Ver status, passagens, display, mapa | ✅ | ✅ | ✅ | ❌ 401 | ❌ 403 |
| Escolher satélite, Auto CAT, A/B, RX ONLY | ✅ | 🔒 PIN + controles ligados | 🔒 PIN + controles ligados | ❌ | ❌ |
| Rotor: rastrear / estacionar / PARAR | ✅ | 🔒 PIN | 🔒 PIN | ❌ | ❌ |
| TX / PTT / comando CAT direto | ❌ nunca | ❌ nunca | ❌ nunca | ❌ | ❌ |
| Configurações, OTA, PIN, chave | ✅ | ❌ | ❌ | ❌ | ❌ |
| Regra de firewall do Windows | ✅ (UAC) | ❌ | ❌ | ❌ | ❌ |

Detalhes:
- 🟢 Controles remotos desligados por padrão (`web_controls = False`).
- 🟢 POST de controle exige cabeçalho `X-PT2VHF: 1` e `Origin` igual ao `Host`.
- 🟢 PIN de 4 a 12 dígitos, guardado como PBKDF2-SHA256 com sal; 5 erros por IP = 5 min de bloqueio.
- 🟢 "Nova chave" invalida links e sessões abertas.
- 🟡 No modo só-localhost não há checagem do cabeçalho `Host` (ver achado A5 em code-analysis.md).
