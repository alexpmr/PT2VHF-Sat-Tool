# Arquitetura — PT2VHF SAT Tool 1.9.7

> Reversa (Arquiteto), 27/11/2026. Escala: 🟢 CONFIRMADO · 🟡 INFERIDO · 🔴 LACUNA.
> Diagramas: [C4 Contexto](c4-context.md) · [C4 Containers](c4-containers.md) · [C4 Componentes](c4-components.md)
> · [ERD](erd-complete.md) · [Matriz de impacto](traceability/spec-impact-matrix.md) · [ADRs](adrs/).

## Visão geral
🟢 Aplicativo desktop monolítico em Python 3.11 + PySide6 (PySide2 no ramo legado Win7), distribuído como
instalador Windows (Inno Setup + PyInstaller), pacote `.deb` e execução direta em Linux/macOS. Um único
processo com a thread da GUI e threads de trabalho; sem banco de dados; sem backend próprio além do site
www.pt2vhf.com (OTA e registro de indicativos).

## Estilo arquitetural
- 🟢 **Núcleo de domínio puro + casca Qt.** Cálculo orbital, protocolos CAT/rotor, DSP, AX.25, SSTV e o
  servidor web são funções e classes sem Qt, testadas por pytest. A GUI (`app.py`, `rotor_ui.py`,
  `sdr_panel.py`) orquestra.
- 🟢 **Concorrência por chave.** `MainWindow.background(key, fn)` evita duplicar a mesma tarefa; resultados
  voltam por sinais (ADR 002).
- 🟢 **Configuração única** em `settings.json` com migrações "uma vez" (ADR 004).
- 🟢 **Falha segura**: nunca transmitir (ADR 001), OTA fechado em pt2vhf.com + SHA-256 (ADR 003), rotor
  começa desligado (ADR 009), controles web com PIN (ADR 008).

## Integrações externas
| Integração | Protocolo | Direção | Módulo | Observação |
|---|---|---|---|---|
| CelesTrak / AMSAT / R4UAB | HTTPS, OMM JSON e TLE | entrada | catalog.py | cache 2 h (ADR 006) |
| SatNOGS DB | HTTPS REST | entrada; saída (SiDS) | catalog, satinfo, telemetry | consulta única de transmissores (ADR 007) |
| Wikipedia / Wikimedia | HTTPS | entrada | satinfo, media | opcional |
| www.pt2vhf.com | HTTPS `update.php`, `/downloads/sat-tool/` | entrada; saída (indicativo) | updater.py | contagem em download.php |
| Rádios | Serial (Kenwood ASCII, Yaesu 5 bytes, ICOM CI-V) / TCP rigctld | saída (sem PTT) | cat.py, rigs.py | |
| Rotor | Serial GS-232 / TCP rotctld | saída + leitura | rotor.py | |
| RTL-SDR | USB librtlsdr | entrada | sdr.py, rtl_driver.py | driver WinUSB via wdi-simple |
| DDE | Win32 DDE | saída | dde_server.py | só Windows |
| KISS TNC | TCP | entrada | telemetry.py | SoundModem/Direwolf |
| Painel web | HTTP :8094 | entrada/saída | web_ui.py | localhost ou LAN privada |

## Dívidas técnicas
| # | Dívida | Impacto | Confiança |
|---|---|---|---|
| D1 | `app.py` com 5.225 linhas e imports circulares com `rotor_ui`/`sdr_panel` | mudanças na GUI têm alto raio de impacto | 🟢 |
| D2 | Achados A1–A5 do Arqueólogo (corrida no gravador SDR, porta/socket sem limpeza, JSON quebrado, Host no web) | travamentos e erros difíceis de reproduzir | 🟢/🟡 |
| D3 | User-Agent fixo em 1.3.0 (A6) | identificação errada junto ao CelesTrak | 🟢 |
| D4 | Testes nomeados por versão (`test_v1xx_*`), não por funcionalidade | difícil achar a cobertura de uma feature | 🟢 |
| D5 | ICOM, Kenwood TS-790, WiSpDDE, rotctld e SSTV sem teste em hardware real | regressões só aparecem no campo | 🟢 (memória do projeto) |
| D6 | Ramo Win7/PySide2 sem build ativo no CI | código morto ou edição quebrada sem aviso | 🟡 |
| D7 | Telemetria sem rede tenta o SatNOGS a cada quadro (A7) | atraso e threads extras | 🟢 |

## Implantação
🟢 `.github/workflows/windows.yml`: push na `main` roda testes, gera instalador e `.deb`, cria a GitHub
Release (só origem dos arquivos) e o job `publish_site` atualiza `downloads/sat-tool/` e `updates.json` no
repositório do site, que publica na Hostinger.
