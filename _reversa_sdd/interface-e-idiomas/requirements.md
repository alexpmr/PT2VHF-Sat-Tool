# Interface e idiomas

## Visão Geral
Janela principal do SAT Tool (PySide6/PySide2): instância única, abertura com splash, temporizadores do ciclo
de operação, 10 idiomas, temas, escala da interface, medidor de CPU/RAM e a configuração persistente em
`settings.json` com migrações "uma vez". 🟢

## Responsabilidades
- Criar o mutex `PT2VHF_Sat_Tool_Running` (para o instalador saber que o app está aberto) e mostrar a abertura de 10 s "Powered by www.PT2VHF.com". 🟢
- Orquestrar temporizadores (`tick` 1 s, `cat_live_tick` 250 ms, heartbeat 30 s, catálogo aos 1,5 s, versão aos 12 s). 🟢
- Executar trabalho pesado em segundo plano (`background`). 🟢
- Traduzir a interface em tempo real (10 idiomas). 🟢
- Aplicar temas, escala e dimensionamento de formulários. 🟢
- Carregar, migrar e gravar `settings.json`. 🟢

## Regras de Negócio
- O mutex `PT2VHF_Sat_Tool_Running` só sinaliza ao instalador/OTA que o app está aberto; o app **não** impede uma segunda instância. 🟢 [Revisão] `app.py: _single_instance_mutex`, `main`
- Idioma padrão = idioma do sistema. 🟢
- Escala 80–100 % definida antes da `QApplication`. 🟢
- Um único binding Qt por build (PySide6 ou PySide2 no Win7). 🟢
- Migrações com flags `*_migrated` rodam uma vez (ADR 004). 🟢
- `settings.json` ilegível não pode impedir o programa de abrir (hoje impede: A4). 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Sinalizar ao instalador que o app está aberto (mutex) | Must | Setup pede para fechar o app |
| RF-02 | Configuração persistente com migrações | Must | Valores do usuário preservados |
| RF-03 | Recuperar de `settings.json` corrompido | Must | Abre com padrões e guarda cópia do arquivo ruim |
| RF-04 | 10 idiomas com troca imediata | Should | Todos os textos mudam sem reiniciar |
| RF-05 | Temas e checagem WCAG | Should | Contraste mínimo atendido |
| RF-06 | Escala 80–100 % | Should | Aplicada na próxima abertura |
| RF-07 | Medidor de CPU/RAM | Could | Atualiza a cada segundo |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | Rede/serial fora da thread da GUI | `MainWindow.background` (ADR 002) | 🟢 |
| Robustez | Leitura de configuração tolerante a falha | `config.py: Config.__init__` | 🟢 (A4 pendente) |
| Acessibilidade | Tema de alto contraste e checagem WCAG | `appearance.py` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um settings.json com JSON quebrado
Quando o programa abre
Então abre com os padrões, guarda o arquivo ruim como cópia e avisa no log

Dado o sistema em espanhol
Quando o programa abre pela primeira vez
Então a interface está em espanhol

Dado o programa aberto
Quando o instalador de uma versão nova roda
Então detecta o app aberto pelo mutex
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Configuração e mutex | Must | Base de tudo |
| Idiomas, temas, escala | Should | Público internacional |
| Medidor | Could | Diagnóstico |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sat_tool/app.py` | `MainWindow`, `background`, `Events`, temporizadores | 🟢 |
| `sat_tool/config.py` | `Config`, `DEFAULTS`, migrações | 🟢 |
| `sat_tool/i18n.py`, `i18n_runtime.py`, `locales/` | traduções | 🟢 |
| `sat_tool/appearance.py`, `form_sizing.py`, `ui_scale.py`, `resource_meter.py`, `qt_compat.py`, `frequency.py`, `profile.py` | aparência e utilidades | 🟢 |
