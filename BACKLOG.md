# PT2VHF Sat Tool — backlog

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

## Regra de distribuição — instaladores EXE diretos (todas as releases)
- [x] Os instaladores Windows 7 x86 e Windows 11 x64 devem ser gerados e publicados como arquivos **`*-Setup.exe`**, disponíveis para download direto nos assets da Release e no README.
- [x] **Nunca compactar o instalador em ZIP** nem exigir que o usuário extraia arquivos para executá-lo.
- [x] O pacote **portátil permanece `*-Portable.zip`**, pois contém o executável e suas dependências em diretórios.
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
