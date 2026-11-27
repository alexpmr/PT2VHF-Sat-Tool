# Diagnóstico, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `install_diagnostics` | `()` | — | `faulthandler`, marcador |
| `report_exception` | `(source, exception)` | — | evento |
| `run_self_test` | `(report_path, expected_qt="")` | código de saída | usado pelo CI |
| `EventJournal` | `append(message)`, `export(destination, visible_log, diagnostics_dir, version)` | — | 🟢 [Revisão] `log_journal.py:21`, `:34` |

## Fluxo Principal
1. Na abertura, `install_diagnostics` grava estado "rodando" e verifica a sessão anterior. 🟢
2. Heartbeat a cada 30 s. 🟢
3. Ao sair normalmente, `clean_shutdown`. 🟢

## Fluxos Alternativos
- **`--self-test`:** importa os módulos, valida o binding Qt e grava o relatório, sem abrir a janela. 🟢

## Dependências
- `faulthandler`, `zipfile`, psutil. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Autoteste dentro do próprio binário | `diagnostics.py` | 🟢 |

## Estado Interno
Arquivos de estado e eventos em `diagnostic_dir()`. 🟢

## Observabilidade
É a própria camada de observabilidade do app. 🟢

## Riscos e Lacunas
- 🟡 `diagnostics.py` importa quase todos os módulos: qualquer import quebrado falha o autoteste (desejado).
