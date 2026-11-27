# Painel web, Design Técnico

## Interface
Ver [contracts.md](contracts.md).

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `LocalStatusServer.__init__` | `(lan=False, port=8094, map_path=None, controls=False, pin_hash_value="", pin_salt="", ...)` | — | `web_ui.py:278` |
| `LocalStatusServer.start` | `()` | URL | thread `sat-web` |
| `validate_control` | `(payload)` | `(action, value)` | `PermissionError` para TX |
| `check_pin` | `(ip, pin)` | `ok`/`bad`/`locked` | bloqueio 5 min |

## Fluxo Principal
1. A GUI inicia o servidor em `127.0.0.1:8094` (ou `0.0.0.0` em LAN). 🟢
2. `publish_web_snapshot` atualiza `_snapshot` e o PNG do display. 🟢
3. O navegador consulta `/api/status` periodicamente. 🟢
4. Controles entram em `owner.commands`; `web_tick` esvazia a fila na thread da GUI. 🟢

## Fluxos Alternativos
- **Sem chave na LAN:** 401 com instrução. 🟢
- **Controles desligados:** 403. 🟢
- **Origem diferente:** 403. 🟢

## Dependências
- `http.server` da biblioteca padrão; `hmac`, `hashlib`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Servidor da biblioteca padrão | `ThreadingHTTPServer` | 🟢 |
| Comandos via fila consumida pela GUI | `owner.commands` (ADR 002) | 🟢 |
| PIN com PBKDF2 e sal | `pin_hash` (ADR 008) | 🟢 |

## Estado Interno
Snapshot, PNG, sessões, tentativas de PIN por IP, fila de comandos. 🟢

## Observabilidade
`owner._event` registra sessões, recusas e comandos. 🟢

## Riscos e Lacunas
- 🟡 A5: falta validar `Host` no modo localhost (DNS rebinding lê o status).
