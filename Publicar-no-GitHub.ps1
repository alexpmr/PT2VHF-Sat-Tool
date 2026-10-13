# PT2VHF Sat Tool - importacao inicial segura do codigo para o repositorio GitHub.
# Nao reescreve o historico, nao remove o LICENSE remoto, nao usa force push.
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/alexpmr/PT2VHF-Sat-Tool.git'
$source = $PSScriptRoot
$version = 'v0.1.2'
$target = Join-Path ([System.IO.Path]::GetTempPath()) ("PT2VHF-Sat-Tool-Publicacao-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

function Run-Git([string[]]$Parameters) {
  & git @Parameters
  if ($LASTEXITCODE -ne 0) { throw ("Git falhou (codigo " + $LASTEXITCODE + "): git " + ($Parameters -join ' ')) }
}

Write-Host "PT2VHF Sat Tool - Publicacao inicial no GitHub" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw 'Git for Windows nao encontrado. Instale: https://git-scm.com/downloads/win'
}
foreach ($required in @('README.md', 'run.py', 'requirements.txt', 'sat_tool', 'tests', 'installer', '.github')) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $required))) {
    throw "Arquivo/pasta obrigatorio ausente: $required. Extraia TODO o ZIP antes de executar."
  }
}

Run-Git -Parameters @('clone', '--branch', 'main', '--single-branch', $repo, $target)
$identityName = (& git config --get user.name)
$identityEmail = (& git config --get user.email)
if (-not $identityName -or -not $identityEmail) {
  Write-Host 'Configure a identidade Git do seu Windows:' -ForegroundColor Yellow
  Write-Host '  git config --global user.name "Seu Nome"'
  Write-Host '  git config --global user.email "seu-email-do-github"'
  Write-Host "Clone de seguranca preservado em: $target"
  throw 'Identidade Git nao configurada.'
}

foreach ($entry in @('.github', '.gitignore', 'BACKLOG.md', 'README.md', 'installer', 'scripts', 'Gerar-Instalador-e-Portable.cmd', 'requirements-win7.txt', 'requirements-win11.txt', 'requirements.txt', 'run.py', 'sat_tool', 'tests')) {
  Copy-Item -LiteralPath (Join-Path $source $entry) -Destination (Join-Path $target $entry) -Recurse -Force
}
Run-Git -Parameters @('-C', $target, 'add', '--all')
& git -C $target diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
  Write-Host 'O repositorio ja contem os mesmos arquivos. Nenhuma alteracao a publicar.' -ForegroundColor Green
} elseif ($LASTEXITCODE -eq 1) {
  Run-Git -Parameters @('-C', $target, 'commit', '-m', 'feat: PT2VHF Sat Tool v0.1.2 updater and live satellite catalog')
  Run-Git -Parameters @('-C', $target, 'push', 'origin', 'main')
  Write-Host 'Codigo publicado no GitHub (main).' -ForegroundColor Green
} else {
  throw 'Nao foi possivel verificar o diff antes de publicar.'
}
# Push the release tag only after the branch has been pushed successfully.
$existingTag = (& git -C $target ls-remote --tags origin 'refs/tags/v0.1.2')
if (-not $existingTag) {
  Run-Git -Parameters @('-C', $target, 'tag', $version)
  Run-Git -Parameters @('-C', $target, 'push', 'origin', $version)
  Write-Host 'Tag v0.1.2 enviada. GitHub Actions executará o build das quatro variantes.' -ForegroundColor Green
} else {
  Write-Host 'Tag remota v0.1.2 ja existe; nenhum retag forçado.' -ForegroundColor Yellow
}
Write-Host "Repositorio: https://github.com/alexpmr/PT2VHF-Sat-Tool"
Write-Host "Checkout mantido para auditoria: $target"
Write-Host 'Acompanhe o build em: https://github.com/alexpmr/PT2VHF-Sat-Tool/actions'
