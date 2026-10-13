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
        if (-not (Test-Path -LiteralPath (Join-Path $Package 'PT2VHF-Sat-Tool.exe'))) {throw 'Portable incompleto.'}
        if (-not (Test-Path -LiteralPath (Join-Path $Destination 'portable.flag'))) {throw 'Destino nao e uma instalacao portable.'}
        # Stage files were already safely extracted from a verified package.
        # Do not delete or overwrite data/ (settings and downloaded orbital catalogs).
        $fullSource = [System.IO.Path]::GetFullPath($Package).TrimEnd('\')
        Get-ChildItem -LiteralPath $fullSource -Force -Recurse | ForEach-Object {
            $relative = $_.FullName.Substring($fullSource.Length).TrimStart('\')
            $parts = $relative -split '\\'
            if ($parts[0] -ine 'data') {
                $target = Join-Path $Destination $relative
                if ($_.PSIsContainer) {
                    if (-not (Test-Path -LiteralPath $target)) {
                        New-Item -ItemType Directory -Path $target -Force | Out-Null
                    }
                } else {
                    $parent = Split-Path -Parent $target
                    if (-not (Test-Path -LiteralPath $parent)) {
                        New-Item -ItemType Directory -Path $parent -Force | Out-Null
                    }
                    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
                }
            }
        }
    }
    if (Test-Path -LiteralPath $Executable) {
        Start-Process -FilePath $Executable
    }
} catch {
    $message = "Falha ao instalar atualizacao PT2VHF Sat Tool: $($_.Exception.Message)"
    $log = Join-Path $env:TEMP 'PT2VHF-Sat-Tool-update-error.txt'
    $message | Out-File -FilePath $log -Encoding UTF8
}
