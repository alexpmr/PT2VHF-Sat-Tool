# Fluxo — Atualização do catálogo orbital

```mermaid
flowchart TD
  S[abertura +1,5 s ou botão] --> G[para cada grupo selecionado]
  G --> C{cache do grupo < 2 h?}
  C -- sim --> U[usa o cache]
  C -- não --> N{fonte TLE texto?<br/>amsat / r4uab}
  N -- sim --> T[baixa TLE → parse_tle → tle_to_omm]
  N -- não --> O[CelesTrak gp.php GROUP=…&FORMAT=json]
  T --> W[grava group_<g>.json atômico]
  O --> W
  C -. erro .-> E[usa cache antigo se houver<br/>e registra o erro]
  W --> D[satélites padrão ausentes]
  U --> D
  E --> D
  D --> K[CelesTrak CATNR → reserva SatNOGS TLE]
  K --> M[merge_orbits por NORAD<br/>CATEGORIES + ALT_NAMES + EPOCH mais novo]
  M --> A[amateur_omm.json]
```

## Transmissores (botão Atualizar frequências)
1. `GET https://db.satnogs.org/api/transmitters/?format=json` (todas as páginas, só no próprio domínio). 🟢
2. Agrupa por `norad_cat_id`, grava `tx_<norad>.json` de quem tem transmissor; zera quem deixou de ter. 🟢
