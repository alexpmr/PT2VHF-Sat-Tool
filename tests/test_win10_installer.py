"""Regressions for installer rejecting Windows 10 in v1.1.0."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_qt6_installer_accepts_supported_windows10():
    script=(ROOT/"installer"/"setup.iss").read_text(encoding="utf-8")
    assert '#define MinTarget "10.0.17763"' in script
    assert 'AppName={#AppName} (Windows 10/11 x64)' in script
    assert 'ArchitecturesInstallIn64BitMode=x64compatible' in script
    assert 'MinVersion={#MinTarget}' in script
    assert 'Win11-x64' in script  # updater's release family still supported


def test_gha_windows10_1809_minimum_both_release_and_local_build():
    workflow=(ROOT/".github"/"workflows"/"windows.yml").read_text(encoding="utf-8")
    local=(ROOT/"scripts"/"Build-Windows.ps1").read_text(encoding="utf-8")
    assert "min_windows: '10.0.17763'" in workflow
    assert "$Minimum = '10.0.17763'" in local
    assert "min_windows: '6.1sp1'" not in workflow
    assert "target: Win7-x86" not in workflow
    assert "v1.3.14" in workflow
    assert "$Version = '1.3.14'" in local
    assert "10.0.22000" not in workflow
    assert "10.0.22000" not in local


def test_release_asset_names_stable_for_existing_updater():
    from sat_tool.updater import select_release
    stem="PT2VHF-Sat-Tool-v1.1.1-Win11-x64"
    data={"schema":1,"source":"https://www.pt2vhf.com","product":"sat","status":"available",
          "version":"1.1.1","files":[{"name":stem+"-Setup.exe","size":10,"sha256":"a"*64,
          "url":"https://www.pt2vhf.com/downloads/sat-tool/"+stem+"-Setup.exe"}]}
    update=select_release(data,"1.1.0","Win11-x64","Setup")
    assert update and update.asset_name==stem+"-Setup.exe"
