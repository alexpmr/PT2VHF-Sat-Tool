"""Informações do satélite para o popup flutuante (mapa, seletor e catálogo).

Fontes: SatNOGS DB (nomes, imagem, status, lançamento, operador, decodificadores) e o resumo
da Wikipedia no idioma da interface. Tudo em cache local (satinfo/<NORAD>.json e imagem), para
funcionar offline com o que já foi visto. Nenhuma chamada de rede ocorre na thread da GUI.
"""
from __future__ import annotations

import base64
import html
import json
import time
from pathlib import Path
from typing import Optional

import requests

HEADERS = {"User-Agent": "PT2VHF-Sat-Tool (radio amateur tracking tool)", "Accept": "application/json"}
SATNOGS = "https://db.satnogs.org/api/satellites/"
SATNOGS_MEDIA = "https://db-satnogs.freetls.fastly.net/media/"
MAX_AGE_S = 7 * 86400
STATUS_PT = {"alive": "ativo", "dead": "inativo", "re-entered": "reentrou na atmosfera",
             "future": "ainda não lançado", "in orbit": "em órbita"}


def cache_dir(data_dir: Path) -> Path:
    d = Path(data_dir) / "satinfo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cached(data_dir: Path, norad: str) -> Optional[dict]:
    try:
        return json.loads((cache_dir(data_dir) / f"{norad}.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _wikipedia_summary(name: str, lang: str) -> dict:
    for wiki in dict.fromkeys([lang, "en"]):
        try:
            r = requests.get(f"https://{wiki}.wikipedia.org/w/api.php",
                             params={"action": "query", "list": "search", "srsearch": f"{name} satellite",
                                     "srlimit": 1, "format": "json"}, headers=HEADERS, timeout=12)
            hits = r.json().get("query", {}).get("search", [])
            if not hits:
                continue
            title = hits[0]["title"]
            s = requests.get(f"https://{wiki}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}",
                             headers=HEADERS, timeout=12).json()
            if s.get("extract"):
                return {"title": s.get("title", title), "extract": s["extract"],
                        "url": s.get("content_urls", {}).get("desktop", {}).get("page", "")}
        except Exception:
            continue
    return {}


def fetch_info(data_dir: Path, norad: str, name: str, lang: str = "pt", force: bool = False) -> dict:
    """Busca (ou reaproveita) as informações. Chamar fora da thread da GUI."""
    norad = str(norad)
    cached = load_cached(data_dir, norad)
    if cached and not force and time.time() - cached.get("fetched", 0) < MAX_AGE_S and cached.get("lang") == lang:
        return cached
    info = dict(cached or {}, norad=norad, name=name, lang=lang)
    try:
        r = requests.get(SATNOGS, params={"norad_cat_id": norad, "format": "json"}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        sats = r.json()
        if sats:
            s = sats[0]
            info.update({k: s.get(k) for k in ("name", "names", "status", "launched", "deployed", "decayed",
                                               "operator", "countries", "website", "reception_status")})
            info["decoders"] = [t.get("decoder") for t in s.get("telemetries") or [] if t.get("decoder")]
            if s.get("image"):
                img_url = SATNOGS_MEDIA + s["image"]
                info["image_url"] = img_url
                try:
                    data = requests.get(img_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15).content
                    if 0 < len(data) < 3_000_000:
                        ext = Path(s["image"]).suffix.lower() or ".jpg"
                        path = cache_dir(data_dir) / f"{norad}{ext}"
                        path.write_bytes(data)
                        info["image_file"] = str(path)
                except Exception:
                    pass
    except Exception as exc:
        info["error"] = str(exc)
    wiki = _wikipedia_summary(info.get("name") or name, lang)
    if wiki:
        info["wiki"] = wiki
    info["fetched"] = time.time()
    try:
        (cache_dir(data_dir) / f"{norad}.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return info


def _date(value) -> str:
    return str(value)[:10] if value else "—"


def image_data_uri(info: dict, limit: int = 400_000) -> str:
    path = info.get("image_file")
    try:
        data = Path(path).read_bytes() if path else b""
    except OSError:
        data = b""
    if data and len(data) <= limit:
        mime = "image/png" if str(path).lower().endswith(".png") else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return info.get("image_url", "")


def info_html(info: Optional[dict], *, name: str, norad: str, live: Optional[dict] = None,
              transponders: Optional[list[dict]] = None, next_pass: Optional[str] = None,
              for_qt: bool = True, max_extract: int = 420) -> str:
    """HTML compacto do popup. for_qt usa imagem em arquivo local (tooltip do Qt)."""
    e = html.escape
    info = info or {}
    parts = ["<div style='max-width:380px'>"]
    if for_qt and info.get("image_file"):
        parts.append(f"<img src='file:///{e(str(info['image_file']).replace(chr(92), '/'))}' width='160'><br>")
    elif not for_qt:
        uri = image_data_uri(info)
        if uri:
            parts.append(f"<img src='{e(uri)}' style='max-width:180px;max-height:120px;float:right;margin:0 0 6px 8px'>")
    parts.append(f"<b style='font-size:14px'>{e(info.get('name') or name)}</b> · NORAD {e(str(norad))}")
    if info.get("names"):
        parts.append(f"<br><i>{e(str(info['names']))}</i>")
    status = STATUS_PT.get(str(info.get("status") or "").lower(), info.get("status") or "")
    meta = [f"Status: {e(status)}" if status else "",
            f"Recepção SatNOGS: {e(str(info.get('reception_status')))}" if info.get("reception_status") else "",
            f"Lançamento: {_date(info.get('launched'))}" if info.get("launched") else "",
            f"Operador: {e(str(info.get('operator')))}" if info.get("operator") not in (None, "", "None") else "",
            f"Países: {e(str(info.get('countries')))}" if info.get("countries") else ""]
    meta = [m for m in meta if m]
    if meta:
        parts.append("<br>" + " · ".join(meta))
    if live:
        parts.append(f"<br><b>Agora:</b> elev. {live.get('elevation', 0):.1f}° · az. {live.get('azimuth', 0):.0f}° · "
                     + ("<span style='color:#5ae1a6'>visível</span>" if live.get("visible") else "abaixo do horizonte"))
    if next_pass:
        parts.append(f"<br><b>Próxima passagem:</b> {e(next_pass)}")
    if transponders:
        lines = []
        for t in transponders[:5]:
            up = f" ↑ {t['uplink'] / 1e6:.3f}" if t.get("uplink") else ""
            lines.append(f"{e(str(t.get('mode', '')))} ↓ {t['downlink'] / 1e6:.3f}{up} MHz"
                         + (" (inversor)" if t.get("inverted") else ""))
        parts.append("<br><b>Canais:</b><br>" + "<br>".join(lines))
    if info.get("decoders"):
        parts.append(f"<br><b>Telemetria:</b> decodificador {e(', '.join(info['decoders']))}")
    wiki = info.get("wiki") or {}
    if wiki.get("extract"):
        text = wiki["extract"]
        if len(text) > max_extract:
            text = text[:max_extract].rsplit(" ", 1)[0] + "…"
        source = f"<br><span style='color:#8fb3c7'>Fonte: Wikipedia · {e(wiki.get('title', ''))}</span>"
        parts.append(f"<p style='margin-top:6px'>{e(text)}{source}</p>")
    if not info:
        parts.append("<br><i>Buscando informações…</i>")
    parts.append("</div>")
    return "".join(parts)
