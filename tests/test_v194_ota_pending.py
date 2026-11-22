"""v1.9.4 (relato 21/11/2026: OTA 1.9.2 → 1.9.3 baixou, fechou e não instalou): diagnóstico na abertura seguinte."""
import json
import time
from pathlib import Path

from sat_tool import updater


def test_pending_update_without_result_reports_helper_log(tmp_path):
    updater.mark_update_pending("1.9.4", tmp_path)
    (tmp_path / updater.HELPER_LOG).write_text("\n".join(f"linha {i}" for i in range(20)), encoding="utf-8")
    target, lines = updater.check_pending_update("1.9.3", tmp_path)
    assert target == "1.9.4" and lines == [f"linha {i}" for i in range(12, 20)]
    assert not (tmp_path / updater.PENDING_FILE).exists()
    assert updater.check_pending_update("1.9.3", tmp_path) is None        # avisa uma vez só


def test_pending_update_is_silent_when_already_on_new_version_or_old(tmp_path):
    updater.mark_update_pending("1.9.4", tmp_path)
    assert updater.check_pending_update("1.9.4", tmp_path) is None
    (tmp_path / updater.PENDING_FILE).write_text(json.dumps({"version": "1.9.4", "at": time.time() - 3 * 86400}))
    assert updater.check_pending_update("1.9.3", tmp_path) is None
    updater.mark_update_pending("1.9.4", tmp_path)
    target, lines = updater.check_pending_update("1.9.3", tmp_path)       # sem log: atualizador nem rodou
    assert target == "1.9.4" and lines == []


def test_updater_kills_a_hung_old_app_instead_of_giving_up():
    script = Path("scripts/apply-update.ps1").read_text(encoding="utf-8")
    assert "Stop-Process -Id $WaitPid -Force" in script and "app nao fechou em 105 s" in script


def test_ci_exercises_ota_with_the_real_installed_program():
    wf = Path(".github/workflows/windows.yml").read_text(encoding="utf-8")
    assert "PT2VHF_SELFTEST_OTA" in wf
    app = Path("sat_tool/app.py").read_text(encoding="utf-8")
    assert 'os.environ.pop("PT2VHF_SELFTEST_OTA"' in app   # o programa reaberto não repete o teste
