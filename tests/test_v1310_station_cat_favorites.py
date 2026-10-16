"""v1.3.10: Maidenhead locator, browser-only station location and robust live CAT."""
import pytest
from pathlib import Path
from sat_tool.maidenhead import maidenhead_to_latlon

ROOT=Path(__file__).resolve().parents[1]


def test_grid_4_char_center_and_finer_subsquare_in_brasilia():
    assert maidenhead_to_latlon("GH64")==(-15.5,-47.0)
    lat,lon=maidenhead_to_latlon("gh64ab")
    assert -16.0<lat<-15.0
    assert -48.0<lon<-46.0
    assert abs(lat+15.5)>0.01  # 6-char precision is not same as 4-char center
    assert maidenhead_to_latlon("GG") == (-25.0,-50.0)


def test_grid_accepts_nested_2_to_10_character_pairs():
    for grid in ("AA","AA00","AA00aa","AA00aa00","AA00aa00aa",
                 "RR99xx99xx"):
        lat,lon=maidenhead_to_latlon(grid)
        assert -90<=lat<=90 and -180<=lon<=180
    for invalid in ("","GH6","GH64ABC","SS00","ZZ99","GHAA",
                    "GH64zy","GH64ab01zz","AA00aa00aa00"," GH64-123 "):
        with pytest.raises(ValueError):
            maidenhead_to_latlon(invalid)


def test_station_ui_contains_only_three_requested_methods():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    station=app.split('station_group,sg=group("ESTAÇÃO TERRENA")',1)[1].split("cfg.addWidget(station_group)",1)[0]
    assert 'self.grid_locator=QLineEdit()' in station
    assert 'self.grid_apply.clicked.connect(self.apply_grid_locator)' in station
    assert 'self.get_position=QPushButton("Solicitar coordenadas ao navegador")' in station
    assert 'self.save_station_btn.clicked.connect(self.save_station)' in station
    assert 'self.station_map_button.hide()' in station
    assert 'self.gps_port=QComboBox()' not in station
    assert 'IP aproximado' not in station
    assert 'GPS USB' not in station
    assert '"Marcar estação no mapa"' not in station
    assert 'self.config.save()' not in app.split("    def apply_grid_locator(",1)[1].split("    def geolocate(",1)[0]


def test_browser_geolocation_requires_user_interaction_and_no_auto_save():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    html=(ROOT/"sat_tool"/"map.html").read_text(encoding="utf-8")
    assert 'self.get_position.clicked.connect(self.geolocate)' in app
    assert 'self.map.page().featurePermissionRequested.connect(self.grant_browser_geo)' in app
    assert 'QUrl.fromLocalFile(str(map_file.resolve()))' in app
    assert "navigator.geolocation.getCurrentPosition(" in html
    assert "window.requestBrowserGeolocation=function()" in html
    assert 'window.takeBrowserGeolocation=function()' in html
    assert 'self.apply_location_fix(fix)' in app
    assert "self.config.save()" not in app.split("    def browser_geolocation_result(",1)[1].split("    def apply_location_fix(",1)[0]


def test_favorite_doubleclick_reverses_row_without_navigation():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    handler=app.split("    def select_catalog_satellite(self,row,col):",1)[1].split("    def filter_sats(",1)[0]
    assert "self.catalog_click_timer.stop()" in handler
    assert "self.toggle_catalog_favorite(" in handler
    assert "self.tabs.setCurrentIndex(" not in handler
    assert "self.centralWidget().setCurrentIndex(" not in handler
    assert "self.sat_combo.setCurrentIndex(" not in handler
    assert "self.catalog_click_timer.start(QApplication.doubleClickInterval()+40)" in app


def test_auto_cat_recovers_after_cat_readback_mismatch_without_button():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    failure=app.split('if key=="cat-track":',1)[1].split('if key=="logs-export":',1)[0]
    assert 'self.cat_tracking_armed=False' not in failure
    assert "self.cat_retry_after=time.monotonic()" in failure
    assert "self.last_freqs=(None,None)" in failure
    loop=app.split('    def track_cat_frequencies(self,now):',1)[1].split('    def cat_live_tick(',1)[0]
    assert "self.cat_tracking_armed=False" not in loop
    assert "self.cat_retry_after" in loop
    assert "self.auto_tune_selected_satellite()" in loop
    assert "Sintonizar agora" not in app
    assert "Aplicar RX/TX no TS-2000" not in app
    assert 'self.rx_mode.activated.connect(self.on_cat_operator_changed)' in app


def test_next_pass_countdown_is_inside_lower_orbital_telemetry_panel():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    assert 'sv.addWidget(upcoming)' in app
    assert 'op.addWidget(upcoming)' not in app
    assert 'rv.insertWidget(0,nextpass,2)' in app
    assert 'self.next_countdown=label("--:--:--")' in app


def test_release_banner_has_no_popup_on_update_check_or_saving_preferences():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    action=app.split("    def save_update_preferences(self):",1)[1].split("    def request_update(",1)[0]
    assert "self.manual_update_requested = False" in action
    code=app.split("if key=='update-check':",1)[1].split("if key=='update-download':",1)[0]
    assert "QMessageBox.information" not in code
    assert "QMessageBox.question" not in code
    assert "data.body" not in code
