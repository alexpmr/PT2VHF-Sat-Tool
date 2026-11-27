# Painel web

## Visão Geral
Servidor HTTP embutido que mostra o estado do SAT Tool (satélite, passagem, frequências, rotor, display e mapa)
num navegador do próprio computador ou da LAN e, se o operador permitir, aceita controles limitados com PIN. 🟢

## Responsabilidades
- Servir página, status JSON, imagem do display e mapa. 🟢
- Controlar acesso: localhost por padrão; LAN com chave na URL → cookie de sessão. 🟢
- Aceitar ações de controle validadas e com PIN, enfileiradas para a GUI. 🟢
- Criar regra de firewall opcional no Windows. 🟢

## Regras de Negócio
- Rede nunca pede TX/PTT nem comando CAT direto; tentativas são registradas e recusadas (R2). 🟢
- Ações permitidas: `select_satellite`, `auto_cat`, `ab`, `rx_only`, `rotor_track`, `rotor_park`, `rotor_stop`. 🟢
- Palavras proibidas na ação: `ptt`, `tx`, `transmit`, `key`, `cat_raw`, `command`. 🟢
- Controles exigem `X-PT2VHF: 1`, mesma origem e PIN (PBKDF2-SHA256, 120.000 iterações). 🟢
- 5 PINs errados travam o IP por 5 min. 🟢
- Clientes fora de loopback/rede privada são recusados. 🟢
- Cookie `HttpOnly`, `SameSite=Strict`, validade `web_session_hours`. 🟢
- Em modo localhost não há checagem do cabeçalho `Host` (A5). 🟡

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | `GET /api/status` com o estado atual | Must | JSON com `controls` |
| RF-02 | Acesso LAN por chave → cookie | Must | Sem chave: 401 |
| RF-03 | `POST /api/control` com PIN | Should | 202 com ação na fila |
| RF-04 | Bloqueio após 5 PINs errados | Must | 429 por 5 min |
| RF-05 | Recusar ações de TX | Must | 403 e evento registrado |
| RF-06 | Regra de firewall opcional | Could | Perfil Privado, sub-rede local |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | CSP restritiva, sem cache | `web_ui.py` | 🟢 |
| Segurança | Corpo limitado a `MAX_BODY` | `web_ui.py: do_POST` | 🟢 |
| Segurança | Comparação de chave em tempo constante | `hmac.compare_digest` | 🟢 |
| Segurança | Proteção contra DNS rebinding em localhost | ausente | 🟡 (A5) |

## Critérios de Aceitação

```gherkin
Dado o painel em modo LAN e um celular na mesma rede
Quando abre o endereço com a chave
Então recebe um cookie de sessão e vê o status

Dado controles ligados
Quando um cliente envia {"action":"ptt"}
Então recebe 403 e o evento é registrado

Dado um cliente que errou o PIN 5 vezes
Quando tenta de novo
Então recebe 429 por 5 minutos

Dado o modo localhost
Quando chega um pedido com Host diferente de 127.0.0.1/localhost
Então o pedido é recusado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Status e acesso | Must | Função principal |
| Recusa de TX e PIN | Must | Segurança |
| Controles | Should | Opcional |
| Firewall | Could | Conveniência |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/web_ui.py` | `LocalStatusServer`, `client_allowed`, `pin_hash`, `valid_pin`, `validate_control`, `FORBIDDEN_WORDS`, `request_windows_firewall_rule` | 🟢 |
| `sat_tool/app.py` | `start_web_server`, `web_tick`, `apply_web_command`, `publish_web_snapshot` | 🟢 |
