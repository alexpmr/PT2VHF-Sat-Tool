# Análise de código — PT2VHF SAT Tool 1.9.7

> Reversa (Arqueólogo), 27/11/2026. Organização das specs: **por funcionalidade** (`feature`).
> Escala: 🟢 CONFIRMADO (lido no código) · 🟡 INFERIDO · 🔴 LACUNA.
> Dicionário de dados completo em [data-dictionary.md](data-dictionary.md); fluxos em [flowcharts/](flowcharts/).

## Princípios que atravessam o código

1. 🟢 **Nunca transmitir pelo CAT.** Nenhum driver envia PTT (`cat.py`, `rigs.py`, docstrings e ausência dos
   comandos `TX;`, `0x08`, `1C 00 01`). O painel web recusa ações com palavras como `ptt`, `tx`, `transmit`
   (`web_ui.FORBIDDEN_WORDS`). A única transmissão é a de SSTV pela placa de som, com PTT pelo VOX do rádio.
2. 🟢 **Qt só na thread da GUI.** Trabalho de rede/serial roda em `MainWindow.background(key, fn)` (thread daemon
   por chave, sem duplicar a mesma chave) e o resultado volta pelos sinais `Events.result/failure/progress/record`.
   `MainWindow.log` reencaminha mensagens de threads pelo sinal `record`.
3. 🟢 **Frequências em Hz inteiros** (`frequency.py`); previsões Doppler são rotuladas como previsão; o estado
   real do rádio vem sempre do readback CAT.
4. 🟢 **Falha fechada no OTA:** só `https://www.pt2vhf.com/downloads/sat-tool/<nome>` com tamanho e SHA-256 do
   manifesto, sem redirecionamento.
5. 🟢 **Migrações de configuração "uma única vez"** com flags `*_migrated` em `settings.json` (o operador pode
   desfazer depois e a migração não volta).

---

## 1. orbita-e-passagens

**Arquivos:** `core.py`, `operations.py`, `quality.py`, `forecast.py`, `passfmt.py`, `alerts.py`,
`maidenhead.py`, `geolocation.py`, `location_map.py`.

### Funções principais
| Função | Entrada → saída | Observação |
|---|---|---|
| `core.make_satellite(omm, ts)` | OMM/TLE → `EarthSatellite` | usa as linhas TLE originais quando existem (fontes AMSAT/R4UAB) 🟢 |
| `core.position(sat, station, when)` | → dict elevação, azimute, distância, `radial_m_s`, subponto, raio do footprint, `visible` | velocidade radial por diferença central de ±0,5 s; positivo = afastando 🟢 |
| `core.doppler_frequencies(up, down, v)` | → (TX corrigido, RX corrigido) | `RX = f·(1−v/c)`, `TX = f/(1−v/c)`; recusa |v| > 20 km/s 🟢 |
| `core.paired_linear_uplink(...)` | cursor do downlink → uplink | interpola na faixa do transponder linear, invertido ou não 🟢 |
| `core.predict_passes(sat, station, now, hours=36)` | → lista {aos, tca, los, max_el} | `find_events` do Skyfield na elevação mínima; passagem em curso começa em `now` 🟢 |
| `core.ground_track_between` / `footprint` | trajetória e círculo de visibilidade | corta no antimeridiano com ponto interpolado na borda ±180° 🟢 |
| `operations.select_channel(rows, modos, bandas)` | transmissores SatNOGS → canal escolhido | prefere canal com uplink, depois FM > SSB > CW; nunca inventa TX para beacon 🟢 |
| `operations.select_next_pass(...)` | → próxima passagem com canal compatível | passagem em curso de maior elevação primeiro, depois a próxima por AOS 🟢 |
| `quality.pass_quality(sat, station, p)` | → 1 a 5 estrelas + motivos | pesos em `WEIGHTS`: elevação, tempo útil, distância, taxa Doppler, sombra (AO-7 só ao sol), congestionamento FM 🟢 |
| `alerts.add_alert/due_alerts/sync_with_passes` | avisos 30 min e 30 s antes do AOS | mesma passagem = mesmo NORAD e AOS a ±5 min; cada aviso dispara uma vez 🟢 |
| `forecast.forecast_passes(orbits, ids, station)` | botão PREVER | passagens das próximas horas de todos os selecionados; CSV 🟢 |
| `maidenhead.maidenhead_to_latlon` | locator → centro da célula | 🟢 |
| `geolocation.lookup_approximate_ip / read_gps_serial` | posição aproximada por IP (com consentimento) ou NMEA do GPS | checksum NMEA validado 🟢 |

### Regras embutidas
- 🟢 `Station.validate`: lat ±90, lon ±180, elevação mínima 0–90°.
- 🟢 `operations.select_channel` ignora transmissores `alive=False` ou com `status` diferente de `active`/vazio.
- 🟢 `profile.freq_band`: VHF 144–148 MHz, UHF 430–450 MHz, 23 cm 1240–1300 MHz; `transponder.BANDS` usa 420–450
  para o CAT (diferença intencional? 🟡).
- 🟢 `core.track_period_bounds`: direções "Futuro", "Passado", "Ambos", "Última passagem"; período 0,1–48 h.

---

## 2. catalogo-e-tle

**Arquivos:** `catalog.py`, `selection.py`, `profile.py`, `transponder.py`, `satellite_info.py`, `satinfo.py`,
`media.py`, `config.py` (satélites padrão).

### Fontes e cache
- 🟢 Grupos CelesTrak (OMM JSON): `amateur, stations, cubesat, starlink, oneweb, weather, science, visual` + fontes
  TLE texto `amsat` (nasabare.txt) e `r4uab` (satonline.txt). Cache por grupo `group_<g>.json`, reaproveitado por
  **2 h** (limite de cortesia da CelesTrak).
- 🟢 Satélites padrão fora dos grupos são buscados por NORAD (`refresh_catnr_omm`); se a CelesTrak não tiver,
  o TLE vem do SatNOGS (`_satnogs_tle_omm`, v1.9.7). Esses entram na categoria sintética `defaults`.
- 🟢 `merge_orbits`: mesmo NORAD em vários grupos vira um registro com `CATEGORIES`; elementos trocados só se o
  `EPOCH` for igual ou mais novo (comparação de texto ISO); nomes de outras fontes viram `ALT_NAMES` (busca).
- 🟢 `parse_tle`: 2LE e 3LE, catálogo Alpha-5 (`A0084` → 100084), linha inválida pulada sem derrubar a fonte.
- 🟢 `tle_to_omm`: converte campos TLE para nomes OMM (EPOCH, BSTAR com expoente implícito etc.).
- 🟢 Transmissores SatNOGS: `refresh_all_transmitters` baixa `/api/transmitters/` inteiro (até 200 páginas,
  paginação só em `https://db.satnogs.org`), agrupa por NORAD e grava `tx_<norad>.json` só para quem tem
  transmissor; zera o cache de quem deixou de ter. Antes eram ~12.500 consultas (v1.9.7).

### Seleção
- 🟢 `config.DEFAULT_SATELLITES`: ISS 25544, SO-50 27607, IO-86 40931, AO-7 7530, FO-29 24278, RS-44 44909,
  SONATE-2 59112, LUČA-1 67287; `DEFAULT_SATELLITE_NAMES = ("HADES-E2",)` (NORAD achado pelo nome no catálogo).
- 🟢 `selection.change_selection`: seleção manual independente do cache de frequências.
- 🟢 `transponder.prioritized_transponders`: SO-50 usa o perfil fixo AMSAT (145,850 ↑ / 436,795 ↓ FM) à frente
  do SatNOGS; nos demais, o primeiro par crossband válido vira o padrão.
- 🟢 `profile.capability`: compatibilidade pelo canal publicado; sem dados, só sugere pelos `CANDIDATES`
  históricos se a estação tiver VHF e UHF.

---

## 3. cat-e-doppler

**Arquivos:** `cat.py` (TS-2000), `rigs.py`, `cat_scan.py`, `dde_server.py`; fluxo na GUI em `app.py`
(`track_cat_frequencies`, `cat_live_tick`, `auto_tune_selected_satellite`, `update_cat_sync_status`).

### TS-2000 (`cat.TS2000`)
- 🟢 Serial 9600 8N1 (stopbits configurável), timeout 0,35 s; `_exchange` remonta respostas fragmentadas até `;`
  (prazo 4 s, até 48 leituras, máx. 256 caracteres) e nunca reenvia comandos de escrita.
- 🟢 Modo SAT: `SA` P1=SAT, P3=MAIN RX/SUB TX; FA = downlink, FB = uplink; FC = receptor SUB (só diagnóstico).
- 🟢 `set_frequencies` valida SAT ligado e orientação MAIN/SUB igual à do programa, escreve RX e TX e confirma por
  readback (`poll_tracking`); diferença → erro.
- 🟢 `set_orientation` (botão MAIN↔SUB) repete a leitura SA até ~2 s antes de declarar falha.
- 🟢 `set_rx_only`: escreve só o VFO de recepção; nunca liga SAT nem escreve uplink.
- 🟢 Leituras opcionais (S-meter, PC, RM, AG/RG/SQ/PA/RA/NB/NR/IF) a cada 5–6 s, nunca bloqueiam o Doppler.

### Outros rádios (`rigs.py`)
| Classe | Protocolo | RX+TX no mesmo rádio |
|---|---|---|
| `FT817` | 5 bytes BCD, 8N2 | split VFO A/B alternando com 0x81 fora de TX |
| `FT847` | 5 bytes, 8N2, CAT ON | modo SAT nativo (SAT RX 0x11/0x17, SAT TX 0x21/0x27) |
| `YaesuText` | FA/FB 9 dígitos, MD0 | RX no VFO-A, TX no VFO-B; split ligado pelo operador |
| `Icom` | CI-V, eco descartado | dual-band (IC-9700/910/9100/820/821/970): SUB = RX, MAIN = TX, modo satélite `16 5A 01` |
| `KenwoodText` | FA/FB/MD/FR/FT | FR0/FT1 (split) |
| `Rigctld` | TCP Hamlib | `S 1 VFOB`, `I`/`X` para o TX |
- 🟢 `DopplerDispatcher`: envia de novo só quando a diferença passa do limiar e o intervalo mínimo passou.
- 🟢 `is_transmitting()` bloqueia mudanças durante o câmbio (exceto onde o modo SAT exige seguir o uplink).

### Laço Auto CAT (GUI)
- 🟢 `cat_live_timer` a 250 ms recalcula a posição; a prévia na tela é limitada a 1 Hz.
- 🟢 Um trabalho CAT por vez (`cat-autotune`, `cat-track`, `cat-readback`, `cat-connect`, `cat-diagnostic`).
- 🟢 Só escreve quando a previsão difere do último pedido **e** do último readback em pelo menos o limiar
  (padrão 1 Hz, intervalo 1 s); par inseguro (mesma banda, sem uplink) desarma o Auto CAT.
- 🟢 Doppler continua fora do horizonte por padrão (`cat_doppler_out_of_view` é forçado a `True` ao carregar).

### DDE (`dde_server.py`)
- 🟢 Servidor "Orbitron/Tracking/TrackingData" via DDEML (ctypes), texto `SN.. AZ.. EL.. DN.. UP.. DM.. UM..`,
  para o WiSpDDE. Só Windows.

---

## 4. rotor

**Arquivos:** `rotor.py`, `rotor_ui.py` (mixin da janela), `rotor_widgets.py`.

- 🟢 Protocolos: GS-232A/B serial (`C2` lê, `Waaa eee` move, `S` para) e Hamlib rotctld TCP (`p`, `P az el`, `S`).
- 🟢 Perfis: G-5400B (az 450°, el 180°, padrão), G-5500, genérico 360/90; tolerância 4°, intervalo mínimo 2 s,
  pré-posicionamento 180 s antes do AOS, máscara de elevação.
- 🟢 `plan_pass`: escolhe `normal` (cabe no curso de azimute com deslocamento 0/±360), `flip` (az+180 e 180−el,
  quando el_max = 180) ou `reposiciona`; preferência `auto`/`flip`/`normal`.
- 🟢 `to_rotor`: entre az e az+360 escolhe o mais próximo do plano (ou da posição atual); soma a correção do norte.
- 🟢 Modos AUTOMÁTICO / MANUAL / DESLIGADO; conectar não arma o automático (v1.9.4); 3 falhas de leitura seguidas
  desarmam o automático com aviso; LOS estaciona uma vez por passagem; Esc/F12 = PARAR; fechar o programa envia `S`.
- 🟢 `calibrated_north_offset` e `jog_target` (setas manuais) com limites do perfil.
- 🔴 Pendência do mantenedor: confirmar para onde a antena apontava com leitura AZ 140° EL 175° (o app trata como
  flip → 320°/5°).

---

## 5. display-lcd

**Arquivos:** `lcd.py`, `lcd_radios.py`, `lcd_bezel.py`, `display_window.py`.

- 🟢 `LcdDisplay` desenha numa imagem do tamanho físico (pixels × devicePixelRatio); só exibe dados e emite sinais
  (A/B, RX ONLY, troca MAIN↔SUB).
- 🟢 Modelos: `matriz` (5×7/6×7), `led7`, `lcd7`, `digital`, `classico` e estilos de rádio (`RADIO_MODELS`):
  IC-706MKIIG, IC-7100, FT-897/857, IC-910H, FT-991A, IC-9700, FT-847, FT-817/818, TS-790, IC-705.
- 🟢 Contagem regressiva de AOS/LOS em segmentos, S-meter, tags de estado, escopo/waterfall do RTL-SDR nos
  modelos com tela (`SCOPE_MODELS`).
- 🟢 Moldura realista (`lcd_bezel`) com etiqueta do operador; display destacável para outro monitor, com posição,
  monitor e tela cheia lembrados (`display_window`).

---

## 6. sdr-e-telemetria

**Arquivos:** `sdr.py`, `dsp.py`, `audio_ring.py`, `rtl_driver.py`, `rx_debug.py`, `ax25.py`, `aprs_info.py`,
`telemetry.py`, `sdr_panel.py`.

- 🟢 `RtlSource`: RTL-SDR local (leitura assíncrona contínua numa thread `sdr-usb`, fila de `ASYNC_QUEUE_BLOCKS`,
  descarta o bloco mais antigo se atrasar) ou `rtl_tcp` (síncrono).
- 🟢 `SdrReceiver._run`: centro = alvo − `IF_OFFSET`; retune só se sair da margem; demodula (`dsp.Demodulator`:
  mixer → FIR com decimação em 2 estágios → FM/SSB/CW/AM → squelch) para áudio 48 kHz; espectro para o waterfall;
  gravação WAV (+ IQ do canal opcional) e AFSK em fila separada.
- 🟢 `audio_ring.AudioRing`: jitter buffer ~300 ms com compensação de deriva para a placa de som (modo pull).
- 🟢 AX.25: AFSK 1200 (Bell 202) com PLL, HDLC/NRZI/bit stuffing, FCS CRC-X25, KISS.
- 🟢 Telemetria: pipeline por transmissor (`voice`, `afsk1200`, `kiss`), SoundModem/Direwolf por KISS TCP com
  reconexão a cada 5 s, decodificadores `satnogs-decoders` por NORAD (cache `satnogs_decoders.json`), CSV diário,
  envio opcional ao SatNOGS (SiDS).
- 🟢 `rtl_driver`: Windows instala WinUSB com `wdi-simple.exe` (um UAC); Linux grava regra udev e blacklist via
  `pkexec`.

---

## 7. sstv

**Arquivos:** `sstv.py`, `sstv_panel.py`.

- 🟢 Modos Robot 36/72, Martin M1/M2, Scottie S1/S2/DX, PD 50/90/120/160/180/240/290; VIS identifica o modo.
- 🟢 Decodificador em fluxo (`Decoder.feed`) com sincronismo por linha, correção de inclinação e desvio de tom
  medido no 1900 Hz do cabeçalho; imagens salvas automaticamente com carimbo.
- 🟢 TX: gera o áudio (`encode`) e toca na saída escolhida; PTT pelo VOX.

---

## 8. atualizacao-ota

**Arquivos:** `updater.py`, `scripts/apply-update.ps1`, `installer/setup.iss`; GUI em `app.py`
(`check_for_updates`, `maybe_prompt_update`, `request_update`, `update_ready`, `show_last_update_result`).

- 🟢 Consulta `https://www.pt2vhf.com/update.php?product=sat[&call=<indicativo>]` sem seguir redirecionamento;
  manifesto `schema 1`, `product sat`, `source https://www.pt2vhf.com`, `status available`.
- 🟢 `install_flavor`: Windows `Win11-x64` (ou `Win7-x86` com PySide2) `Setup`/`Portable`; Linux/macOS `Manual`
  (só avisa e leva ao site); código-fonte (não congelado) nunca se atualiza.
- 🟢 `download_update` exige tamanho e SHA-256, recusa redirecionamento e tamanho divergente.
- 🟢 `launch_staged_update` copia `apply-update.ps1` para a pasta temporária e o executa com console oculto
  (`CREATE_NO_WINDOW`, `CREATE_BREAKAWAY_FROM_JOB` com reserva sem ele); o app sai em seguida.
- 🟢 `apply-update.ps1`: espera a árvore de processos do app (excluindo a si mesmo), encerra filhos que não saem,
  roda o Setup (Inno) ou troca o portátil, grava `PT2VHF-Sat-Tool-update-result.txt`, log por etapa, reabre.
- 🟢 Na abertura seguinte: `read_update_result` e `check_pending_update` explicam a falha com o motivo e o link
  manual. Portátil com versão no nome é renomeado (`rename_portable_to_version`).
- 🟢 Indicativo enviado só se bater em `CALLSIGN_RE` (lista de usuários do site).

---

## 9. painel-web

**Arquivo:** `web_ui.py`; GUI em `app.py` (`start_web_server`, `web_tick`, `apply_web_command`,
`publish_web_snapshot`).

- 🟢 `LocalStatusServer` (ThreadingHTTPServer): `127.0.0.1` por padrão; LAN só com opção explícita, com chave na
  URL que vira cookie de sessão (`HttpOnly`, `SameSite=Strict`, validade `web_session_hours`).
- 🟢 Clientes fora de rede privada/loopback são recusados; CSP restritiva; sem cache.
- 🟢 Controles opcionais (`select_satellite`, `auto_cat`, `ab`, `rx_only`, `rotor_track`, `rotor_park`,
  `rotor_stop`) exigem cabeçalho `X-PT2VHF: 1`, mesma origem e PIN (PBKDF2-SHA256, 120.000 iterações; 5 erros
  travam o IP por 5 min). Os comandos entram numa fila esvaziada pela GUI.
- 🟢 Regra de firewall do Windows opcional (perfil Privado, só sub-rede local, via UAC).

---

## 10. interface-e-idiomas

**Arquivos:** `app.py` (MainWindow, 190 métodos), `i18n.py`, `i18n_runtime.py`, `locales/`, `appearance.py`,
`form_sizing.py`, `ui_scale.py`, `resource_meter.py`, `qt_compat.py`, `frequency.py`.

- 🟢 Mutex `PT2VHF_Sat_Tool_Running` só para o instalador detectar o app aberto (não bloqueia segunda instância; corrigido na revisão), abertura de 10 s dentro da
  janela, temporizadores: `tick` 1 s, `cat_live_tick` 250 ms, heartbeat de diagnóstico 30 s; catálogo em segundo
  plano 1,5 s após abrir; verificação de versão aos 12 s.
- 🟢 10 idiomas (pt-BR, en, es, fr, de, it, ja, pl, nl, zh-Hans); padrão = idioma do sistema; textos dinâmicos
  traduzidos por interceptação dos setters do Qt; texto original guardado no widget para trocar na hora.
- 🟢 Temas (escuro, claro, alto contraste, noturno vermelho) por transformação da folha de estilo; checagem WCAG.
- 🟢 Escala proporcional 80–100 % definida antes da `QApplication` (`QT_SCALE_FACTOR`).
- 🟢 `qt_compat`: um único binding por build (PySide6 Win11/Linux/macOS, PySide2 Win7).

---

## 11. diagnostico

**Arquivos:** `crash_diagnostics.py`, `diagnostics.py`, `log_journal.py`, `rx_debug.py`.

- 🟢 Marcador de saída anormal, `faulthandler` para falhas nativas, eventos com rotação de tamanho; nada de
  coordenadas, CAT ou configurações pessoais.
- 🟢 Autoteste `--self-test <relatorio.json>` usado pelo CI no binário congelado e no `.deb` instalado.
- 🟢 `EventJournal` local, limitado e exportável ("Baixar log completo (ZIP)").
- 🟢 `rx_debug`: log do áudio RX por segundo, travamentos > `STALL_MS`, leituras lentas.

---

## 12. build-e-publicacao

**Arquivos:** `.github/workflows/windows.yml`, `scripts/Build-Windows.ps1`, `scripts/build_deb.py`,
`scripts/build_brand_assets.py`, `scripts/publish_sat_to_site.py`, `installer/setup.iss`, `*.cmd`.

- 🟢 Versão fixada em vários lugares: `sat_tool/__init__.py`, `windows.yml` (`test "$ver" = '1.9.7'`),
  `installer/setup.iss`, `scripts/Build-Windows.ps1` e testes (memória do projeto).
- 🟢 Push na `main` → release no GitHub (pré-lançamento), builds Windows (Setup/Portable), Linux (.tar.gz/.deb) e
  macOS ARM64, validação de pacotes/SHA-256 e publicação no repositório do site (`downloads/sat-tool/` +
  `updates.json`), que a Hostinger publica.
- 🟢 Arquivos grandes vão em partes < 100 MiB (`write_parts`) e o `download.php` do site remonta e conta o
  download (site e OTA uma vez cada).

---

## Achados do Arqueólogo (para o Detetive e o Revisor)

| # | Local | Achado | Confiança |
|---|---|---|---|
| A1 | `sdr.py: SdrReceiver._process` | o gravador é pego sob o lock mas escrito fora dele; `stop_recording()` da GUI pode fechar o WAV no meio de `write()` e a exceção derruba a thread de recepção (o SDR para depois da gravação de uma passagem) | 🟡 corrida plausível, não reproduzida em hardware |
| A2 | `rigs.py: FT817.connect` | se a leitura inicial falha, a porta fica aberta e o objeto parece conectado (`connected` = porta não nula); nova tentativa acusa "porta em uso" | 🟢 |
| A3 | `rigs.py: Rigctld.connect/query` | falha na leitura inicial deixa o socket aberto; um timeout no meio de uma resposta deixa bytes no buffer e as respostas seguintes saem defasadas | 🟢 |
| A4 | `config.py: Config.__init__` | `settings.json` ilegível (JSON quebrado) impede o programa de abrir | 🟢 |
| A5 | `web_ui.py` (modo só localhost) | sem checagem do cabeçalho `Host`: uma página maliciosa com DNS rebinding pode ler `/api/status` (controles continuam protegidos pelo PIN) | 🟡 |
| A6 | `catalog.py` | `HEADERS["User-Agent"]` ainda diz `1.3.0`; o "docstring" do módulo fica depois de `from __future__` e não é docstring | 🟢 (cosmético) |
| A7 | `telemetry.TelemetryDecoder.decoder_names` | sem rede, cada quadro recebido tenta o SatNOGS de novo (até 15 s por quadro, em thread) | 🟢 (baixo impacto) |
| A8 | `.reversa/config.user.toml` | arquivo pessoal versionado no repositório (o próprio arquivo pede para não commitar) | 🟢 |
