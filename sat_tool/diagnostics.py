r"""Self test: run the frozen EXE with --self-test path-to-report.json."""
from __future__ import annotations
import json
import platform
import struct
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

def run_self_test(report_path: str, expected_qt: str = "") -> int:
    result = {
        "schema": 1, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed", "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable, "os": platform.platform(),
        "architecture_bits": struct.calcsize("P") * 8,
        "expected_qt": expected_qt, "versions": {}, "checks": [],
    }
    try:
        import numpy as np
        result["versions"]["numpy"] = np.__version__
        assert np.array([1.0, 2.0]).sum() == 3.0
        assert abs(float(np.linalg.norm([3.0, 4.0])) - 5.0) < 0.0001
        assert np.random.default_rng(123).integers(0, 10) >= 0
        result["checks"].append("numpy_native_blas")
        import skyfield
        from skyfield.api import load
        assert load.timescale(builtin=True) is not None
        result["versions"]["skyfield"] = getattr(skyfield, "__version__", "unknown")
        result["checks"].append("skyfield_bundled_data")
        from sat_tool.qt_compat import QT_BINDING, QWebEngineView, QGeoPositionInfoSource
        result["versions"]["qt_binding"] = QT_BINDING
        if expected_qt and QT_BINDING != expected_qt:
            raise RuntimeError("Qt incompatível: %s (esperado %s)" % (QT_BINDING, expected_qt))
        result["checks"].append("qt_native")
        import sat_tool.app
        result["checks"].append("app_import")
        from pathlib import Path
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        mapfile = root / "sat_tool" / "map.html"
        logo = root / "assets" / "branding" / "icon-256.png"
        if not mapfile.is_file() or not logo.is_file():
            raise FileNotFoundError("Mapa offline e identidade visual devem integrar o EXE")
        html = mapfile.read_text(encoding="utf-8")
        if "MAPA VETORIAL OFFLINE" not in html or "tile.openstreetmap.org" in html:
            raise RuntimeError("Mapa offline indisponível ou ainda depende de OSM tiles")
        result["checks"].append("offline_map_and_brand_embedded")
        result["status"] = "passed"
    except BaseException:
        result["error"] = traceback.format_exc()
    try:
        # On Windows a launcher may pass a quoted argument literally.
        # Strip only matching outer command-line quotes; the report remains local.
        report_path = str(report_path).strip()
        if len(report_path) >= 2 and report_path[0] == report_path[-1] == '"':
            report_path = report_path[1:-1]
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        traceback.print_exc()
        return 2
    return 0 if result["status"] == "passed" else 1
