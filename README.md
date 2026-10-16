<p align="center"><img src="assets/branding/logo-horizontal.svg" alt="PT2VHF Sat Tool" width="560"></p>

# PT2VHF Sat Tool

## Downloads — instaladores e portáteis

**PT2VHF Sat Tool v1.3.10 — Windows 7 SP1, Windows 10 e Windows 11.** Os quatro downloads são arquivos `.exe` diretos. Links ficam disponíveis após aprovação dos builds Windows. Embora seja o marco 1.0 de funcionalidades, permanece em pré-lançamento até a homologação CAT com TS-2000 físico e Windows 7 real.

| Windows | Instalável | Portátil |
| --- | --- | --- |
| **Windows 7 SP1** (x86; executável de 32 bits também para Win7 x64) | [Instalador Win7 x86](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v1.3.10/PT2VHF-Sat-Tool-v1.3.10-Win7-x86-Setup.exe) | [Portable Win7 x86](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v1.3.10/PT2VHF-Sat-Tool-v1.3.10-Win7-x86-Portable.exe) |
| **Windows 10 (1809+)/11** (x64; arquivo `Win11-x64` para manter atualizador) | [Instalador Win11 x64](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v1.3.10/PT2VHF-Sat-Tool-v1.3.10-Win11-x64-Setup.exe) | [Portable Win11 x64](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v1.3.10/PT2VHF-Sat-Tool-v1.3.10-Win11-x64-Portable.exe) |

**Formato dos downloads:** tanto instaladores quanto portáteis são entregues diretamente como arquivos **`.exe`**. O portátil inclui as dependências dentro do mesmo EXE (PyInstaller onefile) e não requer descompactação.

**[Todas as releases](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases)** · **[Acompanhar compilação](https://github.com/alexpmr/PT2VHF-Sat-Tool/actions)**

- **Instalável:** instalação por usuário, atalho e desinstalação, atualização pelo aplicativo usando o Setup de sua edição.
- **Portátil:** execute diretamente `PT2VHF-Sat-Tool-v1.3.10-*-Portable.exe` (um único arquivo). Configurações ficam em `data/` ao lado do EXE, preservadas após atualizações.
- **Win7:** Python 3.8 x86 + PySide2/Qt5 + PyInstaller 5.13.2 (legado, precisa ser validado no Windows 7 real).
- **Win10/11 x64:** Windows 10 1809+ ou Windows 11, Python 3.11 x64 + PySide6/Qt6 + PyInstaller 6.13.0.
- Arquivos SHA256 acompanham cada compilação. A versão Windows 7 é experimental; não confundir sucesso do CI com homologação em campo.

---


## Novidades v1.3.10 — Satélites, Passagens e telemetria TS-2000

- **Passagens:** colunas AOS/TCA/LOS e Max ° dimensionadas pelo conteúdo; colunas Satélite e Modos distribuem todo o espaço livre do painel. Cabeçalhos/valores alinhados e conteúdo integral disponível por tooltip.
- **Satélites:** seleção do catálogo por clique na linha, sem coluna/checkbox “Selecionado”. Registros selecionados ficam com **fundo amarelo e letras pretas** (inclusive após nova pesquisa e reinício). Duplo clique mantém acesso à operação.
- **Baixar/atualizar frequências:** inclui **todos os NORAD IDs do catálogo orbital carregado**, independentemente de favoritos, seleção individual ou filtro de pesquisa. O processo em lote continua cancelável, com progresso, resumo de falhas e confirmação antes de consultas numerosas.
- **Cartões de frequência RX/TX:** exibir modo e frequência corrigida, removendo a linha de deslocamento Doppler desses cartões; a informação orbital/Doppler e o diagnóstico continuam disponíveis em outras seções.
- **Informações reais do TS-2000:** telemetria CAT somente leitura a cada cerca de 2 segundos (enquanto Auto CAT está ativo), incluindo controle MAIN/SUB, TRACE, VFO/MEM, modo MAIN, SUB RX/FC, S-meter MAIN/SUB e potência configurada/medidor quando a resposta for válida. Leitura da potência **não significa medição da saída RF**. As leituras não enviam PTT e não substituem o loop rápido FA/FB de Doppler.
- **Homologação pendente:** verificar a responsividade das leituras com TS-2000 físico e eventual limitação da porta COM; os testes CI usam emulação de protocolo.

## Novidades v1.3.8 — SO-50 FM V/U e diagnóstico do bloqueio CAT

## Ajustes adicionais v1.3.8 — CAT online e agenda automática

- **Doppler CAT em tempo real:** motor CAT com timer independente de 250 ms, sem depender da atualização do mapa. Intervalo de escrita configurável entre **0,25 e 15 segundos**, respeitando a variação mínima em Hz; não promete confirmação subsegundo se a porta serial ou rádio forem mais lentos.
- **Leitura real FA/FB:** cada ajuste usa readback rápido SA/FA/FB, evitando consultar FC/modo/medidores a cada escrita. Exibe diferença em Hz entre o destino CAT enviado e o confirmado, tempo de comando e status sincronizado/divergente; mantém consultas periódicas de telemetria separadas.
- **Seleção de satélite e transponder:** troca pela tabela ou pela lista de passagens aciona a sintonia automática, se Auto CAT estiver autorizado. Seleção manual do serviço é preservada quando o catálogo é atualizado.
- **Próxima passagem e lista:** ambas refletem o satélite selecionado, não o próximo satélite da lista global. O topo usa o canal/transponder atualmente escolhido; datas e contador atualizados automaticamente. A lista de 36 horas é recalculada ao trocar de satélite e de cinco em cinco minutos; **removido o botão Recalcular passagens**. Painel lateral ampliado e sem quebra de linha em horários.
- **Atualização de versões:** não há mais pop-up de aviso ou notas de novidades. A versão nova aparece apenas no botão da barra superior; clicar inicia download verificado por SHA256, com progresso, seguido de instalação. Sem versão disponível, o botão indica Última versão. Erros mantêm o aplicativo aberto.
- **Teste físico pendente:** confirmar CAT em TS-2000 real, latência serial, qualidade de sincronização e segurança durante eventual transmissão.



- Ao selecionar SO-50/NORAD 27607, o canal FM de referência AMSAT passa a ser o perfil padrão, com downlink RX **436,795 MHz** e uplink TX **145,850 MHz**. A ordenação de registros SatNOGS de telemetria ou com canais antigos não poderá substituir esse par na seleção inicial.
- Em outros satélites, transponders completos e crossband passam à frente de entradas RX-only ou da mesma banda. A seleção explícita do operador é preservada durante atualização do catálogo.
- O bloqueio CAT mostra exatamente as frequências **RX/TX**, o **NORAD**, o **nome do transponder** e o **motivo da recusa**; o LOG inclui a mesma evidência para diagnóstico. Não desliga a proteção para pares realmente incompatíveis nem envia PTT.
- O acompanhamento Doppler contínuo a cada segundo da v1.3.7 foi mantido. Ainda é necessário verificar no TS-2000 real.

## Novidades v1.3.7 — Auto CAT contínuo, sem botão de sintonia

- **Auto CAT online em 1 segundo:** com o TS-2000 conectado e SAT ON, o satélite e transponder selecionados são programados uma vez, e FA/downlink e FB/uplink seguem automaticamente as correções Doppler a cada ciclo de 1 segundo quando há variação mínima de 1 Hz. O botão redundante **Sintonizar agora** foi removido da operação principal.
- **Ativação:** a preferência persistente Auto CAT é a autorização do operador; funciona tanto ao conectar o rádio (inclusive conexão automática após reiniciar) quanto ao selecionar satélite/transponder ou ativar SAT. Auto CAT desativado mantém o rádio intocado. A seleção e o controle exigem configuração de localização e elementos orbitais válidos.
- **Migração:** configurações antigas nos valores padrão de 2 segundos/20 Hz passam automaticamente a 1 segundo/1 Hz, sem sobrescrever ajustes personalizados nem reativar Auto CAT desabilitado pelo operador.
- **Uma única rotina:** a caixa antiga de Doppler que podia competir com o acompanhamento contínuo saiu da interface; a barra informa Auto CAT ONLINE quando o primeiro readback é confirmado. Verificação de voo e confirmação dependem da latência do rádio e da porta serial, portanto 1 segundo é o alvo do agendamento e não uma garantia de uma escrita RF por segundo.
- **Segurança:** nunca envia PTT/TX. Não ativa SAT, MAIN/SUB ou TRACE sem a confirmação existente; não reescreve frequências quando a variação é menor que 1 Hz; pausa por mudança manual do operador, falha de leitura/escrita ou perfil mesma banda. Reativar a preferência ou escolher novamente o satélite reinicia o acompanhamento.
- **Edições:** instalador/portátil Windows 7 SP1 x86 e Windows 10 1809+/11 x64. A homologação de CAT contínuo com TS-2000 real permanece pendente.

## Novidades v1.3.6 — correção das respostas CAT fragmentadas (16/10/2026)

- **Evidência de rádio real:** exportação de logs da v1.3.4 mostrou respostas COM1 como `RX F` + `RX A00436799891;`, `RX M` + `RX D4;`, e respostas `SA` fragmentadas. Anteriormente, o driver descartava os fragmentos independentes e gerava falso `TimeoutError`.
- **Enquadramento serial:** o driver agora concatena os segmentos recebidos até o terminador `;`, com limite de tempo total de 4 segundos, máximo de 48 leituras e 256 caracteres. Quadros não correspondentes (`?;`) são ignorados sem invalidar respostas válidas posteriores; respostas sem quadro completo continuam falhando de forma explícita.
- **Segurança:** a correção não repete nem retransmite comandos CAT de escrita; não envia PTT/TX, não ativa SAT automaticamente e preserva `FA` downlink SAT, `FB` uplink SAT e `FC` como VFO independente do sub-receptor, corrigidos na v1.3.5.
- **Verificação:** testes simulados de frames `SA/FA/FB/FC/MD` fragmentados, confirmação pós-sintonia `FA/FB`, falha por resposta incompleta e ausência de repetição de comandos de escrita. Build para Win7 SP1 x86 e Windows 10 1809+/11 x64 (Setup e Portable).
- **Pendente:** validação física do novo parser com TS-2000 e interface USB/COM1 em condições de atraso ou ruído. Latência serial elevada também pode ter origem em driver, cabo, adaptador ou configuração baud/COM; não há prova de qual componente originou a fragmentação.

## Novidades v1.3.5 — correção do uplink SAT no Kenwood TS-2000

- **Correção do protocolo SAT:** conforme o manual oficial Kenwood TS-2000, apêndice p. 135, **FA = downlink SAT** e **FB = uplink SAT**. **FC = VFO independente do sub-receptor**, e não deve ser usado como comando de uplink SAT. O código v1.3.3/v1.3.4 interpretava FC incorretamente. A v1.3.5 usa `FA`/`FB` com readback obrigatório para sintonia SAT e acompanhamento Doppler; lê `FC` para diagnóstico separado. [Manual Kenwood (PDF)](https://www.kenwood.com/usa/Support/pdf/TS-2000-Owner-Manual.PDF).
- **Estado CAT mais transparente:** a interface distingue RX SAT (FA), uplink SAT (FB) e frequência VFO SUB (FC). O diagnóstico continua somente leitura (ID/SA/FA/FB/FC/MD) e não confunde SUB VFO com uplink.
- **Proteção da sintonia manual:** se o operador alterar FA/FB no painel além do limiar de segurança, o rastreio automático é pausado e exige seleção explícita para retomar, evitando disputa de frequências.
- **Segurança:** leitura no boot; nenhuma emissão PTT, TX, SAT, TRACE ou SPLIT automática; a orientação MAIN RX/SUB TX deve estar confirmada antes de gravar VFO. Perfis mesma banda continuam bloqueados para sintonia CAT SAT.
- **Compatibilidade:** Windows 7 SP1 x86 e Windows 10 1809+/11 x64 (Setup e Portable). **Pré-lançamento:** a sintonia SAT com FA/FB precisa de prova de campo no TS-2000 real; não se declara homologada pelos testes simulados do CI.

> **Nota sobre versões antigas:** as notas abaixo referentes ao uso de FC como uplink em v1.3.3 e v1.3.4 descrevem o comportamento histórico, posteriormente corrigido na v1.3.5. Não devem ser utilizadas como instrução CAT atual.

## Novidades v1.3.4 — Auto CAT, acompanhamento contínuo e exportação de logs

- **Conexão CAT automática na abertura** quando houver COM previamente salva e preferência ligada. A conexão inicial **somente lê o rádio** (ID/SA/FA/FC/MD), não sintoniza, não muda SAT e não ativa PTT.
- **Indicador superior conectado/desconectado clicável:** usa a mesma rotina de conexão do botão inferior. Conexão e reconexão feitas em worker Qt, com erro sem bloquear a aplicação. O indicador não mostra falha de conexão quando ocorre apenas erro de sintonia.
- **Auto CAT habilitado por padrão em perfis novos**, preservando preferências ON/OFF já salvas. Ao **selecionar explicitamente** satélite/transponder, arma rastreio de frequências calculadas: aplica MAIN/FA e SUB/FC com confirmação por leitura, usa a cadência configurável de Doppler, limiar Hz e política de visibilidade; o botão **Sintonizar agora** permanece para diagnóstico. O sistema evita comandos para perfil mesma-banda em modo SAT, registra bloqueios e pausa após falhas, sem PTT.
- **LOGs / CAT → Baixar log completo (ZIP):** grava RX/TX e eventos em jornal local rotativo (retém as três gerações mais recentes) e exporta arquivos de sessão, mensagens da tela e relatórios de falha para o local escolhido; o ZIP não é enviado para a Internet. Atenção: logs podem conter indicativo e coordenadas; revise antes de compartilhar. Dados de versões anteriores não persistidos não são recuperáveis.
- **Compatibilidade:** builds de Windows 7 SP1 x86 e Windows 10/11 x64, incluindo Setup e Portable. A validação em equipamento físico TS-2000 ainda é indispensável. A inversão **MAIN TX / SUB RX**, modos da SUB e rastreio em perfil SAT same-band/SPLIT permanecem em backlog; não houve implementação de comandos CAT de inversão sem homologação.

## Correção de controle CAT v1.3.3 — **sub-receptor FC em vez de VFO B FB**

- O protocolo CAT do TS-2000 distingue **FA** (VFO A/MAIN), **FB** (VFO B principal) e **FC** (VFO da sub-banda). Nas versões até v1.3.2, o Sat Tool programava o uplink SUB com `FB`, portanto podia alterar um VFO diferente do usado pelo satélite.
- O driver agora lê `FA` como RX MAIN e `FC` como TX SUB a cada polling; programa `FA` e `FC` com **confirmação obrigatória por leitura de retorno**. Para mudar modo MAIN, exige SAT P3=1 e CTRL MAIN (P4=0); recusa em silêncio apenas se faltarem requisitos, com mensagem no painel CAT. **Não envia PTT**.
- O diagnóstico somente leitura consulta **ID, SA, FA, FB, FC, MD**, exibindo `FB = VFO B` separado de `FC = sub-receptor / uplink`. O operador deve comparar `FC` com o display da sub-banda do TS-2000 antes de autorizar sintonia.
- Testes de simulação usam frequências propositalmente diferentes entre FB e FC para detectar qualquer regressão de VFO. O CI Windows 7 e Windows 10/11 valida o software, **não substitui homologação CAT em rádio físico**.
- Teste real sugerido: SAT ON, SO-50, **primeiro** diagnóstico somente leitura, gire manualmente SUB e observe `FC`; com autorização, clique **Sintonizar agora** e compare os retornos `FA` e `FC`.

## Diagnóstico CAT v1.3.2 — leitura TS-2000 e SAT/MAIN/SUB

- **RÁDIO REAL (CAT):** a tela Operação mostra agora RX (FA), TX (FB) e modo MAIN (MD) efetivamente lidos do TS-2000, separados das frequências orbitais calculadas.
- **SAT/MAIN/SUB:** status SA interpretado e alerta explícito quando o rádio está SAT ON, porém MAIN=UPLINK e SUB=DOWNLINK, orientação que o controlador automático anterior bloqueia.
- **Diagnosticar comunicação CAT · somente leitura:** botão na aba Operação para consultar `ID;`, `SA;`, `FA;`, `FB;`, `MD;`; mostra comandos, respostas e eventuais timeouts na aba LOGs / CAT e em popup. **Não escreve frequências, não altera modo SAT e não transmite.**
- A leitura CAT com falha deixa de parecer uma frequência orbital válida; status indica leitura vencida ou indisponível.
- **Importante:** esta edição serve para obter evidência do rádio real e diagnosticar a regressão reportada de sincronização bidirecional. Não afirmar correção definitiva da sintonia até validar respostas SA/FA/FB/MD físicas. O modo SUB TX ainda requer conferência manual.

## Correção v1.3.1 — sintonia automática CAT ao conectar (15/10/2026)

- Corrigido o caminho em que o TS-2000 **já estava conectado** ao habilitar Auto CAT, ou em que o usuário conectava o rádio **depois** de selecionar satélite/transponder: agora inicia sintonia automaticamente se a opção estiver autorizada, o rádio estiver em SAT e houver TLE recente/frequências válidas.
- Após ativar SAT em **Configurações → Conexão CAT**, a seleção corrente também é aplicada quando Auto CAT está habilitado.
- Botão **Sintonizar agora** junto ao botão de conexão: confirmação explícita mesmo quando Auto CAT está desabilitado; feedback persistente informa “SAT OFF”, “OMM antigo”, “sem transponder” ou erro CAT.
- Troca rápida de satélites: aguarda a transação anterior e aplica a seleção mais recente quando Auto CAT estiver habilitado. Sem PTT, sem habilitar SAT automaticamente.
- **Limite do driver:** controla FA/FB e modo **MAIN (RX)**. O modo SUB (TX) requer conferência manual até implementação e validação específica no TS-2000 real.
- Mantém instaladores Win7 x86 e Win10 1809+/Win11 x64; validação física com o rádio permanece pendente.

## Novidades v1.3.0 — catálogo ampliado, AOS e CAT inteligente (15/10/2026)

- **Catálogo orbital em lote:** CelesTrak grupos `amateur`, `stations`, `cubesat`, `starlink`, `oneweb`, `weather`, `science` e `visual`. Grupos configuráveis e cache de duas horas por fonte; dados unificados pelo NORAD. Starlink não aciona downloads automáticos de frequências SatNOGS para todos os satélites.
- **Pesquisa SO-50:** aliases de SO-50/SAUDISAT 1C (NORAD 27607), FO-29, RS-44 e ISS; filtro por categoria. A grade Satélites mostra **Selecionado** na primeira coluna e renderiza no máximo 350 itens, com busca no catálogo inteiro.
- **Página principal simplificada:** editor anterior de Satélite e Transponder transferido a Configurações; RX/TX compactos no mesmo grupo, sem mostrar os desvios Doppler, mas mantendo as frequências previstas em tempo real. Versão exibida no título, hora UTC em destaque e estado do rádio CAT visível no topo.
- **Auto CAT por seleção:** configurável, desligado por padrão, exige autorização e TS-2000 em SAT; ajusta RX/TX e modo MAIN por CAT, com verificação de leitura. **Modo SUB/TX depende de conferência no rádio; sem PTT.** Sinaliza falhas e serializa alterações.
- **Alarme AOS:** popup e beep 30 segundos antes da próxima entrada no horizonte do satélite **selecionado** (considera elevação mínima da estação); opção para desligar áudio/alarme, registro único por passagem.
- **Progresso/ETA:** atualização orbital por categorias e frequências SatNOGS mostram estimativa do tempo restante e decorrido, percentuais e quantidades.
- **Ainda pendente:** testes com TS-2000 físico e Windows 7 real, validação de modo SUB, outras fontes (AMSAT/SatNOGS orbitais/Space-Track), exportação KML, rotor e melhorias adicionais no backlog. O release permanece **pré-lançamento** até validação operacional.

## Novidades v1.2.0 — interface de operação de satélites (15/10/2026)

- **Operação em dois passos:** satélite e serviço/transponder selecionáveis na área superior da tela principal, com modos evidentes.
- **Frequências RX e TX corrigidas por Doppler em cartões permanentes:** atualização de 1 em 1 segundo mesmo sem CAT ou com satélite fora da visada. Exibe modo e desvio em Hz; canais somente RX não inventam uplink. Frequências nominais na linha de detalhes e no tooltip.
- **CAT sem poluição visual:** apenas botão Conectar/Desconectar e status compacto na página principal; porta COM, baud, stop bits, SAT/TRACE e leituras físicas do rádio em **Configurações → Conexão CAT**.
- **Mapa mais limpo:** duração/direção da trajetória em **Configurações → Mapa e Trajetória**. Marcação de posição permanece em Estação Terrena; a previsão futura e o mapa offline continuam operando.
- **Catálogo:** **Satélites → Baixar/atualizar frequências** mostra barra de progresso central, com NORAD em processamento, N/M, percentual, falhas, cancelamento cooperativo e resumo. **Configurações → Satélites visíveis** agora tem filtro por nome/NORAD sem alterar a seleção persistida.
- **Estabilidade:** correção de uma condição que impedia a troca real de satélite quando já havia uma seleção ativa. Controles de sintonia CAT continuam exigindo autorização; nenhum PTT é enviado.
- **Próximas etapas (backlog):** curva de elevação por passagem, controle opcional de rotor e integração opcional por KML/KMZ com Google Earth. **Esses recursos NÃO fazem parte da v1.2.0.**
- **Validação:** CI compilando Win7 SP1 x86 e Win10 1809+/Win11 x64; é preciso testar layout/DPI e CAT com equipamento físico.

## Novidades v1.1.3 — marcação de satélites e Doppler contínuo (14/10/2026)

- Na aba **Satélites**, a seleção agora tem coluna **Selecionado** com checkboxes. **Marcar todos** e **Desmarcar todos** salvam os NORAD IDs, inclusive antes de haver frequências em cache, e atualizam imediatamente as tabelas de rastreamento.
- **Baixar/atualizar frequências** utiliza, por padrão, o escopo **Habilitados** — assim, após **Marcar todos**, uma única ação dispara a atualização sequencial e cancelável via SatNOGS, com contadores e erros. Para um satélite apenas, altere o escopo para **Selecionado**; não é necessário dar duplo clique.
- O painel **PREVISÃO Doppler** mostra RX/downlink, TX/uplink e offsets em Hz a cada segundo, também para satélites **fora da visada**. Isso não comprova recepção RF.
- A sincronização **CAT do TS-2000** permanece restrita a passagens visíveis por padrão. Na seção **Doppler e Segurança**, o operador pode permitir explicitamente CAT fora da visada, mas ainda precisa ativar Doppler CAT e confirmar a autorização; nenhum PTT é enviado.
- **Segurança:** TLE/OMM vencido, SAT desligado ou CAT desconectado bloqueiam atualização automática do rádio. A prévia é independente de conexão CAT.
- **Validação:** testes de seleção, escopo, Doppler aproximando/afastando e autorização CAT adicionados ao CI. Compilação e autoteste em Windows não equivalem a validação de campo com Kenwood TS-2000.

## Correção de estabilidade v1.1.2 — fechamento inesperado / travamento

- **Thread-safety Qt:** mensagens do CAT produzidas em threads de segundo plano são entregues à interface via `Signal(str)` e `@Slot(str)`, em vez de chamar `QPlainTextEdit` diretamente fora da thread principal. Essa violação anterior era uma causa plausível de encerramentos imprevistos.
- O painel **LOGs/CAT** retém as últimas **4.000 linhas**, impedindo crescimento ilimitado da memória.
- Nova pasta de diagnóstico persistente: `%LOCALAPPDATA%\\PT2VHF\\SatTool\\diagnostics`. Contém `events.log` (últimos eventos e exceções, sem tráfego CAT bruto), `events.log.previous` quando houver rotação, `native-crash.log` (pilhas Python em falhas nativas detectáveis) e `session.json` (último batimento da sessão e indicação de fechamento normal).
- Exceções em workers, na inicialização e no evento principal passam a ser registradas em arquivo. Encerramento inesperado do renderizador QtWebEngine do mapa também é registrado; o aplicativo tenta recarregar a página.
- Permanecem as versões **Windows 7 SP1 x86 (Qt5)** e **Windows 10 1809+/Windows 11 x64 (Qt6)**, com instaladores e portáteis .exe diretos.
- **Pendente:** identificar por logs e teste físico se a falha foi resolvida integralmente. Um travamento pode ter causas adicionais, como processamento orbital, drivers de vídeo/QtWebEngine ou comandos CAT síncronos. O CI Windows Server não substitui ensaio prolongado no computador afetado.

**Se encerrar novamente:** abra a pasta de diagnóstico acima e guarde `events.log`, `native-crash.log`, `session.json`. Consulte também o **Visualizador de Eventos → Logs do Windows → Aplicativo** e anote evento 1000/1001, módulo com falha e código de exceção (quando existirem). Não é necessário enviar configurações da estação ou seus dados pessoais.

## Histórico v1.1.1 — Windows 10 (13/10/2026)

**Erro corrigido:** a edição x64 da v1.1.0 tinha uma restrição de instalação `MinVersion=10.0.22000` (Windows 11), fazendo a mensagem *“This program does not support the version of Windows your computer is running”* aparecer em Windows 10. O instalador x64 da v1.1.1 aceita agora **Windows 10 versão 1809/build 17763 ou mais recente, ou Windows 11, ambos x64**, de acordo com a plataforma suportada pelo Qt6.

**Atenção ao nome do arquivo:** para manter a atualização automática compatível com a v1.1.0, o nome da edição moderna continua `Win11-x64`, mas o Setup **v1.1.1 Win11-x64 também é para Windows 10 x64 1809+**. O painel do Windows mostra a edição como `Windows 10/11 x64`.

- **Windows 10 x64 versão 1809+**: use o Setup ou Portable **Win11-x64 v1.1.1**. Não instale a versão v1.1.0 x64, pois o instalador foi configurado com mínimo do Windows 11.
- **Windows 10 x86 (32 bits) ou mais antigo que versão 1809**: use a edição legada **Win7-x86 v1.1.1**, baseada em PySide2/Qt5. O teste real nessa edição permanece necessário.
- **Windows 11 x64**: continue usando Win11-x64 v1.1.1 normalmente.

Para conferir versão e arquitetura, execute `winver` e abra **Configurações → Sistema → Sobre → Tipo de sistema**. Erros de inicialização depois de instalar são diferentes do bloqueio de versão e devem ser relatados com a versão de Windows e a captura da mensagem.

A v1.1.1 mantém as funções da v1.1.0 sem mudar a interface principal. **Build no Windows Server 2022 não substitui teste de execução no Windows 10 real** nem teste físico CAT com TS-2000.

## Histórico v1.1.0 — frequências, Doppler, idiomas e TS-2000

- **Doppler ao selecionar satélite:** o painel de previsão RX/downlink e TX/uplink atualiza imediatamente ao trocar de satélite ou transponder, mesmo sem rádio conectado. Exibe offsets em Hz e cálculo baseado na estação **salva**; RX-only não recebe TX fictício. Trocar satélite ou canal **suspende ajuste automático CAT anterior** até reativação e consentimento explícitos, sem retunar o rádio inesperadamente.
- **Formato estilo rádio:** `426.252.12 MHz` (10 Hz), `426.252.120 MHz` (1 Hz) ou `426,252120 MHz`, selecionáveis em **Configurações → Idioma e formato de frequência**. Os valores CAT e de previsão são apenas apresentados no formato escolhido; a precisão interna permanece em Hz. Os campos de entrada aceitam tanto os valores convencionais quanto os segmentados, com validação estrita.
- **Satélites:** ações **Marcar todos / Desmarcar todos** na própria aba, opcionais para todos ou somente resultados filtrados. A seleção é salva uma única vez e a agenda é recalculada sem comandos CAT.
- **SatNOGS:** download e atualização das frequências para satélite selecionado, habilitados ou filtrados, com progresso e cancelamento. Tratamento de páginas múltiplas, deduplicação, HTTPS exclusivo e cache atômico para preservar os dados anteriores se uma solicitação falhar. Atualizações são sequenciais para respeitar a API.
- **Kenwood TS-2000:** telemetria de **S-meter MAIN/SUB** (`SM0/SM1`), **potência configurada** (`PC`) e medidor atualmente selecionado (`RM`: SWR/COMP/ALC). São somente consultas CAT, com amostragem opcional limitada a cada cinco segundos; a leitura de potência configurada não é medida RF. **O estado PTT/TX real não é inferido**: aparece como indisponível até existir leitura CAT validada do hardware.
- **Idiomas:** seletor com Português (Brasil), English, Español, Français, Deutsch e Italiano. Traduções iniciais dos comandos, abas, títulos e campos operacionais principais, selecionáveis durante a execução com preferência persistente. **A auditoria das mensagens dinâmicas e de todos os textos do mapa/atualizador ainda está pendente**, para não apresentar internacionalização parcial como completa.
- **Layout:** a organização principal da **v1.0.2 foi preservada**, conforme preferência do operador. A proposta de redesenho está apenas no backlog e não foi aplicada.
- **Verificação:** testes automatizados em Windows 7 x86 (Python 3.8/Qt5) e Windows 11 x64 (Python 3.11/Qt6), compilação de Setup/Portable em `.exe`, checksums. O hardware TS-2000 real e o mapa no Windows 7 físico ainda exigem homologação.

## Novo na versão 1.0.2 — marcar estação no mapa offline

- Em **Configurações → Estação terrena**, clique em **Marcar estação no mapa**. O mesmo botão aparece na barra do mapa na aba **Operação**.
- O aplicativo muda para o mapa vetorial offline e entra em modo de marcação. **Clique** no ponto da antena, **arraste o marcador** para ajustar, ou digite latitude e longitude (WGS-84) diretamente no painel de edição. Use zoom/pan normalmente.
- Botões **Copiar**, **Restaurar anterior**, **Confirmar posição** e **Cancelar**. Coordenadas do ponto são apresentadas com 7 casas decimais; isso é resolução numérica, não promessa de precisão cartográfica do mapa 1:110m.
- **Confirmar posição** mostra posição anterior e proposta, mantém a altitude existente e preenche os campos da aba Configurações. A estação somente muda quando você clicar separadamente em **Salvar estação**.
- Enquanto a posição está sendo editada, os cálculos de órbitas, próximas passagens, AOS/TCA/LOS e Doppler **permanecem ligados às coordenadas salvas**, mesmo que os campos estejam temporariamente diferentes. Nenhum comando é enviado ao rádio.
- Após salvar, o aplicativo atualiza o marcador e recalcula a agenda, a geometria de recepção e o Doppler.
- Não requer acesso à Internet, ao serviço de localização do Windows ou ao provedor de tiles OSM. A precisão depende de identificar visualmente o local na base geográfica; para localização fina use coordenadas obtidas por GPS/referência cartográfica.

**Atenção:** o mapa offline Natural Earth é de escala mundial e não contém ruas. A marcação é conveniente para estimativa/seleção geográfica; para posicionar a antena com precisão, digite suas coordenadas GPS conhecidas.

## Novo na versão 1.0.1 — localização corrigida (Windows 7/11)

Na aba **Configurações → Estação terrena**, a origem de coordenadas pode ser escolhida explicitamente:

1. **Localização do Windows** (QtPositioning), apenas se o sistema disponibilizar um provedor. Se não houver, a aplicação explica como continuar; não depende desse serviço para funcionar.
2. **Localização aproximada por IP**, solicitada somente depois de **consentimento explícito**. Serviço externo [ipwho.is](https://ipwho.is/) via HTTPS; recebe IP público e metadados normais da requisição. O resultado pode representar somente cidade/região, nunca a posição real da antena. A consulta não roda no início do aplicativo.
3. **Receptor GPS por porta COM dedicada**, NMEA RMC/GGA com checksum e indicação de fix válido; escolha porta e baud independentes do CAT. O programa **somente lê** a porta GPS, não transmite nem modifica rádio.
4. **Entrada manual**, sempre disponível e sem rede; indicada para coordenadas conhecidas da estação.

O resultado da localização é mostrado para conferência, incluindo origem, altitude quando fornecida e indicação de precisão não informada. **Somente após confirmar** os campos são preenchidos; **a estação não muda** até clicar separadamente em **Salvar estação**. Cancelamentos, timeout, ausência de provedor e erros de Internet deixam intactas as coordenadas existentes.

**Recomendação:** para Doppler e previsão precisa de passagens, utilize as coordenadas reais da antena, não uma estimativa pelo IP.

A release também preserva a agenda FM/SSB/CW, as frequências previstas de Doppler por TLE/OMM, o mapa vetorial offline e o CAT do Kenwood TS-2000 com autorização explícita.

## Histórico: v1.0.0 — planejamento por passagem e Doppler

- **Próxima passagem automaticamente selecionada:** somente satélites habilitados e canais SatNOGS compatíveis com o perfil da estação FM/SSB/CW e bandas RX/TX. Satélite, modo e situação de RX apenas/RX-TX ficam explícitos.
- **Cronômetro ao vivo:** antes de AOS, tempo até a passagem; durante, tempo restante até LOS, barra de progresso e horários locais AOS/TCA/LOS. Quando a passagem termina, o indicador troca para a próxima elegível.
- **Frequência prevista com Doppler:** RX/downlink e TX/uplink previstos em MHz, diferenças assinadas em Hz, atualizadas com a velocidade radial da órbita SGP4/TLE/OMM. Antes da passagem a previsão é calculada para AOS; durante a passagem usa a posição atual. O uplink é indisponível para serviços exclusivamente de recepção.
- **Segurança CAT:** a previsão **não altera automaticamente o TS-2000**. Frequências lidas do rádio aparecem apenas no painel CAT após conexão e leitura confirmada; ajuste dos VFOs exige autorização operacional separada. TLE/OMM com época acima de sete dias não gera previsão apresentada como válida nem habilita Doppler automático.
- **Controle de trajetória do mapa:** opções *Última passagem*, 2 h, 5 h, 10 h, 24 h e Personalizado (0,5 a 48 h); direção Passado, Futuro ou Ambos. Passado tem linha sólida, futuro linha tracejada. O mapa permanece offline e os cálculos usam cache orbital; mudança de período não baixa TLE. Preferências persistem entre sessões.
- **Mapa no Windows 7:** substituição de CSS `inset:0` por coordenadas `top/right/bottom/left` para acomodar o QtWebEngine legado e evitar o mapa pequeno no canto. Precisa de confirmação visual em Windows 7 físico.
- **Localização:** a mensagem de solicitação de cadastro da estação é apagada após renderização bem-sucedida do mapa.
- **Compatibilidade:** instalador e portátil, cada um em um arquivo EXE para Win7 x86 e Win11 x64. Atualização automática conservadora, com SHA-256 e confirmação.

*Limitações:* o catálogo de canais pode exigir conexão e atualização do SatNOGS. Se o canal for desconhecido ou incompatível, o aplicativo não inventa um transponder e exibe ausência de previsão operacional compatível. As fontes e a época orbital precisam ser verificadas antes de qualquer transmissão.

## Interface operacional renovada — v1.0.2

**A versão adota a identidade visual PT2VHF Sat Tool** em tons de azul-marinho, ciano e verde-água. O aplicativo mantém as três colunas:
- **Esquerda:** lista de satélites habilitados, modos, seleção e detalhes/transponders.
- **Centro:** mapa-múndi vetorial offline com posição da estação, posição do satélite, órbita (ground track), área de cobertura, zoom e arraste.
- **Direita:** AOS/TCA/LOS e elevação máxima nas passagens, métricas orbitais e painel destacado de **CAT real** com RX FA, TX FB, modo e SAT, incluindo sinalização de desconexão, erro e leitura antiga.

### Mapa corrigido (HTTP 418)
A versão v0.2.0 consultava os tiles públicos da OpenStreetMap Foundation por um QtWebEngine sem identidade de requisição apropriada, e mostrou **418 Access blocked** em uso real. A v1.0.2 **remove essas solicitações** e usa geografia 1:110m do [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/), domínio público, integrada ao aplicativo. A base geográfica funciona sem Internet; a atualização de TLE/OMM e dados SatNOGS continua exigindo rede.

O mapa offline tem estilo cartográfico simplificado (não exibe ruas). Orbitas e posições são calculadas a partir dos elementos orbitais ativos; são dados reais, não linhas ilustrativas.

### Ícone oficial em todos os executáveis
- Logo PT2VHF Sat Tool no cabeçalho do aplicativo e README.
- Arquivos `assets/branding/icon-256.png` e `app-icon.ico` gerados durante a compilação a partir da marca oficial.
- O ícone é aplicado ao EXE instalado, ao EXE portátil, à janela e ao Setup Inno, nas versões Win7 e Win11.
- Autotestes do pacote validam que mapa e marca estão incorporados aos EXEs.
- A arte é proposta inicial; [guia de identidade visual](docs/BRANDING.md).

### Importante sobre validação
Os testes automatizados incluem o carregamento das dependências nativas e a inclusão dos ativos visuais no pacote. **Não** equivalem a confirmar renderização correta do QtWebEngine, o comportamento do mapa em Win7 real nem a operação do rádio TS-2000 físico. Mantenha o CAT desconectado para o primeiro teste visual.

## Seleção inteligente e agenda orbital
- Em **Configurações**, selecione os modos da estação (**FM, SSB e CW**) e as bandas disponíveis. O TS-2000 está disponível como modelo inicial em **Rádio / Conexão CAT**; a porta COM pode ser selecionada ou digitada.
- Ao abrir, os satélites candidatos são sugeridos por capacidades e dados conhecidos; hipóteses históricas são rotuladas **não confirmadas** e não autorizam transmissão. A disponibilidade operacional depende dos dados de transponders.
- Em **Satélites para a página principal**, confirme favoritos ou exclusões por NORAD. A agenda lateral mostra apenas habilitados, ordenada por AOS, com TCA, LOS, elevação máxima e modos; o mapa central acompanha o selecionado.
- Na área do mapa, o painel CAT mostra as frequências realmente lidas **FA RX / FB TX**, SAT e modo MAIN, independentemente das frequências nominais ou calculadas por Doppler. A consulta CAT é assíncrona, aproximadamente a cada segundo, com alerta quando a leitura está desatualizada.
- A seção **TLE / Efemérides** permite ajustar a cadência (mínimo de 2 h); a aba **Sobre** apresenta versão, fontes e licença.
- Fotos são pesquisadas no **Wikimedia Commons** por título correspondente, com autoria/licença; quando não identificáveis, mostra-se um aviso em vez de uma imagem não verificada.

## Publicação e verificações dos EXEs
- O GitHub Actions gera dois instaladores `*-Setup.exe` e dois portáteis `*-Portable.exe`, um par por plataforma.
- O portable usa PyInstaller **--onefile** e executa seu próprio teste de inicialização NumPy/Skyfield/Qt antes da release. Os checksums SHA-256 são publicados separadamente.
- O GitHub Actions roda em Windows Server 2022; isso **não comprova execução em Windows 7 SP1 real**, funcionalidade do QtWebEngine em todo hardware, conexão serial TS-2000 ou homologação CAT/Doppler.
- O aplicativo não transmite nem envia PTT; conecte o rádio somente após conferir alimentação, cabo serial/nível elétrico, parâmetros CAT, frequências e permissões.

## Descrição do aplicativo

Aplicação independente para Windows, voltada ao rastreamento de satélites amadores e ao controle CAT do **Kenwood TS-2000** pela porta serial. **Versão 1.0.0 — MVP ainda sem homologação em TS-2000 físico.**

## Principais funcionalidades

- Mapa-múndi central (OpenStreetMap/Leaflet) com estação, posição orbital, ground track e área de visibilidade aproximada.
- Catálogo de satélites amadores via **CelesTrak OMM JSON e TLE** (OMM prioritário e TLE como fallback); evita a limitação do TLE clássico para NORAD > 99.999.
- Catálogo de transponders/modos via **SatNOGS DB** com associação a NORAD.
- Seleção de satélite, canal, modo e frequências; suporta entradas manuais.
- Próximas passagens pela estação cadastrada em 36h (AOS, elevação máxima, LOS).
- Leitura CAT: `ID`, `SA`, `FA`, `FB`, `MD` (e comando explícito para habilitar SAT sem TRACE).
- Correção Doppler geométrica com atualização controlada de `FA` (RX) e `FB` (TX), quando autorizada pelo operador.
- Configurações persistentes, porta COM, velocidade, stop bits, captura de localização pelo sistema e log CAT.

## Requisitos

- **Win7 SP1 atualizado (x86 ou x64)** ou **Win11 x64**, conforme o pacote; porta serial RS-232 do Kenwood TS-2000 com cabo/interface elétrica apropriada; mesma configuração de baud rate no rádio e no aplicativo.
- Internet para atualizar efemérides, transponders e carregar as camadas do mapa; dados em cache permanecem disponíveis para cálculo orbital, sujeitos ao vencimento.
- Para executar em desenvolvimento: Windows 11 usa Python 3.11 + PySide6 e `requirements-win11.txt`. Windows 7 usa Python 3.8 (última linha com suporte ao Win7), PySide2, `requirements-win7.txt`. `python run.py` inicia a aplicação. **O portátil onefile inclui Python e bibliotecas; não instale Python no computador apenas para executá-lo.**

## Uso e segurança

1. Em **Configurações**, informe indicativo, latitude (sul negativa), longitude (oeste negativa), altitude e elevação mínima. Ou tente capturar a localização no Windows; confira precisão e salve.
2. Clique em **Atualizar órbitas (OMM + TLE)** e selecione o satélite desejado. OMM JSON é preferido; TLE é baixado para interoperabilidade e contingência.
3. Selecione transponder e modo, confirme frequências RX/TX publicadas. Alguns satélites e canais são só de recepção. Verifique se o modo realmente está ativo e se há autorização de uso.
4. Em CAT, configure COM/baud/stop bits compatíveis com o rádio e clique **Conectar**. O software exige a resposta `ID019;` do TS-2000.
5. Clique **Ativar SAT / desativar TRACE** e confirme. O software reconfigura o estado SAT, preservando o canal de memória mas podendo alterar o roteamento MAIN/SUB; não avance sem conferir o rádio.
6. Clique **Aplicar RX/TX** para uma programação inicial com confirmação. O ajuste leva em conta o Doppler calculado.
7. Caso queira ajustes contínuos, habilite **Doppler automático** durante uma passagem visível. Essa opção é desligada ao iniciar, em perda de conexão, fora da passagem e com OMM de idade superior a 7 dias.

**Importante:** O programa **nunca transmite nem envia PTT**. Alterar a frequência TX, porém, pode afetar a próxima transmissão por PTT físico. Confirme faixa, licenciamento, tom, modo, potência e transponder ativo no rádio antes de transmitir. Modo TX SUB ainda é apenas uma indicação na interface; a gravação automática de MD atua somente sobre o modo MAIN.

## Publicação do código e das releases

O repositório `alexpmr/PT2VHF-Sat-Tool` começou com `README.md` e `LICENSE` MIT. A publicação no `main` dispara a compilação e, somente após os autotestes dos EXEs, publica a release v1.0.2 com os quatro arquivos e respectivos checksums.

## Fontes, créditos e licenças

- [Manual oficial Kenwood TS-2000](https://www.kenwood.com/usa/Support/pdf/TS-2000-Owner-Manual.PDF), Apêndice CAT (comandos SA/FA/FB/MD).
- [CelesTrak](https://celestrak.org/NORAD/elements/): dados OMM dos objetos do grupo amateur, sujeitos à política de uso do provedor.
- [SatNOGS DB](https://db.satnogs.org/): dados de transponders sob **CC BY-SA 4.0**; confirmar atribuição e compartilhamento apropriado de derivados.
- Mapa [OpenStreetMap](https://www.openstreetmap.org/copyright) e Leaflet 1.9.4 (BSD-2-Clause); os tiles públicos não são destinados a uso massivo.
- Python Skyfield/SGP4 para cálculo orbital.

## Atualização automática dentro do aplicativo

- O indicador de versão fica na **barra superior**: verde quando nenhuma versão nova é encontrada, laranja quando há nova release, cinza quando a edição atual é de desenvolvimento. Ao clicar, a aplicação consulta o GitHub.
- Verificação automática no início e a cada **15 minutos** (personalizável em Configurações); opção de incluir ou não pré-lançamentos; aviso único por versão e **changelog**.
- A seleção de download respeita obrigatoriamente o **sistema-alvo e o tipo de distribuição** (Win7-x86 ou Win11-x64; Setup ou Portable). A atualização de um canal jamais substitui automaticamente o outro.
- Após consentimento do operador, baixa o pacote e valida o SHA-256 divulgado pela release; sem hash válido, falha fechada. Desliga Doppler, desconecta CAT e encerra o aplicativo antes da instalação. A edição **Setup** abre o instalador; a edição **Portable** atualiza seus arquivos sem apagar `data/`.
- Em Windows 7, o atualizador depende de PowerShell instalado. O serviço GitHub precisa de HTTPS/TLS moderno; uma máquina legada sem suporte TLS não conseguirá atualizar e não deve ser exposta à Internet sem proteção.
- Atualizar o software **não significa** habilitar transmissão. As frequências/autorizações operacionais continuam sob responsabilidade do radioamador.

## Satélites correntes e suas características

A aba **Satélites** é gerada a partir do **catálogo atual CelesTrak OMM/TLE**; não existe lista fixa congelada no código. Apresenta nome, identificador NORAD, inclinação orbital, período orbital, frequências de downlink e modos de modulação existentes no cache SatNOGS, além da indicação do estado dos canais publicados. A seleção abre o satélite diretamente na aba de operação, mostrando também excentricidade, época orbital e transponders. A busca aceita nome, NORAD, frequência e modo.

**Critério de qualidade:** presença em OMM/TLE é **objeto rastreável**, não comprovação de transponder ativo. Canal cadastrado como ativo no SatNOGS não garante que esteja no ar naquele momento. Algumas informações só aparecem após a consulta do transmissor ao SatNOGS. Não presumir permissão de TX com base apenas no cadastro comunitário.

## Limitações conhecidas

- Não houve teste físico do TS-2000, nem compilação/execução do aplicativo em Windows neste ambiente. O build Win7 x86 é experimental até homologação física.
- O provedor de geolocalização depende do Windows e das permissões; não é GPS garantido.
- O mapa depende de Internet para CDN/tiles; previsão e CAT podem usar cache quando disponível.
- Alguns satélites do grupo amateur não têm transponder amador ativo; entradas do SatNOGS são comunitárias.
- O roteiro do transponder invertido usa interpolação linear; operador deve validar sinais e offsets.



## Diagnóstico de inicialização (v1.0.2)

O build anterior apenas verificava a existência do EXE. Agora o GitHub Actions **executa os binários congelados**, verificando importação nativa do NumPy, BLAS, Skyfield, Qt e da aplicação. Se falhar, o pipeline bloqueia a release.

Se persistir erro ao abrir, na pasta do aplicativo execute:

```powershell
.\PT2VHF-Sat-Tool.exe --self-test "$env:TEMP\PT2VHF-Sat-Tool-diagnostics.json"
Get-Content "$env:TEMP\PT2VHF-Sat-Tool-diagnostics.json"
```

O JSON mostra o traceback e as versões usadas. O Win7 SP1 requer atualizações do sistema e runtime Visual C++/UCRT apropriados. Instalar Python ou NumPy no PC não corrige um aplicativo congelado. Não baixe DLLs de sites não oficiais. NumPy travado em 1.23.5 (Win7) e 1.26.4 (Win11); o teste no runner não substitui homologação no Windows real.
