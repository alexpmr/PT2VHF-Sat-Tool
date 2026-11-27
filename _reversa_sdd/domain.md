# Domínio — PT2VHF SAT Tool

> Reversa (Detetive), 27/11/2026. 🟢 CONFIRMADO · 🟡 INFERIDO · 🔴 LACUNA

## Contexto

Programa de estação de radioamador para operar satélites (contatos via repetidores FM e transponders lineares
SSB/CW, recepção de telemetria, APRS e SSTV). O operador escolhe satélites, vê as passagens, e o programa
mantém o rádio e o rotor apontados/sintonizados enquanto ele fala. 🟢

Mantenedor: PT2VHF (Alex). Usuários citados no backlog: PU2MUS e outros operadores. Distribuição oficial só por
www.pt2vhf.com. 🟢

## Glossário

| Termo | Significado no programa |
|---|---|
| **NORAD** | número de catálogo do satélite (chave estável de tudo: seleção, cache, transmissores) 🟢 |
| **OMM / TLE** | elementos orbitais (JSON da CelesTrak ou texto de 2/3 linhas); `EPOCH` mais novo vence 🟢 |
| **Passagem** | intervalo em que o satélite fica acima da elevação mínima: AOS (início), TCA (máxima), LOS (fim) 🟢 |
| **Elevação mínima** | máscara de horizonte da estação (padrão 10°) usada nas previsões 🟢 |
| **Doppler** | desvio de frequência pela velocidade radial; RX = f·(1−v/c), TX = f/(1−v/c) 🟢 |
| **Downlink / uplink** | frequência que o satélite transmite (RX da estação) / que recebe (TX da estação) 🟢 |
| **Transponder linear / invertido** | faixa que repassa SSB/CW; no invertido, subir o uplink desce o downlink 🟢 |
| **Canal** | par downlink/uplink publicado no SatNOGS (ou perfil AMSAT fixo do SO-50) 🟢 |
| **RX only / somente RX** | canal sem uplink (beacon, telemetria) ou modo em que o programa só sintoniza a recepção 🟢 |
| **Crossband** | RX e TX em bandas diferentes (2 m × 70 cm): único par aceito pelo Auto CAT do TS-2000 🟢 |
| **Modo SAT (TS-2000)** | MAIN e SUB em full duplex; FA = downlink, FB = uplink; MAIN↔SUB inverte os papéis 🟢 |
| **Auto CAT** | rastreamento automático de Doppler no rádio pelo CAT, sempre confirmado por readback 🟢 |
| **CAT SYNC** | estado em que a leitura FA/FB do rádio bate com a previsão dentro do limiar 🟢 |
| **Readback** | leitura de volta do rádio após escrever, para confirmar a frequência real 🟢 |
| **Rotor / GS-232 / rotctld** | controlador az/el pela serial (Yaesu GS-232A/B, ERC-M) ou pelo Hamlib em rede 🟢 |
| **Flip** | modo do rotor com elevação até 180°: az+180 e 180−el para atravessar o norte sem dar a volta 🟢 |
| **Estacionar (park)** | levar a antena à posição de repouso do perfil depois do LOS 🟢 |
| **Pré-posicionar** | apontar para o início da passagem até 180 s antes do AOS 🟢 |
| **Display** | painel que imita o mostrador de um rádio real (só exibe; nunca comanda o rádio sozinho) 🟢 |
| **Pipeline** | como receber um transmissor: voz, AFSK 1200 interno ou dados por KISS (SoundModem) 🟢 |
| **SiDS** | protocolo de envio de quadros de telemetria ao SatNOGS DB (opcional) 🟢 |
| **OTA** | atualização pelo próprio programa a partir do site, com SHA-256 🟢 |
| **Variante / edição** | Win11-x64 Setup/Portable, Linux-x64, macOS-arm64 (Win7-x86 legado) 🟢 |
| **Satélites padrão** | ISS, SO-50, IO-86, AO-7, FO-29, RS-44, SONATE-2, LUČA-1 e HADES-E2 (por nome) 🟢 |

## Regras de negócio

### Segurança de transmissão
- R1 🟢 O programa nunca aciona PTT nem envia comandos de transmissão pelo CAT, em nenhum rádio.
- R2 🟢 A rede (painel web) nunca pode pedir TX/PTT nem comandos CAT diretos; tentativas são registradas e recusadas.
- R3 🟢 Frequência só é escrita no TS-2000 com SAT ligado e orientação MAIN/SUB conferida; o Auto CAT é desarmado se
  o par não for crossband válido.
- R4 🟢 Nenhum rádio muda de frequência durante um câmbio (TX), exceto quando o modo SAT do próprio rádio exige que o
  uplink siga o Doppler (FT-847, ICOM dual-band).
- R5 🟢 A transmissão de SSTV é a única exceção ao "nunca transmitir": gera áudio; o PTT é do VOX.

### Seleção e frequências
- R6 🟢 Dados do SatNOGS são "publicados, não confirmados"; o programa diz isso na interface e nunca afirma que um
  satélite está ativo só pela órbita.
- R7 🟢 Canal com uplink tem prioridade; entre eles FM > SSB > CW; beacon nunca vira TX.
- R8 🟢 SO-50 sempre usa o par AMSAT (145,850 MHz ↑ / 436,795 MHz ↓ FM) como padrão.
- R9 🟢 Satélites padrão entram na seleção uma única vez por instalação; se o operador desmarcar, a escolha vale.
- R10 🟢 Seleção manual de satélites não depende do cache de frequências.

### Catálogo e rede
- R11 🟢 A CelesTrak é consultada no máximo a cada 2 h por grupo; falha de rede usa o cache.
- R12 🟢 Satélite padrão sem órbita na CelesTrak usa o TLE do SatNOGS.
- R13 🟢 Transmissores do SatNOGS numa única consulta paginada, sem sair de `db.satnogs.org`.
- R14 🟢 Localização por IP só com consentimento explícito; nada é aplicado à estação sem confirmação.

### Rotor
- R15 🟢 Nenhum movimento por simplesmente escolher um satélite; o rotor começa DESLIGADO e o automático é pedido
  pelo operador.
- R16 🟢 PARAR em qualquer erro de movimento, perda de comunicação (3 leituras falhas), Esc/F12 e ao fechar.
- R17 🟢 Move só quando o erro passa da tolerância (4°) e depois do intervalo mínimo (2 s).

### Atualização e distribuição
- R18 🟢 Downloads e atualizações só de `https://www.pt2vhf.com/downloads/sat-tool/`, com tamanho e SHA-256 do
  manifesto; sem redirecionamento; build de código-fonte nunca se atualiza sozinho.
- R19 🟢 Linux e macOS só recebem aviso e link (instalação manual).
- R20 🟢 O indicativo vai na consulta de versão só se for válido e se `share_callsign` estiver ligado (lista de
  usuários no site).
- R21 🟢 Portátil nunca toca na pasta `data/` ao atualizar.
- R22 🟢 (regra do mantenedor, CLAUDE.md) Versão nova só com pedido explícito; "gerar versão nova" = resolver o
  backlog, release completa, publicar no site e garantir o aviso nos clientes.

### Privacidade e diagnóstico
- R23 🟢 Diagnóstico de falhas sem coordenadas, CAT ou configurações pessoais; logs ficam no computador.
- R24 🟢 Envio de telemetria ao SatNOGS só se o operador ligar a opção.

## Lacunas
- 🔴 L1: para onde a antena apontava quando o rotor leu AZ 140° EL 175° (o app trata como flip → 320°/5°).
- 🔴 L2: `profile.freq_band` usa UHF a partir de 430 MHz e `transponder.BANDS` a partir de 420 MHz: diferença
  intencional (CAT aceita 420–430) ou descuido?
- 🔴 L3: homologação em campo pendente (OTA real, rotor ERC-M, CAT ICOM/Kenwood, WiSpDDE, 2 monitores, LAN) —
  ver `docs/homologacao-campo.md`.
