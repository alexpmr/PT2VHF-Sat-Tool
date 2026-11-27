# Rotor, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `plan_pass` | `(track: list[(t, az, el)], profile, prefer="auto")` | `{"kind": normal/flip/reposiciona, "offset": ...}` | `rotor.py:64` |
| `to_rotor` | `(az, el, plan, profile, current=None, north_offset=0)` | `(az_rotor, el_rotor)` | escolhe az ou az+360 |
| `needs_move` | `(target, current, profile)` | `bool` | tolerância |
| `GS232Rotor` / `RotctldRotor` | `connect`, `position`, `move`, `stop`, `close` | — | rotctld herda do GS-232 |
| `make_rotor` | `(protocol, logger=None)` | instância | fábrica |

Perfis: G-5400B (az 450°, el 180°, padrão), G-5500, genérico 360/90. 🟢

## Fluxo Principal
1. Operador conecta o rotor; modo continua DESLIGADO. 🟢
2. Ao armar Automático, a trilha da passagem é calculada e `plan_pass` escolhe o tipo. 🟢
3. 180 s antes do AOS, pré-posiciona no ponto inicial. 🟢
4. A cada ciclo: lê posição, calcula `to_rotor`, move se `needs_move` e o intervalo passou. 🟢
5. No LOS, estaciona uma vez. 🟢

## Fluxos Alternativos
- **3 leituras falhas:** PARAR e desarma. 🟢
- **Esc/F12 ou fechar:** PARAR. 🟢
- **Manual:** setas chamam `jog_target` dentro dos limites. 🟢

## Dependências
- pyserial; Hamlib rotctld externo; `orbita-e-passagens` para a trilha. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Início em DESLIGADO | `rotor_ui.py` (ADR 009) | 🟢 |
| rotctld reaproveita a lógica do GS-232 | `RotctldRotor(GS232Rotor)` | 🟢 |

## Estado Interno
Modo, plano da passagem atual, última posição, contador de falhas, flag de estacionado. 🟢

## Observabilidade
Log de comandos e falhas; aviso na interface ao desarmar. 🟢

## Riscos e Lacunas
- 🔴 Interpretação de leituras com elevação > 90° (AZ 140° EL 175°) pendente de confirmação do mantenedor.
- 🟡 rotctld sem teste em hardware real.
