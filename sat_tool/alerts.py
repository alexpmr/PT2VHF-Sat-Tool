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
