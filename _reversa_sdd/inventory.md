# Inventário — PT2VHF SAT Tool

> Gerado pelo Reversa (Scout) em 27/11/2026, sobre a versão 1.9.7 (`sat_tool/__init__.py`).
> Escala: 🟢 CONFIRMADO (lido no código) · 🟡 INFERIDO · 🔴 LACUNA

## Visão geral

🟢 Aplicativo desktop em Python + Qt (PySide6; PySide2 no legado Win7) para operação de satélites de radioamador:
previsão de passagens, correção Doppler por CAT no rádio, controle de rotor az/el, receptor RTL-SDR embutido
com áudio/waterfall/decodificação AX.25 e SSTV, painel web local e atualização OTA pelo site www.pt2vhf.com.
Regra de projeto declarada em `sat_tool/app.py` e `sat_tool/cat.py`: o programa **nunca transmite pelo CAT**
(sem PTT; a exceção é a TX de SSTV pela placa de som, acionada pelo operador).

- 205 arquivos versionados fora de `.git/` e das pastas do Reversa; 143 `.py` (~19.400 linhas em `sat_tool/`,
  das quais 5.225 em `app.py`).
- Pacote único `sat_tool/` (plano, sem subpacotes), `tests/` (84 arquivos `test_*.py` + `conftest.py`),
  `scripts/` (build, OTA, publicação), `installer/setup.iss` (Inno Setup), `linux/` (regra udev RTL-SDR),
  `assets/branding/`, `docs/` (branding, homologação em campo, imagens do backlog).

## Árvore de pastas

```
.
├── .github/workflows/windows.yml   CI: testes, builds Win/Linux/macOS, GitHub Release, publicação no site
├── assets/branding/                ícone SVG, logo, banner de abertura
├── docs/                           BRANDING.md, homologacao-campo.md, backlog/ (mockups e capturas)
├── installer/setup.iss             instalador Windows (Inno Setup)
├── linux/                          rtl-sdr.rules + LEIA-ME
├── sat_tool/                       código do aplicativo (55 módulos)
│   └── locales/ (+ dynamic/)       catálogos de tradução: 10 idiomas
├── scripts/                        Build-Windows.ps1, apply-update.ps1, build_deb.py, build_brand_assets.py,
│                                   publish_sat_to_site.py
├── tests/                          pytest (GUI em offscreen, em subprocessos)
├── run.py                          ponto de entrada (autoteste antes de importar a GUI)
├── BACKLOG.md                      backlog oficial do mantenedor (~1.600 linhas)
├── Gerar-Instalador-e-Portable.cmd / Publicar-no-GitHub.cmd/.ps1   atalhos do mantenedor
└── requirements*.txt               pilha fixada (Win11 x64 e legado Win7 x86)
```

## Funcionalidades e arquivos

| Funcionalidade | Arquivos principais |
|---|---|
| orbita-e-passagens | core.py, operations.py, quality.py, forecast.py, passfmt.py, alerts.py, maidenhead.py, geolocation.py, location_map.py |
| catalogo-e-tle | catalog.py, selection.py, profile.py, transponder.py, satellite_info.py, satinfo.py, media.py, config.py (satélites padrão) |
| cat-e-doppler | cat.py (TS-2000), rigs.py (FT-817/847, Yaesu texto, ICOM CI-V, Kenwood texto, rigctld, DopplerDispatcher), cat_scan.py, dde_server.py (Orbitron/WiSpDDE) |
| rotor | rotor.py (GS-232A/B, rotctld), rotor_ui.py, rotor_widgets.py |
| display-lcd | lcd.py, lcd_radios.py, lcd_bezel.py, display_window.py |
| sdr-e-telemetria | sdr.py, dsp.py, audio_ring.py, rtl_driver.py, rx_debug.py, ax25.py, aprs_info.py, telemetry.py, sdr_panel.py |
| sstv | sstv.py, sstv_panel.py |
| atualizacao-ota | updater.py, scripts/apply-update.ps1, installer/setup.iss |
| painel-web | web_ui.py |
| interface-e-idiomas | app.py (MainWindow), i18n.py, i18n_runtime.py, locales/, appearance.py, form_sizing.py, ui_scale.py, resource_meter.py, qt_compat.py, frequency.py |
| diagnostico | crash_diagnostics.py, diagnostics.py (autoteste), log_journal.py, rx_debug.py |
| build-e-publicacao | .github/workflows/windows.yml, scripts/*.py, scripts/*.ps1, installer/setup.iss, *.cmd |

## Pontos de entrada

- 🟢 `run.py`: `--self-test <relatorio.json> [binding]` roda `diagnostics.run_self_test` sem abrir a GUI; caso
  contrário instala o diagnóstico de falhas e chama `sat_tool.app.main()`.
- 🟢 `sat_tool/app.py: main()` — mutex de instância única (`_single_instance_mutex`), splash de 10 s
  (`WELCOME_SECONDS`), `MainWindow`.
- 🟢 `scripts/apply-update.ps1` — atualizador OTA no Windows, lançado pelo app (`updater.start_update_helper`).

## Configuração e dados locais

- 🟢 `sat_tool/config.py` — `Config` (JSON) com `DEFAULTS` e `ROTOR_DEFAULTS`; pasta da aplicação em
  `application_dir()`.
- 🟢 Caches em arquivos JSON (OMM/TLE da CelesTrak, transmissores do SatNOGS, info de satélite, fotos).
- Sem banco de dados.

## CI/CD

- 🟢 Um workflow (`.github/workflows/windows.yml`), disparado por push na `main`, tags `v*`, pull requests e manual.
  Jobs: `prepare_release` (valida versão fixa no YAML e cria a release), `build` (Windows: testes, PyInstaller,
  Inno Setup, autoteste do binário, teste OTA), `build_unix` (Linux .tar.gz/.deb e macOS ARM64), `release`
  (valida pacotes e SHA-256) e `publish_site` (copia instaladores para `alexpmr/pt2vhf-site` e atualiza
  `updates.json`). Em PR só testa e compila.
- 🟢 Commits com `[skip ci]` não disparam o workflow (regra do mantenedor para commits só de documentação).

## Testes

- 🟢 pytest 8.3.5; 84 arquivos, nomeados pela versão em que o comportamento entrou (`test_v171_*`, `test_v194_*`…).
  GUI testada com `QT_QPA_PLATFORM=offscreen`. Há teste de cobertura de i18n que falha quando um texto visível
  novo não entra em `sat_tool/locales/*.json`.
