# Diagnóstico, Tarefas de Implementação

## Tarefas
- [ ] T-01, Marcador de execução, heartbeat e saída limpa
  - Origem no legado: `sat_tool/crash_diagnostics.py:72`–`:126`
  - Critério de pronto: falha anterior detectada
  - Confiança: 🟢
- [ ] T-02, Autoteste
  - Origem no legado: `sat_tool/diagnostics.py:11`
  - Critério de pronto: relatório JSON no CI
  - Confiança: 🟢
- [ ] T-03, Diário exportável e debug RX
  - Origem no legado: `sat_tool/log_journal.py:11`, `rx_debug.py`
  - Critério de pronto: ZIP sem dados pessoais
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_diagnostics.py`, `test_stability.py`, `test_v134_live_log.py`, `test_v191_rx_audio_debug.py`

## Ordem Sugerida
1. T-01, T-02, T-03.

## Lacunas Pendentes (🔴)
- Nenhuma.
