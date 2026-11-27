# C4 Containers — PT2VHF SAT Tool

> Reversa (Arquiteto), 27/11/2026. O sistema é um único processo desktop; os "containers" abaixo são as
> unidades executáveis e de dados dentro da instalação. 🟢 CONFIRMADO.

```mermaid
C4Container
title PT2VHF SAT Tool — Containers
Person(op, "Operador")
System_Boundary(app, "Instalação do SAT Tool") {
  Container(gui, "Aplicativo desktop", "Python 3.11, PySide6", "MainWindow, laços Auto CAT, rotor, alertas")
  Container(workers, "Threads de trabalho", "threading + sinais Qt", "Rede, serial, SDR, DSP, telemetria")
  Container(web, "Servidor web local", "ThreadingHTTPServer :8094", "Status JSON, mapa, controles com PIN")
  Container(ddeSrv, "Servidor DDE", "ctypes/Win32", "Doppler para clientes DDE (só Windows)")
  ContainerDb(cfg, "settings.json", "JSON no perfil do usuário", "Configuração e flags de migração")
  ContainerDb(cache, "Cache de dados", "Arquivos OMM/JSON, logs, WAV, PNG", "TLE (2 h), transmissores, gravações, diário")
  Container(installer, "Instaladores", "Inno Setup / .deb / PyInstaller", "Empacotamento; wdi-simple para driver RTL")
}
Rel(op, gui, "Usa")
Rel(gui, workers, "MainWindow.background(key, fn)")
Rel(workers, gui, "Events.result/failure/progress/record")
Rel(gui, web, "Publica estado")
Rel(gui, ddeSrv, "Publica Doppler")
Rel(gui, cfg, "Lê/grava")
Rel(workers, cache, "Lê/grava")
```
