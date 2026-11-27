# Diagnóstico

## Visão Geral
Registra falhas e eventos para suporte sem expor dados pessoais, executa o autoteste usado pelo CI no binário
empacotado e oferece o log completo exportável e o debug do áudio RX. 🟢

## Responsabilidades
- Detectar saída anormal e falhas nativas (`faulthandler`). 🟢
- Manter eventos com rotação de tamanho (3 MiB). 🟢
- Autoteste `--self-test <relatorio.json>`. 🟢
- Diário de eventos local exportável em ZIP. 🟢
- Debug do áudio RX (por segundo, travamentos > `STALL_MS`). 🟢

## Regras de Negócio
- Sem coordenadas, CAT ou configurações pessoais nos diagnósticos (R23). 🟢
- Logs ficam no computador; nada é enviado automaticamente. 🟢
- Heartbeat a cada 30 s; `clean_shutdown` marca saída normal. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Marcar e relatar saída anormal | Must | Próxima abertura informa a falha |
| RF-02 | Autoteste do binário | Must | Relatório JSON com resultado por módulo |
| RF-03 | Exportar log completo em ZIP | Should | ZIP sem dados pessoais |
| RF-04 | Debug do áudio RX | Could | Arquivo com travamentos |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Privacidade | Sem dados pessoais | `crash_diagnostics.py` | 🟢 |
| Armazenamento | Rotação em 3 MiB | `crash_diagnostics._rotate` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado que o programa fechou por falha nativa
Quando é aberto de novo
Então informa a falha anterior com o arquivo de diagnóstico

Dado o binário recém-gerado no CI
Quando roda com --self-test relatorio.json
Então o relatório indica sucesso e o binding Qt esperado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Autoteste e falhas | Must | Gate do CI e suporte |
| Log e debug RX | Should/Could | Suporte |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/crash_diagnostics.py` | `install_diagnostics`, `heartbeat`, `report_exception`, `report_event`, `clean_shutdown`, `_rotate` | 🟢 |
| `sat_tool/diagnostics.py` | `run_self_test` | 🟢 |
| `sat_tool/log_journal.py` | `EventJournal` | 🟢 |
| `sat_tool/rx_debug.py` | debug do áudio RX | 🟢 |
| `sat_tool/resource_meter.py` | medidor CPU/RAM | 🟢 |
