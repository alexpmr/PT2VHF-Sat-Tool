from __future__ import annotations
from pathlib import Path
import json, os, sys

DEFAULTS = {
    "callsign": "PT2VHF", "lat": "", "lon": "", "altitude_m": 0,
    "min_elevation": 10, "port": "", "baud": 9600, "stopbits": 1,
    "update_interval_s": 1, "tune_threshold_hz": 1,
    "auto_doppler": False, "selected_norad": "",
    "version_check_minutes": 15, "include_prereleases": True,
    "last_update_notice": "",
    "radio_brand": "Kenwood", "radio_model": "TS-2000",
    "radio_modes": ["FM", "SSB", "CW"], "radio_bands": ["VHF", "UHF"],
    "satellite_selection": None, "tle_update_hours": 4,
    "poll_interval_s": 1, "tle_source": "CelesTrak",
    "orbit_groups": ["amateur","stations","cubesat","starlink","oneweb","weather","science","visual"],
    "cat_auto_select": True, "cat_auto_connect_startup": True,
    "cat_tracking_interval_s": 1, "cat_doppler_out_of_view": True,
    "cat_live_v137_migrated": True,
    "aos_alarm_enabled": True, "aos_alarm_sound": True,
    "aos_alarm_fired": [],
    "language": "pt-BR", "frequency_style": "radio10",
    "gps_port": "", "gps_baud": 9600,
    "trail_period": "2 h", "trail_direction": "Futuro", "trail_custom_hours": 3.0,
}


def application_dir() -> Path:
    if getattr(sys, 'frozen', False):
        exe = Path(sys.executable).resolve().parent
        if (exe / "portable.flag").exists() or exe.stem.casefold().endswith("-portable"):
            return exe / "data"
    base = os.environ.get("APPDATA") if sys.platform == "win32" else os.environ.get("XDG_CONFIG_HOME")
    return Path(base) / "PT2VHF" / "SatTool" if base else Path.home() / ".config" / "PT2VHF" / "SatTool"


class Config:
    def __init__(self, path: Path | None = None):
        self.dir = path or application_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "settings.json"
        self.values = dict(DEFAULTS)
        if self.file.exists():
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self.values.update({k:v for k,v in data.items() if k in DEFAULTS})
            # Auto CAT always follows Doppler outside the horizon. Older
            # versions could persist False and allow only the initial tune.
            if self.values["cat_doppler_out_of_view"] is not True:
                self.values["cat_doppler_out_of_view"] = True
                self.save()
            # Migrate v1.3.6 default 2s/20Hz to responsive 1s/1Hz without
            # overriding custom intervals or a disabled Auto CAT preference.
            if not data.get("cat_live_v137_migrated",False):
                if self.values["update_interval_s"] == 2:
                    self.values["update_interval_s"] = 1
                if self.values["tune_threshold_hz"] == 20:
                    self.values["tune_threshold_hz"] = 1
                self.values["cat_live_v137_migrated"] = True
                self.save()

    def save(self):
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)
