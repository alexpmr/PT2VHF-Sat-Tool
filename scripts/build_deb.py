#!/usr/bin/env python3
"""Gera o pacote .deb (Ubuntu 22.04+ / Linux Mint 21+, amd64) a partir da pasta do PyInstaller.

Uso (no CI): python scripts/build_deb.py --version X.Y.Z --app-dir dist/PT2VHF-Sat-Tool-vX.Y.Z --out out
Instala em /opt/pt2vhf-sat-tool, cria o comando ``pt2vhf-sat-tool``, o atalho no menu de aplicativos,
a regra udev do RTL-SDR (acesso sem root) e o bloqueio do driver de TV dvb_usb_rtl28xxu.
As configurações do usuário continuam em ~/.config/PT2VHF/SatTool (não são tocadas pelo pacote).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "pt2vhf-sat-tool"
PREFIX = f"opt/{PACKAGE}"
# Bibliotecas de sistema que o Qt/QtWebEngine empacotado pelo PyInstaller usa (mesma lista do CI).
DEPENDS = ", ".join((
    "libc6 (>= 2.35)", "libegl1", "libgl1", "libxkbcommon0", "libxkbcommon-x11-0", "libfontconfig1",
    "libdbus-1-3", "libnss3", "libxcomposite1", "libxdamage1", "libxrandr2", "libxtst6", "libxshmfence1",
    "libasound2 | libasound2t64", "libxcb-cursor0", "libxcb-icccm4", "libxcb-keysyms1", "libxcb-shape0",
    "libxcb-xinerama0", "libxcb-randr0", "libxcb-render-util0", "libxcb-image0", "libpulse0",
    "libpulse-mainloop-glib0",
))

DESKTOP = """[Desktop Entry]
Type=Application
Name=PT2VHF Sat Tool
GenericName=Rastreio de satélites de radioamador
Comment=Passagens, Doppler/CAT, rotor e SDR para satélites de radioamador
Exec=pt2vhf-sat-tool
Icon=pt2vhf-sat-tool
Terminal=false
Categories=HamRadio;Network;Science;
Keywords=satellite;satélite;ham;radio;rotor;sdr;tle;
"""

POSTINST = """#!/bin/sh
set -e
if [ "$1" = configure ]; then
    command -v udevadm >/dev/null 2>&1 && { udevadm control --reload-rules || true; udevadm trigger --subsystem-match=usb || true; }
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
fi
exit 0
"""

POSTRM = """#!/bin/sh
set -e
command -v udevadm >/dev/null 2>&1 && { udevadm control --reload-rules || true; }
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
exit 0
"""


def build(version: str, app_dir: Path, out: Path) -> Path:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Versão X.Y.Z obrigatória")
    exe_name = f"PT2VHF-Sat-Tool-v{version}"
    if not (app_dir / exe_name).is_file():
        raise SystemExit(f"Executável ausente: {app_dir / exe_name}")
    stage = out / f"{PACKAGE}_{version}_amd64"
    if stage.exists():
        shutil.rmtree(stage)
    opt = stage / PREFIX
    shutil.copytree(app_dir, opt, symlinks=True)

    bin_dir = stage / "usr/bin"
    bin_dir.mkdir(parents=True)
    os.symlink(f"/{PREFIX}/{exe_name}", bin_dir / PACKAGE)

    apps = stage / "usr/share/applications"
    apps.mkdir(parents=True)
    (apps / f"{PACKAGE}.desktop").write_text(DESKTOP, encoding="utf-8")
    icon = ROOT / "assets/branding/icon-256.png"
    if icon.is_file():
        icons = stage / "usr/share/icons/hicolor/256x256/apps"
        icons.mkdir(parents=True)
        shutil.copy2(icon, icons / f"{PACKAGE}.png")

    rules = stage / "usr/lib/udev/rules.d"
    rules.mkdir(parents=True)
    shutil.copy2(ROOT / "linux/rtl-sdr.rules", rules / "60-pt2vhf-rtl-sdr.rules")
    modprobe = stage / "etc/modprobe.d"
    modprobe.mkdir(parents=True)
    (modprobe / "pt2vhf-blacklist-rtl-sdr.conf").write_text(
        "# PT2VHF Sat Tool: libera o RTL-SDR do driver de TV digital\nblacklist dvb_usb_rtl28xxu\n", encoding="utf-8")
    docs = stage / f"usr/share/doc/{PACKAGE}"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "linux/LEIA-ME-RTL-SDR.txt", docs / "LEIA-ME-RTL-SDR.txt")
    if (ROOT / "LICENSE").is_file():
        shutil.copy2(ROOT / "LICENSE", docs / "copyright")

    size_kib = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file() and not f.is_symlink()) // 1024 + 1
    debian = stage / "DEBIAN"
    debian.mkdir()
    (debian / "control").write_text(
        f"Package: {PACKAGE}\nVersion: {version}\nSection: hamradio\nPriority: optional\nArchitecture: amd64\n"
        f"Installed-Size: {size_kib}\nDepends: {DEPENDS}\nMaintainer: PT2VHF <ci@pt2vhf.com>\n"
        "Homepage: https://www.pt2vhf.com/sat\n"
        "Description: PT2VHF Sat Tool - rastreio de satélites de radioamador\n"
        " Passagens, correção Doppler por CAT, controle de rotor, display do rádio,\n"
        " painel SDR com RTL-SDR e telemetria. Inclui a regra udev do RTL-SDR.\n", encoding="utf-8")
    (debian / "conffiles").write_text("/etc/modprobe.d/pt2vhf-blacklist-rtl-sdr.conf\n", encoding="utf-8")
    for name, body in (("postinst", POSTINST), ("postrm", POSTRM)):
        (debian / name).write_text(body, encoding="utf-8")
        (debian / name).chmod(0o755)
    for path in stage.rglob("*"):   # permissões padrão Debian (dpkg recusa diretórios graváveis por todos)
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.parent.name != "DEBIAN" or path.name not in ("postinst", "postrm"):
            path.chmod(0o755 if os.access(path, os.X_OK) else 0o644)

    deb = out / f"PT2VHF-Sat-Tool-v{version}-Linux-x64.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(stage), str(deb)], check=True)
    shutil.rmtree(stage)
    return deb


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True)
    p.add_argument("--app-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    print(build(a.version, a.app_dir, a.out))


if __name__ == "__main__":
    main()
