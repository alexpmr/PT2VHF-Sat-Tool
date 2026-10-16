"""Local, bounded, thread-safe CAT/application event journal and export."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import threading
import zipfile


class EventJournal:
    """Never upload: all bytes remain in the operator-selected local folder."""
    def __init__(self, directory: Path, max_bytes=3 * 1024 * 1024):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path=self.directory/"cat-session.log"
        self.max_bytes=max_bytes
        self.lock=threading.RLock()
        self.append("--- NEW APPLICATION SESSION ---")

    def append(self, message: str):
        timestamp=datetime.now(timezone.utc).isoformat()
        message=str(message).replace("\r", " ").rstrip()
        with self.lock:
            if self.path.exists() and self.path.stat().st_size>self.max_bytes:
                for index in (2, 1):
                    older=self.directory/("cat-session.log."+str(index))
                    newer=self.directory/("cat-session.log."+str(index+1))
                    if older.exists():older.replace(newer)
                if self.path.exists():self.path.replace(self.directory/"cat-session.log.1")
            with self.path.open("a",encoding="utf-8") as f:
                f.write(timestamp+"  "+message+"\n")

    def export(self,destination:Path,visible_log:str="",diagnostics_dir:Path|None=None,version:str=""):
        dest=Path(destination)
        if dest.suffix.lower()!=".zip":
            dest=dest.with_suffix(".zip")
        dest.parent.mkdir(parents=True,exist_ok=True)
        staging=dest.with_suffix(dest.suffix+".tmp")
        with self.lock:
            source_files=[]
            source_files.extend(sorted(self.directory.glob("cat-session.log*")))
            if diagnostics_dir and Path(diagnostics_dir).is_dir():
                for name in ("events.log","events.log.previous","native-crash.log","native-crash.log.previous"):
                    p=Path(diagnostics_dir)/name
                    if p.is_file():source_files.append(p)
            metadata={"created_utc":datetime.now(timezone.utc).isoformat(),
                      "app_version":version,"format":"UTF-8; timestamps UTC",
                      "warning":"May contain callsigns, coordinates, serial COM ports and CAT traffic.",
                      "log_files":[p.name for p in source_files]}
            try:
                with zipfile.ZipFile(str(staging),"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("README.json",json.dumps(metadata,ensure_ascii=False,indent=2))
                    archive.writestr("ui-last-4000-lines.txt",visible_log)
                    for p in source_files:
                        group="cat" if p.parent==self.directory else "diagnostics"
                        archive.write(str(p),arcname=group+"/"+p.name)
                staging.replace(dest)
            except Exception:
                if staging.exists():staging.unlink()
                raise
        return str(dest),len(source_files)
