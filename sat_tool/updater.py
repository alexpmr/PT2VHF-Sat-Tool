"""Conservative GitHub release updater; no CAT/radio side effects.

Automatic *checking*, operator-approved download/install. Fails closed without SHA256.
Portable updates are staged and applied after process exit; never touch data/.
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
from urllib.parse import urlparse

import requests

OWNER_REPO = 'alexpmr/PT2VHF-Sat-Tool'
RELEASES_API = 'https://api.github.com/repos/' + OWNER_REPO + '/releases?per_page=30'
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
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
    checksum_url: Optional[str]
    html_url: str


def _safe_github_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'github.com' and p.path.startswith('/' + OWNER_REPO + '/releases/download/')


def select_release(releases: list, current_version: str, variant: str, kind: str,
                   *, include_prereleases: bool = True) -> Optional[AvailableUpdate]:
    current = version_tuple(current_version)
    if current is None:
        raise ValueError('Versão instalada inválida')
    results = []
    for release in releases:
        if release.get('draft') or (release.get('prerelease') and not include_prereleases):
            continue
        tag = str(release.get('tag_name', ''))
        ver = version_tuple(tag)
        if not ver or ver <= current:
            continue
        name = f'PT2VHF-Sat-Tool-v{ver[0]}.{ver[1]}.{ver[2]}-{variant}-{kind}.' + 'exe'
        assets = {a.get('name'): a for a in release.get('assets', []) if a.get('state') == 'uploaded'}
        asset = assets.get(name)
        if not asset or not _safe_github_url(str(asset.get('browser_download_url', ''))):
            continue
        sha = str(asset.get('digest') or '')
        digest = sha[7:].lower() if re.fullmatch(r'sha256:[a-fA-F0-9]{64}', sha) else None
        checksum = assets.get(f'PT2VHF-Sat-Tool-v{ver[0]}.{ver[1]}.{ver[2]}-{variant}-SHA256.txt')
        checksum_url = checksum.get('browser_download_url') if checksum else None
        if checksum_url and not _safe_github_url(checksum_url):
            checksum_url = None
        results.append((ver, AvailableUpdate(
            version='.'.join(map(str, ver)), body=str(release.get('body') or ''),
            is_prerelease=bool(release.get('prerelease')),
            asset_name=name, url=asset['browser_download_url'],
            expected_sha256=digest, checksum_url=checksum_url,
            html_url=str(release.get('html_url') or '')
        )))
    return max(results, key=lambda x: x[0])[1] if results else None


def check_for_update(current_version: str, variant: str, kind: str,
                     *, include_prereleases: bool = True):
    response = requests.get(RELEASES_API, timeout=20,
                            headers={'Accept':'application/vnd.github+json', 'User-Agent': 'PT2VHF-Sat-Tool-updater'})
    response.raise_for_status()
    releases = response.json()
    if not isinstance(releases, list):
        raise ValueError('Resposta GitHub Releases inválida')
    return select_release(releases, current_version, variant, kind,
                          include_prereleases=include_prereleases)


def parse_checksum_manifest(text: str, name: str):
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\\/]+)', line.strip())
        if match and match.group(2) == name:
            return match.group(1).lower()
    return None


def _manifest_checksum(update: AvailableUpdate):
    if update.expected_sha256:
        return update.expected_sha256
    if update.checksum_url is None:
        raise ValueError('Release sem hash SHA-256 verificável; atualização bloqueada')
    r = requests.get(update.checksum_url, timeout=25)
    r.raise_for_status()
    return parse_checksum_manifest(r.text, update.asset_name) or _missing_checksum()


def _missing_checksum():
    raise ValueError('Checksum do arquivo ausente ou inválido; atualização bloqueada')


def download_update(update: AvailableUpdate, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """Stage verified EXE installer or onefile portable executable."""
    expected = _manifest_checksum(update)
    folder = Path(tempfile.mkdtemp(prefix='pt2vhf_sat_update_'))
    dest = folder / update.asset_name
    digest = hashlib.sha256()
    total = 0
    with requests.get(update.url, stream=True, timeout=(15, 120), headers={'User-Agent':'PT2VHF-Sat-Tool-updater'}) as r:
        r.raise_for_status()
        size = int(r.headers.get('Content-Length') or 0)
        if size > MAX_PACKAGE_BYTES:
            raise ValueError('Pacote excede limite de tamanho')
        with dest.open('wb') as fh:
            for chunk in r.iter_content(chunk_size=128*1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_PACKAGE_BYTES:
                    raise ValueError('Pacote excede limite de tamanho')
                digest.update(chunk)
                fh.write(chunk)
                if progress:
                    progress(total, size)
    if total == 0 or digest.hexdigest() != expected:
        dest.unlink(missing_ok=True)
        raise ValueError('SHA-256 não confere: atualização abortada')
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


def launch_staged_update(package: Path, *, portable: bool, script_path: Path,
                         exe_path: Optional[Path] = None):
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
    args = [str(Path(os.environ.get('SYSTEMROOT', r'C:\Windows')) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'),
            '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(helper),
            '-WaitPid', str(os.getpid()), '-Package', str(candidate), '-Destination', str(destination),
            '-Executable', str(exe), '-Mode', 'Portable' if portable else 'Setup']
    subprocess.Popen(args, close_fds=True, creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
