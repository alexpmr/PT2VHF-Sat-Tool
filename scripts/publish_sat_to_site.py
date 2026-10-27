#!/usr/bin/env python3
"""Copia os EXEs verificados do Sat Tool para o repositório do site e atualiza updates.json.

Uso (no CI): python scripts/publish_sat_to_site.py --version 1.3.14 --release-dir release --site-dir site
O site www.pt2vhf.com (Hostinger) é implantado a partir desse repositório.
Recusa regressão de versão, arquivos vazios ou que não sejam executáveis Windows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

SITE = "https://www.pt2vhf.com"
FOLDER = "downloads/sat-tool"
VARIANT = "Win11-x64"
EDITIONS = (
    ("windows-installer", "Setup", "Windows — Instalador", "Windows 10 1809+ / 11 64 bits (recomendado)"),
    ("windows-portable", "Portable", "Windows — Portátil", "Windows 10 1809+ / 11 64 bits, EXE único sem instalar"),
)


def vtuple(raw):
    return tuple(map(int, raw.split(".")))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True)
    p.add_argument("--release-dir", required=True, type=Path)
    p.add_argument("--site-dir", required=True, type=Path)
    p.add_argument("--notes", default="")
    args = p.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        p.error("Versão semântica X.Y.Z obrigatória")
    manifest_path = args.site_dir / "updates.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise SystemExit("Esquema inesperado do updates.json")
    entry = manifest.setdefault("products", {}).setdefault("sat", {"name": "PT2VHF Sat Tool"})
    published = entry.get("version")
    if published and vtuple(published) > vtuple(args.version):
        raise SystemExit(f"Recusada regressão de {published} para {args.version}")

    target = args.site_dir / FOLDER
    target.mkdir(parents=True, exist_ok=True)
    for old in target.iterdir():
        if old.is_file() and old.name.startswith("PT2VHF-Sat-Tool-v"):
            old.unlink()
    files = []
    for category, kind, label, detail in EDITIONS:
        name = f"PT2VHF-Sat-Tool-v{args.version}-{VARIANT}-{kind}.exe"
        source = args.release_dir / name
        if not source.is_file() or source.stat().st_size <= 0:
            raise SystemExit("Arquivo ausente ou vazio: " + name)
        with source.open("rb") as fh:
            if fh.read(2) != b"MZ":
                raise SystemExit("Executável Windows inválido: " + name)
        shutil.copy2(source, target / name)
        files.append({
            "category": category, "label": label, "name": name,
            "url": f"{SITE}/{FOLDER}/{name}",
            "size": source.stat().st_size, "sha256": sha256(source), "detail": detail,
        })
    sums = "".join(f"{f['sha256']}  {f['name']}\n" for f in files)
    sums_name = f"PT2VHF-Sat-Tool-v{args.version}-{VARIANT}-SHA256.txt"
    (target / sums_name).write_text(sums, encoding="ascii")
    files.append({
        "category": "checksums", "label": "Somas de verificação", "name": sums_name,
        "url": f"{SITE}/{FOLDER}/{sums_name}",
        "size": (target / sums_name).stat().st_size, "sha256": sha256(target / sums_name),
        "detail": "SHA-256 dos arquivos da versão",
    })

    for stale in ("ciUrl", "ciLabel"):
        entry.pop(stale, None)
    entry.update({
        "name": "PT2VHF Sat Tool",
        "version": args.version,
        "developmentVersion": args.version,
        "date": date.today().isoformat(),
        "page": SITE + "/sat",
        "notes": args.notes,
        "files": files,
        "releaseStatus": "Instalador e portátil oficiais para Windows 10/11 x64. Confira o SHA-256 antes da instalação.",
        "updateEndpoint": SITE + "/update.php?product=sat",
    })
    manifest["updated"] = date.today().isoformat()
    staging = manifest_path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, manifest_path)
    print(f"Sat Tool v{args.version}: {len(files)} arquivos publicados em {FOLDER}")


if __name__ == "__main__":
    main()
