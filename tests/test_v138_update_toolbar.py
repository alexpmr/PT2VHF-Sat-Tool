"""Regression: update button owns download; no changelog/news modal.

v1.3.13: the new-version prompt (maybe_prompt_update) only asks whether to
update; it shows no changelog and starts the same request_update flow.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_new_version_only_shows_in_top_toolbar():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    update=app.split("    def background_result(self,key,data):",1)[1].split("    def background_error(",1)[0]
    check=update.split("if key=='update-check':",1)[1].split("if key=='update-download':",1)[0]
    assert "self.version_btn.setText(f'Nova versão {data.version} · instalar')" in check
    assert "self.version_btn.setStyleSheet" in check
    assert "QMessageBox.information" not in check
    assert "data.body" not in check
    assert "self.request_update(manual=True)" in check


def test_version_click_starts_download_and_keeps_checksum_verification():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    click=app.split("    def request_update(self,manual=False):",1)[1].split("    def download_progress(",1)[0]
    assert "QMessageBox.question" not in click
    assert "u.body" not in click
    assert "self.background('update-download'," in click
    assert "download_update(u," in click
    assert "self.update_dialog=QProgressDialog" in click
    done=app.split("    def update_ready(self,package):",1)[1].split("    def station(self):",1)[0]
    assert "launch_staged_update(Path(package)" in done
    assert done.index("launch_staged_update(")<done.index("self.radio.disconnect()")


def test_selected_pass_time_and_cat_sync_controls_are_not_decorative():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert "self.cat_live_timer.timeout.connect(self.cat_live_tick)" in app
    assert "self.cat_sync_status=label(" in app
    assert "self.update_cat_sync_status(state)" in app
    assert "self.refresh_passes()" in app
    assert "self.next_times.setWordWrap(False)" in app
    assert "Recalcular passagens" not in app
