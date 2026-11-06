"""v1.6.0: rótulos Hoje/Amanhã, TCA/LOS só hora, avisos agendados por passagem."""
from datetime import date, datetime, timedelta, timezone

from sat_tool import alerts, passfmt

T0 = datetime(2026, 11, 6, 21, 50, tzinfo=timezone.utc)


def test_aos_labels_today_tomorrow_date_and_midnight_crossing():
    local_today = T0.astimezone().date()
    assert passfmt.aos_label(T0, local_today).startswith("Hoje ")
    assert passfmt.aos_label(T0 + timedelta(days=1), local_today).startswith("Amanhã ")
    later = T0 + timedelta(days=2)
    assert passfmt.aos_label(later, local_today).startswith(later.astimezone().strftime("%d/%m/%y"))
    assert passfmt.aos_label(T0, local_today, lang="en").startswith("Today ")
    aos = datetime.combine(local_today, datetime.min.time()).astimezone() + timedelta(hours=23, minutes=58)
    assert passfmt.time_label(aos + timedelta(minutes=5), aos).endswith("(+1)")
    assert ":" in passfmt.time_label(aos) and "/" not in passfmt.time_label(aos)


def row(minutes=40, norad="27607"):
    aos = T0 + timedelta(minutes=minutes)
    return {"id": norad, "name": "SO-50", "aos": aos, "los": aos + timedelta(minutes=10), "max_el": 42}


def test_alerts_fire_once_30min_and_30s_and_follow_recomputed_aos():
    store = []
    p = row()
    alerts.add_alert(store, p, (1800, 30))
    assert alerts.due_alerts(store, T0) == []
    first = alerts.due_alerts(store, p["aos"] - timedelta(minutes=29))
    assert [lead for _, lead in first] == [1800]
    assert alerts.due_alerts(store, p["aos"] - timedelta(minutes=10)) == []
    moved = dict(p, aos=p["aos"] + timedelta(seconds=40), los=p["los"] + timedelta(seconds=40))
    alerts.sync_with_passes(store, [moved])
    assert alerts.due_alerts(store, p["aos"] - timedelta(seconds=20)) == []  # novo AOS: ainda faltam 60 s
    second = alerts.due_alerts(store, moved["aos"] - timedelta(seconds=25))
    assert [lead for _, lead in second] == [30]
    alerts.due_alerts(store, moved["los"] + timedelta(seconds=1))
    assert store == []  # removido após o LOS


def test_add_remove_and_late_30s_not_fired():
    store = []
    p = row(minutes=1)
    alerts.add_alert(store, p, (30,))
    assert alerts.remove_alert(store, "27607", p["aos"]) and store == []
    alerts.add_alert(store, p, (30,))
    assert alerts.due_alerts(store, p["aos"] + timedelta(minutes=2)) == []  # passagem já iniciada: sem contagem
