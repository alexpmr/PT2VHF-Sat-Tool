# Interface e idiomas, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `MainWindow.background` | `(key, fn)` | — | uma thread por chave |
| `Events` | sinais `result`, `failure`, `progress`, `record` | — | ponte para a GUI |
| `Config.__init__` | `(path)` | — | carrega e migra |
| `Config.save` | `()` | — | grava `settings.json` |
| `i18n_runtime.PolishTranslator` | `(app)` | — | intercepta setters do Qt |

## Fluxo Principal
1. `ui_scale` define `QT_SCALE_FACTOR`; cria `QApplication`; verifica o mutex. 🟢
2. Carrega `Config` (migrações), idioma e tema. 🟢
3. Mostra a abertura de 10 s dentro da janela. 🟢
4. Liga temporizadores; aos 1,5 s catálogo; aos 12 s versão. 🟢

## Fluxos Alternativos
- **Segunda instância:** não é bloqueada; duas janelas disputariam portas seriais e a porta 8094. 🟢 [Revisão]
- **Configuração corrompida:** hoje exceção na abertura (A4). 🟢

## Dependências
- PySide6 6.7–6.9 (PySide2 5.15 no Win7), psutil. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Tradução por interceptação de setters | `i18n_runtime.py` | 🟢 |
| Temas por transformação da folha de estilo | `appearance.py` | 🟢 |
| `qt_compat` como camada única | `qt_compat.py` | 🟢 |

## Estado Interno
`settings.json`, estado da janela, temporizadores, chaves de trabalho ativas. 🟢

## Observabilidade
`MainWindow.log` e sinal `record`. 🟢

## Riscos e Lacunas
- 🟢 D1: `app.py` com 5.225 linhas e imports circulares.
- 🟢 A4: JSON quebrado impede a abertura.
