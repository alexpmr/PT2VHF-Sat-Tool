# Build e publicação, Tarefas de Implementação

## Tarefas
- [ ] T-01, Atualizar a versão em todos os arquivos fixos
  - Origem no legado: `sat_tool/__init__.py`, `.github/workflows/windows.yml`, `installer/setup.iss`, `scripts/Build-Windows.ps1`, testes
  - Critério de pronto: CI aceita a versão
  - Confiança: 🟢
- [ ] T-02, Pipeline de build e autoteste
  - Origem no legado: `.github/workflows/windows.yml`
  - Critério de pronto: todos os jobs verdes
  - Confiança: 🟢
- [ ] T-03, Publicação no site com SHA-256
  - Origem no legado: `scripts/publish_sat_to_site.py`
  - Critério de pronto: `updates.json` confere com os arquivos
  - Confiança: 🟢
- [ ] T-04, Verificação pública
  - Origem no legado: regra do mantenedor (CLAUDE.md)
  - Critério de pronto: `/sat`, `/updates.json`, `update.php?product=sat` e download real conferidos
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v172_versioned_binaries.py`, `test_v173_deb_package.py`, `test_win10_installer.py`

## Ordem Sugerida
1. T-01, T-02, T-03, T-04.

## Lacunas Pendentes (🔴)
- Nenhuma.
