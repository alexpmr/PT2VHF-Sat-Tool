"""v1.9.1: o atualizador é filho do app e não pode se incluir na árvore que espera/encerra."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_helper_skips_itself_when_walking_the_app_process_tree():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    body = ps[ps.index("function Get-Descendants"):ps.index("function Wait-Exit")]
    assert re.search(r"ProcessId -eq \$PID\) \{ continue \}", body)
    assert "$id -ne $WaitPid -and $id -ne $PID" in ps


def test_ci_runs_the_helper_as_a_child_of_the_process_it_waits_for():
    wf = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert "'-WaitPid',`$PID" in wf and "Invoke-Ota $helper" in wf
