# Display LCD, Tarefas de Implementação

## Pré-requisitos
- [ ] Qt disponível; `LcdState` definido

## Tarefas
- [ ] T-01, Modelo `LcdState` e estilos genéricos
  - Origem no legado: `sat_tool/lcd.py:161`, `:237`–`:586`
  - Critério de pronto: todos os estilos pintam um estado vazio
  - Confiança: 🟢
- [ ] T-02, Estilos de rádio e moldura
  - Origem no legado: `sat_tool/lcd_radios.py`, `lcd_bezel.py`
  - Critério de pronto: 10 modelos disponíveis
  - Confiança: 🟢
- [ ] T-03, Escopo/waterfall
  - Origem no legado: `sat_tool/lcd.py`, `SCOPE_MODELS`
  - Critério de pronto: só nos modelos com tela
  - Confiança: 🟢
- [ ] T-04, Janela destacável
  - Origem no legado: `sat_tool/display_window.py`
  - Critério de pronto: posição e tela cheia lembradas
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v160_lcd_cat.py`, `test_v171_radio_displays.py`, `test_v192_bezel.py`
- [ ] TT-02, `test_v171_display_keys_detach.py`, `test_v172_display_countdown.py`

## Ordem Sugerida
1. T-01, T-02, T-04, T-03.

## Lacunas Pendentes (🔴)
- Nenhuma.
