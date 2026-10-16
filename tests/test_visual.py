"""The map MUST remain operational without external map tile requests."""
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def test_vector_map_offline_and_public_domain_attribution():
    html=(ROOT/"sat_tool"/"map.html").read_text(encoding="utf-8")
    assert "MAPA VETORIAL OFFLINE" in html
    assert "NATURAL EARTH" in html
    assert 'id="land"' in html
    assert 'id="overlay"' in html
    assert "window.updateOrbit" in html
    assert "window.fitStation" in html
    assert "tile.openstreetmap.org" not in html
    assert "https://unpkg.com" not in html
    assert len(html) > 25000  # bundled coastline outlines
    assert "window.zoom" in html and "wheel" in html


def test_branded_all_windows_build_flavors():
    script=(ROOT/".github"/"workflows"/"windows.yml").read_text(encoding="utf-8")
    assert script.count("--icon 'assets/branding/app-icon.ico'") == 2
    assert script.count("'assets/branding/icon-256.png;assets/branding'") == 2
    assert "Generate and verify Windows brand icons" in script
    assert "Portable ONEFILE EXE" in script
    assert "Win7-x86" in script and "Win11-x64" in script
    assert "v1.3.3" in script


def test_installation_icon_and_brand_assets_exist():
    source=(ROOT/"installer"/"setup.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=" in source
    assert "app-icon.ico" in source
    assert (ROOT/"assets"/"branding"/"app-icon.svg").exists()
    assert (ROOT/"assets"/"branding"/"logo-horizontal.svg").exists()


def test_brand_application_maintains_caller_data():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "def branding_asset(" in app
    assert "self.setWindowIcon(QIcon" in app
    assert "self.cat_rx.setText(" in app
    assert "self.cat_tx.setText(" in app
    assert "self.sat_list.setRowCount(" in app
