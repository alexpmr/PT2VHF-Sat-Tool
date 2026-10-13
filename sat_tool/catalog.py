from __future__ import annotations
"""Catalog cache and network sources. OMM JSON supports six-digit NORAD IDs."""
from pathlib import Path
from datetime import datetime, timezone
import json
import requests

CELESTRAK_OMM = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=json"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"
SATNOGS_TRANSMITTERS = "https://db.satnogs.org/api/transmitters/"
HEADERS = {"User-Agent": "PT2VHF-Sat-Tool/0.1.2 (radio amateur tracking tool)", "Accept": "application/json"}


def cache_path(data_dir: Path, name: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / name


def refresh_omm(data_dir: Path):
    response = requests.get(CELESTRAK_OMM, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data or not all("NORAD_CAT_ID" in o for o in data):
        raise ValueError("Catálogo OMM recebido em formato inválido")
    cache_path(data_dir, "amateur_omm.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def load_omm(data_dir: Path):
    file = cache_path(data_dir, "amateur_omm.json")
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else []


def refresh_transmitters(data_dir: Path, norad: int):
    response = requests.get(SATNOGS_TRANSMITTERS,
                            params={"format": "json", "satellite__norad_cat_id": norad},
                            headers=HEADERS, timeout=25)
    response.raise_for_status()
    result = response.json()
    rows = result if isinstance(result, list) else result.get("results", [])
    if not isinstance(rows, list):
        raise ValueError("Resposta de transponders inválida")
    cache_path(data_dir, f"tx_{norad}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def load_transmitters(data_dir: Path, norad: int):
    file = cache_path(data_dir, f"tx_{norad}.json")
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else []


def age_hours(data_dir: Path, name: str) -> float | None:
    file = data_dir / name
    if not file.exists():
        return None
    return (datetime.now(timezone.utc).timestamp() - file.stat().st_mtime) / 3600


def parse_tle(text: str) -> list[dict]:
    """Parse 3LE and 2LE feeds; TLE supports five-digit catalog numbers only."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    result = []
    i = 0
    while i < len(lines):
        name = ""
        if not lines[i].startswith("1 "):
            name = (lines[i][2:] if lines[i].startswith("0 ") else lines[i]).strip()
            i += 1
        if i+1 >= len(lines):
            break
        one,two=lines[i:i+2]
        if (one.startswith("1 ") and two.startswith("2 ") and len(one)>=69
            and len(two)>=69 and one[2:7]==two[2:7]):
            norad=int(one[2:7])
            result.append({"NORAD_CAT_ID":norad,"OBJECT_NAME":name or f"NORAD {norad}",
                           "TLE_LINE1":one,"TLE_LINE2":two})
            i+=2
        else:
            i+=1
    return result


def refresh_tle(data_dir: Path) -> list[dict]:
    response = requests.get(CELESTRAK_TLE, headers=HEADERS, timeout=30)
    response.raise_for_status()
    text = response.text
    objects = parse_tle(text)
    if not objects:
        raise ValueError("TLE vazio ou inválido")
    cache_path(data_dir, "amateur.tle").write_text(text, encoding="utf-8")
    return objects


def load_tle(data_dir: Path) -> list[dict]:
    file = cache_path(data_dir, "amateur.tle")
    return parse_tle(file.read_text(encoding="utf-8")) if file.exists() else []


def refresh_orbits(data_dir: Path) -> list[dict]:
    # Keep OMM as the preferred primary feed: unlike classical TLE, covers
    # NORAD > 99999; fetch TLE as requested for interoperability/fallback.
    omm, tle = None, None
    errors=[]
    try:omm=refresh_omm(data_dir)
    except Exception as e:errors.append(f"OMM: {e}")
    try:tle=refresh_tle(data_dir)
    except Exception as e:errors.append(f"TLE: {e}")
    if omm:return omm
    if tle:return tle
    raise ConnectionError("; ".join(errors))


def load_orbits(data_dir: Path) -> list[dict]:
    omm=load_omm(data_dir)
    return omm if omm else load_tle(data_dir)
