# Máquinas de estado — PT2VHF SAT Tool

> Reversa (Detetive), 27/11/2026.

## 1. Auto CAT (TS-2000) 🟢 `app.py`

```mermaid
stateDiagram-v2
  [*] --> Desconectado
  Desconectado --> Conectando: Conectar / abertura com porta salva
  Conectando --> Conectado: ID019; confirmado
  Conectando --> Desconectado: falha (porta ausente / em uso / sem resposta)
  Conectado --> SAT_OFF: SA P1=0
  SAT_OFF --> Conectado: operador liga SAT
  Conectado --> Armado: Auto CAT ligado + satélite + canal crossband
  Armado --> SintoniaInicial: primeira vez (preset FA/FB/MD)
  SintoniaInicial --> Rastreando: readback confere
  SintoniaInicial --> Backoff: falha
  Rastreando --> Rastreando: Doppler ≥ limiar → escreve e confere
  Rastreando --> Backoff: readback diverge / timeout
  Backoff --> Rastreando: tempo de espera passou
  Rastreando --> Bloqueado: par inseguro (mesma banda / sem uplink)
  Bloqueado --> Armado: operador escolhe outro canal
  Armado --> Conectado: Auto CAT desligado
  Conectado --> Desconectado: Desconectar / fechar
```

## 2. Rotor 🟢 `rotor_ui.py`

Modos escolhidos pelo operador: **DESLIGADO** (padrão), **MANUAL**, **AUTOMÁTICO**.
Chips exibidos no modo automático: AGUARDANDO AOS → PRÉ-POSICIONANDO → RASTREANDO → ESTACIONADO.

```mermaid
stateDiagram-v2
  [*] --> Desconectado
  Desconectado --> Desligado: conectar (posição lida)
  Desligado --> Manual: modo MANUAL
  Desligado --> Automatico: modo AUTOMÁTICO
  Manual --> Desligado
  Automatico --> Desligado
  state Automatico {
    [*] --> SemPassagem
    SemPassagem --> AguardandoAOS: próxima passagem
    AguardandoAOS --> PrePosicionando: AOS − 180 s
    PrePosicionando --> Rastreando: AOS
    Rastreando --> Estacionado: LOS (estaciona 1 vez)
    Estacionado --> AguardandoAOS: próxima passagem
  }
  Automatico --> Parado: Esc/F12, PARAR, 3 falhas, erro ao mover
  Parado --> Automatico: clique em PARADO
  Desligado --> Desconectado: desconectar / fechar (envia S)
```

## 3. Atualização OTA 🟢 `app.py` + `updater.py` + `apply-update.ps1`

```mermaid
stateDiagram-v2
  [*] --> Ocioso
  Ocioso --> Consultando: 12 s após abrir / a cada 15 min / botão
  Consultando --> Ocioso: nada novo, Linux/macOS só avisam
  Consultando --> Disponivel: versão maior com arquivo da variante
  Disponivel --> Adiada: "Depois" (snooze por versão)
  Disponivel --> Baixando: aprovado ou OTA automático
  Baixando --> Falha: tamanho/SHA diverge, redirecionamento
  Baixando --> Pronta: verificado
  Pronta --> Aplicando: pendência anotada, atualizador iniciado, app sai
  Aplicando --> Concluida: resultado "ok" na próxima abertura
  Aplicando --> FalhaExplicada: resultado de erro ou pendência sem resultado
```

## 4. Receptor SDR 🟢 `sdr.py`

`Parado → Rodando (start) → Gravando (início da passagem, se ligado) → Rodando (LOS) → Parado (stop / erro)`.
Erro na thread vira `status.error` com ajuda de driver (`open_error_help`).

## 5. Aviso de passagem 🟢 `alerts.py`

`Agendado (leads 1800/30 s) → Disparado por lead (uma vez cada) → Removido (após o LOS)`.
