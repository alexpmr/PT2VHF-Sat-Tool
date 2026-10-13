# PT2VHF Sat Tool — backlog

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
