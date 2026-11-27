# Fluxo — Atualização OTA (Windows)

```mermaid
sequenceDiagram
  participant App as Sat Tool
  participant Site as www.pt2vhf.com
  participant PS as apply-update.ps1
  participant Inno as Setup (Inno)
  App->>Site: GET /update.php?product=sat[&call=]
  Site-->>App: manifesto schema 1 (versão, files[name,url,size,sha256])
  App->>App: select_release (variante Win11-x64, Setup ou Portable)
  App->>App: aviso / OTA automático (auto_update)
  App->>Site: GET /downloads/sat-tool/<nome> (sem redirecionamento)
  Site-->>App: bytes (download.php remonta as partes e conta 1 download)
  App->>App: confere tamanho + SHA-256
  App->>App: mark_update_pending; copia apply-update.ps1 para %TEMP%
  App->>PS: powershell oculto (WaitPid, Package, Destination, Mode, Version)
  App->>App: encerra
  PS->>PS: espera a árvore de processos do app (sem incluir a si mesmo)
  alt Setup
    PS->>Inno: /VERYSILENT … log em %TEMP%
    Inno-->>PS: código de saída
  else Portable
    PS->>PS: troca o EXE portátil (nunca toca em data/)
  end
  PS->>PS: grava update-result.txt e reabre o programa
  App->>App: na abertura: read_update_result / check_pending_update
```
