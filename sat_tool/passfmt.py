"""Formatação das horas de passagem (v1.6.0): AOS "Hoje/Amanhã/DD/MM/AA HH:MM", TCA/LOS só HH:MM."""
from __future__ import annotations

from datetime import date, datetime

WORDS = {"pt": ("Hoje", "Amanhã"), "en": ("Today", "Tomorrow"), "es": ("Hoy", "Mañana"),
         "fr": ("Aujourd’hui", "Demain"), "de": ("Heute", "Morgen"), "it": ("Oggi", "Domani")}


def _words(lang: str):
    return WORDS.get((lang or "pt").split("-")[0].lower(), WORDS["pt"])


def aos_label(aos: datetime, today: date | None = None, lang: str = "pt") -> str:
    local = aos.astimezone()
    today = today or datetime.now().astimezone().date()
    delta = (local.date() - today).days
    today_w, tomorrow_w = _words(lang)
    day = today_w if delta == 0 else tomorrow_w if delta == 1 else local.strftime("%d/%m/%y")
    return f"{day} {local:%H:%M}"


def time_label(moment: datetime | None, aos: datetime | None = None) -> str:
    if moment is None:
        return "—"
    local = moment.astimezone()
    text = f"{local:%H:%M}"
    if aos is not None:
        days = (local.date() - aos.astimezone().date()).days
        if days > 0:
            text += f" (+{days})"
    return text


def full_tooltip(moment: datetime | None) -> str:
    if moment is None:
        return ""
    return f"{moment.astimezone():%d/%m/%Y %H:%M:%S} local · {moment:%H:%M:%S} UTC"
