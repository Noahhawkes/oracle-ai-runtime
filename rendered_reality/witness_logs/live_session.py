"""
rendered_reality/witness_logs/live_session.py

Track a live build / OBS session as a witness object. The OBS video is FUTURE
evidence: its path and hash stay holes until the file actually exists and is
hashed. Nothing here claims ORACLE observed anything it did not.

Uses Python None (never JSON null) inside code.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LiveSession:
    session_id: str
    operator: str = "Noah.Physical"
    device_context: str = "PC"
    recording_status: str = "OBS live recording active"
    source_type: str = "live_build_session"
    purpose: str = ""
    start_time_local: str | None = None
    started_at: str = field(default_factory=_utc)
    notes: list[dict] = field(default_factory=list)
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    holes: list[str] = field(default_factory=list)
    closed_at: str | None = None
    canon_status: str = "runtime_ingested_record"
    approval_status: str = "pending_noah_physical"

    def add_note(self, text: str, kind: str = "note") -> dict:
        note = {"at": _utc(), "kind": kind, "text": text}
        self.notes.append(note)
        return note

    def attach_artifact_path(self, path: str) -> str:
        self.artifact_path = str(path)
        # path provided -> drop the "path not yet provided" hole
        self.holes = [h for h in self.holes if "path not yet provided" not in h.lower()]
        if not Path(self.artifact_path).exists():
            note = "OBS artifact path set but file not found yet"
            if note not in self.holes:
                self.holes.append(note)
        return self.artifact_path

    def hash_artifact_when_available(self) -> str | None:
        """Hash the artifact only if it actually exists. Honest None otherwise."""
        if not self.artifact_path:
            return None
        p = Path(self.artifact_path)
        if not p.exists():
            return None
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        self.artifact_sha256 = "sha256:" + h.hexdigest()
        self.holes = [x for x in self.holes if "hash" not in x.lower()]
        return self.artifact_sha256

    def close_session(self) -> "LiveSession":
        self.closed_at = _utc()
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    def write(self, path: str) -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return str(path)


def start_session(session_id: str, **kwargs) -> LiveSession:
    s = LiveSession(session_id=session_id, **kwargs)
    s.holes = [
        "OBS video file path not yet provided",
        "OBS recording hash not available until recording is saved",
    ]
    return s
