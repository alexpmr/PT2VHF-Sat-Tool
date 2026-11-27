# SDR e telemetria

## Visão Geral
Recebe o satélite com um RTL-SDR (local ou rtl_tcp), demodula FM/SSB/CW/AM para a placa de som, grava a
passagem, decodifica AFSK 1200/AX.25 e telemetria (satnogs-decoders), recebe quadros de TNCs KISS e,
opcionalmente, envia telemetria ao SatNOGS. Instala o driver do RTL-SDR. 🟢

## Responsabilidades
- Ler IQ do RTL-SDR e sintonizar com deslocamento de FI e Doppler. 🟢
- Demodular e entregar áudio a 48 kHz com jitter buffer. 🟢
- Desenhar espectro/waterfall. 🟢
- Gravar WAV (e IQ do canal opcional) por passagem. 🟢
- Decodificar AFSK 1200 → HDLC → AX.25 → telemetria; KISS por TCP. 🟢
- Registrar CSV diário; enviar ao SatNOGS (SiDS) se ligado. 🟢
- Instalar WinUSB (Windows) ou regra udev (Linux). 🟢

## Regras de Negócio
- Envio de telemetria ao SatNOGS só se o operador ligar (R24). 🟢
- Retune do hardware só quando o alvo sai da margem. 🟢
- Fila USB descarta o bloco mais antigo se atrasar. 🟢
- KISS reconecta a cada 5 s. 🟢
- Gravação não pode derrubar a recepção (hoje pode: A1). 🟢
- Sem rede, decodificadores não devem ser consultados a cada quadro (hoje são: A7). 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Receber e demodular com Doppler | Must | Áudio contínuo sem cortes > 300 ms |
| RF-02 | Waterfall | Should | Atualiza com o espectro |
| RF-03 | Gravar passagem em WAV | Should | Parar gravação não para o SDR |
| RF-04 | AX.25 e telemetria | Should | Quadro de teste decodificado |
| RF-05 | KISS TCP | Should | Reconexão automática |
| RF-06 | Envio SiDS opcional | Could | Só com opção ligada |
| RF-07 | Instalação do driver | Must (Windows) | Um único UAC |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Tempo real | Thread `sdr-usb` dedicada e fila limitada | `sdr.py: RtlSource` | 🟢 |
| Latência | Jitter buffer ~300 ms com compensação de deriva | `audio_ring.py` | 🟢 |
| Concorrência | Gravador escrito fora do lock | `sdr.py: SdrReceiver._process` | 🟡 (A1) |
| Rede | Até 15 s por quadro sem rede | `telemetry.TelemetryDecoder.decoder_names` | 🟢 (A7) |

## Critérios de Aceitação

```gherkin
Dado o SDR recebendo e gravando uma passagem
Quando o operador para a gravação no meio de um bloco
Então a gravação é fechada e a recepção continua

Dado o computador sem internet
Quando chegam vários quadros AX.25
Então o programa não consulta o SatNOGS a cada quadro

Dado a opção de envio ao SatNOGS desligada
Quando um quadro é decodificado
Então nada é enviado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Recepção, áudio, driver | Must | Função do painel SDR |
| Gravação, AX.25, telemetria, KISS | Should | Uso frequente em passagens |
| SiDS | Could | Opcional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/sdr.py` | `SdrDevice`, `SdrSettings`, `RtlSource`, `SimulatedSource`, `ReceiverStatus`, `PassRecorder`, `SdrReceiver` | 🟢 |
| `sat_tool/dsp.py` | `FirDecimator`, `Mixer`, `Demodulator` | 🟢 |
| `sat_tool/audio_ring.py` | `AudioRing` | 🟢 |
| `sat_tool/ax25.py` | `AfskDemodulator`, `HdlcDeframer`, `KissDecoder` | 🟢 |
| `sat_tool/telemetry.py` | `KissTcpClient`, `TelemetryDecoder`, `TelemetryLog` | 🟢 |
| `sat_tool/aprs_info.py`, `rtl_driver.py`, `rx_debug.py`, `sdr_panel.py` | APRS, driver, debug, painel | 🟢 |
