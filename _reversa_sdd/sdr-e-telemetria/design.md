# SDR e telemetria, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `SdrReceiver.start/stop` | `(settings: SdrSettings)` | — | thread própria |
| `SdrReceiver.set_target` | `(freq_hz, mode)` | — | retune só fora da margem |
| `SdrReceiver.start_recording/stop_recording` | `(path)` | — | usa `PassRecorder` |
| `Demodulator.process` | `(iq: np.ndarray)` | áudio 48 kHz | FM/SSB/CW/AM + squelch |
| `HdlcDeframer.feed` | `(bits)` | quadros | FCS CRC-X25 |
| `KissTcpClient` | `(host, port)` | quadros | reconexão 5 s |
| `TelemetryDecoder.decode` | `(norad, frame)` | campos | cache `satnogs_decoders.json` |

## Fluxo Principal
1. `RtlSource` lê IQ assíncrono (thread `sdr-usb`) para a fila. 🟢
2. `SdrReceiver._run` sintoniza centro = alvo − `IF_OFFSET`, demodula e calcula o espectro. 🟢
3. `_process` entrega áudio ao `AudioRing`, espectro à GUI, amostras ao gravador e AFSK à fila separada. 🟢
4. AFSK → HDLC → AX.25 → `TelemetryDecoder` → `TelemetryLog` (CSV) → SiDS opcional. 🟢

## Fluxos Alternativos
- **rtl_tcp:** leitura síncrona. 🟢
- **Sem SDR:** `SimulatedSource` para testes. 🟢
- **Gravação parada durante `write()`:** hoje pode lançar exceção na thread (A1). 🟡

## Dependências
- pyrtlsdr, pyrtlsdrlib, numpy, satnogs-decoders, aprslib, QtMultimedia. 🟢
- `wdi-simple.exe` (Windows), `pkexec` (Linux). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Decimação em 2 estágios | `dsp.py: FirDecimator` | 🟢 |
| AFSK em fila separada do áudio | `sdr.py` | 🟢 |
| Driver WinUSB com um UAC | `rtl_driver.py` | 🟢 |

## Estado Interno
Fila de blocos, frequência central, gravador sob lock, status (`ReceiverStatus`). 🟢

## Observabilidade
`rx_debug`: log por segundo, travamentos > `STALL_MS`, leituras lentas. 🟢

## Riscos e Lacunas
- 🟡 A1: corrida entre `stop_recording` e `write` do gravador.
- 🟢 A7: consulta ao SatNOGS a cada quadro sem rede.
