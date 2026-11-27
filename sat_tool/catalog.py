"""Catalog cache and network sources. OMM JSON supports six-digit NORAD IDs."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import requests

from . import __version__
from .config import DEFAULT_SATELLITES

# CelesTrak group feeds return batches; per-NORAD requests only for missing default satellites.
DEFAULT_GROUPS = ("amateur", "stations", "cubesat", "starlink", "oneweb",
                  "weather", "science", "visual", "amsat", "r4uab")
# v1.8.1: fontes extras em TLE texto (3 linhas), tratadas como categorias como as da CelesTrak
TLE_SOURCES = {"amsat": "https://www.amsat.org/amsat/ftp/keps/current/nasabare.txt",
               "r4uab": "https://www.r4uab.ru/satonline.txt"}
ALL_GROUPS = DEFAULT_GROUPS + ("active",)
CELESTRAK_OMM = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=json"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"
SATNOGS_TRANSMITTERS = "https://db.satnogs.org/api/transmitters/"
HEADERS = {"User-Agent": f"PT2VHF-Sat-Tool/{__version__} (radio amateur tracking tool)",  # v1.9.8: era fixo em 1.3.0
           "Accept": "application/json"}
ALIASES = {"27607": ("SO-50", "SO50", "SAUDISAT 1C", "SAUDISAT-1C"),
           "25544": ("ISS", "ARISS", "ZARYA"),
           "24278": ("FO-29", "FO29", "JAS-2"),
           "44909": ("RS-44", "RS44", "DOSAAF-85"),
           "7530": ("AO-7", "AO7", "OSCAR 7"),
           "40931": ("IO-86", "IO86", "LAPAN-A2"),
           "59112": ("SONATE-2", "SONATE2"),
           "67287": ("LUCA-1", "LUČA-1", "LUCA1", "RS90S")}


def normalized_satellite_search(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD",str(text).casefold())
                   if c.isalnum() and not unicodedata.combining(c))


def satellite_search_text(ident, orbit):
    fields=[str(ident), str(orbit.get("OBJECT_NAME",""))]+list(ALIASES.get(str(ident),()))
    fields+=[str(n) for n in orbit.get("ALT_NAMES",[])]
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
            if existing:
                # o primeiro nome (CelesTrak) fica; nomes de outras fontes (AMSAT, R4UAB) viram apelidos de busca
                names=[existing.get("OBJECT_NAME"),row.get("OBJECT_NAME")]+list(existing.get("ALT_NAMES",[]))
                names=[str(n) for n in dict.fromkeys(names) if n]
                if names:
                    winner["OBJECT_NAME"]=names[0]
                    if names[1:]:winner["ALT_NAMES"]=names[1:]
            output[ident]=winner
    return list(output.values())


def refresh_group_omm(data_dir, group):
    if group not in ALL_GROUPS:
        raise ValueError("Categoria orbital não reconhecida")
    if group in TLE_SOURCES:
        response=requests.get(TLE_SOURCES[group],headers={**HEADERS,"Accept":"text/plain"},timeout=45)
        response.raise_for_status()
        objects=[tle_to_omm(row) for row in parse_tle(response.text)]
    else:
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


SATNOGS_TLE = "https://db.satnogs.org/api/tle/"


def _satnogs_tle_omm(ident):
    """v1.9.7: reserva quando a CelesTrak não tem o NORAD (ex.: "No GP data found"): TLE do SatNOGS DB."""
    response=requests.get(SATNOGS_TLE,params={"format":"json","norad_cat_id":ident},headers=HEADERS,timeout=30)
    response.raise_for_status()
    rows=response.json()
    if isinstance(rows,dict):
        rows=rows.get("results",[])
    objects=[]
    for row in rows if isinstance(rows,list) else []:
        if not isinstance(row,dict):
            continue
        text="\n".join(str(row.get(k) or "") for k in ("tle0","tle1","tle2"))
        for parsed in parse_tle(text):
            if str(parsed["NORAD_CAT_ID"])==str(ident):
                objects.append(tle_to_omm(parsed))
    if not objects:
        raise ValueError("SatNOGS sem TLE para NORAD "+str(ident))
    return objects[:1]


def refresh_catnr_omm(data_dir, ident):
    """OMM de um único NORAD, com cache de 2 h como os grupos. v1.9.7: se a CelesTrak não tiver, usa o SatNOGS."""
    ident=str(int(ident))
    file=cache_path(data_dir,"catnr_"+ident+".json")
    hours=age_hours(data_dir,file.name)
    if file.exists() and hours is not None and hours<2:
        return json.loads(file.read_text(encoding="utf-8"))
    try:
        try:
            response=requests.get("https://celestrak.org/NORAD/elements/gp.php",
                                  params={"CATNR":ident,"FORMAT":"json"},headers=HEADERS,timeout=30)
            response.raise_for_status()
            try:
                objects=response.json()
            except ValueError:
                raise ValueError("CelesTrak sem dados para NORAD "+ident+": "+response.text.strip()[:60])
            if not isinstance(objects,list) or not objects or \
                    not all(isinstance(o,dict) and "NORAD_CAT_ID" in o for o in objects):
                raise ValueError("OMM inválido para NORAD "+ident)
        except Exception as celestrak_error:
            try:
                objects=_satnogs_tle_omm(ident)
            except Exception as satnogs_error:
                raise ValueError(f"{celestrak_error}; {satnogs_error}")
    except Exception:
        if file.exists():
            return json.loads(file.read_text(encoding="utf-8"))
        raise
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
        try:
            old=load_group_omm(data_dir,group)
            hours=age_hours(data_dir,"group_"+group+".json")
            if old and hours is not None and hours<2:
                all_data[group]=old  # CelesTrak group cache minimum 2h
            else:
                all_data[group]=refresh_group_omm(data_dir,group)
        except Exception as exc:
            errors.append(group+": "+str(exc))
            cached=load_group_omm(data_dir,group)
            if cached:all_data[group]=cached
        if progress:progress(index,len(groups),group,len(all_data.get(group,[])),len(errors))
    # Satélites padrão fora dos grupos baixados são buscados pelo NORAD (v1.3.16).
    present={str(row.get("NORAD_CAT_ID")) for rows in all_data.values() for row in rows if isinstance(row,dict)}
    extra=[]
    for ident in DEFAULT_SATELLITES:
        if ident in present:
            continue
        try:
            extra+=refresh_catnr_omm(data_dir,ident)
        except Exception as exc:
            errors.append("NORAD "+ident+": "+str(exc))
    if extra:
        all_data["defaults"]=extra
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


def _fetch_transmitter_pages(params, max_pages=25, progress=None, cancel=None):
    """Baixa todas as páginas de /api/transmitters/ (lista simples ou paginada). Nunca devolve página parcial."""
    from urllib.parse import urljoin, urlparse
    rows=[]
    url=SATNOGS_TRANSMITTERS
    seen=set()
    for page in range(max_pages):
        if cancel is not None and cancel():
            raise InterruptedError("Atualização cancelada")
        if url in seen:raise ValueError("Paginação SatNOGS cíclica")
        seen.add(url)
        response=requests.get(url,params=params,headers=HEADERS,timeout=60 if params and "satellite__norad_cat_id" not in params else 25)
        response.raise_for_status()
        result=response.json()
        if isinstance(result,list):
            current,nxt=result,None
        elif isinstance(result,dict):
            current,nxt=result.get("results",[]),result.get("next")
        else:raise ValueError("Resposta de transponders inválida")
        if not isinstance(current,list):raise ValueError("Registros de transponder inválidos")
        rows.extend(current)
        if progress is not None:progress(page+1,len(rows))
        if not nxt:break
        url=urljoin(SATNOGS_TRANSMITTERS,nxt)
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.hostname!="db.satnogs.org":
            raise ValueError("Paginação SatNOGS encaminhou para domínio não autorizado")
        params=None
    else:raise ValueError("Paginação SatNOGS excedeu o limite")
    return rows


def _unique_transmitters(rows):
    unique={}
    for entry in rows:
        if not isinstance(entry,dict):raise ValueError("Transponder em formato inválido")
        key=str(entry.get("uuid") or entry.get("id") or (entry.get("description"),entry.get("downlink_low"),entry.get("uplink_low")))
        unique[key]=entry
    return list(unique.values())


def _write_transmitters(data_dir: Path, norad: int, rows):
    target=cache_path(data_dir,f"tx_{norad}.json")
    temp=target.with_suffix(".tmp")
    temp.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    temp.replace(target)


def refresh_transmitters(data_dir: Path, norad: int):
    # Some API deployments paginate results; never persist partial pages.
    result=_unique_transmitters(_fetch_transmitter_pages({"format":"json","satellite__norad_cat_id":norad}))
    _write_transmitters(data_dir,norad,result)
    return result


def refresh_all_transmitters(data_dir: Path, ids, progress=None, cancel=None) -> dict:
    """v1.9.7: UMA consulta ao SatNOGS com todos os transmissores (alguns MB), em vez de uma por satélite.

    Antes eram ~12.500 requisições sequenciais (horas, e o SatNOGS limita/recusa consultas em sequência).
    Grava tx_<norad>.json só para quem tem transmissores; um cache antigo de quem deixou de ter é zerado.
    Satélites sem transmissor não ganham arquivo vazio (o catálogo tem milhares deles).
    """
    rows=_fetch_transmitter_pages({"format":"json"},max_pages=200,progress=progress,cancel=cancel)
    by_norad={}
    for entry in _unique_transmitters(rows):
        norad=entry.get("norad_cat_id")
        try:
            norad=int(norad)
        except (TypeError,ValueError):
            continue
        by_norad.setdefault(norad,[]).append(entry)
    cache_path(data_dir,"satnogs_transmitters.json")
    temp=data_dir/"satnogs_transmitters.tmp"
    temp.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    temp.replace(data_dir/"satnogs_transmitters.json")
    stats={"total":0,"ok":0,"no_data":0,"failed":[],"cancelled":False,"rows":{},"downloaded":len(rows)}
    for ident in ids:
        try:
            norad=int(ident)
        except (TypeError,ValueError):
            continue
        stats["total"]+=1
        found=by_norad.get(norad,[])
        if found:
            _write_transmitters(data_dir,norad,found)
            stats["ok"]+=1
            stats["rows"][str(ident)]=found
        else:
            stats["no_data"]+=1
            if (data_dir/f"tx_{norad}.json").exists():
                _write_transmitters(data_dir,norad,[])
    return stats


def load_transmitters(data_dir: Path, norad: int):
    file = cache_path(data_dir, f"tx_{norad}.json")
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else []


def age_hours(data_dir: Path, name: str) -> float | None:
    file = data_dir / name
    if not file.exists():
        return None
    return (datetime.now(timezone.utc).timestamp() - file.stat().st_mtime) / 3600


_ALPHA5 = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # sem I e O, como no padrão Alpha-5 do Space Force


def tle_catalog_number(field: str) -> int | None:
    """Número de catálogo do TLE, inclusive Alpha-5 ("A0084" → 100084, "Z9999" → 339999). None se inválido."""
    field = field.strip()
    if field.isdigit():
        return int(field)
    if len(field) == 5 and field[0] in _ALPHA5 and field[1:].isdigit():
        return (_ALPHA5.index(field[0]) + 10) * 10000 + int(field[1:])
    return None


def parse_tle(text: str) -> list[dict]:
    """Parse 3LE and 2LE feeds. v1.9.4: aceita Alpha-5 (catálogo acima de 99999); uma linha inválida é
    pulada em vez de derrubar a fonte inteira (antes um "A0084" no satonline.txt da R4UAB derrubava tudo)."""
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
            norad=tle_catalog_number(one[2:7])
            if norad is None:
                i+=2
                continue
            result.append({"NORAD_CAT_ID":norad,"OBJECT_NAME":name or f"NORAD {norad}",
                           "TLE_LINE1":one,"TLE_LINE2":two})
            i+=2
        else:
            i+=1
    return result


def _tle_float(text):
    """Campo TLE com ponto decimal implícito e expoente (" 12345-4" → 0.12345e-4, "-11606-4" → -0.11606e-4)."""
    text=text.strip()
    if not text:
        return 0.0
    if "." in text:
        return float(text)
    sign=-1.0 if text[0]=="-" else 1.0
    body=text.lstrip("+-")
    if len(body)>=2 and body[-2] in "+-":
        return sign*float("0."+body[:-2]+"e"+body[-2:])
    return sign*float("0."+body)


def tle_to_omm(row):
    """Linha TLE → campos OMM (mesmos nomes da CelesTrak); as linhas originais seguem para a propagação."""
    from datetime import timedelta
    one,two=row["TLE_LINE1"],row["TLE_LINE2"]
    year=int(one[18:20]);year+=2000 if year<57 else 1900
    epoch=datetime(year,1,1,tzinfo=timezone.utc)+timedelta(days=float(one[20:32])-1)
    designator=one[9:17].strip()
    object_id=""
    if len(designator)>=5 and designator[:2].isdigit():
        launch_year=int(designator[:2]);launch_year+=2000 if launch_year<57 else 1900
        object_id=f"{launch_year}-{designator[2:]}"
    return {**row,
            "OBJECT_NAME":row.get("OBJECT_NAME") or f"NORAD {row['NORAD_CAT_ID']}",
            "OBJECT_ID":object_id,"NORAD_CAT_ID":int(row["NORAD_CAT_ID"]),
            "EPOCH":epoch.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "MEAN_MOTION":float(two[52:63]),"ECCENTRICITY":float("0."+two[26:33].strip()),
            "INCLINATION":float(two[8:16]),"RA_OF_ASC_NODE":float(two[17:25]),
            "ARG_OF_PERICENTER":float(two[34:42]),"MEAN_ANOMALY":float(two[43:51]),
            "EPHEMERIS_TYPE":0,"CLASSIFICATION_TYPE":one[7] if one[7].strip() else "U",
            "ELEMENT_SET_NO":int(one[64:68] or 0),"REV_AT_EPOCH":int(two[63:68] or 0),
            "BSTAR":_tle_float(one[53:61]),"MEAN_MOTION_DOT":float(one[33:43]),
            "MEAN_MOTION_DDOT":_tle_float(one[44:52])}


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
