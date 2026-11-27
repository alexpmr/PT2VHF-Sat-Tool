# SSTV, Tarefas de Implementação

## Tarefas
- [ ] T-01, Tabela de modos e VIS
  - Origem no legado: `sat_tool/sstv.py:19`, `:56`–`:151`
  - Critério de pronto: todos os modos identificados
  - Confiança: 🟢
- [ ] T-02, Decodificador em fluxo com correções
  - Origem no legado: `sat_tool/sstv.py:236`
  - Critério de pronto: ida e volta encode→decode
  - Confiança: 🟢
- [ ] T-03, Codificador e saída de áudio
  - Origem no legado: `sat_tool/sstv.py:160`, `sstv_panel.py`
  - Critério de pronto: WAV válido
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v190_sstv.py`

## Ordem Sugerida
1. T-01, T-02, T-03.

## Lacunas Pendentes (🔴)
- Validação em hardware real.
