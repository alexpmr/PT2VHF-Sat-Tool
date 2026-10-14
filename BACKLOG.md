## v1.1.3 — correção de seleção em lote e Doppler fora da visada (14/10/2026)
- [x] **Bug reportado:** na aba Satélites, Marcar todos não apresentava seleção visível e Baixar/atualizar frequências utilizava escopo inicial Selecionado, restringindo indevidamente a atualização a um único satélite; a ação parecia exigir duplo clique no satélite.
- [x] **Correção em código:** seleção explícita e persistente, checkboxes por satélite, marcação/desmarcação global ou filtrada, e download SatNOGS sequencial/cancelável para os Habilitados por padrão, sem acoplamento ao duplo clique.
- [x] **Doppler:** atualização visual RX/TX e offsets em Hz a cada segundo mesmo abaixo do horizonte; CAT autorizado separadamente, bloqueado por padrão fora da visada; opção explícita com confirmação operacional.
- [x] **Testes automatizados criados:** marcação sem frequências prévias, atualização de múltiplos NORADs, Doppler em aproximação/afastamento, persistência da configuração e proteção CAT.
- [ ] **Homologação física:** reproduzir aba Satélites e CAT/Doppler em Windows 7 e Windows 10/11, inclusive com TS-2000 conectado e satélite fora da visada; verificar temporização, comportamento do rádio e limites da API SatNOGS. Uma passagem de CI não encerra esta pendência.

## [P2] Aba Satélites — progresso central do download de frequências (14/10/2026)
- [ ] Ao clicar em **Satélites → Baixar/atualizar frequências**, exibir **janela centralizada sobre a aplicação** com barra de progresso horizontal; não depender apenas do status discreto na página.
- [ ] Mostrar **N de M satélites processados**, percentual, nome e NORAD em processamento e contadores de sucesso, sem dados, falhas e cancelados. O percentual deve medir *itens concluídos / total*, inclusive itens com erro, sem confundir progresso e sucesso.
- [ ] Permitir **Cancelar** de forma cooperativa: parar antes da próxima requisição, aguardar a atual/timeout e preservar o cache já atualizado. Evitar execuções simultâneas.
- [ ] No término, apresentar resumo com **Fechar** e erros detalhados no LOG. Atualizar a interface apenas na thread Qt por sinais, sem congelamento (PySide2/Win7 x86 e PySide6/Win10/11 x64).
- [ ] Testar escopos **Selecionado / Habilitados / Resultados filtrados**, 1 ou muitos satélites, ausência de frequências, timeouts, falhas HTTP e cancelamento; não realizar nenhum comando CAT/PTT.

## [P2] Configurações — pesquisar satélites visíveis na página principal (14/10/2026)
- [ ] Na seção **Configurações → Satélites visíveis na página principal**, adicionar **campo de pesquisa/filtro** imediatamente acima da tabela de satélites, com placeholder `Pesquisar por nome ou NORAD…` e ação **Limpar**.
- [ ] Filtrar **instantaneamente enquanto digita**, sem diferenciar maiúsculas/minúsculas nem acentos, por **nome/indicativo do satélite e NORAD ID**. Opcionalmente permitir modo **FM/SSB/CW** quando houver dados no catálogo; o filtro não depende de download prévio das frequências.
- [ ] O filtro deve **modificar somente as linhas exibidas**, nunca desmarcar, apagar ou mudar a seleção persistida. Ao limpar, todos os satélites reaparecem com seus estados anteriores.
- [ ] Exibir contador `X resultados de Y satélites · Z habilitados` e mensagem explícita quando não houver correspondências.
- [ ] Preservar os comandos existentes **Marcar tudo, Desmarcar tudo e Sugestões automáticas**; se houver intenção de aplicá-los apenas aos resultados filtrados, exigir opção de **escopo explícito**, evitando modificar inadvertidamente a seleção global.
- [ ] Atualização de tabela/filtro não pode desativar Doppler CAT, recalcular operações desnecessariamente ou enviar comandos ao TS-2000. Validar seleção individual, digitação rápida, limpeza do filtro, reinício, Windows 7 e Windows 10/11 e idiomas suportados.

## [P1] Página principal — RX/TX Doppler sempre visíveis, sem rádio e fora da visada (14/10/2026)
- [ ] **Requisito funcional do operador:** ao selecionar qualquer satélite com órbita válida e pelo menos uma frequência de transponder publicada/configurada, **exibir permanentemente na página principal a frequência nominal e a frequência corrigida em tempo real por Doppler**, **independentemente** de conexão CAT com o Kenwood TS-2000, visibilidade RF, AOS/LOS ou elevação negativa. Seleção do satélite não deve depender de duplo clique nem de abertura de outras abas.
- [ ] **Cartões operacionais próprios e sempre visíveis:** apresentar de forma destacada **RX / downlink previsto** e **TX / uplink previsto**, valores completos em MHz, correções separadas com sinal (+/- Hz), nome/NORAD do satélite, transponder/modo e indicação `EM PASSAGEM` ou `FORA DA VISADA`. O painel previsto deve ser visualmente independente dos cartões **RX/TX realmente lidos do rádio (CAT)**. Não trocar previsão por `— MHz` apenas porque o CAT está desconectado.
- [ ] **Atualização periódica incondicional:** usar temporizador de apresentação independente do CAT e da visibilidade, com recálculo mínimo **a cada 1 segundo** enquanto um satélite estiver selecionado (admitir intervalo de exibição configurável, sem depender do intervalo de comandos CAT). Atualizar imediatamente ao trocar satélite, transponder, frequência manual ou coordenadas da estação após salvar, sem aguardar um novo duplo clique.
- [ ] **Integridade do cálculo:** usar estação terrestre efetivamente salva, TLE/OMM adequado, posição/velocidade radial SGP4/Skyfield e frequências nominais imutáveis em Hz para evitar acumulação ou inversão indevida do Doppler. Respeitar diferenças de sinal entre uplink e downlink e o caso **RX-only** (mostrar RX; não inventar TX).
- [ ] **Ausência de dados:** quando não houver frequência configurada/publicada, oferecer ação clara **Selecionar ou baixar frequências**, preservando o satélite atual; quando TLE/OMM estiver ausente/vencido, exibir status específico e orientar atualização, sem apresentar valores antigos como atuais.
- [ ] **Segurança:** cálculo e exibição são **simulação/previsão**, nunca prova de escuta RF. Não executar comandos de sintonia CAT ou PTT para manter a interface atualizada. Controle automático do TS-2000 continua um recurso separado, com confirmação e políticas de visibilidade próprias.
- [ ] **Responsividade e critérios de aceite:** manter ambos os cartões completos e legíveis em tamanhos mínimos de janela, com/sem rádio conectado, satélite acima/abaixo do horizonte, antes/durante/depois de passagem, RX-only, faixas 145/435/1296 MHz, troca rápida de seleção, modos manuais, Windows 7/10/11 e escalas de DPI. Verificar números mudando em tempo real sem clique adicional.
- [ ] **Observação sobre v1.1.3:** já existe prévia Doppler calculada, mas este item exige **exibição operacional principal, permanente, independente dos cartões CAT** — não marcar como concluído apenas por haver cálculo de 1 s em um rótulo secundário.

## [P1] Interface — frequências CAT RX/TX cortadas em janelas menores (14/10/2026)
- [ ] **Reprodução visual:** no painel **RÁDIO / CAT · KENWOOD TS-2000** da página principal, os cartões **RX / DOWNLINK** e **TX / UPLINK** ficam com a linha da frequência ("— MHz" quando desconectado ou frequência real quando conectado) parcialmente ou totalmente **cortada na vertical** em certos tamanhos de janela/resoluções/escalas de DPI. Evidência: captura do operador em 14/10/2026, com os números/placeholder visivelmente encobertos pela borda inferior do cartão.
- [ ] **Ponto de investigação:** `sat_tool/app.py`, cartões `self.cat_rx`/`self.cat_tx`, construídos como `QLabel` com texto em duas linhas, `QHBoxLayout`, `font-size:18px`, `padding:12px` e `wordWrap(True)`; verificar cálculo de `sizeHint`, `minimumSizeHint`, compressão pelo layout e competição por espaço vertical com mapa/painéis vizinhos.
- [ ] **Correção responsiva:** garantir altura mínima real para **rótulo + valor + padding/borda** nos dois cartões, com políticas de tamanho Qt adequadas; impedir clipping vertical e horizontal. Permitir adaptação de fonte/espaçamento ou empilhamento dos cartões quando faltar largura, preservando o **valor completo** (frequência e unidade MHz). Não mascarar o problema apenas escondendo o texto por elipse.
- [ ] **Prioridade de informação:** mostrar primeiro e sempre a frequência CAT de RX e TX. Telemetria secundária pode reduzir espaço/ser recolhida ou entrar em área rolável; o painel central também deve permitir rolagem vertical se a altura disponível for insuficiente, sem encobrir frequências nem comandos de operação.
- [ ] **Critérios de aceite:** testar conectado/desconectado, leituras completas (ex.: `145.825.00 MHz`, `435.000.00 MHz` e faixas 1.296 MHz), janela maximizada/restaurada, dimensões mínimas permitidas, telas 1366×768/1920×1080, DPI 100/125/150/200%, fontes do Windows e Win7/PySide2 vs Win10/11/PySide6. Rótulos, valores e unidades sempre inteiramente legíveis, sem sobreposição ou cortes.
- [ ] **Não alterar** o cálculo Doppler, mapeamento MAIN/SUB, estado CAT ou comandos ao rádio: correção deve ser apenas de layout/apresentação.

# PT2VHF Sat Tool — backlog

## BUG crítico — Win7 não responde / Win10 encerra inesperadamente (v1.1.1)
- [x] Relato de campo em 13/10/2026: Windows 7 apresentava travamentos; depois de reinstalar o computador com Windows 10, o instalador v1.1.1 funciona, mas o aplicativo às vezes encerra repentinamente. Não há dump da falha para confirmar a causa exata.
- [x] **Defeito objetivo identificado:** `TS2000` chama o callback `MainWindow.log` no contexto de `background("cat-poll",self.radio.poll)`, e o callback escrevia diretamente em `QPlainTextEdit` fora da thread Qt GUI. Corrigido em **v1.1.2**, com sinal `Events.record` e `@Slot(str)` executado na thread principal.
- [x] **Prevenir vazamento de memória:** impor limite de 4.000 linhas no painel de LOGs CAT; os eventos persistidos têm rotação de arquivo de 2 MB.
- [x] **Diagnóstico de fechamento:** ativar `faulthandler` antes de carregar GUI, captar exceções Python do processo e das threads, gravar `%LOCALAPPDATA%\\PT2VHF\\SatTool\\diagnostics\\{events.log,native-crash.log,session.json}` e batimento a cada 30 s. Registrar sessão anterior não encerrada normalmente sem atribuir automaticamente a crash.
- [x] **QtWebEngine:** observar `renderProcessTerminated`, registrar evento e tentar recarregar mapa; manter operação principal quando o renderizador secundário falhar.
- [ ] **Confirmar causa real:** testar após v1.1.2 durante várias horas, com e sem TS-2000 CAT, com/sem Internet, com mapa ativo e com aba LOGs aberta; verificar arquivo de diagnóstico e eventos Windows na hora da falha.
- [ ] **Performance de Windows 7/10:** medir duração de `tick()` de 1 s, `update_next_indicator`, `refresh_passes`, processamento de TLE, QtWebEngine GPU e uso de memória; mover operações CAT **síncronas ainda executadas pela GUI** para fila/worker serial dedicado com segurança e confirmações antes de alterar VFOs. Validar ausência de deadlocks/concorrência e vazamento de threads.
- [ ] **Reproduzir em Win10 físico:** coletar `winver`, CPU/RAM, se rádio está conectado no instante do fechamento, porta serial, screenshot de logs, Visualizador de Eventos (eventos 1000/1001; módulo e código de exceção), sem pedir dados sensíveis desnecessários.
- [ ] **Critérios de aceite para estabilidade:** zero encerramentos inesperados e interface responsiva em sessões prolongadas (sugestão: 8–24 h) no Windows 10 e Windows 7, repetidas com CAT desconectado e conectado. Build em Windows Server não prova homologação de hardware.

## BUG v1.1.0 — Instalador x64 rejeita Windows 10 (correção v1.1.1)
- [x] **Reprodução:** em PC Windows 10 recém-formatado, o Setup da v1.1.0 x64 informa `This program does not support the version of Windows your computer is running`, antes de instalar.
- [x] **Causa verificada:** alvo `Win11-x64` configura `MinVersion=10.0.22000` no Inno Setup, restringindo explicitamente o instalador ao Windows 11; o nome da distribuição não esclarecia a incompatibilidade.
- [x] **Correção v1.1.1:** reduzir limite do instalador Qt6 x64 para `10.0.17763` (Windows 10 1809 ou posterior), alinhado à plataforma suportada pelo Qt 6.8/6.9, mantendo Windows 11 x64. Alterar workflow, instalador padrão e script de compilação local, com regressão automatizada.
- [x] **Preservar atualização OTA:** manter nomes `Win11-x64` para Setup/Portable e `AppId` da família Qt6, embora agora suporte Windows 10 x64, evitando quebrar downloads/update de instalações anteriores. No display do instalador, indicar `Windows 10/11 x64` e explicitar no README.
- [x] **Fallback:** manter instalador `Win7-x86` para Windows 10 de 32 bits e versões antigas, sem prometer que Qt6 roda nessas máquinas.
- [ ] **Homologação física:** verificar instalação e execução numa máquina real com Windows 10 1809+/22H2 x64 (Setup e Portable), preferencialmente recém-formatada, sem requisitos pré-instalados; conferir OpenGL/QtWebEngine, mapa, Python DLLs, Windows Defender/SmartScreen, atualizador e desinstalação. Verificar também fallback x86 em Windows 10 de 32 bits. CI Windows Server 2022 não comprova execução em Windows 10 real.
- [ ] **Se continuar falhando:** coletar `winver`, edição/arquitetura, nome completo do EXE, captura da mensagem e se erro ocorre ao abrir Setup ou Portable. Não recomendar desativar antivírus.

## v1.1.0 — implementações, limites e testes pendentes
- [x] **Doppler previsto imediato** ao mudar satélite/transponder, RX/TX com offsets separados e RX-only, usando estação salva e TLE/OMM em cache, sem programação CAT sem autorização.
- [x] **Proteção CAT ao trocar alvo:** suspender ajuste automático anterior e exigir nova ativação consentida; polling e escrita seriados com confirmação de retorno FA/FB.
- [x] **Formato de frequência configurável:** 426.252.12 (10 Hz), 426.252.120 (1 Hz) ou decimal 426,252120 MHz, sem perda interna de Hz.
- [x] **Satélites:** Marcar todos/Desmarcar todos diretamente na aba, selecionando catálogo todo ou somente resultados filtrados; atualização de lista e agenda em lote.
- [x] **Frequências SatNOGS:** consulta individual/selecionados/filtrados em background, progresso, cancelamento, paginação, deduplicação e cache atômico; sem misturar atualização de TLE/OMM.
- [x] **CAT TS-2000 read-only:** S-meter MAIN/SUB, potência configurada (não potência RF medida) e RM selecionado; intervalos de telemetria opcionais moderados; sem comando PTT ou TX.
- [x] **i18n inicial:** seletor PT-BR/EN/ES/FR/DE/IT com tradução dos títulos, botões e campos principais, preferência persistente e troca no aplicativo.
- [x] **Sem reformulação do layout principal:** mantidas as três colunas e barra inferior da v1.0.2, conforme decisão do operador.
- [ ] **i18n integral:** auditar traduções remanescentes de textos dinâmicos, atualizador, mapa HTML, mensagens CAT e todas as fontes externas nos seis idiomas antes de considerar cobertura 100%.
- [ ] **Homologação física:** verificar comandos SM0/SM1/PC/RM e FA/FB no TS-2000, RX/TX real e SAT MAIN/SUB; estado de transmissão apenas com leitura confiável confirmada.
- [ ] **Homologação Windows real:** abrir a v1.1.0 em Win7 SP1 físico (Qt5/portátil e instalador), Win11 x64, diferentes DPI e COM, validando tráfego SatNOGS e painel de frequências.

## UX / UI — simplificar a tela principal (aba Operação) [ADIADO — manter layout atual]
- [ ] **Objetivo:** reduzir a poluição visual e priorizar a operação de satélites, com **mapa central dominante**, passagem atual/próxima, satélite/transponder selecionado, frequências Doppler RX/TX e estado essencial do TS-2000. Preservar acesso a todas as funções existentes, sem removê-las.
- [ ] **Redesenhar por hierarquia de informação:** barra superior compacta com nome/versão, estação, fonte/idade TLE, data/hora e estado CAT; em seguida apenas uma faixa discreta para **próxima passagem + contador regressivo + AOS/LOS** (e progresso quando em passagem). Evitar repetição dessa mesma informação em vários painéis.
- [ ] **Coluna esquerda compacta:** pesquisa e seleção do satélite, modos compatíveis e escolha do transponder; mostrar inicialmente resumo com nome/NORAD/modo e frequências nominais principais. Deixar **ficha técnica extensa, foto, detalhes orbitais, filtros avançados e ações de atualização de catálogos** recolhidos em `Detalhes` / `Mais opções` ou nas abas já existentes. Não manter simultaneamente lista grande, combo redundante e ficha longa na vista básica.
- [ ] **Mapa como elemento central prioritário:** aumentar a área útil; colocar trajetória (Última passagem/2/5/10 h/personalizado), Passado/Futuro/Ambos, camadas e `Marcar estação` em **uma barra de ferramentas curta ou menu expansível**. Exibir status de órbita e referência cartográfica em um rodapé mínimo/tooltip, sem sobrepor trajetórias.
- [ ] **Coluna direita em duas seções claras:** (a) próximas passagens em lista compacta e rolável, com AOS/TCA/LOS/elevação, e (b) cartão compacto do TS-2000 com **CAT, modo, RX/TX reais, SAT**; medidores S-meter/potência/ALC/SWR e detalhes do protocolo em uma seção **expandível**. Telemetria orbital extensa (velocidade radial, distância, altitude etc.) deve ficar em `Detalhes orbitais`, mostrando apenas azimute/elevação na visão essencial.
- [ ] **Frequências sem duplicidade:** ter um destaque operacional único para **RX/downlink e TX/uplink Doppler previstos**, com valores nominais e offsets disponíveis por expansão; manter as leituras reais CAT visualmente separadas. Adotar o formato segmentado de frequência já previsto no backlog. Para satélites RX-only, ocultar TX operacional e explicar por tooltip/estado.
- [ ] **CAT na tela principal:** manter conexão/desconexão e status sempre acessíveis; recolher por padrão campos de porta COM, baud, stop bits, habilitação SAT/TRACE, calibração, limiares e comandos técnicos em `Configurações CAT`/painel avançado. **Nunca ocultar avisos críticos** ou confirmação de comandos que mudem o rádio; Doppler automático CAT deve continuar exigindo consentimento explícito.
- [ ] **Menos ruído de status:** substituir mensagens permanentes repetitivas e legendas longas por estados curtos, tooltips e `Detalhes`. Exibir alertas apenas quando pertinentes: TLE vencido, CAT desconectado se ação exigir CAT, ausência de coordenadas, canal incompatível, AOS iminente ou erro de leitura. Não usar animações piscantes ou cores vibrantes por decoração.
- [ ] **Layout responsivo e personalizável:** divisórias ajustáveis; permitir recolher painéis esquerdo/direito, maximizar mapa e abrir detalhes sob demanda. Salvar preferências de largura, painéis expandidos, modo simples/avançado e dimensões da janela; opção `Restaurar layout padrão`. Em telas de 1366×768, DPI 125–200% e Win7/Win11, evitar clipping de frequência, botões ou mapa pequeno.
- [ ] **Acessibilidade:** contraste adequado em tema escuro/claro, fontes tabulares para frequências/temporizadores, indicadores com texto + ícone (não apenas cor), foco/teclado, tooltips traduzíveis nos seis idiomas previstos e rolagem apenas nos painéis de detalhes.
- [ ] **Critérios de aceite:** na abertura, o operador deve reconhecer sem rolar **satélite selecionado, modo, próximo AOS/tempo restante, RX/TX previsto, se o rádio está conectado e o mapa**. Um clique revela detalhes; operações essenciais não exigem navegar por várias abas. Comparar capturas antes/depois e executar testes de regressão para mapa, SAT, CAT, Doppler, atualização de transponders, estados desconectados e tradução. Manter operação segura sem TX/PTT automático.

## Rádio Kenwood TS-2000 — telemetria CAT em tempo real / VU-meter e painel operacional
- [ ] Criar painel **TS-2000 em tempo real**, na aba **Operação**, com apresentação de instrumento compacto e opção de expandir os detalhes em aba ou janela destacável. Mostrar estado CAT conectado/desconectado, última leitura e qualidade/latência da comunicação.
- [ ] Apresentar **S-meter MAIN e SUB** (medidores de sinal recebido, barras graduadas e valor bruto), usando as consultas CAT **SM** documentadas pelo Kenwood. Para o MAIN a documentação indica faixa de leitura 0–30 e para SUB 0–15; rotular corretamente como **S-meter**, não VU de áudio ou dBm/RSSI calibrado. Conversão aproximada para S1–S9/+dB apenas mediante tabela calibrada/documentada; nunca inventar dBm ou sinal físico.
- [ ] Exibir **RX/TX em tempo real**, com indicador visual destacado (RX verde-água, TX vermelho), estado TX confirmado por consulta de estado CAT **somente leitura** e faixa em transmissão quando suportada; diferenciar transmissão real observada de habilitação de TX e do fato de uma frequência de uplink estar configurada. **Não enviar comandos `TX;`, `RX;` ou PTT para verificar o estado**, pois alteram o rádio.
- [ ] Exibir **modo/modulação real** (FM, USB, LSB, CW, CW-R, AM, FSK etc.), frequência CAT MAIN/SUB, RX/downlink e TX/uplink, status SAT, controle MAIN/SUB, TRACE e banda ativa. Mostrar leitura real, alvos de Doppler calculados e deltas separadamente, sem atribuir valores estimados ao rádio.
- [ ] Mostrar **potência configurada (W)** por leitura CAT `PC;` (parâmetro de potência ajustada no rádio), diferenciando-a claramente de **potência RF realmente entregue**. Não exibir `PC;` como wattímetro; só mostrar potência RF medida quando existir telemetria CAT de medidor comprovadamente compatível e devidamente validada.
- [ ] Investigar leitura de medidores CAT `RM;` — instrumento/escala SWR, ALC ou compressão — e quais leituras podem ser exibidas sem mudar o estado do medidor físico; respeitar que **SWR no TS-2000 é aplicável apenas a HF/50 MHz** segundo o manual, portanto ocultar ou marcar não disponível nas operações VHF/UHF por satélite.
- [ ] Painéis propostos: **S-meter MAIN/SUB**, **RX/TX**, **Modo RX/TX**, **Potência ajustada**, **Indicadores de ALC/SWR/COMP quando suportados**, **SAT/TRACE**, **Frequência real vs. Doppler previsto**, **CAT/porta/baud**. Disponibilizar modo compacto e ampliado, sem esconder mapa ou próximas passagens em 1366×768.
- [ ] Implementar **polling serial assíncrono** e configurável (sugestão: 1 s para S-meter/estado e 2–5 s para informações menos voláteis), evitando bloqueio da interface e saturação CAT; serializar leituras com atualização Doppler dos VFOs. Registrar amostras, exceções, timeouts e diferenças de estado no **LOGs/CAT**, com opção de ocultar logs muito frequentes.
- [ ] **Estados e segurança:** quando CAT desconectar, travar, não responder ou retornar dado inválido, marcar medidores como **sem leitura/desatualizados** e nunca manter um valor antigo com aparência de tempo real. Não iniciar TX, mudar potência, trocar modos, acionar PTT ou alterar VFOs simplesmente para consultar telemetria. Escrever configurações somente por ação específica autorizada pelo operador.
- [ ] Usar como referência primária **Kenwood TS-2000 Instruction Manual / Appendix PC Control Commands** e validar parser/formatos de `SM`, `PC`, `RM`, `MD`, `SA`, `FA`, `FB` e possíveis comandos de estado RX/TX contra documentação e respostas capturadas do **TS-2000 físico**, antes de marcar cada indicador como homologado. Testes Win7/11: SUB OFF/ON, SAT, RX, TX externo/manual, variações de potência, sinais fortes/fracos, troca rápida de banda e reconexão.

## Frequências — formato visual segmentado como no rádio (426.252.12 MHz)
- [ ] Na barra de operação, cartões CAT, frequências nominais de transponder, campos de **RX/downlink e TX/uplink**, próximas passagens e previsão Doppler, oferecer exibição segmentada no estilo rádio: **`426.252.12 MHz`**, com espaços/agrupamentos de dígitos legíveis, numerais monoespaçados/tabulares e a unidade **MHz** separada. Preservar sinal do deslocamento Doppler em Hz ao lado.
- [ ] Definir explicitamente a **semântica das casas** do formato solicitado: neste exemplo, agrupamento de **426 MHz / 252 kHz / 12 dezenas de Hz**, equivalente a **426 252 120 Hz** (426,252120 MHz). Essa pontuação é **somente apresentação**, nunca número decimal com dois pontos.
- [ ] Permitir precisão selecionável: **`###.###.## MHz`** (resolução visual de 10 Hz, ex. `426.252.12 MHz`) e **`###.###.### MHz`** (resolução de 1 Hz, ex. `426.252.120 MHz`), com alternativa decimal convencional **`426,252120 MHz`** para exibição/cópia. Arredondamento somente visual e explícito, sem perdas na frequência de 1 Hz da comunicação CAT.
- [ ] Implementar um **formatador central** de frequências, usando valores inteiros em Hz internamente e no protocolo CAT (FA/FB); todas as telas devem renderizar consistentemente inclusive 145/435/1.296 MHz, frequência ausente, RX-only, variações Doppler negativas/positivas e diferentes idiomas.
- [ ] Manter **campos de edição e copiar/colar** desambiguados: aceitar formatos válidos documentados, validar faixa física e rejeitar separadores ambíguos sem confirmação. Ao enviar CAT, nunca interpretar `426.252.12` como float nem perder os 10/1 Hz finais.
- [ ] Testes de conversão ida/volta, formatação com zeros finais, 10 Hz e 1 Hz, Doppler de poucos Hz, localização decimal pt-BR e locale EN, leitura dos VFOs, exibição Win7/Win11 e preferências de exibição persistentes.

## Internacionalização (i18n) — adicionar outros idiomas à aplicação
- [ ] Implementar seletor de **Idioma** em **Configurações → Aplicativo**, com opções iniciais **Português (Brasil)** (padrão), **English**, **Español**, **Français**, **Deutsch** e **Italiano**. Preparar arquitetura extensível para outras traduções sem duplicar telas; nomes de idioma apresentados também na língua nativa (bandeiras apenas como auxílio, nunca único identificador).
- [ ] Troca de idioma **em tempo de execução**, sem perder estação, satélite selecionado, modos FM/SSB/CW, porta CAT, preferências do mapa ou edição não salva. Persistir idioma em configuração para instalável/portátil; se alguma janela só puder ser atualizada reiniciando, avisar claramente e preservar dados.
- [ ] Centralizar todas as strings de interface por **chaves de tradução**, não por textos fixos no código. Cobrir integralmente barra superior/versão, abas Operação/Configurações/LOGs/Sobre, catálogo e fichas dos satélites, seleção múltipla, frequências/transponders, TLE/OMM, passagens e contadores, mapa HTML/SVG offline, controle de trajetória, seleção da estação no mapa, geolocalização Windows/IP/GPS/manual, CAT, Doppler, instalador, atualizador, diálogos, placeholders, tooltips, tabelas, status, avisos e mensagens de erro.
- [ ] Tradução também de **textos dinâmicos**, inclusive AOS/TCA/LOS, `em passagem`, `tempo restante`, `sem transponder`, `CAT desconectado`, `TLE vencido`, confirmação de escrita CAT, atualização de frequências, falhas de rede e nomes de unidades quando apropriado. **Não traduzir** nomes oficiais de satélites, indicativos, NORAD IDs, comandos CAT, códigos de modos e dados brutos de LOG sem semântica traduzível.
- [ ] Formatação por locale: data/hora, separador decimal, fusos (UTC/local), pluralização, números e unidades; **cálculo interno sempre UTC/número normalizado**. Entrada de latitude/longitude deve continuar aceitando formatos validados com ponto/vírgula, independentemente do idioma. Não modificar frequências ou parâmetros operacionais ao trocar idioma.
- [ ] Localizar a interface do mapa offline usando o mesmo catálogo de strings do desktop, com fallback seguro sem Internet. Aplicar tradução consistente a mensagens criadas em workers, notificações e diagnóstico, mantendo detalhes técnicos úteis.
- [ ] Fallback para **pt-BR** (ou chave identificável no LOG) caso falte alguma tradução; criar auditoria automatizada de chaves ausentes, chaves órfãs, strings fixas em português/inglês e interpolação/escapes inválidos. Documentar fluxo de contribuição e revisão de traduções.
- [ ] Testes de regressão Win7 PySide2/Qt5 e Win11 PySide6/Qt6: seleção e persistência dos seis idiomas, reabertura do aplicativo, janelas e mensagens dinâmicas, layout com textos longos, 1366×768/DPI aumentado, caracteres acentuados, Unicode, atualizador e instaladores. Verificar que **nenhuma aba permanece parcialmente em outro idioma** após mudança.

## Satélites — marcar todos / desmarcar todos na listagem principal
- [x] O código atual já dispõe de ações `Marcar tudo` e `Desmarcar tudo` em **Configurações → Satélites para a página principal**; a solicitação é disponibilizá-las também de forma direta e visível na própria área/aba de seleção de satélites, sem buscar os controles nas configurações.
- [ ] Colocar **Marcar todos** / **Desmarcar todos** ao lado da pesquisa/filtros da relação de satélites. Operar sobre **todos os satélites** ou **somente os resultados filtrados**, com indicação explícita do escopo, contadores `selecionados/visíveis/total` e opção de desfazer seleção em massa.
- [ ] Persistir seleções; atualizar imediatamente lista principal, previsão AOS/TCA/LOS, próximo satélite e modo compatível. Não confundir seleção da lista com comandos CAT; nenhuma troca em massa de VFOs, PTT ou Doppler transmitido.
- [ ] Evitar travamento com centenas de entradas (bloquear sinais enquanto marca, efetuar uma gravação e recalcular agenda uma única vez). Testar seleção vazia, mudança de filtro, listas grandes e reinicialização em Win7/Win11.

## Satélites — baixar e atualizar frequências/transponders
- [x] **Situação atual:** o cliente usa a API SatNOGS DB em `/api/transmitters/`, cache por NORAD `tx_<NORAD>.json` e o botão `Atualizar frequências / modos` para **o satélite selecionado**; há pré-busca limitada de alguns satélites da agenda. Isso não equivale à atualização completa do catálogo escolhido.
- [ ] Na **aba Satélites** e em **Configurações → Satélites**, incluir botão **Baixar / atualizar frequências** para satélite selecionado, **todos os habilitados** ou apenas os satélites filtrados, exibindo escopo, progresso `N de M`, último sucesso, quantidade de canais recebidos, fonte, erros e opção de cancelar. Atualizar a lista de modos e frequências assim que novos dados válidos forem recebidos.
- [ ] Download em segundo plano com timeout, limite de concorrência, cache/ETag quando permitido, intervalo configurável (sugestão 24 h) e respeito aos limites/políticas SatNOGS. Permitir atualização ao abrir apenas quando necessário, sem consultas em massa descontroladas nem bloqueio do mapa.
- [ ] Exibir na ficha do satélite todos os canais disponíveis com **uplink/downlink nominais (MHz)**, limites inferior/superior quando transponder linear, modo FM/USB/LSB/CW/digital, inversão, beacon/RX-only, status publicado, nome/descrição, fonte e momento da última obtenção. Deixar explícito que status da base não garante operação atual.
- [ ] Tratar satélites sem transponders cadastrados, dados incompletos, páginas paginadas/respostas vazias, falhas HTTPS/offline, registros duplicados, flags `alive`/`status` e NORAD de seis dígitos. **Preservar último cache válido** quando a consulta falhar; sinalizar cache antigo, jamais apagar frequências ao receber erro.
- [ ] **Separar completamente** atualização de frequências/transponders (SatNOGS) da atualização dos elementos orbitais **TLE/OMM** (CelesTrak). Mostrar época/idade TLE e última atualização de frequências individualmente; ambas alimentam a previsão Doppler, mas não devem ser confundidas.
- [ ] Após atualização, recalcular transponder compatível, frequências **nominais** e **Doppler previsto**, usando a estação salva; exibir diferenças RX/TX. Não retunar o TS-2000 automaticamente. Se CAT Doppler estiver ativo, exigir confirmação para mudar o transponder/frequência em uso.
- [ ] Testar Win7/11, seleção individual/em massa, SatNOGS indisponível, cache anterior, cancelamento, períodos, campos ausentes, FM/SSB/CW, linear inversor e RX-only, e consistência com próxima passagem/indicador CAT.

## BUG v1.0.2 — ao selecionar satélite/transponder, RX/TX não seguem Doppler
- [ ] **Reprodução informada pelo operador:** ao selecionar um satélite, a aplicação não ajusta as frequências RX/downlink e TX/uplink com as correções Doppler correspondentes, gerando inconsistência entre a seleção orbital e a operação esperada.
- [x] **Diagnóstico do código v1.0.2:** `choose_satellite()` e `choose_mode()` desmarcam explicitamente `doppler_checkbox`; `choose_mode()` carrega apenas as frequências **nominais** SatNOGS nos campos `down_edit`/`up_edit`; a previsão corrigida aparece em `corrected_label` no próximo `tick()` (com defasagem) e `corrected()` retorna erro quando o canal é só recepção; a atualização real dos VFOs exige acionar `Aplicar RX/TX no TS-2000` ou habilitar manualmente o Doppler automático.
- [ ] **Recalcular imediatamente ao escolher satélite:** executar cálculo de posição/velocidade radial com a **estação efetivamente salva**, TLE/OMM selecionado e transponder escolhido; mostrar **RX corrigido**, **TX corrigido**, offsets Doppler RX/TX em Hz e horário do cálculo sem aguardar o próximo tick. Na troca de transponder/mode, refazer o cálculo imediatamente.
- [ ] **Identidade das frequências:** manter as frequências nominais do transponder em seus campos de referência **sem sobrescrevê-las com valores já corrigidos**, impedindo Doppler duplo/cumulativo. Criar painel operacional destacado com frequências **alvo Doppler** e **CAT efetivamente lido** lado a lado; indicar claramente quando o CAT está desconectado, SAT OFF, fora de passagem ou TLE vencido.
- [ ] **Serviço correto:** tratar canal FM simplex/duplex, transponder linear SSB/CW com inversão e posição escolhida dentro do passband; para beacon/telemetria somente RX, calcular e exibir RX Doppler sem exigir TX e **jamais inventar uplink**. Se não houver transponder válido, avisar em vez de manter valores de satélite anterior.
- [ ] **Seleção e modo Doppler:** remover a perda **silenciosa** do modo de acompanhamento ao mudar satélite/transponder. Distinguir **prévia automática em tela** (sempre que houver dados válidos) de **controle automático CAT** (ação explícita e consentida). Se a sessão de CAT Doppler estiver ativa, ao mudar de satélite impedir mudança silenciosa da sintonia: suspender escrita até confirmar o novo alvo e critérios de segurança, preservando no painel o estado anterior e a explicação da suspensão.
- [ ] **CAT TS-2000 — quando autorizado:** validar rádio conectado, SAT confirmado, VFO MAIN RX/SUB TX conforme comando CAT correto, época orbital vigente, transponder com frequências válidas e passagem acima da elevação mínima; então aplicar RX/TX corrigidos e continuar atualizando no intervalo configurado/limiar em Hz. Quando fora de passagem, **somente prever**, sem retunar o rádio. Nenhum comando PTT/TX acionado pelo aplicativo.
- [ ] **TLE/OMM:** identificar fonte, época e idade dos elementos orbitais; atualizar a projeção com os dados em cache no ritmo do acompanhamento, não fazer download a cada segundo. Com TLE antigo (>7 dias por padrão), ausência de localização salva ou dados orbitais inválidos, informar razão e bloquear escrita CAT automática.
- [ ] **Concorrência e integridade:** serializar escrita/polling CAT, sincronizar leitura de retorno FA/FB e comparar frequência comandada versus confirmada. Na seleção rápida entre satélites, não aplicar comandos atrasados de satélite anterior; cancelamento/timeout devem preservar valores reais e registrar diagnóstico no LOGs/CAT.
- [ ] **Teste de regressão (Win7/Win11 + TS-2000 físico):** troca de satélite e transponder, FM/SSB/CW, linear inversor/não inversor, apenas RX, Doppler aproximando/afastando, diferença RX/TX e ordem dos VFOs, correção imediatamente na interface mesmo offline, CAT conectado/desconectado, SAT ON/OFF, AOS/TCA/LOS, horizonte/elevação mínima, TLE vencido, valores ausentes, sinal de ajuste e troca rápida de satélite. Não confundir testes de software com homologação do TS-2000 real.

## v1.0.2 — seleção da estação no mapa: implementação e testes
- [x] Botão **Marcar estação no mapa** na aba Configurações e na barra da aba Operação, com modo de edição explicitamente ativado.
- [x] Mapa Natural Earth offline: clique para marcar, arraste do marcador, zoom, pan e conversão de pixels/SVG/viewport para latitude/longitude WGS-84.
- [x] Painel de prévia com campos numéricos, botões **Copiar**, **Restaurar anterior**, **Confirmar posição**, **Cancelar** e marcador distinto do ponto salvo.
- [x] Prévia não persiste configuração, não conecta o rádio, não executa CAT, Doppler automático ou PTT. Confirmação preenche campos e retorna à aba Configurações; salvar permanece operação separada.
- [x] Correção de integridade: cálculos orbitais, passagens, telemetria e Doppler usam **somente a estação salva**; edição de latitude/longitude não aplica nova estação antes de Salvar.
- [x] Validação de coordenadas e respostas JavaScript do mapa, rejeitando parâmetros inválidos/não finitos/fora do WGS-84.
- [x] Sem consulta a provedores externos de mapas nem necessidade de GPS ou serviço de localização Windows para posicionar marcador.
- [ ] Homologar visualmente arraste/zoom, atualização após Salvar, alta DPI e diferentes resoluções no Win7 SP1 real e Win11, incluindo HTML/QtWebEngine legado.
- [ ] Verificar precisão de estações com GPS de referência: Natural Earth é mapa mundial, não substitui mapa de ruas/cadastro GPS preciso.
- [ ] Homologar no rádio físico os comandos CAT e Doppler, que permanecem protegidos nesta entrega.

## Configurações — marcar a localização da estação diretamente no mapa
- [ ] Criar recurso **“Marcar estação no mapa”** na aba **Configurações → Estação terrena**, disponível também como atalho no mapa da aba **Operação**. Abrir o mapa-múndi existente (vetorial/offline) em **modo de seleção de localização**, sem interferir na navegação ou seleção normal de satélites.
- [ ] Permitir **clicar no ponto correspondente à antena/estação**, colocar um marcador temporário PT2VHF (indicativo atual) e converter corretamente a posição do clique para **latitude/longitude decimais assinadas (WGS-84)**, inclusive com zoom, pan, redimensionamento, DPI elevado e telas Windows 7/11.
- [ ] Permitir **arrastar o marcador**, dar zoom, centralizar no marcador, copiar as coordenadas e ajustá-las numericamente; toda mudança deve atualizar imediatamente a prévia das coordenadas e vice-versa.
- [ ] Exibir no painel de revisão as **coordenadas anteriores** e as **coordenadas propostas**, com latitude/longitude (precisão adequada), indicação da fonte **“Selecionada manualmente no mapa”**, indicativo e data/hora da seleção. **Altitude não deve ser inferida** da cor do mapa ou fixada em zero; conservar a altitude cadastrada ou solicitar valor explícito.
- [ ] Incluir ações **Confirmar posição**, **Cancelar**, **Restaurar posição anterior** e **Usar localização atual já cadastrada**. Cancelar ou fechar o modo seleção **não** altera os campos nem a estação persistida.
- [ ] Após confirmar o marcador, **pré-preencher** latitude e longitude na aba Configurações e solicitar o clique separado em **Salvar estação**, mantendo a proteção já adotada para GPS/IP: sem gravação ou alteração operacional silenciosa.
- [ ] Após salvar, atualizar o marcador definitivo da estação na aba Operação, recalcular AOS/TCA/LOS, azimute, elevação, distâncias, trajetória e Doppler com a **estação confirmada**; atualizar o contador da próxima passagem e limpar avisos antigos de cadastro. Se não houver TLE/OMM, informar essa pendência sem perder o cadastro.
- [ ] Manter a opção manual, Windows, IP aproximado e GPS NMEA como **fontes alternativas e independentes**, sem transmissão de coordenadas para provedores externos para marcar o ponto no **mapa offline**.
- [ ] Diferenciar visualmente **marcador em edição** (prévia) e **marcador salvo/ativo**; não reposicionar automaticamente a estação ao clicar em satélite, trajetória, footprint ou controles de zoom fora do modo de edição.
- [ ] Integrar o seletor ao mapa HTML/SVG com comunicação segura QtWebEngine ↔ Python, sem executar comandos CAT nem iniciar PTT/TX; limitar eventos aceitos a coordenadas válidas e não confiar em strings arbitrárias da página.
- [ ] Testar cliques e arraste em zoom/pan, 1366×768, maximizado, escala DPI, proximidades de ±180° de longitude e ±90° de latitude, Windows 7 (Qt5) e 11 (Qt6), modo offline, ausência de estação, posição já cadastrada, cancelamento, recarga de aplicativo e nova previsão após salvar.

## v1.0.1 — localização manual/Windows/IP/GPS e distribuição
- [x] Fonte de localização selecionável em Configurações: Windows, IP aproximado (opt-in), GPS serial NMEA e entrada manual.
- [x] Fallback claro quando `QGeoPositionInfoSource.createDefaultSource` retorna `None`, sem exigir instalação de GPS/driver e sem apagar cadastro anterior.
- [x] IP via HTTPS com consentimento explícito e aviso de compartilhamento do IP público; resultado rotulado aproximado, sem altitude ou precisão inventadas.
- [x] Receptor GPS serial independente da porta CAT do TS-2000, leitura NMEA RMC/GGA somente RX, validação de checksum e fix; timeout e sem PTT.
- [x] Pré-visualização e confirmação de coordenadas antes de preencher; clique separado em Salvar estação; nenhuma aplicação automática à estação/radio.
- [x] Testes unitários de parsers, faixas/hemisférios, consulta IP, privacidade, preservação dos campos, ausência de CAT na porta GPS.
- [ ] Homologar a geolocalização no Windows 7 SP1 e Windows 11 físicos, com permissão de localização e diferentes adaptadores GPS NMEA; comparar precisão com GPS de referência.
- [ ] Confirmar operação completa do CAT TS-2000 e atualização Doppler em hardware real, mantendo transmissão desativada até autorização do operador.

## BUG — Obter coordenadas do computador: provedor de localização indisponível (13/10/2026)
- [x] **Diagnóstico da captura:** ao pressionar `Obter coordenadas do computador`, aparece o diálogo `Localização indisponível` com a mensagem `O sistema não forneceu um provedor de localização`. O código atual usa `QGeoPositionInfoSource.createDefaultSource(self)` e recebe `None`, isto é, **não há provedor de posicionamento disponível via QtPositioning naquele ambiente**. Isso não significa que a estação mudou de lugar nem que a latitude/longitude tenham sido apagadas.
- [x] **Corrigir a experiência Windows 7/11, instalado e portátil:** detectar a ausência de provedor **antes** de solicitar coordenadas e apresentar alternativas objetivas na própria aba, em lugar de um pop-up genérico: **Inserir manualmente**, **Obter localização aproximada por IP (opcional)** e, quando existir dispositivo compatível, **Usar GPS conectado**. Não prometer localização GPS do computador quando não houver hardware/serviço disponível.
- [x] **Fallback por IP somente após consentimento explícito**, com URL/provedor HTTPS, política de privacidade, dados enviados (IP público e metadados básicos da requisição), timeout, tratamento offline e possibilidade de desativar. Rotular como **aproximada (cidade/região, não posição da antena)** e exibir precisão estimada quando o serviço informar; não gravar automaticamente nem habilitar cálculos de operação/transmissão sem revisão do operador.
- [x] **GPS opcional**: avaliar NMEA de receptor serial/USB e/ou GPS conectado ao sistema para precisão real; não confundir **porta CAT do TS-2000** com porta GPS. Prever detecção e escolha explícita da origem. Não transformar isto em dependência obrigatória.
- [x] **Preservar campos existentes** quando a busca falhar/expirar/for cancelada. Preencher latitude e longitude somente com resposta válida e com confirmação, aceitar hemisférios/sinais, validar intervalos e mostrar fonte, timestamp e estimativa de precisão. Altitude ausente ou inválida não deve ser substituída por zero silenciosamente.
- [ ] **Testar** sem provedor Qt, permissão negada, serviço Windows desligado, resposta tardia/timeout, Windows 7 SP1 (PySide2/Qt5) e Windows 11 (PySide6/Qt6), rede offline, IP sem precisão suficiente, GPS serial desconectado e coordenadas anteriores já salvas. As previsões AOS/TCA/LOS e Doppler devem usar apenas a estação efetivamente confirmada pelo operador.
- [x] Atualizar texto de ajuda do botão para `Obter localização (quando disponível)`; permitir escolher a fonte e abrir ajuda de configuração/permissões do Windows quando aplicável. Registrar o motivo em LOGs sem vazar coordenadas exatas a serviços externos sem autorização.

## v1.0.0 — entregas e limites de validação
- [x] Selecionar a próxima passagem por satélite habilitado, modos FM/SSB/CW e bandas da estação usando canais publicados no SatNOGS.
- [x] Indicador com nome/NORAD associado à agenda, AOS/TCA/LOS, elevação máxima, contagem regressiva até AOS e tempo restante até LOS; barra de progresso.
- [x] Exibir RX/downlink e TX/uplink **calculados e rotulados como previsão Doppler**, com offsets separados em Hz; previsão futura usa AOS e passagem ativa usa hora atual, baseada na época OMM/TLE.
- [x] Respeitar RX-only, transponder linear normal/invertido, TLE vencido (>7 dias), sem CAT automático ao clicar no evento.
- [x] Controles de trajetória principal: Última passagem, 2/5/10/24 h, personalizado 0,5–48 h e modos Passado/Futuro/Ambos, com escolhas persistentes e worker orbital.
- [x] Trajetória passada reconstruída em linha sólida e prevista em tracejado; segmentação no meridiano de 180°; cálculo em cache sem downloads no refresh visual.
- [x] Corrigir o CSS legado do mapa (`inset` → bordas explícitas) para mitigar renderização reduzida no QtWebEngine do Win7; limpar aviso de estação quando mapa renderizado.
- [x] Preservar instalador e portátil **.exe direto** (Win7 e Win11); ampliar testes automatizados para janelas temporais, serviços FM/SSB/CW, beacons e Doppler.
- [ ] Validar **visualmente** janela redimensionada e mapa no Windows 7 SP1 físico, trajetória escolhida e contador em passagem real; conferir precisão com AMSAT/SatNOGS e a época orbital.
- [ ] Validar Doppler real no Kenwood TS-2000 via CAT, identificação dos VFOs, inversão, comandos SAT/TRACE, leitura MAIN/SUB e atualização ao alterar o rádio manualmente.
- [ ] Verificar transição automática AOS/LOS com satélites simultâneos e banda VHF/UHF, bem como atualização e migração do EXE portátil em Windows 7/11 reais.
- [ ] Funcionalidade de fotos e status operacional de todos os satélites depende de dados externos e licença confirmada; catálogo Orbital não certifica satélite ativo.

## Mapa principal — janela configurável de visualização da trajetória orbital
- [ ] Adicionar controle compacto **Período da órbita / Trajetória** à barra do mapa, para escolher a janela temporal representada na tela. **Sugestões** de presets: **Última passagem**, **2 h**, **5 h**, **10 h**, **24 h** e **Personalizado**; os períodos não são limites fixos e poderão ser alterados após testes de usabilidade.
- [ ] Diferenciar claramente **histórico da trajetória** (trecho já percorrido, linha sólida), **posição atual** (marcador de satélite) e **trajetória futura prevista** (linha tracejada). Oferecer opções separadas `Passado`, `Futuro` ou `Ambos`, com indicação explícita do intervalo, evitando confundir histórico calculado com posições recebidas.
- [ ] O preset **Última passagem** significa, quando houver posição da estação, a passagem anterior em relação ao horizonte/elevação mínima cadastrada; se não houver estação configurada, indicar indisponibilidade e usar um período de tempo selecionável, sem inventar AOS/LOS.
- [ ] Em 2/5/10 horas, interpretar o valor conforme `Passado`, `Futuro` ou `Ambos`; para `Ambos`, separar duração de cada direção ou informar claramente como a janela é dividida, sem ambiguidade.
- [ ] Exibir início/fim em **data e hora local**, com opção UTC; manter indicação de **época TLE/OMM**, validade e se o trecho é previsto ou reconstruído matematicamente. Orbitas anteriores não equivalem a histórico real de telemetria.
- [ ] Atualizar a linha da órbita e footprint para o satélite atualmente selecionado, preservar a posição de mapa/zoom ao trocar o período e permitir exibir a cobertura opcionalmente. Renderizar corretamente cruzamentos da linha internacional de data (±180°), sem criar saltos retos pelo mapa.
- [ ] Preservar escolha entre sessões e adicionar botão `Padrão` (sugestão inicial: **2 horas futuras**) sem obrigar o operador a utilizar os presets.
- [ ] Calcular amostras orbitais localmente a partir do TLE/OMM em cache, em worker com passo temporal adaptativo, simplificação de trilha e limite de pontos para evitar travamentos no Windows 7 e 11; **não disparar requisições TLE** ao mover o controle.
- [ ] Testar 2/5/10/24 h, janelas customizadas, órbitas múltiplas, virada de dia, passagem pelo antimeridiano, TLE antigo, resize/zoom, ausência de estação e preservação de preferências.

## Operação — frequências da próxima passagem com Doppler baseado em TLE/OMM
- [ ] No indicador de **Próxima passagem** e **Em passagem**, mostrar satélite, modo operacional escolhido (FM, SSB, CW etc.), transponder/canal, frequência nominal de **RX/downlink** e **TX/uplink**, mais as frequências calculadas com Doppler e offsets assinados em Hz (MHz com 6 casas decimais).
- [ ] Calcular Doppler a partir do **TLE/OMM válido**, posição/altitude da estação e velocidade radial satélite–estação pelo mesmo modelo SGP4/Skyfield do mapa e das passagens. Calcular separadamente compensação de RX/downlink e TX/uplink; nunca usar uma correção fixa.
- [ ] **Antes do AOS**, indicar frequências Doppler **previstas para o AOS**, identificadas como previsão futura e não sintonia atual do rádio. Opcionalmente permitir inspeção das frequências previstas em TCA e LOS.
- [ ] **Durante a passagem**, atualizar as frequências Doppler calculadas em intervalos configuráveis (padrão 1 segundo), com tempo remanescente até LOS; após LOS, selecionar automaticamente o próximo satélite compatível.
- [ ] Em transponders **SSB/CW lineares**, respeitar banda, ponto escolhido no passband, transponder normal/invertido e pareamento RX/TX. Em FM, usar o canal nominal correto. Para **beacon e recepção apenas**, mostrar TX indisponível; não inventar uplink.
- [ ] Separar visualmente **frequência publicada pelo provedor**, **frequência prevista calculada** e **frequência realmente lida via CAT do TS-2000**. Sem CAT conectado, exibir somente a previsão; não indicar que VFOs foram alterados.
- [ ] Exibir **fonte, época (epoch), idade e última obtenção do TLE/OMM**. Se os elementos estiverem vencidos ou ausentes, avisar e bloquear **escrita automática de Doppler ao CAT**; nunca disfarçar dados antigos como atuais.
- [ ] Atualizar TLE/OMM pelo intervalo configurado e política do provedor, usando cache; **não baixar TLE a cada segundo**. Aplicar filtros de modos/bandas, satélites habilitados e altitude mínima da estação.
- [ ] A seleção/click da passagem pode preencher o painel de planejamento, **mas não deve conectar, habilitar SAT, transmitir, acionar PTT ou reprogramar VFOs sem autorização explícita**.
- [ ] Testar FM, SSB, CW, inversão, beacon RX-only, AOS/TCA/LOS, dados orbitais vencidos, ausência de transponder, troca de satélite e comparação entre cálculo e leitura CAT.

## Operação — indicador de próxima passagem compatível e tempo restante
- [ ] Adicionar **indicador permanente e destacado no topo da aba Operação**, junto à versão/estado do rádio ou acima do painel "Próximas passagens", mostrando **satélite correspondente (nome + NORAD), modo de operação compatível (FM/SSB/CW e futuros), data/hora local de AOS, TCA e LOS** e **contagem regressiva**.
- [ ] Usar **somente os satélites habilitados pelo operador** em Configurações → Satélites e o **perfil operacional da estação** em Configurações → Rádio: modos marcados, capacidades RX/TX por banda/VFO, transponder/canal disponível, elevação mínima e localização. Não usar satélites meramente catalogados ou com modo incompatível para o indicador principal.
- [ ] Distinguir serviços **FM, SSB (USB/LSB de transponder linear), CW bidirecional, beacon CW somente RX, digimodos e telemetria**. Não considerar um beacon como transponder para QSO; mostrar *RX apenas* quando aplicável. Respeitar o modo escolhido (um ou vários) e permitir o usuário alternar rapidamente os modos filtrados sem reabrir Configurações.
- [ ] **Antes da passagem (AOS futuro)**: exibir `PRÓXIMA PASSAGEM · RS-44 · SSB · em 00:18:42` e, logo abaixo, data/hora AOS, TCA, LOS, elevação máxima prevista e frequências publicadas para o modo compatível (se existirem). Para intervalos longos usar dias/horas/minutos; atualizar contador visual a cada segundo.
- [ ] **Durante a passagem (AOS ≤ agora < LOS)**: destacar `EM PASSAGEM · RS-44 · SSB · resta 00:06:31`, exibir barra de progresso **AOS → TCA → LOS**, máxima elevação, azimute/elevação atuais e, opcionalmente, tempo até ou desde TCA. Se houver várias passagens simultâneas compatíveis, priorizar **a atual** por critério documentado (ex.: maior elevação atual), com acesso às demais.
- [ ] **Após LOS**: mudar automaticamente para o próximo evento elegível (sem contador negativo ou horários vencidos); transição AOS/LOS determinística com hora UTC internamente e conversão à hora local apenas na apresentação. Destacar fusos e passagens que cruzam meia-noite.
- [ ] **Interação:** clique no indicador seleciona o satélite e seu serviço/transponder compatível na lista lateral e no mapa, destaca a linha da agenda e mostra suas frequências de uplink/downlink; **não conectar, transmitir, ativar SAT, reprogramar VFO ou iniciar Doppler automaticamente**.
- [ ] **Cores e estados:** verde-água durante passagem, azul para próxima passagem, âmbar para dados incompletos/próximos de vencer; apresentar ícone/texto além da cor. Mostrar `Nenhuma passagem compatível no período` se a lista filtrada estiver vazia, ou aviso objetivo se faltarem estação, dados TLE/OMM, status de canal ou seleção de modos.
- [ ] **Integridade dos dados:** agenda e indicador devem utilizar exatamente a mesma previsão orbital e os mesmos filtros, recalculando quando mudar TLE/OMM, estação, bandas, modos, satélites habilitados ou janela de previsão. A animação do contador deve usar tempo monotônico/referência do relógio sem disparar download de TLE a cada segundo. Dados desatualizados não podem ser apresentados como passagem confirmada; o status de funcionamento do transponder exige evidência atual.
- [ ] **Testes Win7/Win11:** FM somente, SSB somente, CW somente, vários modos, beacon RX-only, banda incompatível, duas passagens simultâneas, antes/exatamente em AOS, TCA e LOS, virada do dia, mudança de timezone/relógio, cache TLE expirado, perda temporária de Internet e nenhum satélite correspondente. Layout não deve sobrepor o mapa ou cortar textos em 1366×768 / DPI ampliado.

## Validação visual — Windows 11 (13/10/2026)
- [x] **Aplicativo aberto no Windows 11 — v0.2.1:** captura enviada pelo usuário mostra interface PT2VHF Sat Tool renderizada; confirmação visual de inicialização, sem atestar se era instalador ou portátil.
- [x] **Mapa vetorial offline preenche a coluna central no Win11:** diferentemente do teste fotográfico no Win7, o mapa-múndi, linha da órbita selecionada, footprint, marcador de satélite ISS (ZARYA) e estação PT2VHF estão desenhados em tamanho adequado. Sem mensagem de HTTP 418 visível na captura; não significa teste prolongado de rede.
- [x] **Previsões exibidas para a estação no Win11:** painel `Próximas passagens — 36 h` contém linhas com AOS, TCA, LOS, elevação máxima e modos; a estação PT2VHF está visível no mapa. Dados ainda não foram conferidos independentemente quanto à exatidão orbital.
- [x] **Indicador CAT coerente ao desconectar:** rádio Kenwood TS-2000 aparece como **Desconectado**, RX/TX reais não exibidos nos cartões; números Doppler no rodapé são apenas cálculos, não leituras ou confirmação de sintonia do TS-2000.
- [ ] **REGRESSÃO DE MENSAGEM DESATUALIZADA:** sob o mapa permanece o texto `Para ver órbitas/passagens, cadastre sua estação. Cadastre latitude e longitude na aba Configurações` apesar de o Win11 já apresentar PT2VHF no mapa, métricas orbitais e próximas passagens. Limpar a mensagem quando o cadastro estiver válido e a primeira órbita for renderizada; mostrar a mensagem apenas se latitude/longitude faltarem ou forem inválidas, com testes ao salvar localização, trocar abas e reiniciar.
- [ ] **Separação de dados CAT:** tornar ainda mais explícito que valores RX/TX nos cartões vêm **somente de CAT confirmado**, enquanto frequência nominal e Doppler do rodapé são **estimativas calculadas**; ao desconectar, nunca apresentar cálculo como telemetria efetiva.
- [ ] **Avaliar layout em 1366×768 ou alturas próximas:** conferir se lista lateral e campos de frequências nominais são roláveis e não ficam inacessíveis atrás da faixa CAT inferior. Windows 11 com tamanhos de janela pequenos, escala 125–200% e Windows 7 serão testados separadamente.
- [ ] **Pendente de homologação:** interface testada visualmente, mas **nenhuma confirmação** de rádio conectado, leitura serial real, correção CAT de Doppler, transmissão ou validação temporal de previsões.

## Validação de campo — Windows 7 SP1 (13/10/2026)
- [x] **Instalação e abertura:** usuário apresentou foto da janela do PT2VHF Sat Tool funcionando no Windows 7, com abas, catálogo lateral, painel de passagens e comandos CAT visíveis. Confirma abertura básica; **não** certifica funcionamento integral, CAT, Doppler ou previsões.
- [ ] **REGRESSÃO VISUAL — MAPA OFFLINE COM TAMANHO INCORRETO NO WINDOWS 7:** captura mostra o mapa e seus controles renderizados como **um retângulo pequeno no canto superior esquerdo** da área central, enquanto quase toda a região prevista para mapa permanece vazia/azul. A base vetorial parece ter sido carregada, porém não se ajusta ao tamanho disponível. Corrigir layout/viewport da página HTML/SVG hospedada em `QWebEngineView`/PySide2/QtWebEngine no Windows 7; testar primeiro renderização em maximizado e após redimensionamento, resolução e DPI. Verificar `setHtml` com base URL, dimensões do viewport, repaint/resize e aceleração gráfica/driver. Considerar fallback robusto compatível com Qt5 para desenhar o mapa, sem reintroduzir tiles bloqueados ou dependência de CDN.
- [ ] Teste de regressão específico: no Win7, mapa deve preencher toda a coluna central, preservar proporção cartográfica e manter visíveis a órbita, posição da estação/satélite, legenda e os botões de zoom após redimensionar a janela, alternar de abas e alterar DPI.
- [ ] Verificar cadastro de latitude/longitude (a captura mostra aviso **Cadastrar a estação** e agenda de passagens vazia); não interpretar ausência de passagens como bug antes de cadastrar coordenadas válidas. Após salvar a estação, confirmar previsão AOS/TCA/LOS para satélites habilitados.
- [ ] Homologar portas COM, leituras CAT, atualização Doppler e atualização automática em hardware real separadamente.

## v0.2.1 — layout aprovado, identidade visual e mapa offline
- [x] Adotar tela **Operação** de três colunas: satélites/modos na esquerda, mundo/órbita no centro e agenda/telemetria CAT à direita.
- [x] Aplicar cabeçalho e paleta do PT2VHF Sat Tool, gerar ícones multirresolução e embuti-los no EXE instalável e portátil de ambos os Windows; `SetupIconFile` no Inno Setup.
- [x] Inserir lista de satélites selecionáveis na esquerda, sincronizada com seletor NORAD/modos e filtros, sem eliminar o formulário de frequências manuais.
- [x] Criar painel de frequências **RX FA e TX FB realmente lidas**, modo MAIN e SAT à direita, com status claro de desconexão, ausência/erro de CAT e leitura antiga.
- [x] Substituir integralmente os tiles bloqueados por HTTP 418 por **mapa vetorial offline Natural Earth de domínio público**, com zoom e arraste, sem dependência de Leaflet/CDN.
- [x] Preservar cálculos de órbita, footprint, AOS/TCA/LOS, correção Doppler e CAT existentes.
- [x] Atualizar README e testes automatizados para exigir marca + mapa offline nos executáveis e quatro arquivos `*.exe` (Win7/Win11, Setup/Portable).
- [ ] Homologar experiência visual real em Win7/11, tamanhos de tela pequenos, alta DPI e QtWebEngine; verificar ausência do erro HTTP 418 no hardware do operador.
- [ ] Homologar CAT TS-2000 real e atualização in-place de cada tipo de EXE; não assumir uso de RX/TX sem leitura CAT confirmada.
- [ ] Confirmar identidade visual como definitiva e validar variantes de ícones/tema claro; próxima etapa possível: thumbnails por satélite à esquerda e mais refinamento da responsividade.

## Identidade visual oficial — PT2VHF Sat Tool
- [x] Definir conceito visual e produzir arquivos SVG vetoriais como base de marca em `assets/branding/`, com documentação em `docs/BRANDING.md`.
- [ ] Padronizar **símbolo de satélite, órbita terrestre e ondas de RF**, logotipo horizontal `PT2VHF SAT TOOL` e assinatura reduzida para áreas compactas. Evitar logotipos de fabricantes/AMSAT/organizações externas.
- [ ] Integrar ícone oficial na janela principal, barra de título, taskbar/Alt+Tab, bandeja (se implementada), notificações, diálogos, janelas auxiliares, splash de inicialização e tela **Sobre**.
- [ ] Compilar `.ico` multirresolução (16, 24, 32, 48, 64, 128 e 256 px) e ícones PNG (16/24/32/48/64/128/256/512/1024); testar transparência, legibilidade em tamanhos pequenos e fundos claros/escuros.
- [ ] Adicionar ícone ao PyInstaller (`--icon`) em **todos os quatro EXEs** (Win7 Setup/Portable, Win11 Setup/Portable), e `SetupIconFile` no Inno Setup. Garantir consistência entre EXE do instalador, EXE instalado, atalho e Desinstalador.
- [ ] Aplicar tema e tokens de cores nas abas, menus, botões, mapas, tabelas, indicadores CAT/TLE/Doppler e mensagens, sem reduzir contraste de informações operacionais; não usar fundos espaciais complexos atrás de telemetria/frequências.
- [ ] Atualizar README do GitHub (marca acima dos downloads), banner da release, screenshots, manual, changelog, página Sobre e artefatos de build com a mesma identidade.
- [ ] Criar variantes para fundo claro, fundo escuro e versão monocromática; prever alto contraste, escalonamento DPI 100–250%, Windows 7/11 e leitura por tecnologias assistivas.
- [ ] Preservar os nomes **PT2VHF Sat Tool** (aplicativo) e `PT2VHF-Sat-Tool` (repositório); não alterar o identificador de instalação ou diretórios de dados somente por identidade visual.
- [ ] CI: validar que os quatro EXEs, instaladores e recursos visuais contêm o ícone correto e não recorrem ao ícone padrão do Python/Qt/PyInstaller.
- [ ] Validação visual real em Windows 7 SP1 e Windows 11, incluindo taskbar, atalhos, instalador, diálogos, ícones pequenos e transparência.
- [ ] Arte conceitual aprovada pelo operador antes de considerar a identidade final/homologada.

## Erro observado no mapa — tiles HTTP 418 / Access blocked
- [ ] Tratar o erro exibido na v0.2.0: OpenStreetMap responde **HTTP 418: Access blocked** ao carregamento de tiles no QtWebEngine.
- [ ] Auditar política de uso do servidor de tiles, identificação da aplicação/headers, comportamento de WebEngine, cache, frequência de solicitações e condição de bloqueio; não implementar bypass ou disfarçar cliente.
- [ ] Configurar serviço cartográfico permitido, com atribuição e limites observados, ou mapa geográfico local/offline de fallback; diferenciar camada de mapa-base da renderização da órbita.
- [ ] Deixar órbita, posição do satélite, footprint, estação, previsões e telemetria funcionarem mesmo quando os tiles remotos falharem.
- [ ] Detectar HTTP 403/418/429/5xx e apresentar estado amigável, logs e opção de troca de mapa, nunca tiles repetindo avisos de erro por toda a tela.
- [ ] Testar Win7/Win11, rede restrita, bloqueio do provedor, ausência de internet, troca de base cartográfica e atribuição.

## v0.2.0 — entregas integradas (homologação de campo pendente)
- [x] Quatro downloads EXE diretos: Win7 x86 Setup e Portable onefile; Win11 x64 Setup e Portable onefile. **Nenhum portátil em ZIP**.
- [x] Atualizador seleciona `Portable.exe` por variante, verifica SHA-256 e substitui o EXE somente depois do encerramento; os dados locais ficam em `data/`.
- [x] Perfil da estação com seleção de modos **FM/SSB/CW** e bandas, persistente; fabricante Kenwood, modelo TS-2000 e porta serial configuráveis.
- [x] Sugestão inicial de satélites por modos/bandas baseada em canais SatNOGS em cache e candidatos históricos rotulados como **não confirmados**; seleção manual por NORAD prevalece.
- [x] Filtro de satélites da página principal pelos habilitados, agenda de próximas passagens AOS/TCA/LOS/elevação/mode e seleção no mapa.
- [x] Foto de satélite pesquisada no Wikimedia Commons com metadados de licença e crédito, sem usar imagem quando a identificação for incerta.
- [x] Configuração de intervalo TLE/OMM (4 h por padrão, mínimo 2 h), aba Sobre e painel CAT acima do mapa com frequências reais FA/FB e modo, polling não bloqueante.
- [x] Autoteste nos executáveis Setup/Portable congelados no Windows CI (NumPy/Skyfield/Qt); falha impede publicação.
- [ ] Validar instalação e primeiro início em Windows 7 SP1 e Windows 11 físicos, com porta COM real, QtWebEngine e provedores orbitais.
- [ ] Homologar comandos CAT, sequenciamento SAT/TRACE e Doppler no TS-2000 real sem transmissão involuntária.
- [ ] Obter índice operacional completo e atualizado de todos os transponders ativos (hoje a descoberta é progressiva e usa cache/candidatos marcados como não confirmados).
- [ ] Automatizar controle SUB/TX mode conforme CAT TS-2000 validado e ampliar metadados fotográficos oficiais do operador.
- [ ] Migração de Portable ZIP da v0.1.x para Portable EXE da v0.2.x deve ser **manual**: a edição antiga procura ZIP e não entende o novo formato. Manter a pasta `data/` ao lado do novo EXE.

## MVP 0.1.1 (código e pipelines preparados — validar em Windows/TS-2000)
- [x] Windows desktop PySide6 (Win11) e PySide2 (Win7) com mapa central, satélite e órbita desenhados sobre OpenStreetMap.
- [x] Estação cadastrável: indicativo, latitude, longitude, altitude, elevação mínima.
- [x] Botão de localização via serviço de localização do sistema, dependente das permissões.
- [x] OMM + TLE CelesTrak grupo amateur; cache, atualização e fallback TLE em caso de falha OMM.
- [x] Transponders SatNOGS, modos e faixas, seleção de transponder manual ou publicada.
- [x] Previsão de passagens AOS/MAX/LOS de 36 horas e ordenação.
- [x] Doppler uplink/downlink por velocidade radial e derivada numérica da distância.
- [x] Kenwood TS-2000 conexão CAT, leitura de FA/FB/SA/MD; ativar SAT/TRACE OFF.
- [x] Ajuste manual CAT com confirmação; Doppler automático somente ativação explícita.
- [x] Workflow Windows em matriz (Win7 SP1 x86 e Win11 x64): dois ZIP portáteis e dois instaladores Inno Setup, com checksums e release automática em tag.
- [x] Log CAT RX/TX, eventos e falhas; dados do usuário persistentes.

## Configurações — conexão CAT e rádio
- [ ] Criar grupo dedicado **Conexão / Rádio** na aba Configurações, separado da configuração da estação.
- [ ] **Fabricante** selecionável; valor padrão **Kenwood**. Não apresentar fabricantes ainda não suportados como operacionais.
- [ ] **Modelo** dependente do fabricante; padrão **TS-2000**. Preparar drivers CAT por fabricante/modelo, com identificação, capacidades e comandos específicos.
- [ ] **Porta serial COM** selecionável com nome e descrição do adaptador; botão **Atualizar portas**; permitir entrada manual e informar porta ausente/ocupada.
- [ ] Configurar e persistir **baud rate**, bits de dados, paridade, stop bits e timeout conforme capacidades do equipamento; padrões TS-2000: 9600, 8N1. Validar parâmetros antes de conectar.
- [ ] Botões **Conectar / Desconectar** com indicador de conexão e mensagem de erro detalhada; testar comando de identificação CAT (`ID;`) e confrontar resposta com modelo selecionado.
- [ ] Salvar fabricante, modelo, porta e parâmetros; nunca habilitar escrita CAT/Doppler sem conexão válida e autorização explícita do operador.

## Mapa — painel CAT em tempo real (rádio conectado)
- [ ] Exibir **sobre ou junto do mapa**, sempre visível durante o rastreio, painel de telemetria do rádio com **Fabricante / Modelo**, **porta COM**, **estado CAT (conectado/desconectado)** e **modo SAT (ON/OFF)**.
- [ ] Mostrar **frequência RX/downlink real lida do TS-2000** (`FA`), **frequência TX/uplink real lida** (`FB`) em MHz com resolução adequada, e **modos de modulação** reportados por CAT (pelo menos MAIN/`MD`; SUB somente após implementar leitura confiável, sem inferir).
- [ ] Apresentar **VFO / MAIN / SUB** conforme leitura CAT do TS-2000 em SAT, distinguindo explicitamente canais controlados e os dados que o protocolo efetivamente consegue confirmar.
- [ ] Mostrar separadamente **frequências CAT confirmadas**, **frequências-alvo calculadas pelo Doppler** e o **offset Doppler** (Hz, com sinal) para RX e TX. Não tratar cálculo como leitura real do rádio.
- [ ] Fazer atualização periódica enquanto conectado (alvo 1 segundo, configurável) e atualização imediata depois de comandos CAT confirmados; refletir alterações manuais feitas diretamente no transceptor.
- [ ] Executar polling em worker não bloqueante com serialização dos acessos CAT, tratamento de timeout/reconexão, evitando congelar a interface, colisões com escrita Doppler e cargas excessivas na porta COM.
- [ ] Mostrar **hora da última leitura bem-sucedida**, estado **atualizando / desatualizado / erro / desconectado**, e limpar ou marcar valores antigos; jamais exibir telemetria vencida como estado atual.
- [ ] Estado real **RX/TX/PTT** somente se houver comando CAT comprovadamente suportado e validado; caso contrário apresentar **indisponível** e não inferir transmissão a partir da frequência ou operação Doppler.
- [ ] Painel compacto, legível em Win7/Win11, permitindo expandir detalhes técnicos e mantendo mapa/órbita visíveis. CAT deve continuar exclusivamente sem acionamento PTT pelo aplicativo.

## Tela inicial — seleção inteligente pelo perfil operacional da estação
- [ ] **Ao abrir o aplicativo**, carregar indicativo, latitude/longitude/altitude e perfil da estação e exibir, automaticamente, os **satélites amadores compatíveis com as capacidades reais** do equipamento, organizados em painel lateral de próximas passagens. O mapa-múndi central mostra posição, órbita e cobertura do satélite selecionado.
- [ ] Em **Configurações → Estação / Rádio**, criar perfil editável de **modos disponíveis: FM, SSB (USB/LSB) e CW**, além de bandas, faixas RX/TX por VFO (MAIN/SUB), antenas e restrições operacionais. Para o Kenwood TS-2000, propor os modos suportados como configuração inicial, mas conferir limites reais por banda e hardware; não deduzir que todo satélite FM/SSB/CW é utilizável.
- [ ] **Primeira execução:** pré-selecionar somente candidatos que tenham ao menos um transponder/serviço publicado, compatível com modo e bandas da estação, com trajetória válida e sem indicação confiável de inatividade. Diferenciar *operável em TX/RX*, *somente recepção*, *compatibilidade parcial* e *desconhecido/sem dados*. Beacon CW não equivale a transponder CW bidirecional; transponders lineares podem exigir USB/LSB diferentes no uplink/downlink.
- [ ] Persistir três camadas distintas: **candidatos sugeridos automaticamente**, **seleção confirmada pelo operador (favoritos/exclusões)** e **satélite atualmente acompanhado**. **Nunca sobrescrever os ajustes manuais** quando TLE/modos mudarem ou o aplicativo reiniciar. Oferecer botão **Recalcular sugestões** e **Restaurar seleção automática**; deixar novos candidatos como sugestões, sem ativação silenciosa após primeira configuração.
- [ ] Painel lateral **Próximas passagens** exibindo apenas habilitados por padrão, ordenados por **AOS crescente** e com agrupamentos **Passando agora**, **Próximas horas**, **Hoje**, **Amanhã** e **Posteriores**; calendário/lista navegável por período configurável (24h, 48h, 7 dias).
- [ ] Cada linha/card mostra **nome/foto (com licença), NORAD, modos utilizáveis FM/SSB/CW, frequências uplink e downlink, tipo de transponder, status operacional, AOS (início), TCA (máximo), LOS (fim), elevação máxima, azimutes AOS/LOS, duração, tempo restante e status TLE**. Hora local pela estação (timezone/IANA) com opção de UTC e **data explícita** para cruzamento de dia/fuso.
- [ ] Clique em satélite/passagem seleciona-o no **mapa central**, atualiza sua órbita, ground track, horizonte/footprint, AOS/LOS e ficha técnica/operacional, sem conectar nem alterar o rádio por conta própria. **Controle CAT e Doppler continuam desabilitados até ação explícita** do operador e validação de segurança.
- [ ] Atualizar indicadores visuais/contagem regressiva a cada segundo com efemérides já carregadas; **não baixar TLE a cada atualização da interface**. Recalcular a agenda apenas em mudança de estação/perfil/filtros/TLE, mudança relevante de tempo ou por solicitação. Utilizar workers para não bloquear o mapa.
- [ ] Quando a estação ainda não tiver localização ou perfil válidos, orientar configurar esses dados; não inventar horários de passagens. Quando não houver satélites compatíveis, mostrar causa e permitir ampliar filtros sem confundir ausência de dados com inexistência de passagens.
- [ ] Separar **compatibilidade técnica** de **autorização regulamentar para TX** e da confirmação de funcionamento do satélite; indicar fontes e atualização das informações.
- [ ] Testes: FM apenas, SSB apenas, CW apenas, múltiplos modos, beacon RX-only, inversão de transponder, VFO/banda incompatível, satélite inativo, seleção manual persistente, offline/TLE antigo, passagem cruzando meia-noite, timezone e mudança de coordenadas.

## Configurações — Satélites amadores e favoritos da página principal
- [ ] Criar a seção **Configurações → Satélites**, com catálogo pesquisável (nome, apelido, NORAD, COSPAR, faixa, modo, tipo e status), seleção individual por checkbox, **Marcar todos / Desmarcar todos** e ação **Mostrar apenas selecionados**.
- [ ] Persistir em configuração local, pela chave **NORAD_CAT_ID**, a seleção de satélites a acompanhar; não usar o nome como identificador único e tratar renomeações/aliases.
- [ ] Exibir **somente os satélites selecionados** na página **Operação**: seletor, mapa, trajetórias, previsão/próximas passagens, notificações e demais listagens operacionais. Manter o catálogo completo na aba **Satélites** para descobrir e ativar outros; oferecer a opção separada **Mostrar todos no catálogo**.
- [ ] Disponibilizar preferências **Favoritos**, **Mostrar apenas operacionais (segundo fontes)** e filtros por VHF/UHF, FM, SSB, CW, digital, telemetria, repetidor FM, linear, APRS e recepção apenas. O status ativo depende de evidência datada; classificação orbital não é prova de operação.
- [ ] **Ficha de satélite**: foto real (quando licenciada) ou ilustração **identificada como ilustração**, nome, outros nomes, NORAD, COSPAR, missão/operador, tipo de satélite, lançamento, situação conhecida, massa/dimensões quando disponíveis, órbita, inclinação, altitude aproximada, período, excentricidade, epoch dos elementos, visibilidade desde a estação, AOS/TCA/LOS, elevação máxima e azimute.
- [ ] **Ficha de rádio/transponder**: frequências e intervalos exatos **uplink/downlink**, beacon, modos RX/TX, conversão de banda, sentido de transponder linear (normal/invertido), tom CTCSS quando publicado, largura de banda, polarização (se verificada), disponibilidade de TX e notas operacionais, com fonte, timestamp e sinalização de valores desconhecidos.
- [ ] Cada frequência deve ser rotulada por tipo: **publicada** (SatNOGS/AMSAT), **confirmada no rádio via CAT** ou **alvo calculado com Doppler**; não misturar bases. Não marcar automaticamente TX como permitido ou transponder como operante porque possui elementos orbitais.
- [ ] **Fotos**: pesquisar primeiro páginas oficiais dos operadores/AMSAT e acervos Wikimedia Commons; obter foto da espaçonave ou foto de integração real, não imagens de satélites homônimos; registrar URL original, autor, crédito, licença e data. Usar cache e placeholder quando não houver imagem comprovada/licenciada; permitir abrir fonte e substituir manualmente a foto.
- [ ] **Consolidação de fontes**: SatNOGS DB (satélites/transmissores e modos; CC BY-SA 4.0), AMSAT (guia de frequências e relatos de operação), CelesTrak (OMM/TLE orbital), operadores e documentação de missão, Wikimedia Commons (imagens com metadados/licença). Priorizar NORAD/COSPAR; guardar proveniência e detectar divergências entre frequências e status.
- [ ] Ordenar os satélites habilitados por **próxima passagem** sobre a estação cadastrada; diferenciar: *operacional confirmado*, *relato recente*, *catálogo sem confirmação*, *inativo/decadente*, *somente beacon* e *dados indisponíveis*. Destacar aqueles com transponder utilizável pelo equipamento/filtros; avisar quando frequência estiver fora da cobertura do TS-2000.
- [ ] Incluir testes para persistência dos favoritos, filtros, status, cache/offline, troca de satélite, consistência de NORAD, ausência de foto e divergência de dados de frequência.

## Configurações — TLE e efemérides orbitais (OMM principal)
- [ ] Criar seção **Configurações → TLE / Efemérides** com fontes configuráveis, ordem de prioridade e diagnóstico: **CelesTrak OMM JSON como padrão**, TLE clássico como alternativa apenas para NORAD compatíveis, e possibilidade futura de importar elementos orbitais locais.
- [ ] Selecionar grupos de dados relevantes (amateur e outros explicitamente habilitados), mostrar URL **HTTPS da consulta**, tamanho, quantidade de objetos, última consulta, última atualização efetiva, **época orbital por satélite**, fonte e saúde do cache; validar integridade/schema/NORAD e evitar resultados vazios ou regressão de idade.
- [ ] **Atualização automática configurável:** opções 2, 4, 8, 12 e 24 horas, padrão **4 horas**, mínimo técnico obrigatório de **2 horas por conjunto** para respeitar o CelesTrak. O botão manual **Atualizar agora** consulta cache sem repetir download antes do prazo mínimo. Retentativas com backoff, proteção contra 403/429/5xx e falha de rede; nunca disparar loop de requisições.
- [ ] Diferenciar **intervalo de atualização TLE/OMM** (horas), **frequência de atualização da posição no mapa** (segundos), **polling CAT** (segundos) e **checagem de versão do programa** (minutos). São tarefas independentes; não vincular a atualização da órbita ao refresh visual.
- [ ] Preservar último conjunto válido offline, com cópias de segurança e escrita atômica; indicar **válido, antigo, indisponível** e **idade da época por satélite**. Nunca descartar cache íntegro porque o download falhou.
- [ ] **Segurança Doppler:** quando os elementos orbitais ultrapassarem o limite configurado, padrão 7 dias, alertar e bloquear *correção automática*; não usar data do arquivo no lugar da época orbital. Não transmitir e não reconfigurar CAT enquanto fonte orbital estiver inválida.
- [ ] Permitir **importar TLE/OMM local**, inspecionar e validar conteúdo antes de usar, e exportar metadados da fonte para depuração. Documentar limitações do TLE clássico para catálogos NORAD de seis ou mais dígitos e compatibilidade com OMM JSON.
- [ ] Registrar logs das consultas (URL, HTTP, duração, tamanho, checksum/validação, contagem de satélites, timestamp e motivo da falha), respeitando privacidade e políticas do provedor; testes de cache/TTL, falha de rede, formato inválido, época vencida e dois conjuntos conflitantes.

## Informações → Sobre (interpretação provisória da solicitação)
- [ ] Disponibilizar **Sobre o PT2VHF Sat Tool** fora dos parâmetros operacionais: versão do aplicativo, edição Windows 7/11, instalável/portátil, canal de atualizações, licença MIT, repositório GitHub, créditos, bibliotecas de terceiros e links para fontes de dados, uso de imagens e respectivas licenças.
- [ ] Permitir copiar diagnóstico do ambiente (SO/arquitetura, Qt, Python empacotado, NumPy, banco TLE/OMM, versão do driver CAT), sem expor dados pessoais/portas sensíveis indevidamente; incluir atalhos **Verificar atualizações** e **Abrir changelog**.

### Referências verificadas
- AMSAT Satellite Database: https://satdb.amsat.org/
- AMSAT Status: https://amsat.org/status/
- AMSAT Live Linear Satellites: https://www.amsat.org/live-linear-satellites/
- SatNOGS DB API: https://librespacefoundation.gitlab.io/satnogs/satnogs-db/api.html
- SatNOGS DB licença: https://db.satnogs.org/about/
- CelesTrak OMM/GP: https://celestrak.org/NORAD/documentation/gp-data-formats.php
- CelesTrak Usage Policy: https://celestrak.org/usage-policy.php
- Wikimedia Commons metadata: https://www.mediawiki.org/wiki/Extension:CommonsMetadata

## Regra de distribuição — QUATRO EXEs DIRETOS (a partir de v0.2.0)
- [x] Os instaladores Windows 7 x86 e Windows 11 x64 devem ser gerados e publicados como arquivos **`*-Setup.exe`**, disponíveis para download direto nos assets da Release e no README.
- [x] **Nunca compactar o instalador em ZIP** nem exigir que o usuário extraia arquivos para executá-lo.
- [x] **O portátil deve ser um único `*-Portable.exe`** via PyInstaller onefile, nunca ZIP a partir da v0.2.0.
- [ ] Nas próximas versões, validar no pipeline a existência dos dois assets `*-Setup.exe` independentes e rejeitar `*-Setup.zip`, `*-Installer.zip` ou equivalentes.

## Validação obrigatória antes de chamar versão estável
- [x] Criar repositório remoto GitHub `alexpmr/PT2VHF-Sat-Tool`.
- [x] Acesso ao GitHub App autorizado e código v0.1.2 publicado.
- [x] CI v0.1.2 compilou os quatro binários, porém sem teste real de inicialização; erro NumPy reportado pelo operador.
- [ ] Homologar Win7 SP1 x86/x64: dependências legadas, Visual C++/Universal CRT e carregamento do QtWebEngine; instalador e portátil.
- [ ] Homologar instalador e portátil no Windows 11 x64.
- [ ] Validar CAT TS-2000 físico, inclusive SA, FA, FB e MD nos VFOs apropriados.
- [ ] Validar desligamento de TRACE por CAT e interferência com configuração prévia do rádio.
- [ ] Verificar se o runtime QtWebEngine carrega Leaflet + tiles OSM no Windows 10/11.
- [ ] Confirmar dados de cada modo/transponder no SatNOGS e autorizações de TX antes de operar.
- [ ] Validar geolocalização conforme permissões do Windows.

## Evolução v0.1.3 — Download, versão e catálogo de satélites
- [x] README GitHub: downloads Win7/Win11, Setup/Portable, **antes da descrição**; links de publicação condicionados à release real.
- [x] Botão de versão na barra superior; comparação semântica com GitHub Releases, changelog e indicação de atualização disponível.
- [x] Verificação automática (padrão 15 minutos), configurável; notificação única por versão; suporte explícito a pré-lançamentos.
- [x] Seleção de asset exata pela distribuição instalada (Win7-x86/Win11-x64; Setup/Portable).
- [x] Download HTTPS com hash SHA-256 obrigatório da release; atualização bloqueada se o hash divergir.
- [x] Encerramento do Doppler e conexão CAT antes de disparar atualizador externo; versão portátil preserva `data/`; Setup usa instalador Inno.
- [x] Aba Satélites: lista dinâmica CelesTrak com nome, NORAD, inclinação, período, modos e frequências de transponders disponíveis no cache SatNOGS.
- [x] Visão detalhada da seleção com excentricidade, época e informações operacionais, sem confundir órbita catalogada com transmissor ativo.
- [ ] Publicar código e release v0.1.3 no repositório remoto, executar o CI e verificar quatro entregáveis Windows.
- [ ] Testar atualização de Setup e Portable em Win7 e Win11 reais, inclusive falha de checksum e conexão de rede.
- [ ] Homologar hardware TS-2000 real, segurança CAT, crash recovery e integridade dos dados portáteis.

## Evolução
- [ ] Controlar o modo TX SUB por CAT após confirmação do sequenciamento CAT específico TS-2000.
- [ ] Transponders com CTCSS por canal e alternância de tom TX.
- [ ] CAT simulador/replay com testes de integração para falha de COM, buffer incompleto, modo RX/TX.
- [ ] Ajuste de offset RX/TX por satélite e telemetria de AFC.
- [ ] Suporte a rotores Az/El (Hamlib/G-5500), com travas.
- [ ] Notificações de AOS/TCA/LOS e favoritos.
- [ ] Histórico, observações e integração com APRS Client (separada).
- [ ] Mapa offline com cartografia incluída para não depender de CDN.
- [x] Relação dos downloads no início do README (links condicionados à release).

## Correção v0.1.3 — NumPy
- [x] Importação testada dentro do EXE empacotado, com relatório JSON mesmo em versão windowed.
- [x] Versão do NumPy fixada por alvo (Win7 x86 / Win11 x64).
- [x] Release bloqueada em caso de falha no smoke test do EXE.
- [ ] Validar software em Windows 7 SP1 e Windows 11 reais e TS-2000.
