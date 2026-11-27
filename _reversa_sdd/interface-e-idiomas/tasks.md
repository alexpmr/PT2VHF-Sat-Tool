# Interface e idiomas, Tarefas de Implementação

## Tarefas
- [ ] T-01, `Config` com padrões, migrações "uma vez" e gravação atômica
  - Origem no legado: `sat_tool/config.py`
  - Critério de pronto: migrações não revertem escolhas
  - Confiança: 🟢
- [ ] T-02, Recuperação de `settings.json` corrompido
  - Origem no legado: `sat_tool/config.py: Config.__init__`
  - Critério de pronto: abre com padrões e guarda cópia `.corrompido`
  - Confiança: 🟢
- [ ] T-03, MainWindow, `background` e sinais
  - Origem no legado: `sat_tool/app.py:118`
  - Critério de pronto: mesma chave não duplica trabalho
  - Confiança: 🟢
- [ ] T-04, Idiomas, temas e escala
  - Origem no legado: `sat_tool/i18n*.py`, `appearance.py`, `ui_scale.py`
  - Critério de pronto: troca de idioma imediata
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v171_i18n.py`, `test_v181_i18n_dynamic.py`, `test_v171_appearance.py`, `test_v192_ui_scale.py`
- [ ] TT-02, Configuração corrompida
- [ ] TT-03, `test_v120_gui_smoke.py`

## Ordem Sugerida
1. T-01, T-02, T-03, T-04.

## Lacunas Pendentes (🔴)
- Nenhuma.
