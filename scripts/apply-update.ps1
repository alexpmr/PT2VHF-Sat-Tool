# PT2VHF Sat Tool: external updater; called only after verified SHA-256 + approval.
# Windows PowerShell 2 compatible (Win7 SP1). Never delete portable data/.
param(
    [int]$WaitPid,
    [string]$Package,
    [string]$Destination,
    [string]$Executable,
    [ValidateSet('Portable','Setup')][string]$Mode
)
$ErrorActionPreference = 'Stop'
try {
    for ($i=0; $i -lt 120; $i++) {
        $p = Get-Process -Id $WaitPid -ErrorAction SilentlyContinue
        if ($null -eq $p) { break }
        Start-Sleep -Seconds 1
    }
    if (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) {
        throw 'Aplicativo nao fechou a tempo. Atualizacao cancelada.'
    }
    if ($Mode -eq 'Setup') {
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) { throw 'Instalador ausente.' }
        $p = Start-Process -FilePath $Package -ArgumentList '/SILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Instalador falhou: $($p.ExitCode)" }
    } else {
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf) -or
            -not $Package.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Portable EXE verificado nao encontrado.'
        }
        if (-not $Executable.EndsWith('-Portable.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Destino nao e a edicao portable onefile.'
        }
        $backup = $Executable + '.previous'
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        if (Test-Path -LiteralPath $Executable) {
            Copy-Item -LiteralPath $Executable -Destination $backup -Force
        }
        try {
            Copy-Item -LiteralPath $Package -Destination $Executable -Force
        } catch {
            if (Test-Path -LiteralPath $backup) { Copy-Item -LiteralPath $backup -Destination $Executable -Force }
            throw
        }
        # data/ is stored beside the executable and deliberately untouched.
    }
    if (Test-Path -LiteralPath $Executable) {
        Start-Process -FilePath $Executable
    }
} catch {
    $message = "Falha ao instalar atualizacao PT2VHF Sat Tool: $($_.Exception.Message)"
    $log = Join-Path $env:TEMP 'PT2VHF-Sat-Tool-update-error.txt'
    $message | Out-File -FilePath $log -Encoding UTF8
}
