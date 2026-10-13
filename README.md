<p align="center"><img src="assets/branding/logo-horizontal.svg" alt="PT2VHF Sat Tool" width="560"></p>

# PT2VHF Sat Tool

## Downloads — instaladores e portáteis

**Versão v0.2.0 — Windows 7 SP1 e Windows 11.** Todos os quatro downloads são arquivos `.exe`. A versão portátil é um **EXE único**, sem ZIP ou instalador; os links tornam-se válidos depois do sucesso da compilação e publicação.

| Windows | Instalável | Portátil |
| --- | --- | --- |
| **Windows 7 SP1** (x86; executável de 32 bits também para Win7 x64) | [Instalador Win7 x86](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v0.2.0/PT2VHF-Sat-Tool-v0.2.0-Win7-x86-Setup.exe) | [Portable Win7 x86](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v0.2.0/PT2VHF-Sat-Tool-v0.2.0-Win7-x86-Portable.exe) |
| **Windows 11** (x64) | [Instalador Win11 x64](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v0.2.0/PT2VHF-Sat-Tool-v0.2.0-Win11-x64-Setup.exe) | [Portable Win11 x64](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v0.2.0/PT2VHF-Sat-Tool-v0.2.0-Win11-x64-Portable.exe) |

**Formato dos downloads:** tanto instaladores quanto portáteis são entregues diretamente como arquivos **`.exe`**. O portátil inclui as dependências dentro do mesmo EXE (PyInstaller onefile) e não requer descompactação.

**[Todas as releases](https://github.com/alexpmr/PT2VHF-Sat-Tool/releases)** · **[Acompanhar compilação](https://github.com/alexpmr/PT2VHF-Sat-Tool/actions)**

- **Instalável:** instalação por usuário, atalho e desinstalação, atualização pelo aplicativo usando o Setup de sua edição.
- **Portátil:** execute diretamente `PT2VHF-Sat-Tool-v0.2.0-*-Portable.exe` (um único arquivo). Configurações ficam em `data/` ao lado do EXE, preservadas após atualizações.
- **Win7:** Python 3.8 x86 + PySide2/Qt5 + PyInstaller 5.13.2 (legado, precisa ser validado no Windows 7 real).
- **Win11:** Python 3.11 x64 + PySide6/Qt6 + PyInstaller 6.13.0.
- Arquivos SHA256 acompanham cada compilação. A versão Windows 7 é experimental; não confundir sucesso do CI com homologação em campo.

---

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

Aplicação independente para Windows, voltada ao rastreamento de satélites amadores e ao controle CAT do **Kenwood TS-2000** pela porta serial. **Versão 0.2.0 — MVP ainda sem homologação em TS-2000 físico.**

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

O repositório `alexpmr/PT2VHF-Sat-Tool` começou com `README.md` e `LICENSE` MIT. A publicação no `main` dispara a compilação e, somente após os autotestes dos EXEs, publica a release v0.2.0 com os quatro arquivos e respectivos checksums.

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



## Diagnóstico de inicialização (v0.2.0)

O build anterior apenas verificava a existência do EXE. Agora o GitHub Actions **executa os binários congelados**, verificando importação nativa do NumPy, BLAS, Skyfield, Qt e da aplicação. Se falhar, o pipeline bloqueia a release.

Se persistir erro ao abrir, na pasta do aplicativo execute:

```powershell
.\PT2VHF-Sat-Tool.exe --self-test "$env:TEMP\PT2VHF-Sat-Tool-diagnostics.json"
Get-Content "$env:TEMP\PT2VHF-Sat-Tool-diagnostics.json"
```

O JSON mostra o traceback e as versões usadas. O Win7 SP1 requer atualizações do sistema e runtime Visual C++/UCRT apropriados. Instalar Python ou NumPy no PC não corrige um aplicativo congelado. Não baixe DLLs de sites não oficiais. NumPy travado em 1.23.5 (Win7) e 1.26.4 (Win11); o teste no runner não substitui homologação no Windows real.
