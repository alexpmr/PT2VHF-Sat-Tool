# Display LCD, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `LcdState` | dataclass (frequências RX/TX, modo, satélite, AOS/LOS, S-meter, tags) | — | `lcd.py:161` |
| `LcdDisplay.set_state` | `(state: LcdState)` | — | redesenha |
| `LcdDisplay` sinais | `swap_clicked`, `rx_only_clicked`, `type_clicked`, `light_clicked`, `model_chosen`, `theme_chosen`, `detach_requested`, `fullscreen_requested`, `scope_clicked` | — | 🟢 [Revisão] `lcd.py:801` |
| `_Style.paint` | `(painter, rect, state)` | — | `_Matrix`, `_Seven`, `_Digital` |

## Fluxo Principal
1. A GUI monta `LcdState` no `tick` (1 s) e na prévia do Auto CAT (≤ 1 Hz). 🟢
2. `LcdDisplay` desenha numa imagem do tamanho físico e pinta na tela. 🟢
3. Cliques viram sinais tratados pela GUI (CAT). 🟢

## Fluxos Alternativos
- **Sem SDR:** área de escopo oculta. 🟢
- **Monitor ausente:** janela destacada volta centralizada ao monitor principal. 🟢 [Revisão] `display_window.restore_placement`

## Dependências
- Qt (via `qt_compat`); `sdr-e-telemetria` para o espectro. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Estilos como estratégia (`_Style`) | `lcd.py` | 🟢 |
| Display somente visual | `lcd.py` | 🟢 |

## Estado Interno
Último `LcdState`, estilo, geometria da janela destacada em `settings.json`. 🟢

## Observabilidade
Sem logs próprios. 🟡

## Riscos e Lacunas
- Nenhum risco aberto após a revisão.
