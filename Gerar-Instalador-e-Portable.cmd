@echo off
setlocal
cd /d "%~dp0"
echo PT2VHF Sat Tool - Construir instalador e portable
choice /c 71 /n /m "Digite 7 (Win7 x86) ou 1 (Win11 x64): "
if errorlevel 2 (
  set TARGET=Win11-x64
) else (
  set TARGET=Win7-x86
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Build-Windows.ps1" -Target %TARGET%
if errorlevel 1 (
  echo ERRO: compilacao nao concluida.
) else (
  echo Consulte os dois arquivos em dist.
)
pause
