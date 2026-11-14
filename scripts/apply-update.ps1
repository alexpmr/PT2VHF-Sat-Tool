# PT2VHF Sat Tool: external updater; called only after verified SHA-256 + approval.
# Windows 10/11. Never delete portable data/.
# v1.6.0: espera a ARVORE de processos do app (inclui QtWebEngineProcess do mapa), encerra
# somente os filhos do proprio Sat Tool que nao sairem, instala com progresso visivel e log,
# grava o resultado e sempre reabre o programa.
param(
    [int]$WaitPid,
    [string]$Package,
    [string]$Destination,
    [string]$Executable,
    [ValidateSet('Portable','Setup')][string]$Mode,
    [string]$Version = ''
)
$ErrorActionPreference = 'Stop'
$resultFile = Join-Path $env:TEMP 'PT2VHF-Sat-Tool-update-result.txt'
$setupLog = Join-Path $env:TEMP 'PT2VHF-Sat-Tool-setup.log'
$status = 'erro'
$detail = ''
# v1.8.1: registro de cada etapa (diagnostico quando o OTA "baixa, fecha e nada acontece")
$helperLog = Join-Path $env:TEMP 'PT2VHF-Sat-Tool-update-helper.log'
function Write-Step([string]$text) {
    try { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $text" | Out-File -FilePath $helperLog -Append -Encoding UTF8 } catch { }
}
Write-Step "inicio: modo=$Mode versao=$Version pid=$WaitPid destino=$Destination exe=$Executable pacote=$Package"

function Get-Descendants([int]$root) {
    # Instantaneo da arvore enquanto o app ainda existe (PIDs dos filhos e netos).
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object ProcessId, ParentProcessId)
    $found = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($root)
    while ($queue.Count -gt 0) {
        $p = $queue.Dequeue()
        foreach ($c in $all) {
            # v1.9.1: o proprio atualizador e filho do app (Popen); sem esta exclusao ele entrava na lista,
            # "nao fechava" em 90 s e era encerrado por Stop-Process junto com os filhos do app: o OTA
            # baixava, fechava o programa e nada mais acontecia.
            if ([int]$c.ProcessId -eq $PID) { continue }
            if ($c.ParentProcessId -eq $p -and -not $found.Contains([int]$c.ProcessId)) {
                $found.Add([int]$c.ProcessId); $queue.Enqueue([int]$c.ProcessId)
            }
        }
    }
    return $found
}

function Wait-Exit([int[]]$pids, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        $alive = @($pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($alive.Count -eq 0) { return @() }
        Start-Sleep -Seconds 1
    }
    return @($pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
}

function Get-InnoExitMeaning([int]$code) {
    switch ($code) {
        1 { 'o instalador nao iniciou; o programa pode ainda estar aberto' }
        2 { 'cancelado antes de instalar' }
        3 { 'erro fatal ao preparar a proxima etapa' }
        4 { 'erro fatal durante a instalacao' }
        5 { 'falha ao preparar a instalacao (arquivo em uso)' }
        6 { 'instalador encerrado a forca' }
        7 { 'falha ao preparar a instalacao' }
        8 { 'reinicio do Windows necessario antes de instalar' }
        default { 'erro desconhecido' }
    }
}

try {
    $children = @(Get-Descendants $WaitPid)
    Write-Step "processos do app a esperar: $((@($WaitPid) + $children) -join ',') (atualizador: $PID)"
    $left = Wait-Exit (@($WaitPid) + $children) 90
    Write-Step "app encerrado; restantes: $($left -join ',')"
    if ($left.Count -gt 0) {
        # Somente processos que eram filhos do Sat Tool (mapa/QtWebEngine); nunca de outros programas.
        foreach ($id in $left) {
            if ($id -ne $WaitPid -and $id -ne $PID) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
        }
        $left = Wait-Exit $left 15
        if ($left -contains $WaitPid) { throw 'O PT2VHF Sat Tool nao fechou a tempo. Feche-o e instale manualmente.' }
    }
    # Processos do mapa remanescentes da pasta instalada (ex.: instancia antiga) tambem travam arquivos.
    if ($Mode -eq 'Setup' -and $Destination) {
        Get-Process -Name 'QtWebEngineProcess' -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -and $_.Path.StartsWith($Destination, [System.StringComparison]::OrdinalIgnoreCase)
        } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    if ($Mode -eq 'Setup') {
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) { throw 'Instalador ausente.' }
        # v1.7.1: a tarefa do driver RTL-SDR (wdi-simple, pede UAC e espera ate 60 s) nunca roda no OTA,
        # mesmo que o operador a tenha marcado numa instalacao anterior (o Inno lembra as tarefas).
        # O driver so e instalado pelo botao do painel SDR quando faltar.
        $setupArgs = @('/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CLOSEAPPLICATIONS',
                       '/MERGETASKS="!rtlsdr"', '/OTA', "/LOG=`"$setupLog`"")
        if ($Destination) { $setupArgs += "/DIR=`"$Destination`"" }
        $code = -1
        for ($attempt = 1; $attempt -le 2; $attempt++) {
            Write-Step "instalador: tentativa $attempt"
            # Sem -Wait: ele espera tambem os processos filhos, e o Setup /OTA reabre o programa como filho;
            # o atualizador ficava parado ate o programa ser fechado. Espera so o instalador.
            $p = Start-Process -FilePath $Package -ArgumentList $setupArgs -PassThru
            $null = $p.Handle   # guarda o handle para o ExitCode ficar disponivel
            if (-not $p.WaitForExit(1800000)) { throw 'Instalador nao terminou em 30 minutos.' }
            $code = $p.ExitCode
            Write-Step "instalador: codigo $code"
            # 1 = Setup nao iniciou (ex.: AppMutex ainda presente); 5 = falha em "Preparando para instalar"
            # (arquivo em uso). Uma nova tentativa apos alguns segundos costuma resolver.
            if ($code -eq 0 -or ($code -ne 1 -and $code -ne 5)) { break }
            Start-Sleep -Seconds 5
        }
        if ($code -ne 0) {
            $last = ''
            if (Test-Path -LiteralPath $setupLog) {
                $last = (Get-Content -LiteralPath $setupLog -Tail 3 -ErrorAction SilentlyContinue) -join ' | '
            }
            throw "Instalador terminou com codigo $code ($(Get-InnoExitMeaning $code)). Ultima etapa: $last (log: $setupLog)"
        }
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
        $copied = $false
        for ($i = 0; $i -lt 10 -and -not $copied; $i++) {
            try { Copy-Item -LiteralPath $Package -Destination $Executable -Force; $copied = $true }
            catch { Start-Sleep -Seconds 2 }
        }
        if (-not $copied) {
            if (Test-Path -LiteralPath $backup) { Copy-Item -LiteralPath $backup -Destination $Executable -Force }
            throw 'Nao foi possivel substituir o EXE portatil (arquivo em uso).'
        }
        # data/ is stored beside the executable and deliberately untouched.
    }
    $status = 'ok'
    $detail = "Atualizado para a versao $Version."
} catch {
    $detail = $_.Exception.Message
    "Falha ao instalar atualizacao PT2VHF Sat Tool: $detail" | Out-File -FilePath (Join-Path $env:TEMP 'PT2VHF-Sat-Tool-update-error.txt') -Encoding UTF8
} finally {
    "$status`n$Version`n$detail" | Out-File -FilePath $resultFile -Encoding UTF8
    Write-Step "resultado: $status $detail"
    # v1.7.2: o EXE instalado leva a versao no nome e o Setup (/OTA) abre o EXE novo.
    # v1.8.1: se depois de alguns segundos nenhum EXE do programa estiver rodando na pasta, o atualizador abre
    # o mais recente (antes, se o Setup nao abrisse, nada acontecia). Falha e portatil reabrem como antes.
    $running = $false
    if ($Mode -eq 'Setup' -and $status -eq 'ok' -and $Destination) {
        for ($i = 0; $i -lt 15 -and -not $running; $i++) {
            Start-Sleep -Seconds 1
            $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
                $_.Name -like 'PT2VHF-Sat-Tool*' -and $_.Path -and
                $_.Path.StartsWith($Destination, [System.StringComparison]::OrdinalIgnoreCase)
            }).Count -gt 0
        }
        Write-Step "programa aberto pelo instalador: $running"
    }
    if (-not $running) {
        $launch = $Executable
        if ($Mode -eq 'Setup' -or -not ($launch -and (Test-Path -LiteralPath $launch))) {
            if ($Destination) {
                $newest = Get-ChildItem -LiteralPath $Destination -Filter 'PT2VHF-Sat-Tool*.exe' -File -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -notlike '*Setup*' } |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
                if ($newest) { $launch = $newest }
            }
        }
        if ($launch -and (Test-Path -LiteralPath $launch)) {
            Write-Step "abrindo: $launch"
            Start-Process -FilePath $launch -WorkingDirectory (Split-Path -Parent $launch)
        } else {
            Write-Step "nenhum executavel encontrado para abrir"
        }
    }
}
