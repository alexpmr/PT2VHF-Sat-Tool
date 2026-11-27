# Rotor, Tarefas de Implementação

## Pré-requisitos
- [ ] Trilha de passagem de `orbita-e-passagens`
- [ ] Simulador GS-232 / rotctld para testes

## Tarefas
- [ ] T-01, Parser de posição e comandos GS-232
  - Origem no legado: `sat_tool/rotor.py:19`, `:43`, `:51`
  - Critério de pronto: `AZ=140 EL=175` e `+0140+0175` lidos
  - Confiança: 🟢
- [ ] T-02, Planejamento normal/flip/reposiciona
  - Origem no legado: `sat_tool/rotor.py:64`
  - Critério de pronto: passagem pelo norte sem volta completa no G-5400B
  - Confiança: 🟢
- [ ] T-03, `to_rotor` e `needs_move`
  - Origem no legado: `sat_tool/rotor.py:106`, `:131`
  - Critério de pronto: tolerância 4°, correção do norte aplicada
  - Confiança: 🟢
- [ ] T-04, Drivers GS-232 e rotctld
  - Origem no legado: `sat_tool/rotor.py:137`, `:248`
  - Critério de pronto: `S` enviado ao fechar
  - Confiança: 🟢
- [ ] T-05, Modos e segurança na GUI
  - Origem no legado: `sat_tool/rotor_ui.py`
  - Critério de pronto: abre em DESLIGADO; 3 falhas desarmam
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v171_rotores.py`, `test_v192_rotor_modes.py`, `test_v195_rotctld.py`
- [ ] TT-02, Falha de leitura repetida
- [ ] TT-03, Plano de passagem pelo norte

## Ordem Sugerida
1. T-01, T-02, T-03, T-04, T-05.

## Lacunas Pendentes (🔴)
- Confirmar com o mantenedor a posição real da antena na leitura AZ 140° EL 175°.
