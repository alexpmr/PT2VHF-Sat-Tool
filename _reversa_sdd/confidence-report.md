# Relatório de Confiança — PT2VHF SAT Tool 1.9.7

> Gerado pelo Revisor em 27/11/2026 (modo autônomo, `answer_mode = file`). Contagem de marcadores nas specs das 12 units.

---

## Resumo Geral

| Nível | Quantidade | Percentual |
|-------|-----------|------------|
| 🟢 CONFIRMADO | 460 | 93% |
| 🟡 INFERIDO   | 23 | 5% |
| 🔴 LACUNA     | 14 | 3% |
| **Total**     | 497 | 100% |

**Confiança geral:** 95% (soma de 🟢 + metade dos 🟡)

---

## Por Spec

| Spec | 🟢 | 🟡 | 🔴 | Confiança |
|------|----|----|-----|-----------|
| `atualizacao-ota/` | 38 | 0 | 1 | 97% |
| `build-e-publicacao/` | 34 | 3 | 1 | 93% |
| `cat-e-doppler/` | 48 | 2 | 1 | 96% |
| `catalogo-e-tle/` | 53 | 1 | 1 | 97% |
| `diagnostico/` | 28 | 1 | 1 | 95% |
| `display-lcd/` | 29 | 1 | 1 | 95% |
| `interface-e-idiomas/` | 38 | 0 | 1 | 97% |
| `orbita-e-passagens/` | 56 | 5 | 1 | 94% |
| `painel-web/` | 36 | 3 | 1 | 94% |
| `rotor/` | 36 | 1 | 3 | 91% |
| `sdr-e-telemetria/` | 43 | 3 | 1 | 95% |
| `sstv/` | 21 | 3 | 1 | 90% |

---

## Lacunas Pendentes 🔴

### rotor
- **Leitura AZ 140° EL 175° tratada como flip (320°/5°)** — depende de observação física da antena.
  - Pergunta correspondente: `questions.md#pergunta-1`

### cat-e-doppler / sstv
- **Validação em hardware real** de ICOM, Kenwood TS-790, WiSpDDE e SSTV TX — não se resolve por leitura de código.

---

## Recomendações

- [ ] Corrigir A4 (`settings.json` quebrado) e A1 (gravador do SDR): são os únicos achados que derrubam o programa ou a recepção.
- [ ] Corrigir A2/A3 (porta e socket presos) e A5 (Host no painel web).
- [ ] Alinhar o User-Agent (A6) e limitar as consultas sem rede da telemetria (A7).
- [ ] Responder `questions.md` (4 perguntas).
- [ ] Testes por funcionalidade: hoje os testes são nomeados por versão (`test_v1xx_*`).

---

## Histórico de Reclassificações

| De | Para | Afirmação | Evidência |
|----|------|-----------|-----------|
| 🟢 | 🟢 (corrigida) | "Instância única" → o mutex só serve ao instalador; segunda instância não é bloqueada | `app.py: _single_instance_mutex`, `main` |
| 🟡 | 🟢 | Sinais do display (`swap_clicked`, `rx_only_clicked`, ...) | `lcd.py:801` |
| 🟡 | 🟢 | Monitor removido: display destacado volta ao principal | `display_window.restore_placement` |
| 🟡 | 🟢 | Paginação de transmissores nunca devolve resultado parcial | `catalog.py:214` |
| 🟡 | 🟢 | Métodos do `EventJournal` (`append`, `export`) | `log_journal.py:21`, `:34` |
| 🟡 | 🟢/🟡 | ADR 005: readback confirmado no TS-2000; demais drivers têm `read_frequency` mas sem teste em hardware | `cat.py`, `rigs.py` |
| — | corrigida | ADR 008: em localhost não há chave, mas os controles continuam exigindo PIN | `web_ui.py: do_POST` |
