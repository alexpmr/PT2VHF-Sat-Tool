# Painel web, Contratos

Especificação completa em [../openapi/painel-web.yaml](../openapi/painel-web.yaml). 🟢

| Método | Caminho | Autenticação | Respostas |
|--------|---------|--------------|-----------|
| GET | `/` (`?key=` na LAN) | localhost livre; LAN: chave → 303 + cookie | 200 HTML, 303, 401 |
| GET | `/api/status` | sessão | 200 JSON |
| GET | `/api/display.png` | sessão | 200 PNG, 404 |
| GET | `/map` | sessão | 200 HTML, 404 |
| POST | `/api/control` | sessão + `X-PT2VHF: 1` + mesma origem + PIN | 202, 400, 403, 429 |
| POST | outras rotas | — | 405 |

Corpo do controle: `{"action": "<ação permitida>", "value": <opcional>, "pin": "<PIN>"}`.
