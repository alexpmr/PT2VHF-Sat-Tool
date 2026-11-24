# Homologação em campo — PT2VHF Sat Tool (a partir da v1.9.3)

Roteiro para o operador testar com o equipamento real. Para cada item, responda **OK**, **Falhou** (o que
aconteceu) ou **Não testado**. Em caso de falha: aba **LOGs / CAT → "Baixar log completo (ZIP)"** logo depois.

## 1. Atualização automática (OTA)
- [ ] Com a versão anterior instalada, o aviso de versão nova aparece sozinho (até 15 min) ou por "Verificar atualizações".
- [ ] "Atualizar": o programa fecha, instala e **reabre sozinho** já na versão nova (título e Sobre).
- [ ] Edição usada: Setup ou Portátil? Com o RTL-SDR ligado ou desligado durante a atualização?

## 2. Rotor G-5400B pelo ERC-M (GS-232) — depende do cabo
- [ ] Configurações → Rotores: porta COM encontrada, **Conectar** e posição lida (gauges batem com o indicador do controlador).
- [ ] Ao abrir, o rotor está em **DESLIGADO** e não se move.
- [ ] **MANUAL:** setas ◀ ▶ ▲ ▼ movem no passo escolhido (1°/5°/10°); segurar repete; para nos limites (450° / 180°).
- [ ] **AUTOMÁTICO:** pré-posiciona antes do AOS, acompanha a passagem, faz o flip quando precisa e estaciona no LOS.
- [ ] **PARAR** (botão, Esc e F12) para na hora em qualquer modo; em AUTOMÁTICO passa a MANUAL.
- [ ] Calibração do norte (offset) e posição de estacionamento ficam salvas ao reabrir.

## 3. Rádios por CAT
- [ ] Kenwood TS-2000: frequências e modo seguem o Doppler; tecla A/B (MAIN↔SUB) e RX ONLY.
- [ ] ICOM (CI-V) — modelo: ______ endereço CI-V: ____ — sintoniza RX/TX e o split no mesmo rádio.
- [ ] Kenwood CAT texto (TS-480/590/890/990) — modelo: ______.
- [ ] ICOM IC-9700/910/9100/821 com RX e TX no mesmo rádio: downlink na SUB, uplink na MAIN, modo satélite ligado,
  Doppler do RX acompanhando durante o TX.
- [ ] Yaesu FT-847: modo SAT ligado pelo programa; SAT RX e SAT TX acompanham o Doppler (FM e SSB invertido).
- [ ] Yaesu FT-991/991A (CAT texto): RX no VFO-A, TX no VFO-B com o SPLIT ligado no rádio; modo do VFO-B certo.
- [ ] WiSpDDE (Windows): "Receive DDE from Orbitron" recebe satélite e frequências.

## 4. RTL-SDR
- [x] Áudio de RX contínuo, **sem cortes a cada ~2 s** — **OK, confirmado pelo operador em 24/11/2026.**
- [ ] Waterfall no painel SDR e escopo no display (modelos com escopo); clique no escopo sintoniza.

## 5. Tela e display
- [ ] Escala automática (1.9.3): na tela do PU2MUS (1366×768) a aba Operação cabe sem rolagem.
- [x] Display destacado em **2 monitores** (DPI diferentes): move, tela cheia (F11), lembra o monitor ao reabrir —
  **OK, confirmado pelo operador em 24/11/2026.**
- [ ] Moldura de rádio (Configurações → Aparência) com etiqueta: teclas A/B, RX ONLY, TIPO e LUZ funcionam.

## 6. Rede e idiomas
- [ ] Painel Web aberto no celular/notebook da mesma rede; "Liberar no firewall do Windows" resolve o acesso.
- [ ] Controle pela rede com PIN (satélite, Auto CAT, A/B, RX ONLY, rotor/PARAR) — PTT nunca acionado.
- [ ] Idiomas japonês e chinês com as letras corretas (Windows e macOS).

## 7. Catálogo de satélites
- [ ] **LUČA-1 (RS90S)**, NORAD 67287, aparece na busca do catálogo depois de "Atualizar TLE" (fonte R4UAB ligada) — **na versão com a correção Alpha-5**.
