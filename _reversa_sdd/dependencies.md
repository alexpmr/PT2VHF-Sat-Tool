# Dependências — PT2VHF SAT Tool

> Reversa (Scout), 27/11/2026. Fonte: `requirements-win11.txt`, `requirements-win7.txt`, `requirements.txt`,
> `.github/workflows/windows.yml`.

## Runtime (Windows 10/11 x64, Linux, macOS) — `requirements-win11.txt`

| Pacote | Versão | Uso no código |
|---|---|---|
| PySide6 | >=6.7,<6.10 | GUI, QtWebEngine (mapa), QtMultimedia (áudio), QtPositioning (GPS) — via `qt_compat.py` |
| numpy | 1.26.4 | DSP do SDR (`dsp.py`), SSTV (`sstv.py`), AFSK (`ax25.py`) |
| skyfield | 1.49 | propagação SGP4, passagens, Doppler (`core.py`, `quality.py`) |
| pyserial | 3.5 | CAT, rotor GS-232, GPS NMEA |
| requests | 2.31.0 | CelesTrak, SatNOGS, Wikipedia/Wikimedia, OTA |
| urllib3 | 1.26.20 | fixado junto do requests |
| pyrtlsdr | 0.5.1 | RTL-SDR (`sdr.py`) |
| pyrtlsdrlib | 0.0.7 | librtlsdr empacotada |
| satnogs-decoders | 1.132.0 | telemetria (`telemetry.py`) |
| aprslib | 0.7.2 | APRS (`aprs_info.py`) |
| psutil | 6.1.1 | medidor CPU/RAM, árvore de processos |

## Runtime legado (Windows 7 SP1 x86, Python 3.8.10) — `requirements-win7.txt`

PySide2 5.15.2.1, numpy 1.23.5, skyfield 1.49, pyserial 3.5, requests 2.31.0, urllib3 1.26.20, psutil 6.1.1.
🟡 O workflow atual só tem a matriz `Win11-x64`; o ramo Win7 aparece apenas em verificações condicionais
(`if ('${{ matrix.target }}' -eq 'Win7-x86')`), o que indica edição legada sem build ativo.

## Build e teste (CI)

| Ferramenta | Versão |
|---|---|
| Python | 3.11 |
| pip | <25.1 |
| PyInstaller | 6.13.0 |
| pytest | 8.3.5 |
| Pillow | 10.4.0 (ícones) |
| Inno Setup | instalado no runner Windows |
| libwdi | v1.5.1 (compila `wdi-simple.exe`, instalador WinUSB do RTL-SDR) |
| WDK 8.0 redist | baixado no build |

## Serviços externos

| Serviço | Uso | Módulo |
|---|---|---|
| CelesTrak (OMM/TLE) | órbitas por grupo e por NORAD | catalog.py |
| AMSAT nasabare / R4UAB satonline | fontes de TLE extras (Alpha-5) | catalog.py |
| SatNOGS DB | transmissores, TLE de reserva, info do satélite, telemetria (SiDS) | catalog.py, satinfo.py, telemetry.py |
| Wikipedia / Wikimedia Commons | resumo e foto do satélite | satinfo.py, media.py |
| www.pt2vhf.com (`update.php`, `/downloads`) | OTA e registro de indicativo | updater.py |
| Serviço de IP→localização (opcional, com consentimento) | posição aproximada | geolocation.py |
| Hamlib rigctld / rotctld, SoundModem/Direwolf KISS | integrações locais por TCP | rigs.py, rotor.py, telemetry.py |
