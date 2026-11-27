# Build e publicação

## Visão Geral
Gera e publica cada versão do SAT Tool: testes, instaladores Windows (Setup/Portable), pacotes Linux
(.tar.gz/.deb) e macOS ARM64, validação de SHA-256 e publicação no site www.pt2vhf.com (downloads e
`updates.json`). 🟢

## Responsabilidades
- Rodar a suíte de testes no CI. 🟢
- Empacotar com PyInstaller, Inno Setup e `build_deb.py`. 🟢
- Validar autoteste no binário e no `.deb` instalado. 🟢
- Criar a GitHub Release (só origem dos arquivos). 🟢
- Publicar em `downloads/sat-tool/` e `updates.json` do repositório do site (Hostinger). 🟢

## Regras de Negócio
- Versão nova só com pedido explícito do mantenedor (R22). 🟢
- "Gerar versão nova" = resolver o BACKLOG, release completa, publicar no site, clientes perceberem via OTA (R22). 🟢
- Commits só de documentação/backlog levam `[skip ci]`. 🟢
- Downloads oficiais só por www.pt2vhf.com; GitLab aposentado. 🟢
- Arquivos > 100 MiB vão em partes (`write_parts`) e o `download.php` remonta e conta. 🟢
- Versão fixada em `sat_tool/__init__.py`, `windows.yml`, `installer/setup.iss`, `scripts/Build-Windows.ps1` e testes. 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Push na `main` gera todos os pacotes | Must | Jobs verdes |
| RF-02 | `updates.json` com versão, tamanho e SHA-256 | Must | Hash confere com o arquivo publicado |
| RF-03 | Publicação no site | Must | `/sat` e `update.php?product=sat` mostram a versão |
| RF-04 | Coerência de versão em todos os arquivos | Must | CI falha se divergir |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Integridade | SHA-256 de cada pacote | `scripts/publish_sat_to_site.py` | 🟢 |
| Limite do Git | Partes < 100 MiB | `write_parts` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o mantenedor pediu versão nova e o PR foi aprovado
Quando o merge na main acontece
Então o CI publica os pacotes no site e o OTA oferece a versão aos clientes

Dado um commit só de documentação com [skip ci]
Quando é enviado
Então nenhum build é disparado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Pipeline e publicação | Must | Único canal de distribuição |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `.github/workflows/windows.yml` | jobs de teste, build, release, `publish_site` | 🟢 |
| `scripts/Build-Windows.ps1`, `build_deb.py`, `build_brand_assets.py`, `publish_sat_to_site.py` | build e publicação | 🟢 |
| `installer/setup.iss` | instalador Inno Setup | 🟢 |
