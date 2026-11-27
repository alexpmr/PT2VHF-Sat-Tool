# Catálogo e TLE, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `catalog.merge_orbits` | `(groups)` | dict NORAD → OMM | `CATEGORIES`, `ALT_NAMES` |
| `catalog.refresh_catnr_omm` | `(data_dir, ident)` | OMM | reserva `_satnogs_tle_omm` |
| `catalog.refresh_all_transmitters` | `(data_dir, ids, progress=None, cancel=None)` | dict NORAD → transmissores | paginado |
| `catalog.parse_tle` | `(text)` | `list[dict]` | 2LE/3LE, Alpha-5 |
| `selection.change_selection` | `(orbit_objects, filtered_ids, current_ids, select, filtered)` | nova seleção | 🟢 |
| `transponder.prioritized_transponders` | `(norad, options)` | lista ordenada | SO-50 fixo |

Arquivos no diretório de dados: `group_<g>.json`, `tx_<norad>.json`, `satnogs_decoders.json`. 🟢

## Fluxo Principal
1. 1,5 s após abrir, a GUI dispara a atualização em segundo plano (`background("catalog", ...)`). 🟢
2. Para cada grupo: se o cache tem < 2 h, usa; senão baixa OMM JSON (ou TLE texto para `amsat`/`r4uab`). 🟢
3. `merge_orbits` junta tudo por NORAD. 🟢
4. Padrões ausentes: `refresh_catnr_omm` por NORAD; se faltar, TLE do SatNOGS; categoria `defaults`. 🟢
5. `refresh_all_transmitters` baixa `/api/transmitters/` paginado e grava por NORAD. 🟢
6. A GUI recebe o resultado por sinal e atualiza a lista. 🟢

## Fluxos Alternativos
- **Sem rede:** usa cache e avisa. 🟢
- **Falha ou cancelamento no meio da paginação:** `_fetch_transmitter_pages` nunca devolve página parcial (levanta erro) e nenhum cache é zerado. 🟢 [Revisão] `catalog.py:214`
- **Operador cancela:** `cancel()` interrompe a paginação. 🟢

## Dependências
- requests 2.31; CelesTrak, AMSAT, R4UAB, SatNOGS DB, Wikipedia/Wikimedia. 🟢
- `config.py` (padrões e migrações). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Cache de 2 h por grupo | `catalog.py` (ADR 006) | 🟢 |
| Consulta única de transmissores | `catalog.py:269` (ADR 007) | 🟢 |
| HADES-E2 resolvido por nome | `config.DEFAULT_SATELLITE_NAMES` | 🟢 |

## Estado Interno
Cache em arquivos JSON; seleção e flags de migração em `settings.json`. 🟢

## Observabilidade
Progresso e falhas de download via `Events.progress/failure` e log. 🟢

## Riscos e Lacunas
- 🟢 User-Agent desatualizado (A6).
- 🟡 Comparação de `EPOCH` como texto.
