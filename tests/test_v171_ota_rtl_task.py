"""v1.7.1: OTA nunca executa a tarefa do driver RTL-SDR e informa o motivo exato da falha."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ota_skips_rtl_driver_task():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    assert '/MERGETASKS="!rtlsdr"' in ps and "'/OTA'" in ps
    iss = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")
    run_lines = [l for l in iss.splitlines() if "wdi-simple.exe" in l]
    assert run_lines and all("not IsOta" in l and "not WizardSilent" in l for l in run_lines)
    assert "function IsOta" in iss


def test_ota_reports_exit_code_and_retries():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    assert "Get-InnoExitMeaning" in ps and "-Tail 3" in ps and "$attempt -le 2" in ps


def test_failure_message_has_reason_and_manual_link():
    from sat_tool.updater import update_failure_message
    msg = update_failure_message("Instalador terminou com codigo 5 <x>")
    assert "codigo 5 &lt;x&gt;" in msg and "https://www.pt2vhf.com/sat" in msg
