# SDR e telemetria, Tarefas de Implementação

## Pré-requisitos
- [ ] `SimulatedSource` para testes sem hardware

## Tarefas
- [ ] T-01, Fonte RTL assíncrona com fila limitada
  - Origem no legado: `sat_tool/sdr.py:112`
  - Critério de pronto: atraso descarta o bloco mais antigo
  - Confiança: 🟢
- [ ] T-02, DSP (mixer, FIR, demoduladores, squelch)
  - Origem no legado: `sat_tool/dsp.py`
  - Critério de pronto: tom FM de teste recuperado
  - Confiança: 🟢
- [ ] T-03, Gravação segura: escrever e fechar sob o mesmo lock
  - Origem no legado: `sat_tool/sdr.py: SdrReceiver._process`, `PassRecorder`
  - Critério de pronto: parar gravação durante recepção não derruba a thread
  - Confiança: 🟢
- [ ] T-04, AFSK/HDLC/KISS e decodificadores
  - Origem no legado: `sat_tool/ax25.py`, `telemetry.py`
  - Critério de pronto: quadro de referência decodificado
  - Confiança: 🟢
- [ ] T-05, Sem rede: lembrar falha e não consultar a cada quadro
  - Origem no legado: `sat_tool/telemetry.py: TelemetryDecoder.decoder_names`
  - Critério de pronto: no máximo uma tentativa por intervalo
  - Confiança: 🟢
- [ ] T-06, Instalação do driver
  - Origem no legado: `sat_tool/rtl_driver.py`
  - Critério de pronto: `test_v150_rtl_driver.py` verde
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v140_sdr.py`, `test_v140_dsp_ax25.py`, `test_v140_telemetry.py`, `test_v160_audio.py`
- [ ] TT-02, Parar gravação em paralelo à recepção
- [ ] TT-03, Telemetria sem rede

## Ordem Sugerida
1. T-01, T-02, T-03, T-04, T-05, T-06.

## Lacunas Pendentes (🔴)
- Nenhuma.
