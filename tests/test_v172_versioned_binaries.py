"""v1.7.2 (backlog 12/11/2026): nomes dos binários com a versão, sem quebrar o OTA."""
from pathlib import Path

from sat_tool.updater import rename_portable_to_version, versioned_portable_target

ROOT = Path(__file__).resolve().parents[1]


def test_installer_names_exe_with_version_and_removes_old_ones():
    iss = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")
    assert '#define AppExe "PT2VHF-Sat-Tool-v" + AppVersion + ".exe"' in iss
    assert 'DestName: "{#AppExe}"' in iss and 'Excludes: "\\PT2VHF-Sat-Tool.exe"' in iss
    assert '[InstallDelete]' in iss and '{app}\\PT2VHF-Sat-Tool.exe' in iss and '{app}\\PT2VHF-Sat-Tool-v*.exe' in iss
    # atalhos, ícone de desinstalação e execução final apontam para o EXE com versão
    assert 'Filename: "{app}\\PT2VHF-Sat-Tool.exe"' not in iss
    # OTA: o Setup abre o EXE novo (o atualizador antigo reabriria o caminho do EXE anterior)
    assert 'Filename: "{app}\\{#AppExe}"; Flags: nowait runasoriginaluser; Check: IsOta' in iss


def test_updater_relaunches_new_exe_only_when_needed():
    ps = (ROOT / "scripts" / "apply-update.ps1").read_text(encoding="utf-8")
    assert "$Mode -eq 'Setup' -and $status -eq 'ok'" in ps
    assert "-Filter 'PT2VHF-Sat-Tool*.exe'" in ps
    # v1.8.1: se o Setup não reabrir o programa, o atualizador abre o EXE mais novo da pasta
    assert "programa aberto pelo instalador" in ps and "if (-not $running)" in ps


def test_linux_and_macos_packages_carry_version():
    wf = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert 'mv dist/PT2VHF-Sat-Tool/PT2VHF-Sat-Tool "dist/PT2VHF-Sat-Tool/$app"' in wf
    assert 'mv dist/PT2VHF-Sat-Tool.app "dmg/$app.app"' in wf


def test_portable_exe_renamed_after_ota(tmp_path):
    old = tmp_path / "PT2VHF-Sat-Tool-v1.7.1-Win11-x64-Portable.exe"
    old.write_bytes(b"MZ")
    assert versioned_portable_target(old, "1.7.1") is None
    assert versioned_portable_target(tmp_path / "PT2VHF-Sat-Tool.exe", "1.7.2") is None  # Setup: nada a fazer
    new = rename_portable_to_version("1.7.2", exe_path=old)
    assert new == tmp_path / "PT2VHF-Sat-Tool-v1.7.2-Win11-x64-Portable.exe"
    assert new.read_bytes() == b"MZ" and not old.exists()
    # nome já ocupado: não sobrescreve
    other = tmp_path / "PT2VHF-Sat-Tool-v1.7.0-Win11-x64-Portable.exe"; other.write_bytes(b"x")
    assert rename_portable_to_version("1.7.2", exe_path=other) is None and other.exists()
