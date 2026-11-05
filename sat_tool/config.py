from __future__ import annotations
from pathlib import Path
import json, os, sys

DEFAULT_SATELLITES = ("25544", "27607", "40931", "7530", "24278", "44909", "59112")

DEFAULTS = {
    # v1.4.0: SDR, equipamentos RX/TX separados e telemetria.
    "rx_device": "TS-2000", "tx_device": "TS-2000",
    "ft817_port": "", "ft817_baud": 9600, "rigctld_host": "127.0.0.1:4532",
    "rtl_tcp": "", "sdr_ppm": 0, "sdr_bias_tee": False, "sdr_gain_db": None,
    "sdr_audio_device": "", "sdr_record": False, "sdr_record_iq": False,
    "sdr_volume": 0.8, "sdr_squelch_db": -120, "sdr_autostart": True, "sdr_dock_visible": False,
    "kiss_enabled": False, "kiss_host": "127.0.0.1:8100", "satnogs_upload": False,
    "callsign": "PT2VHF", "lat": "", "lon": "", "altitude_m": 0,
    "min_elevation": 10, "port": "", "baud": 9600, "stopbits": 1,
    "update_interval_s": 1, "tune_threshold_hz": 1,
    "auto_doppler": False, "selected_norad": "",
    "version_check_minutes": 15, "include_prereleases": True,
    # Versão adiada pelo botão "Depois" do aviso de nova versão: {"version", "at"}.
    "update_prompt_snooze": {},
    "last_update_notice": "",
    "radio_brand": "Kenwood", "radio_model": "TS-2000",
    "radio_modes": ["FM", "SSB", "CW"], "radio_bands": ["VHF", "UHF"],
    # Satélites habilitados por padrão (v1.3.16): ISS, SO-50, IO-86, AO-7, FO-29,
    # RS-44 e SONATE-2. Instalações existentes recebem os mesmos uma única vez.
    "satellite_selection": list(DEFAULT_SATELLITES), "tle_update_hours": 4,
    "poll_interval_s": 1, "tle_source": "CelesTrak",
    "orbit_groups": ["amateur","stations","cubesat","starlink","oneweb","weather","science","visual"],
    "catalog_category_filter": ["amateur","stations","cubesat","starlink","oneweb","weather","science","visual"],
    "cat_auto_select": True, "cat_auto_connect_startup": True,
    "cat_tracking_interval_s": 1, "cat_doppler_out_of_view": True,
    "cat_live_v137_migrated": True,
    "default_satellites_v1316_migrated": True,
    "aos_alarm_enabled": True, "aos_alarm_sound": True,
    "aos_alarm_lead_seconds": 10, "aos_alarm_fired": [],
    "web_enabled": False, "web_allow_lan": False, "web_port": 8094,
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
            # v1.3.16: soma os satélites padrão à seleção existente uma única vez,
            # sem desmarcar nada; desmarcar depois não é revertido.
            if not data.get("default_satellites_v1316_migrated", False):
                current = self.values.get("satellite_selection")
                # None (seleção automática) já inclui os padrões em enabled_satellite_ids.
                if current is not None:
                    merged = [str(n) for n in current]
                    merged += [n for n in DEFAULT_SATELLITES if n not in merged]
                    self.values["satellite_selection"] = merged
                self.values["default_satellites_v1316_migrated"] = True
                self.save()

    def save(self):
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)
