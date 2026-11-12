"""Conservative PT2VHF site updater; no CAT/radio side effects.

Manifest and packages come exclusively from https://www.pt2vhf.com.
Automatic *checking*, operator-approved download/install. Fails closed without
size + SHA256. Portable updates are staged and applied after process exit; never touch data/.
"""
from __future__ import annotations

import hashlib
import shutil
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

import requests

ORIGIN = 'https://www.pt2vhf.com'
SITE_HOST = 'www.pt2vhf.com'
UPDATE_API = ORIGIN + '/update.php?product=sat'
WEB_URL = ORIGIN + '/sat'
DOWNLOAD_PREFIX = '/downloads/sat-tool/'
HEADERS = {'Accept': 'application/json', 'User-Agent': 'PT2VHF-Sat-Tool-updater'}
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
HASH_RE = re.compile(r'[0-9a-f]{64}')
MAX_MANIFEST_BYTES = 2_000_000
MAX_PACKAGE_BYTES = 600 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024


def version_tuple(raw: str):
    match = VERSION_RE.fullmatch(str(raw).strip())
    return tuple(map(int, match.groups())) if match else None


def install_flavor(qt_binding: str, *, frozen: Optional[bool] = None, exe_path: Optional[Path] = None):
    """Return correct release family and install type; dev builds never self-update."""
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    if not frozen:
        return None
    if sys.platform.startswith('linux'):
        return 'Linux-x64', 'Manual'
    if sys.platform == 'darwin':
        return 'macOS-arm64', 'Manual'
    if sys.platform != 'win32':
        return None
    root = (exe_path or Path(sys.executable)).resolve().parent
    portable = (root / 'portable.flag').exists() or (exe_path or Path(sys.executable)).stem.casefold().endswith('-portable')
    variant = 'Win7-x86' if qt_binding == 'PySide2' else 'Win11-x64'
    return variant, ('Portable' if portable else 'Setup')


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    body: str
    is_prerelease: bool
    asset_name: str
    url: str
    expected_sha256: Optional[str]
    expected_size: int
    html_url: str


def asset_name(version: str, variant: str, kind: str) -> str:
    """Windows: Setup/Portable EXE (OTA). Linux/macOS: pacote baixado pelo site (Manual)."""
    if kind == 'Manual':
        return f'PT2VHF-Sat-Tool-v{version}-{variant}' + ('.dmg' if variant.startswith('macOS') else '.tar.gz')
    return f'PT2VHF-Sat-Tool-v{version}-{variant}-{kind}.exe'


def is_official_asset(url: str, name: str) -> bool:
    """Only https://www.pt2vhf.com/downloads/sat-tool/<name>.exe is accepted."""
    try:
        info = urlsplit(url)
        return (info.scheme == 'https' and info.netloc == SITE_HOST
                and info.path == DOWNLOAD_PREFIX + name
                and not info.query and not info.fragment and '%' not in info.path
                and bool(re.fullmatch(r'[A-Za-z0-9_.-]+', name))
                and name.casefold().endswith(('.exe', '.tar.gz', '.dmg')))
    except (TypeError, ValueError, AttributeError):
        return False


def select_release(manifest, current_version: str, variant: str, kind: str,
                   *, include_prereleases: bool = True) -> Optional[AvailableUpdate]:
    """Validate the PT2VHF site manifest (schema 1) and pick this build's EXE.

    Returns None when the site has nothing newer for this variant/kind.
    Raises ValueError for manifests that are malformed or not from the site.
    """
    current = version_tuple(current_version)
    if current is None:
        raise ValueError('Versão instalada inválida')
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        raise ValueError('Manifesto do site PT2VHF inválido')
    if manifest.get('product') != 'sat' or manifest.get('source') != ORIGIN:
        raise ValueError('Manifesto não pertence ao PT2VHF Sat Tool')
    if manifest.get('status') == 'unpublished':
        return None
    ver = version_tuple(str(manifest.get('version') or ''))
    if manifest.get('status') != 'available' or ver is None:
        raise ValueError('Versão publicada no site inválida')
    if ver <= current:
        return None
    version = '.'.join(map(str, ver))
    name = asset_name(version, variant, kind)
    files = manifest.get('files')
    if not isinstance(files, list):
        raise ValueError('Manifesto sem lista de arquivos')
    for entry in files:
        if not isinstance(entry, dict) or entry.get('name') != name:
            continue
        url, size, sha = entry.get('url'), entry.get('size'), entry.get('sha256')
        if not isinstance(url, str) or not is_official_asset(url, name):
            return None
        if type(size) is not int or not 0 < size <= MAX_PACKAGE_BYTES:
            return None
        if not isinstance(sha, str) or not HASH_RE.fullmatch(sha):
            return None
        return AvailableUpdate(
            version=version, body=str(manifest.get('notes') or ''), is_prerelease=False,
            asset_name=name, url=url, expected_sha256=sha, expected_size=size,
            html_url=str(manifest.get('page') or WEB_URL))
    return None


def check_for_update(current_version: str, variant: str, kind: str,
                     *, include_prereleases: bool = True):
    response = requests.get(UPDATE_API, timeout=20, headers=HEADERS, allow_redirects=False)
    if response.is_redirect or response.url != UPDATE_API:
        raise ValueError('Redirecionamento bloqueado na consulta de atualização')
    response.raise_for_status()
    if len(response.content) > MAX_MANIFEST_BYTES:
        raise ValueError('Manifesto excede limite de tamanho')
    return select_release(response.json(), current_version, variant, kind,
                          include_prereleases=include_prereleases)


def parse_checksum_manifest(text: str, name: str):
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\\/]+)', line.strip())
        if match and match.group(2) == name:
            return match.group(1).lower()
    return None


def download_update(update: AvailableUpdate, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """Stage verified EXE installer or onefile portable executable from www.pt2vhf.com."""
    if not is_official_asset(update.url, update.asset_name):
        raise ValueError('Pacote de atualização fora do domínio www.pt2vhf.com')
    expected = str(update.expected_sha256 or '').lower()
    if not HASH_RE.fullmatch(expected) or not 0 < update.expected_size <= MAX_PACKAGE_BYTES:
        raise ValueError('Atualização sem tamanho e SHA-256 verificáveis; atualização bloqueada')
    folder = Path(tempfile.mkdtemp(prefix='pt2vhf_sat_update_'))
    dest = folder / update.asset_name
    digest = hashlib.sha256()
    total = 0
    with requests.get(update.url, stream=True, timeout=(15, 120), allow_redirects=False,
                      headers={'User-Agent':'PT2VHF-Sat-Tool-updater'}) as r:
        if r.is_redirect:
            raise ValueError('Redirecionamento do download não permitido')
        r.raise_for_status()
        size = int(r.headers.get('Content-Length') or update.expected_size)
        if size != update.expected_size:
            raise ValueError('Tamanho do pacote diverge do manifesto do site')
        with dest.open('wb') as fh:
            for chunk in r.iter_content(chunk_size=128*1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > update.expected_size:
                    raise ValueError('Pacote excede o tamanho publicado')
                digest.update(chunk)
                fh.write(chunk)
                if progress:
                    progress(total, size)
    if total != update.expected_size or digest.hexdigest() != expected:
        dest.unlink(missing_ok=True)
        raise ValueError('SHA-256 ou tamanho não confere: atualização abortada')
    return dest


def safe_extract_portable(zip_path: Path) -> Path:
    """Stage ZIP contents only, refuse zip-slip, links and user data replacement."""
    output = zip_path.parent / 'prepared'
    output.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        total = 0
        members = zf.infolist()
        if len(members) > 30000:
            raise ValueError('ZIP contém entradas excessivas')
        for entry in members:
            name = entry.filename.replace('\\', '/')
            path = Path(name)
            if (name.startswith('/') or ':' in name or not name or '..' in path.parts or
                    path.parts[0].casefold() == 'data' or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('ZIP contém caminho inseguro')
            total += entry.file_size
            if total > MAX_UNPACKED_BYTES:
                raise ValueError('ZIP expandido excede limite')
        zf.extractall(output)
    if not (output / 'PT2VHF-Sat-Tool.exe').is_file() or not (output / 'portable.flag').exists():
        raise ValueError('Pacote portátil incompleto')
    return output


def update_script_args(helper: Path, *, pid: int, package: Path, destination: Path, exe: Path,
                       portable: bool, version: str = '') -> list:
    """Linha de comando do apply-update.ps1 (v1.6.0: inclui a versão para o relatório final)."""
    return [str(Path(os.environ.get('SYSTEMROOT', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'),
            '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(helper),
            '-WaitPid', str(pid), '-Package', str(package), '-Destination', str(destination),
            '-Executable', str(exe), '-Mode', 'Portable' if portable else 'Setup', '-Version', str(version)]


def read_update_result(temp_dir: Optional[Path] = None) -> Optional[tuple]:
    """Resultado da última atualização externa (status, versão, detalhe) e remove o arquivo."""
    path = Path(temp_dir or tempfile.gettempdir()) / 'PT2VHF-Sat-Tool-update-result.txt'
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        path.unlink()
    except OSError:
        return None
    lines += ['', '', '']
    return lines[0].strip(), lines[1].strip(), lines[2].strip()


MANUAL_DOWNLOAD_URL = 'https://www.pt2vhf.com/sat'


def update_failure_message(detail: str) -> str:
    """Texto (rich text) da falha de OTA: motivo exato (código do Inno + última etapa do log) e link manual."""
    from html import escape
    return (f"A atualização automática não terminou.<br><br><b>Motivo:</b> {escape(detail or 'desconhecido')}"
            f"<br><br>O programa continua na versão anterior. Baixe e instale a versão nova manualmente em "
            f"<a href='{MANUAL_DOWNLOAD_URL}'>{MANUAL_DOWNLOAD_URL.split('//')[1]}</a> "
            f"ou tente de novo pelo botão de versão.<br>Log do instalador: %TEMP%\\PT2VHF-Sat-Tool-setup.log")


def launch_staged_update(package: Path, *, portable: bool, script_path: Path,
                         exe_path: Optional[Path] = None, version: str = ''):
    """Launch an external PowerShell helper. App must exit immediately afterward."""
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise RuntimeError('Atualização local só é permitida nos EXEs Windows')
    exe = (exe_path or Path(sys.executable)).resolve()
    destination = exe.parent
    if package.suffix.lower() != '.exe' or not package.is_file():
        raise ValueError('Atualização requer pacote EXE verificado')
    candidate = package
    # Onefile extraction is deleted at exit; external updater must live in temp.
    helper = package.parent / 'apply-update.ps1'
    shutil.copy2(script_path, helper)
    if not script_path.is_file():
        raise FileNotFoundError('Atualizador externo não incluído no pacote')
    args = update_script_args(helper, pid=os.getpid(), package=candidate, destination=destination, exe=exe,
                              portable=portable, version=version)
    # Processo independente: continua vivo depois que o app (e seus filhos) encerram.
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0) \
        | getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0)
    try:
        subprocess.Popen(args, close_fds=True, creationflags=flags)
    except OSError:
        # Alguns ambientes proíbem sair do job: tenta sem CREATE_BREAKAWAY_FROM_JOB.
        subprocess.Popen(args, close_fds=True, creationflags=flags & ~getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0))
