from __future__ import annotations
"""Catalog cache and network sources. OMM JSON supports six-digit NORAD IDs."""
from pathlib import Path
from datetime import datetime, timezone
import json
import requests

# CelesTrak group feeds return batches; never request one orbit per satellite.
DEFAULT_GROUPS = ("amateur", "stations", "cubesat", "starlink", "oneweb",
                  "weather", "science", "visual")
ALL_GROUPS = DEFAULT_GROUPS + ("active",)
CELESTRAK_OMM = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=json"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"
SATNOGS_TRANSMITTERS = "https://db.satnogs.org/api/transmitters/"
HEADERS = {"User-Agent": "PT2VHF-Sat-Tool/1.3.0 (radio amateur tracking tool)",
           "Accept": "application/json"}
ALIASES = {"27607": ("SO-50", "SO50", "SAUDISAT 1C", "SAUDISAT-1C"),
           "25544": ("ISS", "ARISS", "ZARYA"),
           "24278": ("FO-29", "FO29", "JAS-2"),
           "44881": ("RS-44", "RS44", "DOSAAF-85")}


def normalized_satellite_search(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD",str(text).casefold())
                   if c.isalnum() and not unicodedata.combining(c))


def satellite_search_text(ident, orbit):
    fields=[str(ident), str(orbit.get("OBJECT_NAME",""))]+list(ALIASES.get(str(ident),()))
    return normalized_satellite_search(" ".join(fields))


def merge_orbits(groups):
    """Merge duplicate NORAD IDs without losing category memberships."""
    output={}
    for category, objects in groups.items():
        for row in objects:
            if not isinstance(row,dict) or not row.get("NORAD_CAT_ID"):
                continue
            ident=str(row["NORAD_CAT_ID"])
            existing=output.get(ident)
            categories=set(existing.get("CATEGORIES",[])) if existing else set()
            categories.add(category)
            # Only replace orbital elements when the GP epoch is newer.
            current_epoch=str(row.get("EPOCH",""))
            old_epoch=str(existing.get("EPOCH","")) if existing else ""
            winner=dict(row) if not existing or (current_epoch and current_epoch>=old_epoch) else dict(existing)
            winner["CATEGORIES"]=sorted(categories)
            output[ident]=winner
    return list(output.values())


def refresh_group_omm(data_dir, group):
    if group not in ALL_GROUPS:
        raise ValueError("Categoria orbital não reconhecida")
    response=requests.get("https://celestrak.org/NORAD/elements/gp.php",
                          params={"GROUP":group,"FORMAT":"json"},headers=HEADERS,timeout=45)
    response.raise_for_status()
    objects=response.json()
    if not isinstance(objects,list) or not objects or not all(
            isinstance(o,dict) and "NORAD_CAT_ID" in o for o in objects):
        raise ValueError("OMM inválido para "+group)
    file=cache_path(data_dir,"group_"+group+".json")
    temp=file.with_suffix(".tmp")
    temp.write_text(json.dumps(objects,ensure_ascii=False),encoding="utf-8")
    temp.replace(file)
    return objects


def load_group_omm(data_dir,group):
    file=data_dir/("group_"+group+".json")
    if not file.exists():return []
    return json.loads(file.read_text(encoding="utf-8"))


def refresh_multi_omm(data_dir,groups=None,progress=None):
    groups=tuple(dict.fromkeys(groups or DEFAULT_GROUPS))
    all_data={}
    errors=[]
    for index,group in enumerate(groups,1):
        try:all_data[group]=refresh_group_omm(data_dir,group)
        except Exception as exc:
            errors.append(group+": "+str(exc))
            cached=load_group_omm(data_dir,group)
            if cached:all_data[group]=cached
        if progress:progress(index,len(groups),group,len(all_data.get(group,[])),len(errors))
    merged=merge_orbits(all_data)
    if not merged:
        cached=load_omm(data_dir)
        if cached:return cached
        raise ConnectionError("; ".join(errors) or "Nenhuma órbita obtida")
    file=cache_path(data_dir,"amateur_omm.json")  # Legacy cache name for v1.x migration.
    temp=file.with_suffix(".tmp")
    temp.write_text(json.dumps(merged,ensure_ascii=False),encoding="utf-8")
    temp.replace(file)
    return merged


def cache_path(data_dir: Path, name: str) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / name


def refresh_omm(data_dir: Path):
    """Legacy single-amateur endpoint kept for diagnostics and compatibility."""
    data=refresh_group_omm(data_dir,"amateur")
    cache_path(data_dir,"amateur_omm.json").write_text(
        json.dumps(data,ensure_ascii=False),encoding="utf-8")
    return data

def load_omm(data_dir: Path):
    file = cache_path(data_dir, "amateur_omm.json")
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else []


def refresh_transmitters(data_dir: Path, norad: int):
    # Some API deployments paginate results; never persist partial pages.
    from urllib.parse import urlparse
    rows=[]
    url=SATNOGS_TRANSMITTERS
    params={"format":"json","satellite__norad_cat_id":norad}
    seen=set()
    for page in range(25):
        if url in seen:raise ValueError("Paginação SatNOGS cíclica")
        seen.add(url)
        response=requests.get(url,params=params,headers=HEADERS,timeout=25)
        response.raise_for_status()
        result=response.json()
        if isinstance(result,list):
            current,nxt=result,None
        elif isinstance(result,dict):
            current,nxt=result.get("results",[]),result.get("next")
        else:raise ValueError("Resposta de transponders inválida")
        if not isinstance(current,list):raise ValueError("Registros de transponder inválidos")
        rows.extend(current)
        if not nxt:break
        from urllib.parse import urljoin
        url=urljoin(SATNOGS_TRANSMITTERS,nxt)
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.hostname!="db.satnogs.org":
            raise ValueError("Paginação SatNOGS encaminhou para domínio não autorizado")
        params=None
    else:raise ValueError("Paginação SatNOGS excedeu o limite")
    unique={}
    for entry in rows:
        if not isinstance(entry,dict):raise ValueError("Transponder em formato inválido")
        key=str(entry.get("uuid") or entry.get("id") or (entry.get("description"),entry.get("downlink_low"),entry.get("uplink_low")))
        unique[key]=entry
    result=list(unique.values())
    target=cache_path(data_dir,f"tx_{norad}.json")
    temp=target.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
    temp.replace(target)
    return result


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


def refresh_orbits(data_dir: Path, groups=None, progress=None) -> list[dict]:
    # Keep OMM as the preferred primary feed: unlike classical TLE, covers
    # NORAD > 99999; fetch TLE as requested for interoperability/fallback.
    omm, tle = None, None
    errors=[]
    try:omm=refresh_multi_omm(data_dir,groups,progress)
    except Exception as e:errors.append(f"OMM: {e}")
    try:tle=refresh_tle(data_dir)
    except Exception as e:errors.append(f"TLE: {e}")
    if omm:return omm
    if tle:return tle
    raise ConnectionError("; ".join(errors))


def load_orbits(data_dir: Path) -> list[dict]:
    omm=load_omm(data_dir)
    return omm if omm else load_tle(data_dir)
