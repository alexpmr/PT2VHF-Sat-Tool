# SSTV

## Visão Geral
Decodifica imagens SSTV recebidas (por exemplo da ISS) a partir do áudio do SDR ou da placa de som, e gera o
áudio SSTV para transmissão pelo VOX do rádio. 🟢

## Responsabilidades
- Identificar o modo pelo cabeçalho VIS. 🟢
- Decodificar em fluxo com sincronismo, correção de inclinação e de desvio de tom. 🟢
- Salvar imagens automaticamente com carimbo. 🟢
- Codificar imagem em áudio e tocar na saída escolhida. 🟢

## Regras de Negócio
- Modos: Robot 36/72, Martin M1/M2, Scottie S1/S2/DX, PD 50/90/120/160/180/240/290. 🟢
- Desvio de tom medido no 1900 Hz do cabeçalho. 🟢
- TX de SSTV é a única transmissão; o programa não aciona PTT, usa o VOX (R5). 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Decodificar áudio em fluxo | Must | Imagem codificada e decodificada é reconhecível |
| RF-02 | Detectar modo por VIS | Must | Modo correto em todos os modos suportados |
| RF-03 | Salvar imagens com carimbo | Should | Arquivo PNG criado |
| RF-04 | Codificar e tocar SSTV | Could | WAV gerado com cabeçalho VIS |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Tolerância | Correção de inclinação e de desvio de tom | `sstv.py: Decoder` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um áudio Robot 36 gerado pelo próprio codificador
Quando é decodificado
Então a imagem resultante corresponde à original

Dado um áudio com desvio de 50 Hz
Quando é decodificado
Então o desvio é compensado pelo tom de 1900 Hz
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Decodificação | Must | Uso em eventos ARISS |
| TX | Could | Sem teste em hardware real |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/sstv.py` | `Mode`, `Decoder`, `Image`, `encode`, `decode_audio`, `vis_header`, `write_wav`, `read_wav` | 🟢 |
| `sat_tool/sstv_panel.py` | painel | 🟢 |
