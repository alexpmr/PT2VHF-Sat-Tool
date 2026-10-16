# Compila instalador e portatil com as dependencias do alvo na maquina Windows.
# Executar no Windows 10/11 com Python Launcher, Inno Setup 6 e Internet.
param([ValidateSet('Win7-x86','Win11-x64')][string]$Target = 'Win11-x64')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$Version = '1.3.11'
if ($Target -eq 'Win7-x86') {
  $PythonSelector = '-3.8-32'
  $Deps = 'requirements-win7.txt'
  $PyInstaller = '5.13.2'
  $Minimum = '6.1sp1'
  $Arch = 'x86compatible'
  $Bits = '32'
} else {
  $PythonSelector = '-3.11-64'
  $Deps = 'requirements-win11.txt'
  $PyInstaller = '6.13.0'
  $Minimum = '10.0.17763'
  $Arch = 'x64compatible'
  $Bits = '64'
}
function Invoke-Checked([string]$Description, [string]$File, [string[]]$Arguments) {
  Write-Host "[BUILD] $Description" -ForegroundColor Cyan
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Description falhou (exit $LASTEXITCODE)" }
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python Launcher (py.exe) nao instalado.' }
$Venv = Join-Path (Get-Location) ('.build-venv-' + $Target)
Invoke-Checked 'Criando Python virtual' 'py' @($PythonSelector,'-m','venv',$Venv)
$Exe = Join-Path $Venv 'Scripts\python.exe'
Invoke-Checked 'Instalando dependencias' $Exe @('-m','pip','install','-r',$Deps,'pyinstaller=='+$PyInstaller,'pytest==7.4.4','Pillow==10.4.0')
Invoke-Checked 'Auditando dependencias' $Exe @('-m','pip','check')
Invoke-Checked 'Executando testes unitarios' $Exe @('-m','pytest','-q','tests')
Invoke-Checked 'Conferindo arquitetura' $Exe @('-c',"import struct; assert str(struct.calcsize('P') * 8) == '$Bits'")
Invoke-Checked 'Conferindo binding Qt' $Exe @('-c',"from sat_tool.qt_compat import QT_BINDING; print(QT_BINDING)")
Invoke-Checked 'Gerando icones oficiais' $Exe @('scripts/build_brand_assets.py')
$AppDir = 'dist/PT2VHF-Sat-Tool'
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
Invoke-Checked 'Compilando executavel Windows' $Exe @('-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','PT2VHF-Sat-Tool','--icon','assets/branding/app-icon.ico','--add-data','sat_tool/map.html;sat_tool','--add-data','assets/branding/icon-256.png;assets/branding','--add-data','scripts/apply-update.ps1;scripts','--hidden-import','sat_tool.app','--hidden-import','sat_tool.cat','--collect-all','skyfield','--collect-binaries','numpy','run.py')
$Bin = Join-Path $AppDir 'PT2VHF-Sat-Tool.exe'
if (-not (Test-Path $Bin)) { throw "Arquivo ausente: $Bin" }
$Report = Join-Path (Resolve-Path 'dist').Path ("sattool-selftest-$Target.json")
$Expected = if ($Target -eq 'Win7-x86') { 'PySide2' } else { 'PySide6' }
$Result = Start-Process -FilePath (Resolve-Path $Bin).Path -ArgumentList @('--self-test',('"' + $Report + '"'),$Expected) -PassThru -Wait
if (-not (Test-Path $Report)) { throw "EXE nao gerou relatorio: $($Result.ExitCode)" }
$Smoke = Get-Content $Report -Raw | ConvertFrom-Json
if ($Result.ExitCode -ne 0 -or $Smoke.status -ne 'passed' -or -not $Smoke.frozen) { throw "EXE falhou: $(Get-Content $Report -Raw)" }
$Portable = "dist/PT2VHF-Sat-Tool-v$Version-$Target-Portable.exe"
Invoke-Checked 'Compilando portatil onefile EXE' $Exe @('-m','PyInstaller','--noconfirm','--clean','--windowed','--onefile','--name',"PT2VHF-Sat-Tool-v$Version-$Target-Portable",'--icon','assets/branding/app-icon.ico','--add-data','sat_tool/map.html;sat_tool','--add-data','assets/branding/icon-256.png;assets/branding','--add-data','scripts/apply-update.ps1;scripts','--hidden-import','sat_tool.app','--hidden-import','sat_tool.cat','--collect-all','skyfield','--collect-binaries','numpy','run.py')
if (-not (Test-Path $Portable)) { throw "Portable EXE ausente: $Portable" }
$PortableReport = Join-Path (Resolve-Path 'dist').Path "portable-selftest-$Target.json"
$PResult = Start-Process -FilePath (Resolve-Path $Portable).Path -ArgumentList @('--self-test',('"' + $PortableReport + '"'),$Expected) -PassThru -Wait
if (-not (Test-Path $PortableReport)) { throw "Portable EXE nao gerou relatorio (exit $($PResult.ExitCode))" }
$PData = Get-Content $PortableReport -Raw | ConvertFrom-Json
if ($PResult.ExitCode -ne 0 -or $PData.status -ne 'passed') { throw "Falha portable: $(Get-Content $PortableReport -Raw)" }
$ISCC = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (-not (Test-Path $ISCC)) { throw 'Inno Setup 6 nao encontrado: https://jrsoftware.org/isinfo.php' }
Invoke-Checked 'Compilando instalador' $ISCC @("/DBuildFlavor=$Target","/DMinTarget=$Minimum","/DTargetArch=$Arch",'installer/setup.iss')
$Installer = "dist/PT2VHF-Sat-Tool-v$Version-$Target-Setup.exe"
if (-not (Test-Path $Installer)) { throw "Instalador ausente: $Installer" }
$Checks = @($Portable,$Installer) | ForEach-Object {
  $sum=(Get-FileHash $_ -Algorithm SHA256).Hash.ToLowerInvariant()
  "$sum  $(Split-Path $_ -Leaf)"
}
$Checks | Set-Content "dist/PT2VHF-Sat-Tool-v$Version-$Target-SHA256.txt" -Encoding Ascii
Write-Host "ENTREGUES: $Portable e $Installer" -ForegroundColor Green
Write-Host 'A compatibilidade final exige teste no Windows alvo e TS-2000 fisico.' -ForegroundColor Yellow
