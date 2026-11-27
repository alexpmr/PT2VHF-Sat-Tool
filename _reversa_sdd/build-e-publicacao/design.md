# Build e publicação, Design Técnico

## Interface
Gatilho: push na `main` (exceto `[skip ci]`). Saídas: GitHub Release (pré-lançamento), commit no repositório
do site com `downloads/sat-tool/*` e `updates.json`. 🟢

## Fluxo Principal
1. Testes (pytest 8.3.5, Python 3.11). 🟢
2. Build Windows (PyInstaller 6.13, Inno Setup, libwdi `wdi-simple.exe`), Linux (.tar.gz/.deb), macOS ARM64. 🟢
3. Autoteste nos binários. 🟢
4. Release no GitHub. 🟢
5. `publish_sat_to_site.py` copia os pacotes (em partes se preciso), calcula tamanho/SHA-256 e atualiza `updates.json`. 🟢
6. Push no site → Hostinger publica. 🟢

## Fluxos Alternativos
- **Falha em qualquer job:** nada é publicado. 🟡
- **Win7-x86:** ramo condicional sem build ativo (D6). 🟡

## Dependências
- GitHub Actions, token para o repositório do site, Hostinger. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| GitHub Release só como origem | CLAUDE.md, `windows.yml` | 🟢 |
| Site como fonte única de downloads | ADR 003 | 🟢 |

## Estado Interno
Nenhum; tudo derivado do commit. 🟢

## Observabilidade
Logs do Actions; verificação manual de `/sat`, `/updates.json` e `update.php?product=sat`. 🟢

## Riscos e Lacunas
- 🟢 Versão repetida em vários arquivos: esquecimento quebra o CI.
- 🟡 Implantação Hostinger confirmada só pela verificação do endereço público.
