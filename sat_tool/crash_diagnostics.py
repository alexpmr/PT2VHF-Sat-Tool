"""Crash diagnostics for packaged Windows builds.

Stores an abnormal-exit marker and Python native crash tracebacks; no network,
station coordinates, CAT packets, or personal application settings are copied.
"""
from __future__ import annotations

import faulthandler
import json
import os
import platform
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

_DIAG = None
_CRASH_STREAM = None
_LOCK = threading.RLock()


def utc_time():
    return datetime.now(timezone.utc).isoformat()


def diagnostic_dir():
    """Writable diagnostic directory for Setup and self-contained Portable EXEs."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    path = (Path(base) / "PT2VHF" / "SatTool" / "diagnostics") if base else (
        Path.home() / ".pt2vhf" / "sattool" / "diagnostics")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _rotate(path, max_size=3*1024*1024):
    if path.exists() and path.stat().st_size > max_size:
        old = path.with_suffix(path.suffix + ".previous")
        try:
            if old.exists():old.unlink()
            path.replace(old)
        except OSError:
            pass


def _append_event(message):
    if _DIAG is None:return
    try:
        with _LOCK:
            with (_DIAG / "events.log").open("a", encoding="utf-8") as file:
                file.write(utc_time() + "  " + str(message).rstrip() + "\n")
    except OSError:
        pass


def _state(status, **fields):
    if _DIAG is None:return
    payload={"schema":1,"updated_utc":utc_time(),"status":status,
             "pid":os.getpid(),"python":platform.python_version(),
             "platform":sys.platform}
    payload.update(fields)
    try:
        with _LOCK:
            temp=_DIAG / "session.tmp"
            temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            temp.replace(_DIAG / "session.json")
    except OSError:
        pass


def install_diagnostics():
    global _DIAG,_CRASH_STREAM
    try:
        _DIAG=diagnostic_dir()
        for name in ("events.log","native-crash.log"):_rotate(_DIAG/name)
        prior=_DIAG/"session.json"
        if prior.exists():
            try:
                previous=json.loads(prior.read_text(encoding="utf-8"))
                if previous.get("status")=="running":
                    _append_event("Previous session ended without a recorded clean shutdown "
                                  "(power loss/forced close/native crash possible)")
            except (OSError,ValueError):
                pass
        _CRASH_STREAM=(_DIAG/"native-crash.log").open("a",encoding="utf-8",buffering=1)
        faulthandler.enable(file=_CRASH_STREAM,all_threads=True)
        old_hook=sys.excepthook
        def global_exception(exc_type,exc_value,trace):
            _append_event("Uncaught Python exception:\n"+
                          "".join(traceback.format_exception(exc_type,exc_value,trace)))
            _state("exception")
            if old_hook:old_hook(exc_type,exc_value,trace)
        sys.excepthook=global_exception
        if hasattr(threading,"excepthook"):
            old_thread_hook=threading.excepthook
            def thread_exception(args):
                _append_event("Uncaught worker exception:\n"+
                              "".join(traceback.format_exception(
                                args.exc_type,args.exc_value,args.exc_traceback)))
                if old_thread_hook:old_thread_hook(args)
            threading.excepthook=thread_exception
        _state("running",started_utc=utc_time())
        _append_event("Application starting (diagnostics enabled)")
        return _DIAG
    except Exception:
        # A full/unwritable disk must not prevent the application from launching.
        return None


def heartbeat():
    """Called from a low-frequency Qt timer; distinguishes hangs and exits."""
    _state("running",last_heartbeat_utc=utc_time())


def report_exception(source,exception):
    _append_event(str(source)+": "+
                  "".join(traceback.format_exception(
                    type(exception),exception,exception.__traceback__)))


def report_event(message):
    _append_event(message)


def clean_shutdown():
    _append_event("Application exited through the normal Qt event loop")
    _state("closed")
