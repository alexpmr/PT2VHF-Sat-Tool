# Órbita e passagens

## Visão Geral
Calcula, a partir dos elementos orbitais e da estação do operador, a posição de cada satélite, as próximas
passagens, a correção Doppler e a qualidade de cada passagem, e avisa antes do AOS. É o núcleo numérico que
alimenta CAT, rotor, display e painel web. 🟢

## Responsabilidades
- Propagar órbitas SGP4 (Skyfield) a partir de OMM/TLE. 🟢
- Calcular azimute, elevação, distância, velocidade radial, subponto e footprint. 🟢
- Prever passagens (AOS, TCA, LOS, elevação máxima) nas próximas 36 h. 🟢
- Converter frequências nominais em frequências corrigidas por Doppler (RX e TX). 🟢
- Escolher canal e próxima passagem operável; dar nota de 1 a 5 estrelas. 🟢
- Emitir alertas 30 min e 30 s antes do AOS; gerar previsão em CSV (PREVER). 🟢
- Obter a posição da estação por locator, GPS NMEA ou IP (com consentimento). 🟢

## Regras de Negócio
- RX = f·(1 − v/c) e TX = f / (1 − v/c); velocidade radial positiva = afastando. 🟢
- Velocidade radial com |v| > 20 km/s é recusada como inválida. 🟢
- Passagem em curso começa em "agora", não no AOS passado. 🟢
- Canal com uplink tem prioridade; depois FM > SSB > CW; beacon nunca vira TX (R7). 🟢
- Transmissores `alive=False` ou com status diferente de `active`/vazio são ignorados. 🟢
- Mesma passagem = mesmo NORAD e AOS a ±5 min; cada alerta dispara uma única vez. 🟢
- Estação válida: latitude ±90°, longitude ±180°, elevação mínima entre 0° e 90°. 🟢
- Localização por IP só com consentimento; nada aplicado sem confirmação (R14). 🟢
- Faixas de banda diferem entre `profile.freq_band` (UHF 430–450) e `transponder.BANDS` (420–450). 🟡 intencional?

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Propagar a posição de um satélite em qualquer instante | Must | ISS a partir de OMM conhecido bate com Skyfield em < 0,1° |
| RF-02 | Prever passagens acima da elevação mínima em 36 h | Must | Lista ordenada com aos < tca < los e max_el ≥ mínimo |
| RF-03 | Corrigir uplink e downlink por Doppler | Must | 435 MHz a +7 km/s gera RX ≈ 434,98 MHz |
| RF-04 | Calcular o uplink pareado em transponder linear (normal e invertido) | Must | Cursor no centro do downlink leva ao centro do uplink |
| RF-05 | Selecionar canal e próxima passagem compatíveis com a estação | Must | Satélite só com beacon não gera TX |
| RF-06 | Pontuar a qualidade da passagem com motivos | Should | Nota 1–5 com lista de motivos |
| RF-07 | Alertar 30 min e 30 s antes do AOS | Should | Cada alerta dispara uma vez por passagem |
| RF-08 | Exportar previsão das próximas horas em CSV | Could | Arquivo com todos os satélites selecionados |
| RF-09 | Trajetória e footprint cortados no antimeridiano | Should | Nenhuma linha atravessando o mapa inteiro |
| RF-10 | Posição por locator, GPS ou IP | Should | Locator GG66 resulta no centro da célula |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Recalcular posição a 4 Hz sem travar a GUI | `app.py: cat_live_tick` (250 ms) | 🟢 |
| Precisão | Velocidade radial por diferença central de ±0,5 s | `core.py: position` | 🟢 |
| Privacidade | IP só com consentimento explícito | `geolocation.py: lookup_approximate_ip` | 🟢 |
| Confiabilidade | Checksum NMEA validado | `geolocation.py: read_gps_serial` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um satélite com OMM válido e a estação em Brasília
Quando o operador abre a lista de passagens
Então vê as passagens das próximas 36 h com AOS, TCA, LOS, elevação máxima e estrelas

Dado um satélite que está passando agora
Quando as passagens são calculadas
Então a primeira passagem começa no instante atual

Dado uma velocidade radial calculada acima de 20 km/s
Quando o Doppler é pedido
Então o cálculo é recusado e nenhuma frequência é enviada ao rádio

Dado um satélite cujos transmissores são só beacons
Quando o canal é escolhido
Então nenhum uplink é proposto
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Propagação, passagens, Doppler | Must | Base de CAT, rotor, display e web |
| Seleção de canal e próxima passagem | Must | Alimenta Auto CAT |
| Qualidade e alertas | Should | Ajuda à decisão, com alternativa manual |
| CSV de previsão, IP | Could | Uso ocasional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/core.py` | `make_satellite`, `position`, `doppler_frequencies`, `paired_linear_uplink`, `predict_passes`, `ground_track_between`, `footprint`, `track_period_bounds`, `Station` | 🟢 |
| `sat_tool/operations.py` | `select_channel`, `select_next_pass` | 🟢 |
| `sat_tool/quality.py` | `pass_quality`, `WEIGHTS` | 🟢 |
| `sat_tool/alerts.py` | `add_alert`, `due_alerts`, `sync_with_passes` | 🟢 |
| `sat_tool/forecast.py` | `forecast_passes` | 🟢 |
| `sat_tool/passfmt.py`, `maidenhead.py`, `geolocation.py`, `location_map.py` | formatação, locator, GPS/IP, mapa | 🟢 |
