# Identidade visual — PT2VHF Sat Tool (proposta inicial)

## Direção de marca
Universo radioamador, satélites, órbitas e comunicação RF, com aparência de software técnico e missão crítica. A marca **não representa** Kenwood, AMSAT, SatNOGS ou CelesTrak. Baseada no tema escuro e ciano do aplicativo.

## Ativos vetoriais (fontes)
- `assets/branding/app-icon.svg`: símbolo quadrado, utilizável como fonte mestre para recursos PNG e ICO.
- `assets/branding/logo-horizontal.svg`: assinatura horizontal do nome.
- As peças são **propostas em SVG**, sem aprovação de identidade definitiva. Para o Windows, converter/exportar versões rasterizadas e validar a leitura nos tamanhos pequenos.

## Paleta
| Uso | Hex |
| --- | --- |
| Fundo primário | `#081323` |
| Superfície/painel | `#0B1526` |
| Superfície elevada | `#14283D` |
| Ciano de marca | `#22D2EE` |
| Azul de marca | `#4696FF` |
| Verde-água | `#64DED2` |
| Texto principal | `#E8EDF5` |
| Status conectado/ok | `#69E3BC` |
| Atenção/pendente | `#F0C186` |
| Erro/indisponível | `#E98B81` |

## Tipografia
Segoe UI / Arial ou fonte de sistema equivalente; títulos em negrito; frequências e timestamps em tabular/monoespaçada legível. Legibilidade de RX/TX, modo, CAT e segurança prevalece sobre a estética.

## Aplicação planejada
1. `QApplication.setWindowIcon` e `QMainWindow.setWindowIcon`, menus, diálogos, pop-ups e aba Sobre.
2. `PyInstaller --icon` para Setup e Portable no Windows 7 e Windows 11, incluindo taskbar/Alt+Tab e atalhos.
3. `Inno Setup SetupIconFile`, Add/Remove Programs, desinstalador e ícones de tarefas.
4. Splash não bloqueante, telas de onboarding/primeira configuração, cabeçalho da janela.
5. README logo antes dos downloads, release notes, screenshots, documentação e manuais.
6. Variante clara, monocromática e tamanhos 16 a 1024 px; analisar contraste WCAG para textos informativos e não depender apenas de cor para estados CAT.

## Controle de mudança
A identidade visual não modifica o identificador de instalação, chaves de configuração, pasta de dados, indicativo ou comandos CAT. Aplicação em código, artefatos finais e homologação Win7/Win11 permanecem abertas no BACKLOG.md.
