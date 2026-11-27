# Atualização OTA

## Visão Geral
Verifica, baixa e instala versões novas do SAT Tool somente a partir de www.pt2vhf.com, com conferência de
tamanho e SHA-256, e registra opcionalmente o indicativo do operador na lista de usuários do site. 🟢

## Responsabilidades
- Consultar `update.php?product=sat` (com `&call=` opcional). 🟢
- Escolher o pacote certo para a instalação (Setup/Portable, Win11-x64/Win7-x86). 🟢
- Baixar com verificação de tamanho e SHA-256. 🟢
- Aplicar com `apply-update.ps1` fora do processo do app e reabrir. 🟢
- Explicar falhas na abertura seguinte com link manual. 🟢

## Regras de Negócio
- Só `https://www.pt2vhf.com/downloads/sat-tool/<nome>`, sem redirecionamento (R18, ADR 003). 🟢
- Linux e macOS só recebem aviso e link (R19). 🟢
- Execução pelo código-fonte nunca se atualiza. 🟢
- Indicativo só se válido (`CALLSIGN_RE`) e se `share_callsign` ligado (R20). 🟢
- Portátil nunca toca em `data/` (R21). 🟢
- OTA automático ligado por padrão e configurável. 🟢
- Download OTA conta uma vez no `download.php`. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Verificar versão aos 12 s e pelo botão | Must | Versão maior gera aviso/instalação |
| RF-02 | Baixar com SHA-256 | Must | Hash divergente aborta |
| RF-03 | Aplicar Setup ou trocar portátil | Must | App reabre na versão nova |
| RF-04 | Resultado da atualização na abertura seguinte | Should | Falha mostra motivo e link |
| RF-05 | Registrar indicativo | Could | Só com opção ligada |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Origem única e hash obrigatório | `updater.py: is_official_asset`, `download_update` | 🟢 |
| Robustez | Helper desacoplado (`CREATE_BREAKAWAY_FROM_JOB`) | `updater.py: helper_creation_flags` | 🟢 |
| Privacidade | Indicativo só com consentimento | `updater.py: callsign_param` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o manifesto com a versão 1.9.8 e SHA-256 correto
Quando o app 1.9.7 instalado verifica atualização
Então baixa, confere o hash, aplica e reabre na 1.9.8

Dado um manifesto com URL fora de www.pt2vhf.com
Quando o app verifica
Então a atualização é ignorada

Dado um arquivo baixado com tamanho diferente
Quando a verificação roda
Então a instalação é abortada com mensagem e link manual
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Verificar, baixar, aplicar | Must | Canal oficial de atualização |
| Resultado e indicativo | Should/Could | Suporte e lista de usuários |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/updater.py` | `install_flavor`, `select_release`, `is_official_asset`, `check_for_update`, `download_update`, `launch_staged_update`, `start_update_helper`, `read_update_result`, `check_pending_update`, `rename_portable_to_version` | 🟢 |
| `scripts/apply-update.ps1` | aplicação | 🟢 |
| `sat_tool/app.py` | `check_for_updates`, `maybe_prompt_update`, `request_update`, `update_ready`, `show_last_update_result` | 🟢 |
