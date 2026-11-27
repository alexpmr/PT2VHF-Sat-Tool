# Catálogo e TLE

## Visão Geral
Mantém o catálogo local de satélites: baixa elementos orbitais (CelesTrak, AMSAT, R4UAB, SatNOGS), baixa os
transmissores do SatNOGS, mescla fontes, guarda cache e controla quais satélites o operador acompanha. 🟢

## Responsabilidades
- Baixar e cachear grupos OMM da CelesTrak e listas TLE extras. 🟢
- Buscar satélites padrão fora dos grupos por NORAD, com reserva no SatNOGS. 🟢
- Mesclar registros do mesmo NORAD vindos de várias fontes. 🟢
- Baixar todos os transmissores do SatNOGS numa consulta paginada. 🟢
- Manter a seleção do operador e os satélites padrão. 🟢
- Ordenar transponders e mostrar informações do satélite (Wikipedia/foto). 🟢

## Regras de Negócio
- CelesTrak consultada no máximo a cada 2 h por grupo; falha de rede usa o cache (R11, ADR 006). 🟢
- Satélite padrão sem órbita na CelesTrak usa o TLE do SatNOGS (R12). 🟢
- Transmissores numa única consulta paginada (até 200 páginas), sem sair de `db.satnogs.org` (R13, ADR 007). 🟢
- Elementos de um NORAD só são trocados se o `EPOCH` for igual ou mais novo. 🟢
- Linha TLE inválida é pulada sem derrubar a fonte; catálogo Alpha-5 aceito (`A0084` → 100084). 🟢
- Padrões: ISS, SO-50, IO-86, AO-7, FO-29, RS-44, SONATE-2, LUČA-1 e HADES-E2 por nome (R9). 🟢
- Satélites padrão entram uma vez por instalação; desmarcar vale (R9, ADR 004). 🟢
- SO-50 sempre com o par AMSAT 145,850 ↑ / 436,795 ↓ FM (R8). 🟢
- Seleção manual não depende do cache de frequências (R10). 🟢
- Dados do SatNOGS são "publicados, não confirmados" (R6). 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Atualizar grupos da CelesTrak respeitando cache de 2 h | Must | Segunda atualização em < 2 h não faz requisição |
| RF-02 | Ler TLE 2LE/3LE e Alpha-5 | Must | Linha ruim é ignorada; resto carrega |
| RF-03 | Mesclar fontes por NORAD com `CATEGORIES` e `ALT_NAMES` | Must | Busca por nome alternativo encontra o satélite |
| RF-04 | Buscar padrões por NORAD com reserva SatNOGS | Must | LUČA-1 e HADES-E2 aparecem mesmo fora da CelesTrak |
| RF-05 | Baixar todos os transmissores numa consulta | Must | `tx_<norad>.json` só para quem tem transmissor |
| RF-06 | Selecionar e desselecionar satélites | Must | Seleção persiste em `settings.json` |
| RF-07 | Priorizar transponders (SO-50 fixo) | Should | SO-50 mostra 145,850/436,795 primeiro |
| RF-08 | Mostrar resumo e foto do satélite | Could | Abre sem rede com mensagem amigável |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Cortesia de rede | Cache de 2 h por grupo | `catalog.py` | 🟢 |
| Disponibilidade | Falha de rede volta ao cache | `catalog.py` | 🟢 |
| Performance | Catálogo em segundo plano 1,5 s após abrir | `app.py` | 🟢 |
| Identificação | User-Agent `PT2VHF-Sat-Tool/1.3.0` desatualizado | `catalog.py: HEADERS` | 🟢 (achado A6) |

## Critérios de Aceitação

```gherkin
Dado que o grupo amateur foi baixado há 30 minutos
Quando o operador pede atualização
Então o programa usa o cache e não consulta a CelesTrak

Dado que a CelesTrak está fora do ar
Quando o catálogo é atualizado
Então o último cache é usado e o operador é avisado

Dado uma lista TLE com uma linha corrompida
Quando a fonte é lida
Então só aquela entrada é descartada

Dado que o operador desmarcou o AO-7
Quando o programa abre de novo
Então o AO-7 continua desmarcado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Download, cache e mescla de OMM | Must | Sem órbita não há passagens |
| Transmissores SatNOGS | Must | Base do Auto CAT |
| Seleção e padrões | Must | Fluxo diário |
| Informações e foto | Could | Complementar |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/catalog.py` | `merge_orbits`, `refresh_catnr_omm`, `refresh_all_transmitters`, `parse_tle`, `tle_to_omm`, `_satnogs_tle_omm`, `HEADERS` | 🟢 |
| `sat_tool/selection.py` | `change_selection` | 🟢 |
| `sat_tool/transponder.py` | `prioritized_transponders`, `BANDS` | 🟢 |
| `sat_tool/profile.py` | `capability`, `freq_band`, `CANDIDATES` | 🟢 |
| `sat_tool/config.py` | `DEFAULT_SATELLITES`, `DEFAULT_SATELLITE_NAMES` | 🟢 |
| `sat_tool/satinfo.py`, `satellite_info.py`, `media.py` | informações e foto | 🟢 |
