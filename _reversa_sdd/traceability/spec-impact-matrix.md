# Spec Impact Matrix

> Reversa (Arquiteto), 27/11/2026. Linha = funcionalidade alterada; coluna = funcionalidade que pode ser
> afetada. ● impacto direto (import ou dado compartilhado, 🟢 pelo grafo AST) · ○ impacto indireto pela
> GUI/estado (🟡).

| Altera ↓ / Afeta → | orbita | catalogo | cat | rotor | lcd | sdr | sstv | ota | web | ui | diag | build |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| orbita-e-passagens | — | ○ | ● | ● | ● | ○ | | | ● | | ● | |
| catalogo-e-tle | ● | — | ● | ○ | ○ | ● | | | ○ | | ● | |
| cat-e-doppler | | | — | ○ | ● | ● | | | ● | | ● | |
| rotor | | | | — | ○ | | | | ● | | ● | |
| display-lcd | | | | | — | | | | | | ● | |
| sdr-e-telemetria | | | ○ | | | — | ● | | ○ | | ● | ● |
| sstv | | | | | | ● | — | | | | | |
| atualizacao-ota | | | | | | | | — | | ○ | ● | ● |
| painel-web | | | | | | | | | — | | ● | |
| interface-e-idiomas | ● | ● | ● | ● | ● | ● | ● | ● | ● | — | ● | |
| diagnostico | | | | | | | | | | | — | |
| build-e-publicacao | | | | | | ● | | ● | | | | — |

## Leitura
- `interface-e-idiomas` (config, i18n, `qt_compat`) é a base de tudo: mexer em `config.py` ou `qt_compat.py`
  exige rodar a suíte inteira.
- `sdr-e-telemetria` ↔ `build-e-publicacao`: o driver WinUSB (`rtl_driver.py`, `wdi-simple.exe`) entra no
  instalador e no OTA (histórico: OTA 1.6.0→1.7.0 travou na etapa do driver).
- `diagnostico` depende de quase todos; toda feature nova precisa aparecer no autoteste.
