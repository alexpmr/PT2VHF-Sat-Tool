# Órbita e passagens, Tarefas de Implementação

## Pré-requisitos
- [ ] Skyfield, numpy e efemérides disponíveis
- [ ] OMM de teste (ISS, SO-50, AO-7) e estação de referência

## Tarefas

- [ ] T-01, Criar satélite a partir de OMM ou TLE preservando as linhas originais
  - Origem no legado: `sat_tool/core.py:51`
  - Critério de pronto: posição igual à do Skyfield com o mesmo TLE
  - Confiança: 🟢
- [ ] T-02, Calcular posição com velocidade radial por diferença central ±0,5 s
  - Origem no legado: `sat_tool/core.py:63`
  - Critério de pronto: sinal positivo ao afastar, negativo ao aproximar
  - Confiança: 🟢
- [ ] T-03, Implementar `doppler_frequencies` e `paired_linear_uplink`
  - Origem no legado: `sat_tool/core.py:28`, `sat_tool/core.py:39`
  - Critério de pronto: casos normal e invertido; recusa |v| > 20 km/s
  - Confiança: 🟢
- [ ] T-04, Prever passagens em 36 h com passagem em curso começando agora
  - Origem no legado: `sat_tool/core.py:123`
  - Critério de pronto: aos < tca < los; passagem em curso com aos = agora
  - Confiança: 🟢
- [ ] T-05, Seleção de canal e próxima passagem
  - Origem no legado: `sat_tool/operations.py:12`, `:49`
  - Critério de pronto: prioridade uplink > FM > SSB > CW; beacon sem TX
  - Confiança: 🟢
- [ ] T-06, Nota de qualidade com `WEIGHTS`
  - Origem no legado: `sat_tool/quality.py:139`
  - Critério de pronto: AO-7 na sombra perde pontos; motivos listados
  - Confiança: 🟢
- [ ] T-07, Alertas 30 min / 30 s com deduplicação ±5 min
  - Origem no legado: `sat_tool/alerts.py:83`
  - Critério de pronto: cada alerta uma vez
  - Confiança: 🟢
- [ ] T-08, Previsão CSV, locator, GPS NMEA e IP com consentimento
  - Origem no legado: `sat_tool/forecast.py:15`, `maidenhead.py`, `geolocation.py`
  - Critério de pronto: checksum NMEA validado; IP só após aceite
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, Passagens e Doppler (ver `tests/test_core.py`, `test_v160_passes.py`)
- [ ] TT-02, Velocidade radial inválida
- [ ] TT-03, Seleção de canal (`tests/test_operations.py`) e qualidade (`test_v150_quality.py`)

## Ordem Sugerida
1. T-01 a T-04 (núcleo), depois T-05/T-06, por fim T-07/T-08.

## Lacunas Pendentes (🔴)
- Nenhuma lacuna bloqueante; confirmar a faixa UHF 420 vs 430 MHz (🟡).
