"""
ambient_watch.py — ORACLE ambient context capture.

Monitors:
  1. Clipboard — every change Noah copies is read and stored
  2. Screenshots — new image files in standard Windows screenshot dirs
  3. OBS recordings — new video files in OBS output directory

Everything captured is compressed to meaning and stored in the
ambient context store (data/ambient.db). ORACLE reads this on every
conversation turn to answer questions like "what was I just looking at?"

No approval gate for capture — Noah controls what is monitored via
the WATCHED_DIRS list and clipboard enable flag. Destructive actions
(deleting, sending data externally) still require SOV1 approval.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
_DB_PATH = ROOT / "data" / "ambient.db"

# ── Directories watched for screenshots / OBS output ─────────────────────────

_SCREENSHOT_DIRS: list[Path] = [
    Path.home() / "Pictures" / "Screenshots",
    Path.home() / "Desktop",
    Path.home() / "OneDrive" / "Pictures" / "Screenshots",
    Path("C:/Users") / "noahh" / "Pictures" / "Screenshots",
]

_OBS_DIRS: list[Path] = [
    Path.home() / "Videos",
    Path.home() / "Desktop",
    Path("C:/Users") / "noahh" / "Videos",
]

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts"}


# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    _ensure_schema(c)
    return c


def _ensure_schema(c: sqlite3.Connection) -> None:
    c.executescript("""
        CREATE TABLE IF NOT EXISTS ambient (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        REAL NOT NULL,
            kind      TEXT NOT NULL,
            content   TEXT NOT NULL,
            hash      TEXT NOT NULL UNIQUE,
            path      TEXT
        );
        CREATE INDEX IF NOT EXISTS ambient_ts ON ambient(ts);
        CREATE INDEX IF NOT EXISTS ambient_kind ON ambient(kind);
    """)
    c.commit()


def _store(kind: str, content: str, path: str = "") -> bool:
    """Store one ambient event. Returns False if duplicate."""
    h = hashlib.sha256(content.encode(errors="replace")).hexdigest()[:32]
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO ambient (ts, kind, content, hash, path) VALUES (?,?,?,?,?)",
                (time.time(), kind, content[:4000], h, path),
            )
            c.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate
    except Exception:
        return False


def get_recent(limit: int = 20, kind: Optional[str] = None) -> list[dict]:
    """Retrieve recent ambient events for ORACLE context injection."""
    try:
        with _conn() as c:
            if kind:
                rows = c.execute(
                    "SELECT ts, kind, content, path FROM ambient WHERE kind=? ORDER BY ts DESC LIMIT ?",
                    (kind, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT ts, kind, content, path FROM ambient ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_context_block(limit: int = 8) -> str:
    """
    Returns a compact context block for injection into ORACLE prompts.
    Shows the most recent ambient captures across all kinds.
    """
    items = get_recent(limit=limit)
    if not items:
        return ""
    lines = ["[AMBIENT CONTEXT — recent captures]"]
    for item in items:
        age = int(time.time() - item["ts"])
        age_str = f"{age}s ago" if age < 120 else f"{age//60}m ago"
        preview = item["content"][:120].replace("\n", " ").strip()
        lines.append(f"  [{item['kind']} {age_str}] {preview}")
    return "\n".join(lines)


# ── Clipboard monitor ─────────────────────────────────────────────────────────

class ClipboardMonitor(threading.Thread):
    """Polls the Windows clipboard every 0.8s and stores changes."""

    def __init__(self):
        super().__init__(daemon=True, name="ClipboardMonitor")
        self._last = ""
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            try:
                text = self._read_clipboard()
                if text and text != self._last and len(text.strip()) > 2:
                    self._last = text
                    stored = _store("clipboard", text.strip())
                    if stored:
                        print(f"[AmbientWatch] Clipboard: {len(text)} chars captured")
            except Exception:
                pass
            time.sleep(0.8)

    def _read_clipboard(self) -> str:
        try:
            import ctypes
            import ctypes.wintypes as wt
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            if not u32.OpenClipboard(None):
                return ""
            try:
                CF_UNICODETEXT = 13
                h = u32.GetClipboardData(CF_UNICODETEXT)
                if not h:
                    return ""
                ptr = k32.GlobalLock(h)
                if not ptr:
                    return ""
                try:
                    return ctypes.wstring_at(ptr)
                finally:
                    k32.GlobalUnlock(h)
            finally:
                u32.CloseClipboard()
        except Exception:
            return ""

    def stop(self):
        self._running = False


# ── Screenshot / file watcher ─────────────────────────────────────────────────

class FileWatcher(threading.Thread):
    """Watches screenshot and OBS output dirs for new files."""

    def __init__(self):
        super().__init__(daemon=True, name="FileWatcher")
        self._running = False
        self._seen: set[str] = set()
        self._seed()

    def _seed(self):
        """Pre-populate seen set so we only capture NEW files."""
        for d in _SCREENSHOT_DIRS + _OBS_DIRS:
            if d.exists():
                for f in d.iterdir():
                    self._seen.add(str(f))

    def run(self):
        self._running = True
        while self._running:
            try:
                self._scan(_SCREENSHOT_DIRS, "screenshot", _IMAGE_EXTS)
                self._scan(_OBS_DIRS, "obs_recording", _VIDEO_EXTS)
            except Exception:
                pass
            time.sleep(2)

    def _scan(self, dirs: list[Path], kind: str, exts: set[str]):
        for d in dirs:
            if not d.exists():
                continue
            try:
                for f in d.iterdir():
                    key = str(f)
                    if key in self._seen:
                        continue
                    self._seen.add(key)
                    if f.suffix.lower() not in exts:
                        continue
                    # Only files modified in last 30s (just created)
                    try:
                        age = time.time() - f.stat().st_mtime
                        if age > 30:
                            continue
                    except Exception:
                        continue

                    content = f"New {kind}: {f.name} ({f.stat().st_size // 1024}KB)"
                    stored = _store(kind, content, path=str(f))
                    if stored:
                        print(f"[AmbientWatch] {kind}: {f.name}")

                        # For screenshots: attempt OCR via tesseract if available
                        if kind == "screenshot":
                            self._ocr(f)
            except PermissionError:
                pass

    def _ocr(self, path: Path):
        """Best-effort OCR via tesseract. Silently skipped if not installed."""
        try:
            result = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "eng", "--psm", "3"],
                capture_output=True, text=True, timeout=10,
            )
            text = result.stdout.strip()
            if text and len(text) > 10:
                _store("screenshot_ocr", text, path=str(path))
                print(f"[AmbientWatch] OCR: {len(text)} chars from {path.name}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception:
            pass

    def stop(self):
        self._running = False


# ── Orchestrator ──────────────────────────────────────────────────────────────

_clipboard_monitor: Optional[ClipboardMonitor] = None
_file_watcher: Optional[FileWatcher] = None
_started = False


def start(enable_clipboard: bool = True, enable_files: bool = True):
    """Start ambient watchers. Safe to call multiple times."""
    global _clipboard_monitor, _file_watcher, _started
    if _started:
        return
    _started = True

    if enable_clipboard:
        _clipboard_monitor = ClipboardMonitor()
        _clipboard_monitor.start()
        print("[AmbientWatch] Clipboard monitoring active")

    if enable_files:
        _file_watcher = FileWatcher()
        _file_watcher.start()
        print("[AmbientWatch] File watcher active (screenshots + OBS)")


def stop():
    global _started
    if _clipboard_monitor:
        _clipboard_monitor.stop()
    if _file_watcher:
        _file_watcher.stop()
    _started = False
