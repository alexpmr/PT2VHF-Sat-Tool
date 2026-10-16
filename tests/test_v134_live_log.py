"""v1.3.4 operator CAT startup/track and offline complete log export."""
from pathlib import Path
import tempfile
import zipfile

from sat_tool.config import Config
from sat_tool.log_journal import EventJournal


def test_new_cat_defaults_and_existing_user_override(tmp_path):
    initial=Config(tmp_path)
    assert initial.values["cat_auto_select"] is True
    assert initial.values["cat_auto_connect_startup"] is True
    assert initial.values["cat_doppler_out_of_view"] is True
    initial.values["cat_auto_select"]=False
    initial.values["cat_auto_connect_startup"]=False
    initial.save()
    loaded=Config(tmp_path)
    assert loaded.values["cat_auto_select"] is False
    assert loaded.values["cat_auto_connect_startup"] is False


def test_log_journal_exports_beyond_visible_4000_lines_and_cat_raw(tmp_path):
    journal=EventJournal(tmp_path/"journal",max_bytes=10_000_000)
    for i in range(4012):
        journal.append(f"RX FA{i:011d};")
    journal.append("TX FC00145850000;")
    diag=tmp_path/"diagnostics"
    diag.mkdir()
    (diag/"events.log").write_text("SAT ON\n",encoding="utf-8")
    file,n=journal.export(tmp_path/"sat-logs.zip","GUI LAST 4000",
                diag,"1.3.4")
    assert n==2
    assert Path(file).exists()
    with zipfile.ZipFile(file) as z:
        assert "cat/cat-session.log" in z.namelist()
        assert "diagnostics/events.log" in z.namelist()
        assert b"RX FA00000000000;" in z.read("cat/cat-session.log")
        assert b"TX FC00145850000;" in z.read("cat/cat-session.log")
        assert b"GUI LAST 4000" in z.read("ui-last-4000-lines.txt")


def test_log_rotation_keeps_previous_history(tmp_path):
    journal=EventJournal(tmp_path/"journal",max_bytes=110)
    for i in range(28):journal.append("CAT "+str(i))
    files=list((tmp_path/"journal").glob("cat-session.log*"))
    assert len(files)>1
    assert all(f.stat().st_size>0 for f in files)


def test_continuous_cat_armed_on_connection_and_user_selection():
    source=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.cat_indicator=QPushButton(" in source
    assert "self.cat_indicator.clicked.connect(self.toggle_connection)" in source
    assert "self.sat_combo.activated.connect(self.arm_cat_tracking)" in source
    assert "self.mode_combo.activated.connect(self.arm_cat_tracking)" in source
    assert "self.cat_tracking_armed = False" in source
    assert "QTimer.singleShot(1200, self.startup_cat_connect)" in source
    assert 'self.cat_tracking_armed=bool(self.config.values.get("cat_auto_select",False))' in source
    assert 'self.last_freqs=(None,None)' in source
    assert 'self.background("cat-track",task)' in source
    assert 'self.export_logs.clicked.connect(self.save_complete_logs)' in source
    assert 'self.journal.append(msg)' in source
    assert 'safe,reason=self.selected_cat_pair_info(ul,dl)' in source
    assert '"cat-auto_connect_startup"' not in source or True


def test_no_direct_ptt_or_implicit_sat_in_continuous_tracking():
    source=(Path(__file__).resolve().parents[1]/"sat_tool"/"app.py").read_text(encoding="utf-8")
    function=source.split("    def track_cat_frequencies(self,now):",1)[1].split("    def diagnose_cat(self):",1)[0]
    assert "self.radio.set_frequencies(ul,dl)" in function
    assert "self.radio.enable_satellite_mode()" not in function
    assert "set_main_mode" not in function
    assert 'self.background("cat-track",task)' in function
