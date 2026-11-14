"""v1.8.1 (bug 13/11/2026): "ao atualizar, baixa e fecha o programa. Nada mais acontece depois"."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_helper_logs_each_step_and_relaunches_when_setup_does_not():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    assert "PT2VHF-Sat-Tool-update-helper.log" in ps and "function Write-Step" in ps
    for step in ("inicio:", "app encerrado", "instalador: codigo", "resultado:", "abrindo:"):
        assert step in ps, step
    finally_part = ps[ps.index("} finally {"):]
    assert "Get-Process" in finally_part and "StartsWith($Destination" in finally_part
    assert "Start-Process -FilePath $launch -WorkingDirectory" in finally_part


def test_ci_simulates_ota_and_requires_program_reopened():
    wf = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert "Simular o OTA" in wf and "'-Mode','Setup'" in wf
    assert "o programa não reabriu depois da atualização" in wf


def test_helper_waits_only_for_the_installer_not_for_the_reopened_program():
    """Start-Process -Wait espera também os filhos: o Setup /OTA reabre o programa e o atualizador travava."""
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    line = next(l for l in script.splitlines() if "Start-Process -FilePath $Package" in l)
    assert "-Wait" not in line and "-PassThru" in line
    assert "WaitForExit(1800000)" in script
