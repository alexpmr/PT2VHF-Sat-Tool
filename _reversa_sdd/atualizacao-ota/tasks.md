# Atualização OTA, Tarefas de Implementação

## Tarefas
- [ ] T-01, Variante de instalação e seleção do asset
  - Origem no legado: `sat_tool/updater.py:44`, `:121`
  - Critério de pronto: Setup e Portable escolhidos corretamente
  - Confiança: 🟢
- [ ] T-02, Download com origem única e SHA-256
  - Origem no legado: `sat_tool/updater.py:108`, `:199`
  - Critério de pronto: URL estranha ou hash errado recusados
  - Confiança: 🟢
- [ ] T-03, Helper e script de aplicação
  - Origem no legado: `sat_tool/updater.py:331`–`:367`, `scripts/apply-update.ps1`
  - Critério de pronto: app reabre na versão nova
  - Confiança: 🟢
- [ ] T-04, Resultado e pendência na abertura
  - Origem no legado: `sat_tool/updater.py:269`–`:322`
  - Critério de pronto: falha explicada com link
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_updater.py`, `test_v160_ota.py`, `test_v181_ota_relaunch.py`, `test_v191_ota_self_kill.py`, `test_v194_ota_pending.py`

## Ordem Sugerida
1. T-01, T-02, T-03, T-04.

## Lacunas Pendentes (🔴)
- Nenhuma.
