# CAT e Doppler, Tarefas de Implementação

## Pré-requisitos
- [ ] `orbita-e-passagens` pronto (Doppler)
- [ ] Simuladores de porta serial para testes

## Tarefas
- [ ] T-01, Driver TS-2000 com `_exchange` sem reenvio e readback
  - Origem no legado: `sat_tool/cat.py:150`, `:387`
  - Critério de pronto: divergência de readback gera erro
  - Confiança: 🟢
- [ ] T-02, Drivers FT-817/818, FT-847, Yaesu texto, ICOM, Kenwood, rigctld
  - Origem no legado: `sat_tool/rigs.py:56`–`:698`
  - Critério de pronto: nenhum comando de TX em nenhum driver
  - Confiança: 🟢
- [ ] T-03, Limpeza de porta/socket em falha de conexão e limpeza de buffer após timeout
  - Origem no legado: `sat_tool/rigs.py: FT817.connect`, `Rigctld.connect/query`
  - Critério de pronto: nova tentativa funciona após falha
  - Confiança: 🟢
- [ ] T-04, `DopplerDispatcher` com limiar e intervalo
  - Origem no legado: `sat_tool/rigs.py:773`
  - Critério de pronto: sem escrita abaixo do limiar
  - Confiança: 🟢
- [ ] T-05, Laço Auto CAT na GUI (250 ms, um trabalho por vez, desarme em par inseguro)
  - Origem no legado: `sat_tool/app.py:3121`, `:3209`
  - Critério de pronto: `test_v137_live_auto_cat.py` verde
  - Confiança: 🟢
- [ ] T-06, Varredura de portas e servidor DDE
  - Origem no legado: `sat_tool/cat_scan.py`, `dde_server.py`
  - Critério de pronto: rádio achado; WiSpDDE recebe texto
  - Confiança: 🟢 / 🟡 (DDE sem teste real)

## Tarefas de Teste
- [ ] TT-01, Framing e readback (`test_v136_cat_framing.py`, `test_v1311_cat_reconcile.py`)
- [ ] TT-02, Drivers (`test_v140_rigs.py`, `test_v194_cat_icom_yaesu.py`, `test_v195_ft847_ft817_displays.py`)
- [ ] TT-03, Falha de conexão FT817 e timeout do rigctld

## Ordem Sugerida
1. T-01/T-02, T-03, T-04, depois T-05 e T-06.

## Lacunas Pendentes (🔴)
- Validação em hardware real de ICOM, Kenwood TS-790 e WiSpDDE.
