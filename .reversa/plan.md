# Plano de Exploração — PT2VHF SAT Tool

> Criado pelo Reversa em 2026-11-27
> Marque cada tarefa com ✅ quando concluída.
> Você pode editar este plano antes de iniciar: adicione, remova ou reordene tarefas conforme necessário.

---

## Fase 1: Reconhecimento 🔍

- [x] ✅ **Scout** — Mapeamento de estrutura de pastas e tecnologias
- [x] ✅ **Scout** — Análise de dependências e gerenciadores de pacotes
- [x] ✅ **Scout** — Identificação de entry points, CI/CD e configurações

## Decisão de organização das specs 🗂️

> Entre o Scout e o Arqueólogo, o Reversa pergunta como você quer organizar as specs (por módulo, caso de uso, endpoint, híbrida, por features ou customizada). A escolha fica persistida em `.reversa/config.toml` na seção `[specs]` e não será reperguntada em execuções futuras. Para reapresentar o menu, remova manualmente a seção.

## Fase 2: Escavação 🏗️

> O Reversa preenche esta seção com os módulos reais após o Scout concluir o reconhecimento.

- [x] ✅ **Arqueólogo** — Análise do módulo `orbita-e-passagens`
- [x] ✅ **Arqueólogo** — Análise do módulo `catalogo-e-tle`
- [x] ✅ **Arqueólogo** — Análise do módulo `cat-e-doppler`
- [x] ✅ **Arqueólogo** — Análise do módulo `rotor`
- [x] ✅ **Arqueólogo** — Análise do módulo `display-lcd`
- [x] ✅ **Arqueólogo** — Análise do módulo `sdr-e-telemetria`
- [x] ✅ **Arqueólogo** — Análise do módulo `sstv`
- [x] ✅ **Arqueólogo** — Análise do módulo `atualizacao-ota`
- [x] ✅ **Arqueólogo** — Análise do módulo `painel-web`
- [x] ✅ **Arqueólogo** — Análise do módulo `interface-e-idiomas`
- [x] ✅ **Arqueólogo** — Análise do módulo `diagnostico`
- [x] ✅ **Arqueólogo** — Análise do módulo `build-e-publicacao`

## Fase 3: Interpretação 🧠

- [x] ✅ **Detetive** — Arqueologia Git e ADRs retroativos
- [x] ✅ **Detetive** — Regras de negócio implícitas e máquinas de estado
- [x] ✅ **Detetive** — Matriz de permissões (RBAC/ACL)
- [x] ✅ **Arquiteto** — Diagramas C4 (Contexto, Containers, Componentes)
- [x] ✅ **Arquiteto** — ERD completo e integrações externas
- [x] ✅ **Arquiteto** — Spec Impact Matrix

## Fase 4: Geração 📝

- [x] ✅ **Redator** — Specs SDD por componente
- [x] ✅ **Redator** — OpenAPI (se aplicável)
- [x] ✅ **Redator** — User Stories (se aplicável)
- [x] ✅ **Redator** — Code/Spec Matrix

## Fase 5: Revisão ✅

- [x] ✅ **Revisor** — Revisão cruzada de specs
- [x] ✅ **Revisor** — Resolução de lacunas com o usuário
- [x] ✅ **Revisor** — Relatório de confiança final

---

## Agentes Independentes

> Execute estes agentes quando os recursos estiverem disponíveis — podem rodar em qualquer fase.

- [~] **Visor** — Análise de interface via screenshots — não se aplica nesta rodada: sem capturas de tela
- [~] **Data Master** — Análise completa do banco de dados — não se aplica: o app não usa banco de dados
- [~] **Design System** — Extração de tokens de design — não se aplica: temas em `appearance.py` já documentados
- [~] **Tracer** — Análise dinâmica (requer sistema acessível) — não se aplica: exige rádio/rotor/SDR reais

---

## Próximo passo

Após o Time de Descoberta concluir e o `_reversa_sdd/` estar populado, você pode disparar um dos fluxos seguintes:

- `/reversa-migrate`: orquestrador do **Time de Migração** (Paradigm Advisor → Curator → Strategist → Designer → Screen Translator → Inspector). Gera as specs do sistema novo. Saída em `_reversa_sdd/migration/` e `_reversa_sdd/screens/`.
- `/reversa-reconstructor`: gera plano bottom-up para reimplementar o software a partir das specs do legado (uma tarefa por sessão).
