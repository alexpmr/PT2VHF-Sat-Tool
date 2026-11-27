# Rotor

## Visão Geral
Aponta a antena para o satélite durante a passagem usando rotores azimute/elevação (G-5400B/G-5500 via ERC-M em
GS-232, ou qualquer rotor do Hamlib rotctld), com planejamento de passagem (normal, flip ou reposicionamento),
modos Automático/Manual/Desligado e parada segura. 🟢

## Responsabilidades
- Falar GS-232A/B por serial e rotctld por TCP. 🟢
- Planejar cada passagem para caber no curso mecânico do rotor. 🟢
- Seguir o satélite no modo Automático, com pré-posicionamento e estacionamento no LOS. 🟢
- Permitir ajuste manual (setas), calibração do norte e parada imediata. 🟢

## Regras de Negócio
- Rotor sempre inicia em DESLIGADO; conectar não arma o Automático (R15, ADR 009). 🟢
- Nenhum movimento por apenas escolher um satélite (R15). 🟢
- PARAR em erro de movimento, 3 leituras falhas seguidas, Esc/F12 e ao fechar o programa (R16). 🟢
- Move só quando o erro passa da tolerância (4°) e depois do intervalo mínimo (2 s) (R17). 🟢
- Pré-posicionamento 180 s antes do AOS; máscara de elevação respeitada. 🟢
- Flip = az+180 e 180−el, só com rotor de elevação 180°. 🟢
- LOS estaciona uma vez por passagem. 🟢
- 🔴 Leitura AZ 140° EL 175° tratada como flip → 320°/5°; o mantenedor ainda precisa confirmar a posição real.

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Ler e mover pelo GS-232 (`C2`, `Waaa eee`, `S`) | Must | Resposta `AZ=xxx EL=yyy` interpretada |
| RF-02 | Ler e mover pelo rotctld (`p`, `P az el`, `S`) | Must | Mesmo comportamento do GS-232 |
| RF-03 | Planejar passagem normal/flip/reposiciona | Must | Passagem que cruza o norte não gira 360° no meio |
| RF-04 | Modos Automático/Manual/Desligado | Must | Abre sempre em Desligado |
| RF-05 | Parada segura | Must | Esc/F12 envia `S` imediatamente |
| RF-06 | Ajuste manual e calibração do norte | Should | Limites do perfil respeitados |
| RF-07 | Gauges e linha da antena no mapa | Could | Direção desenhada até 2.500 km |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança física | Parada em falha de comunicação (3 leituras) | `rotor_ui.py` | 🟢 |
| Desgaste | Tolerância 4° e intervalo 2 s | `rotor.py: RotorProfile`, `needs_move` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o programa recém-aberto com o rotor configurado
Quando a janela aparece
Então o rotor está em DESLIGADO e nenhum comando de movimento foi enviado

Dado o modo Automático e uma passagem que vai de 350° a 20°
Quando o plano é calculado em um G-5400B (450°)
Então a antena segue sem dar a volta completa

Dado o modo Automático
Quando três leituras seguidas falham
Então o rotor recebe PARAR e o Automático é desarmado com aviso
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Parada segura e início desligado | Must | Segurança do equipamento |
| Plano de passagem e Automático | Must | Função principal |
| Manual e calibração | Should | Ajuste |
| Linha no mapa | Could | Visual |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/rotor.py` | `RotorProfile`, `PROFILES`, `parse_position`, `move_command`, `plan_pass`, `to_rotor`, `needs_move`, `GS232Rotor`, `RotctldRotor`, `probe_port`, `probe_rotctld`, `calibrated_north_offset`, `jog_target`, `antenna_line` | 🟢 |
| `sat_tool/rotor_ui.py` | `RotorUiMixin` | 🟢 |
| `sat_tool/rotor_widgets.py` | gauges | 🟢 |
