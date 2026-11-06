"""Pure helpers for AOS reminders and progress estimates."""
from __future__ import annotations


def eta_seconds(completed, total, elapsed):
    """Estimate from completed items; never claim precision for 0-1 observations."""
    if completed < 2 or total <= 0 or elapsed <= 0:
        return None
    if completed >= total:
        return 0
    return max(0,round((total-completed)*elapsed/completed))


def format_duration(seconds):
    if seconds is None:
        return "Calculando…"
    seconds=max(0,int(seconds))
    h,remain=divmod(seconds,3600)
    m,s=divmod(remain,60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def selected_aos_alarm(passes,selected_norad,now,seen,seconds=30):
    """Return first upcoming AOS for selected NORAD only, once per passage."""
    if not selected_norad:
        return None
    for row in sorted((r for r in passes if str(r.get("id"))==str(selected_norad)),
                      key=lambda p:p["aos"]):
        remaining=(row["aos"]-now).total_seconds()
        key=str(selected_norad)+"@"+row["aos"].isoformat()
        if 0 < remaining <= seconds and key not in seen:
            return key,row,remaining
    return None


# ---------------------------------------------------------------- v1.6.0
# Avisos agendados por passagem (clique direito na tabela): 30 min e/ou 30 s antes do AOS.
from datetime import datetime as _dt, timedelta as _td

DEFAULT_LEADS = (1800, 30)


def _parse(value):
    return value if isinstance(value, _dt) else _dt.fromisoformat(str(value))


def find_alert(alerts, norad, aos, tolerance_s=300):
    """Mesma passagem = mesmo NORAD e AOS a menos de 5 min (órbita recalculada move o AOS)."""
    for a in alerts:
        if str(a.get("norad")) == str(norad) and abs((_parse(a["aos"]) - aos).total_seconds()) <= tolerance_s:
            return a
    return None


def add_alert(alerts, row, leads):
    """Agenda/atualiza avisos de uma passagem; leads em segundos antes do AOS."""
    found = find_alert(alerts, row["id"], row["aos"])
    if found is None:
        found = {"norad": str(row["id"]), "name": row.get("name", str(row["id"])), "fired": [], "leads": []}
        alerts.append(found)
    found.update({"aos": row["aos"].isoformat(), "los": row["los"].isoformat(),
                  "max_el": float(row.get("max_el", 0))})
    found["leads"] = sorted(set(int(x) for x in list(found.get("leads", [])) + list(leads)), reverse=True)
    return found


def remove_alert(alerts, norad, aos):
    found = find_alert(alerts, norad, aos)
    if found is not None:
        alerts.remove(found)
    return found is not None


def sync_with_passes(alerts, passes):
    """Acompanha o novo AOS/LOS calculado para a mesma passagem."""
    for a in alerts:
        for p in passes:
            if str(p.get("id")) == a["norad"] and abs((p["aos"] - _parse(a["aos"])).total_seconds()) <= 300:
                a["aos"], a["los"] = p["aos"].isoformat(), p["los"].isoformat()
                a["max_el"] = float(p.get("max_el", a.get("max_el", 0)))


def due_alerts(alerts, now):
    """Avisos a disparar agora (uma única vez cada) e remoção dos já terminados (após o LOS)."""
    due = []
    for a in list(alerts):
        aos, los = _parse(a["aos"]), _parse(a["los"])
        if now > los:
            alerts.remove(a)
            continue
        for lead in a.get("leads", []):
            if lead not in a["fired"] and now >= aos - _td(seconds=lead):
                a["fired"].append(lead)
                if now < aos + _td(seconds=5) or lead >= 60 and now < los:
                    due.append((a, lead))
    return due
