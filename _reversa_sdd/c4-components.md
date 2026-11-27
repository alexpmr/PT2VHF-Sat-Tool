# C4 Componentes — Aplicativo desktop

> Reversa (Arquiteto), 27/11/2026. Grafo de imports extraído por AST (🟢). Os componentes seguem as 12
> funcionalidades das specs.

```mermaid
flowchart LR
  subgraph GUI["Aplicativo desktop (app.py — MainWindow)"]
    MW[MainWindow<br/>+ RotorUiMixin + painel SDR]
  end
  subgraph ORB["orbita-e-passagens"]
    core[core.py] --- quality[quality.py] --- forecast[forecast.py] --- passfmt[passfmt.py] --- operations[operations.py]
  end
  subgraph CATL["catalogo-e-tle"]
    catalog[catalog.py] --- selection[selection.py] --- transponder[transponder.py] --- satinfo[satinfo.py / satellite_info.py / media.py]
  end
  subgraph CATD["cat-e-doppler"]
    cat[cat.py TS-2000] --- rigs[rigs.py demais rádios + rigctld] --- cat_scan[cat_scan.py] --- frequency[frequency.py] --- dde[dde_server.py]
  end
  subgraph ROT["rotor"]
    rotor[rotor.py GS-232/rotctld] --- rotor_ui[rotor_ui.py] --- rotor_widgets[rotor_widgets.py]
  end
  subgraph LCD["display-lcd"]
    lcd[lcd.py] --- lcd_radios[lcd_radios.py] --- lcd_bezel[lcd_bezel.py] --- display_window[display_window.py]
  end
  subgraph SDR["sdr-e-telemetria"]
    sdr[sdr.py] --- dsp[dsp.py] --- ax25[ax25.py] --- telemetry[telemetry.py] --- aprs[aprs_info.py] --- audio_ring[audio_ring.py] --- rtl_driver[rtl_driver.py] --- sdr_panel[sdr_panel.py] --- rx_debug[rx_debug.py]
  end
  subgraph SSTV["sstv"]
    sstv[sstv.py] --- sstv_panel[sstv_panel.py]
  end
  subgraph OTA["atualizacao-ota"]
    updater[updater.py]
  end
  subgraph WEB["painel-web"]
    web_ui[web_ui.py] --- location_map[location_map.py / map.html]
  end
  subgraph UI["interface-e-idiomas"]
    config[config.py] --- appearance[appearance.py] --- i18n[i18n.py / i18n_runtime.py / locales] --- ui_scale[ui_scale.py / form_sizing.py] --- profile[profile.py / maidenhead.py / geolocation.py] --- qt_compat[qt_compat.py]
  end
  subgraph DIAG["diagnostico"]
    diagnostics[diagnostics.py] --- crash[crash_diagnostics.py] --- log_journal[log_journal.py] --- resource_meter[resource_meter.py] --- alerts[alerts.py]
  end
  MW --> ORB & CATL & CATD & ROT & LCD & SDR & OTA & WEB & UI & DIAG
  sdr_panel --> SSTV
  catalog --> config
  updater --> crash
  rotor_ui -.import circular.-> MW
  sdr_panel -.import circular.-> MW
```

## Observações
- 🟢 `app.py` (5.225 linhas) concentra a orquestração; `rotor_ui.py` e `sdr_panel.py` são mixins/painéis que
  importam `app` de volta (acoplamento circular resolvido em tempo de execução).
- 🟢 Os módulos de domínio puro (`core`, `cat`, `rigs`, `rotor`, `dsp`, `ax25`, `sstv`, `web_ui`, `frequency`)
  não importam nada do pacote: são testáveis isoladamente, e é aí que está a maior parte dos 394 testes.
- 🟢 `diagnostics.py` importa quase tudo: é o autoteste de inicialização e o relatório de suporte.
