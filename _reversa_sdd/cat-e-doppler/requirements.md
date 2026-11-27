# CAT e Doppler

## Visão Geral
Sintoniza o rádio do operador pelo CAT com as frequências corrigidas por Doppler durante a passagem (Auto CAT),
para TS-2000 e demais rádios suportados, sem nunca transmitir. Também publica o Doppler por DDE. 🟢

## Responsabilidades
- Conectar ao rádio (serial ou Hamlib rigctld) e detectar porta/modelo (`cat_scan`). 🟢
- Configurar modo satélite ou split conforme o rádio. 🟢
- Escrever RX/TX corrigidos e confirmar por leitura de volta. 🟢
- Ler estado do rádio (S-meter, modo, TX) sem atrasar o Doppler. 🟢
- Publicar Doppler para clientes DDE (WiSpDDE/Orbitron). 🟢

## Regras de Negócio
- Nunca acionar PTT nem comandos de TX (R1, ADR 001). 🟢
- TS-2000: só escreve com SAT ligado e orientação MAIN/SUB conferida (R3). 🟢
- Nenhum rádio muda de frequência durante TX, exceto quando o modo SAT exige seguir o uplink (R4). 🟢
- Escreve só quando a previsão difere do último pedido e do último readback em pelo menos o limiar (padrão 1 Hz, intervalo 1 s). 🟢
- Par inseguro (mesma banda, sem uplink) desarma o Auto CAT. 🟢
- RX ONLY escreve só o VFO de recepção e nunca liga SAT. 🟢
- Doppler continua fora do horizonte por padrão (`cat_doppler_out_of_view` forçado a `True`). 🟢
- Um trabalho CAT por vez. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Conectar ao TS-2000 em modo SAT e ler FA/FB | Must | Status "sincronizado" após readback |
| RF-02 | Auto CAT: escrever Doppler a cada mudança acima do limiar | Must | Sem escrita quando a diferença < limiar |
| RF-03 | Suportar FT-817/818, FT-847, Yaesu texto, ICOM CI-V, Kenwood texto, rigctld | Must | Cada driver passa no teste de protocolo |
| RF-04 | Trocar MAIN↔SUB e A/B | Should | Confirmado por leitura em até ~2 s |
| RF-05 | Modo RX ONLY | Should | Nenhum comando de uplink enviado |
| RF-06 | Varrer portas para achar o rádio | Should | Lista portas que respondem |
| RF-07 | Servidor DDE para WiSpDDE | Could | Texto `SN.. AZ.. EL.. DN.. UP..` |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Timeout serial 0,35 s; resposta remontada em até 4 s | `cat.py: TS2000._exchange` | 🟢 |
| Segurança operacional | Sem PTT | `cat.py`, `rigs.py` | 🟢 |
| Robustez | Leituras opcionais a cada 5–6 s não bloqueiam o Doppler | `cat.py` | 🟢 |
| Robustez | Falha de conexão deve liberar porta/socket | `rigs.py: FT817.connect`, `Rigctld.connect` | 🟢 (achados A2, A3) |

## Critérios de Aceitação

```gherkin
Dado o TS-2000 em modo SAT com MAIN=RX e SUB=TX
Quando o Auto CAT está ligado durante uma passagem
Então FA recebe o downlink corrigido, FB o uplink corrigido, e o readback confirma

Dado o rádio em TX
Quando o Doppler muda
Então nenhuma frequência é escrita (salvo o uplink em modo SAT)

Dado que o FT-817 não responde à leitura inicial
Quando a conexão falha
Então a porta é fechada e uma nova tentativa funciona

Dado que o rigctld demora no meio de uma resposta
Quando ocorre timeout
Então o buffer é limpo e a próxima resposta não sai defasada
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| TS-2000 e Auto CAT | Must | Rádio homologado do mantenedor |
| Demais drivers | Must | Suportados na interface (sem teste em hardware real para ICOM/Kenwood) |
| DDE | Could | Integração opcional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/cat.py` | `TS2000` (`_exchange`, `set_frequencies`, `set_orientation`, `set_rx_only`, `poll_tracking`) | 🟢 |
| `sat_tool/rigs.py` | `FT817`, `Icom`, `FT847`, `YaesuText`, `KenwoodText`, `Rigctld`, `DopplerDispatcher` | 🟢 |
| `sat_tool/cat_scan.py` | varredura de portas | 🟢 |
| `sat_tool/dde_server.py` | servidor DDE | 🟢 |
| `sat_tool/app.py` | `track_cat_frequencies`, `cat_live_tick`, `auto_tune_selected_satellite`, `update_cat_sync_status` | 🟢 |
