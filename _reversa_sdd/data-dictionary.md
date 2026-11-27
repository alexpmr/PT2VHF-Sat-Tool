# Dicionário de dados — PT2VHF SAT Tool 1.9.7

> Reversa (Arqueólogo), 27/11/2026. Não há banco de dados: tudo é JSON/CSV/WAV em disco e estruturas em memória.
> 🟢 CONFIRMADO · 🟡 INFERIDO · 🔴 LACUNA

## 1. Pasta de dados (`Config.dir`)

🟢 `config.application_dir()`:
- EXE portátil (`portable.flag` ao lado do EXE ou nome terminando em `-portable`): `<pasta do EXE>/data`
- Windows instalado: `%APPDATA%\PT2VHF\SatTool`
- Linux/macOS: `$XDG_CONFIG_HOME/PT2VHF/SatTool` ou `~/.config/PT2VHF/SatTool`

| Arquivo | Conteúdo | Escrita |
|---|---|---|
| `settings.json` | configuração (seção 2) | atômica (`.tmp` + replace) 🟢 |
| `group_<grupo>.json` | OMM/TLE convertido por grupo | atômica; reaproveitado < 2 h 🟢 |
| `catnr_<norad>.json` | OMM de um satélite padrão | atômica; < 2 h 🟢 |
| `amateur_omm.json` | catálogo mesclado (nome legado) | atômica 🟢 |
| `amateur.tle` | TLE de reserva (grupo amateur) | direta 🟢 |
| `satnogs_transmitters.json` | lista completa de transmissores do SatNOGS | atômica 🟢 |
| `tx_<norad>.json` | transmissores de um satélite | atômica 🟢 |
| `satnogs_decoders.json` | NORAD → nomes de decodificador | direta 🟢 |
| `satinfo/<norad>.json` + imagem | info do SatNOGS e resumo da Wikipedia | 🟢 |
| `photo_<norad>.json` | foto licenciada do Wikimedia Commons | 🟢 |
| `logs/` | diário de eventos CAT/app (`EventJournal`) | 🟢 |
| `aos_start.wav`, `aos_tick.wav` | sons do aviso de AOS | 🟢 |
| telemetria `telemetria_AAAA-MM-DD.csv` | quadros recebidos (seção 6) | append 🟢 |
| gravações `*.wav`, `*_iq48k.cf32` | passagens do RTL-SDR | 🟢 |
| `diagnostics/` (`session.json`, `rx-audio-debug.log`…) | diagnóstico | rotação 🟢 |

Arquivos em `%TEMP%` do OTA: `PT2VHF-Sat-Tool-update-result.txt`, `-update-pending.json`, `-update-helper.log`,
`-update-helper.out`, `-setup.log`, pasta `pt2vhf_sat_update_*`. 🟢

## 2. `settings.json` (`config.DEFAULTS`)

Só chaves conhecidas em `DEFAULTS` são aceitas ao carregar (`Config.__init__`). 🟢

### Estação e rádio
| Chave | Tipo | Padrão |
|---|---|---|
| `callsign` | str | `"PT2VHF"` |
| `lat`, `lon` | str | `""` |
| `altitude_m` | número | 0 |
| `min_elevation` | número | 10 |
| `port`, `baud`, `stopbits` | str, int, int | `""`, 9600, 1 |
| `radio_brand`, `radio_model` | str | `"Kenwood"`, `"TS-2000"` |
| `radio_modes` | list | `["FM","SSB","CW"]` |
| `radio_bands` | list | `["VHF","UHF"]` |
| `rx_device`, `tx_device` | str (`RIG_MODELS`) | `"TS-2000"` |
| `ft817_port`, `ft817_baud` | str, int | `""`, 9600 |
| `rigctld_host` | str | `"127.0.0.1:4532"` |
| `gps_port`, `gps_baud` | str, int | `""`, 9600 |

### CAT / Doppler
| Chave | Tipo | Padrão |
|---|---|---|
| `auto_doppler` | bool | False |
| `cat_auto_select` | bool | True |
| `cat_auto_connect_startup` | bool | True |
| `cat_tracking_interval_s` | número | 1 |
| `cat_doppler_out_of_view` | bool | True (forçado a True ao carregar) |
| `update_interval_s` | número | 1 |
| `tune_threshold_hz` | int | 1 |
| `poll_interval_s` | número | 1 |
| `rx_only` | bool | False |
| `main_sub_swapped` | dict | `{}` |
| `main_sub_confirmed` | bool | False |
| `cat_details_visible` | bool | False |

### Satélites e catálogo
| Chave | Tipo | Padrão |
|---|---|---|
| `satellite_selection` | list[str] | `DEFAULT_SATELLITES` |
| `selected_norad` | str | `""` |
| `named_defaults_applied` | list | `[]` |
| `orbit_groups`, `catalog_category_filter` | list | 10 grupos (inclui `amsat`, `r4uab`) |
| `tle_update_hours` | número | 4 |
| `tle_source` | str | `"CelesTrak"` |
| `pass_window_hours` | número | 36 |
| `pass_alerts` | list[dict] | `[]` (seção 5) |
| `trail_period`, `trail_direction`, `trail_custom_hours` | str, str, float | `"2 h"`, `"Ambos"`, 3.0 |

### Avisos, atualização e web
| Chave | Tipo | Padrão |
|---|---|---|
| `aos_alarm_enabled`, `aos_alarm_sound` | bool | True |
| `aos_alarm_lead_seconds` | int | 10 |
| `aos_alarm_fired` | list | `[]` |
| `auto_update` | bool | True |
| `version_check_minutes` | int | 15 |
| `include_prereleases` | bool | True |
| `share_callsign` | bool | True |
| `update_prompt_snooze` | dict `{version, at}` | `{}` |
| `last_update_notice` | str | `""` |
| `web_enabled`, `web_allow_lan`, `web_controls` | bool | False |
| `web_port` | int | 8094 |
| `web_pin_hash`, `web_pin_salt` | str | `""` |
| `web_session_hours` | int | 8 |

### SDR e telemetria
| Chave | Tipo | Padrão |
|---|---|---|
| `rtl_tcp` | str | `""` |
| `sdr_ppm` | int | 0 |
| `sdr_bias_tee` | bool | False |
| `sdr_gain_db` | float/None | None (automático) |
| `sdr_audio_device` | str | `""` |
| `sdr_record`, `sdr_record_iq` | bool | False |
| `sdr_volume` | float | 0.8 |
| `sdr_squelch_db`, `sdr_squelch_pct` | número | −120, 0 |
| `sdr_user_stopped`, `sdr_autostart` | bool | False, True |
| `sdr_filters` | dict | `{}` |
| `wf_rows_per_s`, `wf_average`, `wf_height` | int | 20, 0, 90 |
| `sdr_dock_visible`, `sdr_dock_floating`, `sdr_dock_user_hidden` | bool | False |
| `sdr_dock_height` | int | 200 |
| `kiss_enabled` | bool | False |
| `kiss_host` | str | `"127.0.0.1:8100"` |
| `satnogs_upload` | bool | False |
| `aprs_on_map` | bool | True |

### Display, aparência e escala
| Chave | Tipo | Padrão |
|---|---|---|
| `lcd_theme` | str | `"âmbar"` |
| `display_model` | str | `"matriz"` |
| `display_font` | str | `"normal"` |
| `display_detached`, `display_window_fullscreen` | bool | False |
| `display_window_aspect`, `display_window_rect` | None/valor | None |
| `display_window_screen` | str | `""` |
| `display_bezel` | bool | False |
| `display_label`, `display_sublabel` | str | `""` |
| `frequency_style` | str | `"radio10"` |
| `language` | str | `""` (idioma do sistema) |
| `ui_scale` | str | `"auto"` |
| `ui_scale_learned` | dict | `{}` |
| `theme_preset` | str | `"escuro"` |
| `theme_accent_hue` | int | −1 |
| `theme_brightness`, `theme_contrast`, `theme_saturation` | int | 100 |
| `theme_font_px` | int | 12 |
| `theme_follow_display`, `theme_follow_map` | bool | False |

### Rotor (`ROTOR_DEFAULTS`)
| Chave | Tipo | Padrão |
|---|---|---|
| `rotor_enabled` | bool | False |
| `rotor_port`, `rotor_baud` | str, int | `""`, 9600 |
| `rotor_protocol` | `gs232` \| `rotctld` | `gs232` |
| `rotor_rotctld` | str | `127.0.0.1:4533` |
| `rotor_profile` | `g5400b` \| `g5500` \| `az360_el90` | `g5400b` |
| `rotor_az_max`, `rotor_el_max` | float | 450, 180 |
| `rotor_north_offset` | float | 0 |
| `rotor_park_az`, `rotor_park_el` | float | 0, 0 |
| `rotor_tolerance` | float | 4 |
| `rotor_min_interval` | float | 2 |
| `rotor_prepos_s` | float | 180 |
| `rotor_min_el` | float | 0 |
| `rotor_preference` | `auto` \| `flip` \| `normal` | `auto` |
| `rotor_jog_step` | float | 5 |
| `rotor_bar_visible` | bool/None | None |

### Flags de migração (uma única vez)
`cat_live_v137_migrated`, `trail_ambos_v160_migrated`, `tle_sources_v181_migrated`,
`default_satellites_v1316_migrated`, `luca1_default_v196_migrated` (todas True em instalação nova). 🟢

## 3. Registro orbital (OMM)

Campos CelesTrak usados: `OBJECT_NAME`, `OBJECT_ID`, `NORAD_CAT_ID` (int, até 6 dígitos), `EPOCH`
(`AAAA-MM-DDTHH:MM:SS.ffffff`), `MEAN_MOTION`, `ECCENTRICITY`, `INCLINATION`, `RA_OF_ASC_NODE`,
`ARG_OF_PERICENTER`, `MEAN_ANOMALY`, `EPHEMERIS_TYPE`, `CLASSIFICATION_TYPE`, `ELEMENT_SET_NO`, `REV_AT_EPOCH`,
`BSTAR`, `MEAN_MOTION_DOT`, `MEAN_MOTION_DDOT`. Acréscimos do programa: `CATEGORIES` (list), `ALT_NAMES` (list),
`TLE_LINE1`/`TLE_LINE2` (fontes TLE). 🟢

## 4. Transmissor SatNOGS (linha de `tx_<norad>.json`)

Campos lidos: `uuid`, `description`, `alive`, `status`, `type`, `mode`, `uplink_low`, `uplink_high`,
`downlink_low`, `downlink_high`, `invert`, `baud`, `norad_cat_id`. 🟢

Opção derivada (`core.transponder_options`): `name`, `downlink`, `downlink_high`, `uplink`, `uplink_high`, `mode`,
`inverted`, `uuid`, `receive_only`, `type`, `baud`. Canal escolhido (`operations.select_channel`): `mode`,
`downlink_hz`, `uplink_hz`, `rx_only`, `linear`, `inverted`, `name`, `source`. 🟢

## 5. Passagem e aviso

- Passagem (`core.predict_passes`): `aos`, `tca`, `los` (datetime UTC), `max_el` (float, 1 casa); a GUI acrescenta
  `id` (NORAD), `name`, `channel`, `in_progress`. 🟢
- Aviso (`settings.pass_alerts[]`): `norad`, `name`, `aos`, `los` (ISO), `max_el`, `leads` (segundos, ex. 1800 e
  30), `fired` (leads já disparados). Removido após o LOS. 🟢

## 6. Telemetria (CSV)

Colunas: `utc`, `norad`, `satellite`, `source`, `bytes`, `hex`, `ax25`, `decoder`, `fields` (JSON). Em memória
acrescenta `aprs`, `aprs_fields`, `aprs_pos`. SiDS: `noradID`, `source`, `timestamp`, `frame`, `locator=longLat`,
`longitude`, `latitude`. 🟢

## 7. Estado do rádio e do display

- `cat.RadioState`: `connected`, `model`, `sat`, `downlink`, `uplink`, `vfo_b`, `sub_receiver`, `mode`, `sat_raw`,
  `signal_main`, `signal_sub`, `power_set_w`, `meter_type`, `meter_value`, `main_downlink`, `extras`. 🟢
- `lcd.LcdState`: `rx_hz`, `rx_mode`, `tx_hz`, `tx_mode`, `rx_only`, `swapped`, `doppler_hz`, `elevation`,
  `visible`, `signal`, `sat_on`, `link`, `auto`, `transmitting`, `power_w`, `swr`, `extras`, `los_s`, `aos_s`,
  `rotor`, `sat_name`, `scope`, `scope_rows`, `scope_span_hz`. 🟢
- `sdr.ReceiverStatus`: `running`, `center_hz`, `channel_hz`, `mode`, `level_db`, `frames`, `error`, `recording`,
  `overruns`, `quality`. 🟢

## 8. Manifesto de atualização (`update.php?product=sat`)

| Campo | Regra |
|---|---|
| `schema` | 1 |
| `product` | `"sat"` |
| `source` | `"https://www.pt2vhf.com"` |
| `status` | `available` (ou `unpublished` = nada a fazer) |
| `version` | `X.Y.Z` |
| `notes`, `page` | texto, URL |
| `files[]` | `name`, `url` (`/downloads/sat-tool/<name>`), `size` (int, ≤ 600 MiB), `sha256` (64 hex) |

Nomes: `PT2VHF-Sat-Tool-v<versão>-Win11-x64-{Setup,Portable}.exe`, `-Linux-x64.tar.gz`, `-Linux-x64.deb`,
`-macOS-arm64.dmg`, `-SHA256.txt`. 🟢

## 9. Painel web

- `/api/status`: snapshot publicado pela GUI (`version`, `passes`, `metrics`, …) + `controls`. 🟢
- `/api/control` (POST JSON): `action` ∈ `CONTROL_ACTIONS`, `value` (bool/str conforme a ação), `pin`. 🟢
- Cookie `PT2VHFSession` (token aleatório de 32 bytes, validade em horas). 🟢
