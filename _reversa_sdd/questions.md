# Perguntas para validação — PT2VHF SAT Tool

> Reversa (Revisor), 27/11/2026. Modo de resposta: arquivo. Preencha **Resposta** e avise com `reversa`.

## Pergunta 1

**Contexto:** `sat_tool/rotor.py: plan_pass/to_rotor`; leitura AZ 140° EL 175° no G-5400B.
**Spec afetada:** `_reversa_sdd/rotor/requirements.md`, `design.md`
**Pergunta:** Quando o rotor leu AZ 140° EL 175°, para onde a antena apontava fisicamente? O app trata como flip (320° / 5°).
**Impacto:** Confirma ou corrige a conversão de leituras com elevação acima de 90°.

**Resposta:** <!-- preencha aqui -->

## Pergunta 2

**Contexto:** `profile.freq_band` (UHF 430–450 MHz) e `transponder.BANDS` (UHF 420–450 MHz).
**Spec afetada:** `_reversa_sdd/orbita-e-passagens/requirements.md`
**Pergunta:** A faixa UHF mais larga (desde 420 MHz) no CAT é intencional?
**Impacto:** Se não for, alinhar as duas faixas.

**Resposta:** <!-- preencha aqui -->

## Pergunta 3

**Contexto:** `app.py: main` cria o mutex mas não impede uma segunda instância.
**Spec afetada:** `_reversa_sdd/interface-e-idiomas/requirements.md`
**Pergunta:** Abrir o programa duas vezes deve ser bloqueado (trazendo a primeira janela à frente)?
**Impacto:** Duas instâncias disputam portas seriais, o SDR e a porta 8094 do painel web.

**Resposta:** <!-- preencha aqui -->

## Pergunta 4

**Contexto:** `.github/workflows/windows.yml` só constrói `Win11-x64`; o ramo Win7-x86/PySide2 ainda existe no código.
**Spec afetada:** `_reversa_sdd/build-e-publicacao/design.md`
**Pergunta:** A edição Windows 7 ainda é suportada?
**Impacto:** Se não for, o código PySide2 pode ser aposentado; se for, falta build no CI.

**Resposta:** <!-- preencha aqui -->
