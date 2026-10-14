"""Regression checks for frozen-app crash diagnostics and GUI thread safety."""
import json
import threading
from pathlib import Path
from sat_tool import crash_diagnostics as cd

ROOT=Path(__file__).resolve().parents[1]


def test_crash_session_markers_and_no_exposure(tmp_path,monkeypatch):
    monkeypatch.setattr(cd,"_DIAG",tmp_path)
    cd.heartbeat()
    state=json.loads((tmp_path/"session.json").read_text(encoding="utf-8"))
    assert state["status"]=="running"
    assert "last_heartbeat_utc" in state
    cd.report_event("Synthetic test before shutdown")
    assert "Synthetic test" in (tmp_path/"events.log").read_text(encoding="utf-8")
    cd.clean_shutdown()
    state=json.loads((tmp_path/"session.json").read_text(encoding="utf-8"))
    assert state["status"]=="closed"


def test_event_log_rotation_keeps_bounded_disk_usage(tmp_path,monkeypatch):
    monkeypatch.setattr(cd,"_DIAG",tmp_path)
    path=tmp_path/"events.log"
    path.write_text("x"*(2*1024*1024+10),encoding="utf-8")
    cd.report_event("new event")
    assert path.stat().st_size<2048
    assert (tmp_path/"events.log.previous").exists()


def test_worker_cat_logs_marshal_through_gui_signal():
    app=(ROOT/"sat_tool"/"app.py").read_text(encoding="utf-8")
    qt=(ROOT/"sat_tool"/"qt_compat.py").read_text(encoding="utf-8")
    assert "record = Signal(str)" in app
    assert "self.events.record.connect(self._append_log)" in app
    assert "threading.current_thread() is threading.main_thread()" in app
    assert "self.events.record.emit(msg)" in app
    assert "@Slot(str)\n    def _append_log" in app
    assert "self.log_view.document().setMaximumBlockCount(4000)" in app
    assert "Slot" in qt


def test_worker_signal_executes_slot_in_gui_thread():
    from sat_tool.qt_compat import QObject, Slot, QT_BINDING
    if QT_BINDING=='PySide6':
        from PySide6.QtCore import QCoreApplication
    else:
        from PySide2.QtCore import QCoreApplication
    from sat_tool.app import Events
    app=QCoreApplication.instance()
    if app is None:app=QCoreApplication([])
    main=threading.get_ident()
    recorded=[]
    class Receiver(QObject):
        @Slot(str)
        def record(self,value):
            recorded.append((value,threading.get_ident()))
    receiver=Receiver()
    events=Events()
    events.record.connect(receiver.record)
    task=threading.Thread(target=lambda:events.record.emit("from CAT"),daemon=True)
    task.start();task.join(timeout=3)
    for _ in range(100):
        app.processEvents()
        if recorded:break
    assert recorded==[("from CAT",main)]
