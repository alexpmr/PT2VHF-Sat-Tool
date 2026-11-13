"""v1.8.0 (backlog 13/11/2026): indicativo enviado na consulta de versão, para a lista de usuários no site."""
from sat_tool import updater


def test_callsign_param_and_url():
    assert updater.callsign_param(" py2xyz ") == "PY2XYZ"
    assert updater.callsign_param("CT/PY2XYZ/P") == "CT/PY2XYZ/P"
    for bad in ("", None, "PY", "123", "PY2XYZ<script>", "A" * 20, "PY2 XYZ"):
        assert updater.callsign_param(bad) == "", bad
    assert updater.update_url("py2xyz") == updater.UPDATE_API + "&call=PY2XYZ"
    assert updater.update_url("CT/PY2XYZ") == updater.UPDATE_API + "&call=CT%2FPY2XYZ"
    assert updater.update_url(None) == updater.UPDATE_API


def test_check_for_update_sends_only_the_callsign(monkeypatch):
    seen = {}

    class R:
        is_redirect = False
        content = b"{}"
        def __init__(self, url): self.url = url
        def raise_for_status(self): pass
        def json(self): return {"schema": 1, "products": {}}

    def fake_get(url, **kw):
        seen["url"], seen["kw"] = url, kw
        return R(url)
    monkeypatch.setattr(updater.requests, "get", fake_get)
    monkeypatch.setattr(updater, "select_release", lambda *a, **k: None)
    updater.check_for_update("1.8.0", "Win11-x64", "Setup", callsign="PY2XYZ")
    assert seen["url"] == updater.UPDATE_API + "&call=PY2XYZ"
    assert "params" not in seen["kw"] and "data" not in seen["kw"]
    updater.check_for_update("1.8.0", "Win11-x64", "Setup")
    assert seen["url"] == updater.UPDATE_API


def test_app_sends_callsign_only_when_enabled_and_station_set():
    from sat_tool.app import MainWindow

    class W:
        update_callsign = MainWindow.update_callsign
    w = W()
    w.config = type("C", (), {})()
    w.config.values = {"callsign": "py2xyz", "lat": "-23.5", "lon": "-46.6", "share_callsign": True}
    assert w.update_callsign() == "PY2XYZ"
    w.config.values["share_callsign"] = False
    assert w.update_callsign() is None
    w.config.values.update(share_callsign=True, lat="")
    assert w.update_callsign() is None      # estação não configurada: não manda o indicativo de exemplo
