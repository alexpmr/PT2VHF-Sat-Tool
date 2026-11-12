"""v1.5.0: popup de informações do satélite (offline/parcial) e boas-vindas."""
import json
from pathlib import Path

from sat_tool import satinfo

ROOT = Path(__file__).resolve().parents[1]


def test_info_html_complete_partial_and_offline(tmp_path):
    info = {"name": "SAUDISAT 1C", "names": "SO-50", "status": "in orbit", "launched": "2002-12-20T00:00:00Z",
            "countries": "SA", "decoders": [], "wiki": {"title": "SaudiSat 1C", "extract": "x " * 400}}
    html = satinfo.info_html(info, name="SO-50", norad="27607",
                             live={"elevation": 42.0, "azimuth": 120, "visible": True},
                             transponders=[{"mode": "FM", "downlink": 436_795_000, "uplink": 145_850_000}],
                             next_pass="06/11 21:00 · máx 60° · 12:00 · ★★★★☆")
    assert "SO-50" in html and "em órbita" in html and "visível" in html and "★★★★☆" in html
    assert "436.795" in html and "Fonte: Wikipedia" in html and "<a " not in html
    assert len(html) < 4000
    assert "Buscando informações" in satinfo.info_html(None, name="X", norad="1")
    (tmp_path / "satinfo").mkdir()
    (tmp_path / "satinfo" / "27607.json").write_text(json.dumps(info))
    assert satinfo.load_cached(tmp_path, "27607")["names"] == "SO-50"


def test_map_has_hover_popup_and_welcome_text():
    html = (ROOT / "sat_tool" / "map.html").read_text(encoding="utf-8")
    assert 'id="satinfo"' in html and "mouseenter" in html and "pinned" in html
    app = (ROOT / "sat_tool" / "app.py").read_text(encoding="utf-8")
    assert "welcome-banner.jpg" in app  # v1.7.2: banner Powered by PT2VHF
    assert "https://www.pt2vhf.com" in app and "'Fechar'" in app and "'Entendi'" not in app
