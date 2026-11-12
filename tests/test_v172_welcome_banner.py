"""v1.7.2 (backlog 12/11/2026): abertura com o banner "Powered by www.PT2VHF.com"."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_welcome_banner_is_shipped_and_used():
    banner = ROOT / "assets" / "branding" / "welcome-banner.jpg"
    assert banner.exists() and banner.stat().st_size < 400_000
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert "branding_asset('welcome-banner.jpg')" in app and "https://www.pt2vhf.com" in app and "'Fechar'" in app
    for path in ("scripts/Build-Windows.ps1", ".github/workflows/windows.yml"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert text.count("welcome-banner.jpg") == text.count("assets/branding/icon-256.png;assets/branding") \
            + text.count("assets/branding/icon-256.png:assets/branding") + (1 if path.endswith(".yml") else 0), path
