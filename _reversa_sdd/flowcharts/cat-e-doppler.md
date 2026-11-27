# Fluxo — Auto CAT Doppler (TS-2000)

> 🟢 `app.py: cat_live_tick` (250 ms) → `track_cat_frequencies` → `cat.TS2000.set_frequencies`

```mermaid
flowchart TD
  T[cat_live_timer 250 ms] --> A{Auto CAT armado,<br/>rádio conectado,<br/>satélite escolhido?}
  A -- não --> X[nada]
  A -- sim --> P[core.position agora<br/>prévia na tela no máx. 1 Hz]
  P --> B{trabalho CAT pendente?<br/>autotune/track/readback/connect/diagnostic}
  B -- sim --> X
  B -- não --> C{SAT ligado ou RX only?<br/>OMM válido?}
  C -- não --> X
  C -- sim --> D{já houve sintonia inicial?}
  D -- não --> AT[auto_tune_selected_satellite<br/>preset do canal: FA/FB/MD]
  D -- sim --> E{backoff de falha<br/>ou intervalo mínimo?}
  E -- aguardar --> X
  E -- ok --> F[corrected: Doppler RX/TX]
  F --> G{par crossband seguro?}
  G -- não --> H[desarma Auto CAT<br/>mostra motivo]
  G -- sim --> I{diferença para o último pedido<br/>E para o readback ≥ limiar?}
  I -- não --> R{readback há ≥ 1 s?}
  R -- sim --> RB[background cat-readback:<br/>SA/FA/FB]
  I -- sim --> W[background cat-track:<br/>SA → FA/FB → readback]
  W --> V{readback confere?}
  V -- sim --> OK[CAT SYNC]
  V -- não --> ERR[erro + backoff]
```

## Regras
- Escrita só com SAT ligado e orientação MAIN/SUB igual à esperada (`set_frequencies`). 🟢
- O programa nunca envia PTT; FC (receptor SUB) nunca é tratado como uplink. 🟢
- Leituras opcionais (S-meter, potência, medidores) em trabalhador separado, no máx. a cada 5–6 s. 🟢
