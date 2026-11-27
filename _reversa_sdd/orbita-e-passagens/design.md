# Órbita e passagens, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `core.make_satellite` | `(omm: dict, ts=None)` | `EarthSatellite` | usa `TLE_LINE1/2` quando a fonte é TLE |
| `core.position` | `(sat, station: Station, when=None, ts=None)` | dict `elevation, azimuth, distance_km, radial_m_s, sublat, sublon, footprint_km, visible` | 🟢 |
| `core.doppler_frequencies` | `(uplink_hz: int, downlink_hz: int, radial_m_s: float)` | `(tx_hz, rx_hz)` | inteiros em Hz |
| `core.paired_linear_uplink` | `(downlink_hz, dl_low, dl_high, ul_low, ul_high, inverted)` | `uplink_hz` | 🟢 |
| `core.predict_passes` | `(sat, station, now=None, hours=36, ...)` | `list[{aos,tca,los,max_el}]` | `find_events` |
| `operations.select_channel` | `(rows, selected_modes, available_bands)` | canal ou `None` | 🟢 |
| `operations.select_next_pass` | `(passes, rows_by_norad, selected_modes, ...)` | passagem | em curso primeiro |
| `quality.pass_quality` | `(sat, station, p, ts, *, norad, mode, downlink_hz, ...)` | `(estrelas, motivos)` | 🟢 |
| `alerts.due_alerts` | `(alerts, now)` | alertas a disparar | marca como disparado |
| `forecast.forecast_passes` | `(orbits, ids, station, *, hours=24, min_elevation=10.0)` | linhas para CSV | 🟢 |

## Fluxo Principal
1. O catálogo entrega OMM por NORAD; `make_satellite` cria o objeto Skyfield (cache por NORAD na GUI). 🟢
2. A cada `tick` (1 s) e `cat_live_tick` (250 ms) a GUI chama `position` para o satélite ativo. 🟢
3. `predict_passes` roda em segundo plano para os selecionados; `pass_quality` anota cada passagem. 🟢
4. `select_next_pass` e `select_channel` definem o alvo do Auto CAT e do rotor. 🟢
5. `doppler_frequencies` (ou `paired_linear_uplink` + Doppler em lineares) gera o par enviado ao CAT. 🟢
6. `alerts.sync_with_passes` e `due_alerts` avisam o operador. 🟢

## Fluxos Alternativos
- **Satélite sem OMM:** fica fora das passagens; aparece como sem órbita. 🟢
- **Velocidade radial inválida:** `doppler_frequencies` levanta erro; o Auto CAT não escreve. 🟢
- **Sem GPS:** posição manual ou por locator. 🟢

## Dependências
- Skyfield 1.49 (SGP4, `find_events`, efemérides de sombra), numpy. 🟢
- `catalogo-e-tle` (OMM e transmissores). 🟢
- `profile.py` (bandas da estação). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Frequências sempre em Hz inteiros | `frequency.py`, `core.doppler_frequencies` | 🟢 |
| Doppler por diferença central de posição, não pela derivada do Skyfield | `core.position` | 🟢 |
| Horizonte de previsão de 36 h | `core.predict_passes` | 🟢 |
| Pesos de qualidade fixos em `WEIGHTS` | `quality.py` | 🟢 |

## Estado Interno
Sem estado próprio nos módulos de cálculo (funções puras). Alertas vivem numa lista em memória com a marca de
disparado; a estação vem de `settings.json`. 🟢

## Observabilidade
Erros de cálculo vão para o log da GUI (`MainWindow.log`). 🟡

## Riscos e Lacunas
- 🟡 Diferença de faixas UHF entre `profile.freq_band` e `transponder.BANDS` sem justificativa no código.
- 🟡 Comparação de `EPOCH` por texto ISO depende de formato uniforme entre fontes.
