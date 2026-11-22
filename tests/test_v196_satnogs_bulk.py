"""v1.9.6 (22/11/2026): frequências do SatNOGS numa única consulta; IO-86 sempre na lista; LUČA-1 padrão."""
import json

from sat_tool import catalog


class Response:
    def __init__(self, payload, text=None):
        self.payload, self.text = payload, text or ""

    def raise_for_status(self):
        pass

    def json(self):
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


def test_bulk_transmitters_one_request_grouped_locally(tmp_path, monkeypatch):
    calls = []
    rows = [{"uuid": "a", "norad_cat_id": 40931, "downlink_low": 435880000},
            {"uuid": "b", "norad_cat_id": 40931, "downlink_low": 145825000},
            {"uuid": "c", "norad_cat_id": 25544, "downlink_low": 145800000},
            {"uuid": "d", "norad_cat_id": None}]

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        return Response(rows)
    monkeypatch.setattr(catalog.requests, "get", get)
    (tmp_path / "tx_7530.json").write_text('[{"uuid":"old"}]', encoding="utf-8")
    ids = [str(n) for n in range(1, 12536)] + ["40931", "25544", "7530"]
    pages = []
    stats = catalog.refresh_all_transmitters(tmp_path, ids, progress=lambda p, n: pages.append((p, n)))
    assert len(calls) == 1 and "satellite__norad_cat_id" not in calls[0][1]      # uma consulta, sem filtro
    assert stats["ok"] == 2 and stats["total"] == len(ids) and pages == [(1, 4)]
    assert len(catalog.load_transmitters(tmp_path, 40931)) == 2
    assert catalog.load_transmitters(tmp_path, 7530) == []                          # cache antigo zerado
    assert not (tmp_path / "tx_1.json").exists()                                   # sem milhares de arquivos vazios
    assert len(json.loads((tmp_path / "satnogs_transmitters.json").read_text(encoding="utf-8"))) == 4


def test_bulk_transmitters_cancel_keeps_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog.requests, "get", lambda *a, **k: Response([{"uuid": "x", "norad_cat_id": 1}]))
    (tmp_path / "tx_1.json").write_text('[{"uuid":"old"}]', encoding="utf-8")
    try:
        catalog.refresh_all_transmitters(tmp_path, ["1"], cancel=lambda: True)
    except InterruptedError:
        pass
    else:
        raise AssertionError("deveria cancelar")
    assert catalog.load_transmitters(tmp_path, 1) == [{"uuid": "old"}]


TLE0, TLE1, TLE2 = ("LAPAN-A2",
                    "1 40931U 15052B   26325.50000000  .00000500  00000-0  20000-4 0  9990",
                    "2 40931   6.0000 100.0000 0013000 200.0000 160.0000 14.76000000123456")


def test_catnr_falls_back_to_satnogs_tle(tmp_path, monkeypatch):
    def get(url, params=None, headers=None, timeout=None):
        if "celestrak" in url:
            return Response(None, "No GP data found")
        return Response([{"tle0": TLE0, "tle1": TLE1, "tle2": TLE2, "norad_cat_id": 40931}])
    monkeypatch.setattr(catalog.requests, "get", get)
    rows = catalog.refresh_catnr_omm(tmp_path, "40931")
    assert rows[0]["NORAD_CAT_ID"] == 40931 and rows[0]["OBJECT_NAME"] == "LAPAN-A2"
    assert abs(rows[0]["MEAN_MOTION"] - 14.76) < 1e-6
    assert "io86" in catalog.satellite_search_text("40931", rows[0])


def test_luca1_default_and_migration(tmp_path):
    from sat_tool.config import Config, DEFAULT_SATELLITES
    assert "67287" in DEFAULT_SATELLITES and "luca1" in catalog.satellite_search_text("67287", {"OBJECT_NAME": "X"})
    (tmp_path / "settings.json").write_text(json.dumps({"satellite_selection": ["25544"],
                                                      "default_satellites_v1316_migrated": True}), encoding="utf-8")
    cfg = Config(tmp_path)
    assert cfg.values["satellite_selection"] == ["25544", "67287"]
    cfg.values["satellite_selection"] = ["25544"]; cfg.save()
    assert Config(tmp_path).values["satellite_selection"] == ["25544"]         # desmarcar depois é respeitado


def test_gui_lists_default_satellites_and_updates_in_one_request():
    import os, subprocess, sys, textwrap
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.check_for_updates=lambda self:None
        gui.QMessageBox.information=staticmethod(lambda *a,**k:None)
        calls=[]
        def fake_all(data_dir,ids,progress=None,cancel=None):
            calls.append(len(ids)); progress(1,3)
            return {"total":len(ids),"ok":1,"no_data":len(ids)-1,"failed":[],"cancelled":False,
                    "rows":{"40931":[{"uuid":"a","norad_cat_id":40931}]}}
        gui.refresh_all_transmitters=fake_all
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); app.processEvents()
            w.background=lambda key,fn:None
            w.omm={"40931":{"OBJECT_NAME":"LAPAN-A2","CATEGORIES":["defaults"]},
                   "11111":{"OBJECT_NAME":"OTHER","CATEGORIES":["defaults2"]}}
            w.refresh_satellite_table()
            assert "40931" in w._catalog_filtered_ids and "11111" not in w._catalog_filtered_ids
            w.catalog_search.setText("io-86"); w.refresh_satellite_table()
            assert w._catalog_filtered_ids==["40931"]
            def bg(key,fn):
                data=fn(); app.processEvents(); w.background_result(key,data)
            w.background=bg
            w.refresh_catalog_transmitters()
            app.processEvents()
            assert calls==[2], calls
            assert w.pass_rows.get("40931")==[{"uuid":"a","norad_cat_id":40931}]
            assert "1/2 com canais" in w.catalog_progress.text(), w.catalog_progress.text()
        print("OK")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr


def test_named_default_hades_e2_marked_once():
    import os, subprocess, sys, textwrap
    source = textwrap.dedent(r'''
        import tempfile
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.check_for_updates=lambda self:None
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow(); app.processEvents()
            w.background=lambda key,fn:None
            w.config.values["satellite_selection"]=["25544"]
            w.populate_catalog([{"NORAD_CAT_ID":25544,"OBJECT_NAME":"ISS (ZARYA)"}])
            assert w.config.values["satellite_selection"]==["25544"] and w.config.values["named_defaults_applied"]==[]
            w.populate_catalog([{"NORAD_CAT_ID":25544,"OBJECT_NAME":"ISS (ZARYA)"},
                                {"NORAD_CAT_ID":99950,"OBJECT_NAME":"HADES E2"}])
            assert w.config.values["satellite_selection"]==["25544","99950"]
            w.config.values["satellite_selection"]=["25544"]
            w.populate_catalog([{"NORAD_CAT_ID":99950,"OBJECT_NAME":"HADES-E2"}])
            assert w.config.values["satellite_selection"]==["25544"]      # desmarcar depois é respeitado
        print("OK")
    ''')
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0 and "OK" in result.stdout, result.stdout + result.stderr
