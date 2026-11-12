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


def test_welcome_closes_itself_after_countdown():
    import os, subprocess, sys, textwrap
    source = textwrap.dedent(r'''
        import tempfile, time
        from pathlib import Path
        from sat_tool import app as gui
        from sat_tool.config import Config
        class FakeWeb(gui.QWidget):
            def setHtml(self,*a,**k):pass
            def page(self):return self
            def runJavaScript(self,*a,**k):pass
            def reload(self):pass
        gui.QWebEngineView=FakeWeb
        gui.load_orbits=lambda d:[]
        gui.MainWindow.background=lambda self,key,fn:None
        gui.MainWindow.check_for_updates=lambda self:None
        assert gui.WELCOME_SECONDS == 10
        gui.WELCOME_SECONDS = 2
        seen = []
        def look():
            m = gui.QApplication.activeModalWidget()
            if m is None:
                gui.QTimer.singleShot(100, look); return
            seen.append(m.findChild(gui.QLabel, 'welcomeCountdown').text())
        with tempfile.TemporaryDirectory() as d:
            gui.Config=lambda:Config(Path(d))
            app=gui.QApplication([])
            w=gui.MainWindow()
            gui.QTimer.singleShot(100, look)
            t=time.monotonic(); w.show_official_site_notice(); dt=time.monotonic()-t
            assert 1.5 < dt < 4, dt          # fechou sozinha ao fim da contagem
            assert seen and seen[0].endswith('2 s'), seen
    ''')
    r = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "LANG": "pt_BR.UTF-8"})
    assert r.returncode == 0, r.stdout + r.stderr
