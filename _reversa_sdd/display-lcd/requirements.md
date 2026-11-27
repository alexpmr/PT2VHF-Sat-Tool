# Display LCD

## Visão Geral
Mostra frequências, modo, contagem de AOS/LOS, S-meter e estado do CAT num display que imita o painel de
rádios conhecidos, destacável para outro monitor. Só exibe dados e emite sinais de botões. 🟢

## Responsabilidades
- Desenhar o display no tamanho físico da tela (pixels × devicePixelRatio). 🟢
- Oferecer estilos genéricos e de rádio (IC-706MKIIG, IC-7100, FT-897/857, IC-910H, FT-991A, IC-9700, FT-847, FT-817/818, TS-790, IC-705). 🟢
- Mostrar escopo/waterfall do RTL-SDR nos modelos com tela. 🟢
- Emitir sinais A/B, RX ONLY e MAIN↔SUB. 🟢
- Destacar para outra janela lembrando posição, monitor e tela cheia. 🟢

## Regras de Negócio
- O display nunca envia comandos ao rádio diretamente; só emite sinais para a GUI. 🟢
- Contagem regressiva de AOS/LOS em segmentos. 🟢
- Moldura com etiqueta do operador. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Renderizar `LcdState` em todos os estilos | Must | Nenhum estilo falha com estado vazio |
| RF-02 | Estilos de rádio com moldura | Should | Imagem nítida em DPR 1 e 2 |
| RF-03 | Escopo/waterfall nos modelos com tela | Could | Só em `SCOPE_MODELS` |
| RF-04 | Display destacável com estado lembrado | Should | Reabre no mesmo monitor |
| RF-05 | Teclas/sinais A/B, RX ONLY, MAIN↔SUB | Must | Sinal chega à GUI |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Qualidade visual | Desenho em resolução física | `lcd.py: LcdDisplay` | 🟢 |
| Desacoplamento | Display sem acesso ao CAT | `lcd.py` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o estilo IC-9700 e uma passagem em 3 minutos
Quando o display atualiza
Então mostra a contagem regressiva de AOS em segmentos

Dado o display destacado em um segundo monitor
Quando o programa é reaberto
Então o display volta ao mesmo monitor e modo de tela

Dado que o segundo monitor foi desconectado
Quando o programa abre
Então o display aparece no monitor principal
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Renderização e sinais | Must | Painel principal de operação |
| Estilos de rádio e destaque | Should | Preferência visual |
| Escopo | Could | Só com SDR |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/lcd.py` | `LcdState`, `_Style`, `_Matrix`, `_Seven`, `_Digital`, `LcdDisplay` | 🟢 |
| `sat_tool/lcd_radios.py` | `RADIO_MODELS`, `SCOPE_MODELS` | 🟢 |
| `sat_tool/lcd_bezel.py` | moldura | 🟢 |
| `sat_tool/display_window.py` | janela destacável | 🟢 |
