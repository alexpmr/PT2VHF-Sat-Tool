# Catálogo e TLE, Tarefas de Implementação

## Pré-requisitos
- [ ] Diretório de dados do usuário definido
- [ ] Acesso HTTPS a CelesTrak e SatNOGS (ou fixtures)

## Tarefas
- [ ] T-01, Download de grupos com cache de 2 h e reserva no cache
  - Origem no legado: `sat_tool/catalog.py`
  - Critério de pronto: sem requisição dentro de 2 h; sem rede usa cache
  - Confiança: 🟢
- [ ] T-02, Parser TLE 2LE/3LE com Alpha-5 e conversão para OMM
  - Origem no legado: `sat_tool/catalog.py:333`
  - Critério de pronto: linha inválida pulada
  - Confiança: 🟢
- [ ] T-03, Mescla por NORAD com regra de EPOCH
  - Origem no legado: `sat_tool/catalog.py:44`
  - Critério de pronto: elemento mais velho não substitui o mais novo
  - Confiança: 🟢
- [ ] T-04, Busca de padrões por NORAD e por nome com reserva SatNOGS
  - Origem no legado: `sat_tool/catalog.py:116`, `config.py`
  - Critério de pronto: LUČA-1 e HADES-E2 presentes
  - Confiança: 🟢
- [ ] T-05, Transmissores numa consulta paginada
  - Origem no legado: `sat_tool/catalog.py:269`
  - Critério de pronto: no máximo 200 páginas, só em db.satnogs.org
  - Confiança: 🟢
- [ ] T-06, Seleção, padrões uma vez e prioridade de transponders
  - Origem no legado: `sat_tool/selection.py:5`, `transponder.py:59`
  - Critério de pronto: desmarcar persiste; SO-50 fixo
  - Confiança: 🟢
- [ ] T-07, User-Agent com a versão real do app
  - Origem no legado: `sat_tool/catalog.py: HEADERS`
  - Critério de pronto: UA igual a `PT2VHF-Sat-Tool/<__version__>`
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_v130_catalog_aos.py`, `test_v181_tle_sources.py`, `test_v194_tle_alpha5.py`
- [ ] TT-02, `test_v197_satnogs_bulk.py`, `test_v196_luca1_default.py`
- [ ] TT-03, Falha de rede com cache

## Ordem Sugerida
1. T-02, T-03, T-01; depois T-04/T-05; por fim T-06/T-07.

## Lacunas Pendentes (🔴)
- Nenhuma.
