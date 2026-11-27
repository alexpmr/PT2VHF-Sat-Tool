# SSTV, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `Decoder.feed` | `(audio: np.ndarray)` | imagens concluídas | fluxo |
| `decode_audio` | `(audio, rate)` | `list[Image]` | lote |
| `encode` | `(rgb, mode_name="Robot 36", rate=48000, amplitude=0.8)` | áudio | `sstv.py:160` |

## Fluxo Principal
1. O painel recebe áudio do SDR ou da placa de som e chama `Decoder.feed`. 🟢
2. VIS define o modo; cada linha é sincronizada e convertida (YCC/RGB). 🟢
3. Ao fim, `Image` é salva com carimbo. 🟢

## Fluxos Alternativos
- **VIS perdido:** 🟡 comportamento de recuperação não confirmado.
- **TX:** `encode` → tocar na saída escolhida; VOX aciona o rádio. 🟢

## Dependências
- numpy, QtMultimedia. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Modos declarados em tabela (`_martin`, `_scottie`, `_pd`) | `sstv.py:56`–`:66` | 🟢 |

## Estado Interno
Buffer de áudio, modo atual, linha em decodificação. 🟢

## Observabilidade
Mensagens no painel. 🟡

## Riscos e Lacunas
- 🟡 SSTV sem teste em hardware real (memória do projeto).
