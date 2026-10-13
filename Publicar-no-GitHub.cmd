@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Publicar-no-GitHub.ps1"
if errorlevel 1 (
  echo.
  echo PUBLICACAO NAO CONCLUIDA. Veja o erro acima.
)
echo.
pause
