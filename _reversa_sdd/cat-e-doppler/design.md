# CAT e Doppler, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `TS2000.set_frequencies` | `(uplink_hz, downlink_hz)` | readback | erro se divergir |
| `TS2000.set_orientation` | `(main_rx: bool)` | — | repete SA até ~2 s |
| `TS2000.set_rx_only` | `(downlink_hz)` | — | sem SAT, sem uplink |
| `<Rig>.connect / close` | `(port, baud, ...)` | — | cada driver em `rigs.py` |
| `<Rig>.is_transmitting` | `()` | `Optional[bool]` | bloqueia escrita em TX |
| `DopplerDispatcher` | limiar + intervalo mínimo | envia ou não | `rigs.py:773` |

Protocolos: Kenwood ASCII `FA/FB/FC/SA;`, Yaesu 5 bytes BCD (8N2), ICOM CI-V com eco, Hamlib rigctld TCP. 🟢

## Fluxo Principal
1. Operador conecta: `background("cat-connect")` abre a porta e lê o estado. 🟢
2. `cat_live_timer` (250 ms) chama `cat_live_tick` → `core.position` → previsão RX/TX. 🟢
3. Se a previsão difere do último pedido e do readback acima do limiar e o intervalo passou, agenda `cat-track`. 🟢
4. O driver escreve e lê de volta; `update_cat_sync_status` mostra o estado. 🟢
5. A cada 5–6 s, leituras opcionais (S-meter etc.) em `cat-readback`. 🟢

## Fluxos Alternativos
- **Orientação divergente no TS-2000:** escrita recusada, Auto CAT desarmado com aviso. 🟢
- **Rádio em TX:** escrita adiada. 🟢
- **Par inseguro:** Auto CAT desarmado. 🟢
- **Falha de conexão:** porta deve ser liberada (hoje não no FT817/Rigctld: A2/A3). 🟢

## Dependências
- pyserial 3.5; Hamlib rigctld externo; `orbita-e-passagens`. 🟢
- ctypes/DDEML no Windows para o DDE. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Nunca reenviar comando de escrita | `cat.py: _exchange` | 🟢 |
| Readback como fonte da verdade | `cat.py: poll_tracking` (ADR 005) | 🟢 |
| ICOM dual-band: SUB=RX, MAIN=TX | `rigs.py: Icom` | 🟢 |

## Estado Interno
Último pedido, último readback, orientação, flag SAT, estado de TX e chaves de trabalho em andamento na
`MainWindow`. 🟢

## Observabilidade
Log de cada escrita/leitura e mensagens de erro de porta (`test_v171_cat_port_error.py`). 🟢

## Riscos e Lacunas
- 🟢 A2: `FT817.connect` deixa a porta aberta se a leitura inicial falha.
- 🟢 A3: `Rigctld` deixa socket aberto e bytes no buffer após timeout.
- 🟡 ICOM, Kenwood TS-790 e WiSpDDE sem teste em hardware real.
