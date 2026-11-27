# Painel web, Tarefas de Implementação

## Tarefas
- [ ] T-01, Servidor e rotas GET
  - Origem no legado: `sat_tool/web_ui.py:275`, `:465`
  - Critério de pronto: rotas respondem conforme contrato
  - Confiança: 🟢
- [ ] T-02, Autenticação por chave/cookie e filtro de clientes
  - Origem no legado: `sat_tool/web_ui.py:177`, `auth`
  - Critério de pronto: IP público recusado
  - Confiança: 🟢
- [ ] T-03, Checar `Host` em modo localhost
  - Origem no legado: `sat_tool/web_ui.py: Handler.auth`
  - Critério de pronto: Host estranho recebe 403/421
  - Confiança: 🟢
- [ ] T-04, Controle com validação, PIN e bloqueio
  - Origem no legado: `sat_tool/web_ui.py:197`, `:490`
  - Critério de pronto: `ptt` recusado; 5 erros → 429
  - Confiança: 🟢
- [ ] T-05, Firewall do Windows
  - Origem no legado: `sat_tool/web_ui.py:220`–`:248`
  - Critério de pronto: regra criada no perfil Privado
  - Confiança: 🟢

## Tarefas de Teste
- [ ] TT-01, `test_web_ui.py`, `test_v171_web_lan.py`
- [ ] TT-02, Host inválido em localhost

## Ordem Sugerida
1. T-01, T-02, T-03, T-04, T-05.

## Lacunas Pendentes (🔴)
- Nenhuma.
