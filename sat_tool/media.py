"""Best-effort licensed imagery from Wikimedia Commons, never guess a satellite photo."""
from __future__ import annotations
from html import escape, unescape
from pathlib import Path
import json
import re
import requests

API="https://commons.wikimedia.org/w/api.php"


def _plain(html):
    return unescape(re.sub(r"<[^>]+>", "", str(html or ""))).strip()


def find_photo(cache_dir: Path, name: str, norad: str):
    """Return photo metadata only if a matching licensed media file is found.

    A missing/ambiguous result returns None. No fake image or generic stock art.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path=cache_dir / ("photo_" + re.sub(r"[^0-9]", "", str(norad)) + ".json")
    if path.exists():
        try:
            item=json.loads(path.read_text(encoding="utf-8"))
            return item if item.get("url") else None
        except (ValueError,OSError):
            pass
    query=str(name).strip()
    if len(query)<4:return None
    response=requests.get(API,params={
        "action":"query","generator":"search","gsrsearch":'"'+query+'"',
        "gsrnamespace":6,"gsrlimit":8,"prop":"imageinfo",
        "iiprop":"url|extmetadata","iiurlwidth":340,"format":"json"
    },headers={"User-Agent":"PT2VHF-Sat-Tool/0.2.0 (amateur radio satellite tracker)"},
       timeout=12)
    response.raise_for_status()
    pages=(response.json().get("query") or {}).get("pages") or {}
    target=re.sub(r"[^a-z0-9]+","",query.casefold())
    for page in pages.values():
        title=page.get("title","")
        normalized=re.sub(r"[^a-z0-9]+","",title.casefold())
        if target not in normalized:
            continue
        info=(page.get("imageinfo") or [{}])[0]
        ext=info.get("extmetadata") or {}
        license_name=_plain((ext.get("LicenseShortName") or {}).get("value"))
        url=info.get("thumburl") or info.get("url")
        source=info.get("descriptionurl")
        if not (license_name and url and source):
            continue
        if not (url.startswith("https://upload.wikimedia.org/") and
                source.startswith("https://commons.wikimedia.org/")):
            continue
        result={"title":title,"url":url,"source":source,"license":license_name,
                "author":_plain((ext.get("Artist") or {}).get("value"))[:200],
                "norad":str(norad),"match":"nome do satélite no título (revisão recomendada)"}
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return result
    return None


def photo_html(photo):
    if photo is None:
        return "<html><body style='background:#0e1f34;color:#91aabc;font:12px Segoe UI'>Foto verificada indisponível; consultar operador/AMSAT.</body></html>"
    image=escape(photo["url"],quote=True);source=escape(photo["source"],quote=True)
    credit=escape((photo.get("author") or "Wikimedia Commons")[:85])
    lic=escape(photo["license"])
    return ("<html><body style='background:#0e1f34;color:#c8dfec;font:11px Segoe UI;margin:4px'>"
            "<a href='"+source+"' target='_blank'><img style='height:110px;max-width:95%;object-fit:contain' src='"+image+"'></a>"
            "<div>Foto: "+credit+" • "+lic+" (Commons)</div></body></html>")
