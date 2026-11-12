"""v1.6.0: OTA conclui (processos do mapa, instalador, resultado) e conta um único download."""
from pathlib import Path

from sat_tool import updater

ROOT = Path(__file__).resolve().parents[1]


def test_script_waits_process_tree_kills_only_app_children_and_reports():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    assert "Get-Descendants" in ps and "Win32_Process" in ps and "ParentProcessId" in ps
    assert "QtWebEngineProcess" in ps and "StartsWith($Destination" in ps
    for flag in ("/SILENT", "/SP-", "/CLOSEAPPLICATIONS", "/LOG=", "/DIR="):
        assert flag in ps
    assert "PT2VHF-Sat-Tool-update-result.txt" in ps
    assert ps.index("finally") < ps.index("Start-Process -FilePath $launch")  # reabre (falha ou portátil; Setup ok: o instalador abre)


def test_installer_detects_running_app_and_webengine_files():
    iss = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")
    assert "AppMutex=PT2VHF_Sat_Tool_Running" in iss
    assert "CloseApplicationsFilter=" in iss and "*.pak" in iss
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert 'CreateMutexW(None,False,"PT2VHF_Sat_Tool_Running")' in app
    assert "os._exit(int(code or 0))" in app and "self.map.deleteLater()" in app


def test_update_args_and_result_roundtrip(tmp_path):
    args = updater.update_script_args(Path("h.ps1"), pid=42, package=Path("S.exe"), destination=Path("C:/A"),
                                      exe=Path("C:/A/PT2VHF-Sat-Tool.exe"), portable=False, version="1.6.0")
    assert args[args.index("-Version") + 1] == "1.6.0" and args[args.index("-Mode") + 1] == "Setup"
    (tmp_path / "PT2VHF-Sat-Tool-update-result.txt").write_text("\ufeffok\n1.6.0\nAtualizado\n", encoding="utf-8")
    assert updater.read_update_result(tmp_path) == ("ok", "1.6.0", "Atualizado")
    assert updater.read_update_result(tmp_path) is None  # lido uma única vez


def test_ota_download_is_exactly_one_get_without_range(monkeypatch):
    import hashlib
    payload = b"MZ" + b"x" * 1000
    calls = []

    class Resp:
        is_redirect = False
        headers = {"Content-Length": str(len(payload))}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): yield payload

    def fake_get(url, **kw):
        calls.append((url, kw.get("headers", {})))
        return Resp()
    monkeypatch.setattr(updater.requests, "get", fake_get)
    monkeypatch.setattr(updater.requests, "head", lambda *a, **k: (_ for _ in ()).throw(AssertionError("HEAD")))
    name = "PT2VHF-Sat-Tool-v9.9.9-Win11-x64-Setup.exe"
    upd = updater.AvailableUpdate("9.9.9", "", False, name, "https://www.pt2vhf.com/downloads/sat-tool/" + name,
                                  hashlib.sha256(payload).hexdigest(), len(payload), "https://www.pt2vhf.com/sat")
    updater.download_update(upd)
    assert len(calls) == 1 and "Range" not in calls[0][1]
