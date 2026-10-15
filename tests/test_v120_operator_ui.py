"""Regression checks for the v1.2.0 operator-first satellite layout and progress UI."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/"sat_tool"/"app.py")


def test_predicted_rx_tx_above_map_and_independent_of_cat():
    source=APP.read_text(encoding="utf-8")
    assert 'operator_panel,ov=group("SATÉLITE · FREQUÊNCIAS DOPPLER CALCULADAS")' in source
    assert "self.pred_rx=label(" in source
    assert "self.pred_tx=label(" in source
    assert "self.pred_rx.setText(" in source
    assert "self.pred_tx.setText(" in source
    assert 'self.preview_doppler(pos=pos,when=now)' in source
    assert 'self.tick_timer.start(1000)' in source
    assert "self.mode_combo,3" in source and "self.sat_combo,2" in source
    assert "self.corrected_label" in source


def test_cat_and_trajectory_controls_are_in_settings():
    source=APP.read_text(encoding="utf-8")
    assert 'rs.addWidget(catview)' in source
    assert 'rs.addLayout(cat_options)' in source
    assert 'tsv.addLayout(trail_bar)' in source
    assert 'self.mark_map_button=QPushButton' not in source
    assert 'self.connection=QPushButton("Conectar")' in source
    assert 'quick_cat.addWidget(self.connection)' in source
    assert 'self.ports.setEditable(True)' in source


def test_satellite_selection_change_is_not_silently_ignored():
    source=APP.read_text(encoding="utf-8")
    part=source.split("    def choose_satellite(self):",1)[1].split(
        "    def refresh_modes(",1)[0]
    assert part.index('if ident==self._active_satellite_id') < part.index(
        'self._active_satellite_id=ident')
    assert 'self.sat=make_satellite(item,self.ts)' in part


def test_settings_filter_preserves_complete_selection():
    source=APP.read_text(encoding="utf-8")
    segment=source.split("    def filter_tracked_satellites(",1)[1].split(
        "    def refresh_tracked_table(",1)[0]
    assert "self.tracked_table.setRowHidden(index,not show)" in segment
    assert "unicodedata.normalize" in segment
    assert "satellite_selection" not in segment
    assert "self.tracked_search.textChanged.connect(self.filter_tracked_satellites)" in source


def test_modal_frequency_download_progress_updates_per_record():
    source=APP.read_text(encoding="utf-8")
    assert "QProgressDialog(" in source
    assert "self.frequency_progress_dialog.setWindowModality(Qt.WindowModal)" in source
    assert "self.frequency_progress_dialog.canceled.connect(self.cancel_catalog_transmitters)" in source
    assert "self.frequency_progress_dialog.setValue(index)" in source
    assert 'stats["no_data"]+=1' in source
    assert 'if "tx-batch" not in self.pending_jobs:return' in source
