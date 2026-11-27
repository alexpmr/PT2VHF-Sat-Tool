# Atualização OTA, Design Técnico

## Interface

| Método | Caminho | Entrada | Saída | Status codes |
|--------|---------|---------|-------|--------------|
| GET | `https://www.pt2vhf.com/update.php?product=sat[&call=]` | indicativo opcional | manifesto JSON `schema 1` | 200 |
| GET | `https://www.pt2vhf.com/downloads/sat-tool/<nome>` | — | binário (contado pelo `download.php`) | 200 |

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `select_release` | `(manifest, current_version, variant, kind, ...)` | `AvailableUpdate` ou `None` | só assets oficiais |
| `download_update` | `(update, progress=None)` | `Path` | tamanho + SHA-256 |
| `launch_staged_update` | `(package, *, portable, script_path, ...)` | — | app sai em seguida |

## Fluxo Principal
1. 12 s após abrir, `check_for_update` consulta o manifesto. 🟢
2. `select_release` escolhe o asset pela variante (`install_flavor`). 🟢
3. `download_update` baixa sem redirecionamento e confere tamanho/hash. 🟢
4. `mark_update_pending` grava a pendência; `launch_staged_update` copia e roda `apply-update.ps1` oculto. 🟢
5. O script espera o app sair, aplica Setup/Portable, grava o resultado e reabre. 🟢
6. Na abertura, `read_update_result`/`check_pending_update` informam sucesso ou falha. 🟢

## Fluxos Alternativos
- **Linux/macOS:** só aviso e link. 🟢
- **Código-fonte:** nunca atualiza. 🟢
- **Processos filhos presos:** o script encerra a árvore (v1.9.1). 🟢

## Dependências
- requests; PowerShell no Windows; Inno Setup no instalador. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Falha fechada em origem/hash | `updater.py` (ADR 003) | 🟢 |
| Helper fora do job do app | `updater.py:354` | 🟢 |

## Estado Interno
Arquivo de pendência e `PT2VHF-Sat-Tool-update-result.txt` na pasta temporária. 🟢

## Observabilidade
Log por etapa do `apply-update.ps1`. 🟢

## Riscos e Lacunas
- 🟢 Manifesto errado no site bloqueia todos os clientes: a publicação precisa conferir tamanho e SHA-256.
