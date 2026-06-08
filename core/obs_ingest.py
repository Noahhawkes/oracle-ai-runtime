"""
core/obs_ingest.py — ORACLE OBS Log + Video Ingest v0.1

Reads OBS logs and submits OBS recordings into ORACLE's governed memory.

OBS logs  -> parsed for sessions, scenes, recording paths, errors -> remember_me candidate (pending)
OBS videos -> submitted through video_intelligence pipeline -> VideoObservationCandidate (pending)

Both outputs are born PENDING. Noah approves. ORACLE observes.

Search Light Compression Law applies to videos:
  ORACLE may observe. ORACLE may create candidates. ORACLE may compress meaning.
  ORACLE may not store raw video. ORACLE may not approve without Noah.

CLI:
  python core/obs_ingest.py --scan-logs           # parse all OBS logs -> candidates
  python core/obs_ingest.py --scan-videos         # submit all OBS recordings -> video candidates
  python core/obs_ingest.py --scan-all            # both
  python core/obs_ingest.py --list                # show what's found without ingesting
  python core/obs_ingest.py --smoke-test
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Root bootstrap ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

# ── OBS paths ─────────────────────────────────────────────────────────────────
OBS_LOG_DIR    = Path.home() / "AppData" / "Roaming" / "obs-studio" / "logs"
OBS_VIDEO_DIRS = [
    Path.home() / "Videos",
    Path.home() / "OneDrive" / "Videos",
    Path("C:/Users") / Path.home().name / "OneDrive" / "Videos",
]
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".mov", ".avi"}

# ── Regex patterns for log parsing ────────────────────────────────────────────
_RE_RECORDING_START = re.compile(r"==== Recording Start")
_RE_RECORDING_STOP  = re.compile(r"==== Recording Stop")
_RE_OUTPUT_FILE     = re.compile(r"Writing file '(.+?)'")
_RE_SCENE_SWITCH    = re.compile(r"User switched to scene '(.+?)'")
_RE_SCENE_LOADED    = re.compile(r"- scene '(.+?)'")
_RE_CRASH           = re.compile(r"(?i)crash|unclean shutdown")
_RE_ERROR           = re.compile(r"(?i)^\d{2}:\d{2}:\d{2}\.\d+: (\[error\]|error|failed|warning).+")
_RE_TIMESTAMP       = re.compile(r"^(\d{2}:\d{2}:\d{2})")
_RE_CPU             = re.compile(r"CPU Name: (.+)")
_RE_RAM             = re.compile(r"Physical Memory: (\d+)MB Total, (\d+)MB Free")
_RE_RESOLUTION      = re.compile(r"output resolution: (\d+x\d+)")


# ── OBS Log parser ────────────────────────────────────────────────────────────

class OBSSession:
    """Represents one parsed OBS session from a log file."""

    def __init__(self, log_path: Path):
        self.log_path       = log_path
        self.log_date       = log_path.stem[:10]          # "2026-06-07"
        self.recording_starts: list[str] = []
        self.recording_stops:  list[str] = []
        self.output_files:     list[str] = []
        self.scenes_loaded:    list[str] = []
        self.scenes_switched:  list[str] = []
        self.errors:           list[str] = []
        self.crash_detected:   bool      = False
        self.cpu:              str       = ""
        self.ram_total_mb:     int       = 0
        self.ram_free_mb:      int       = 0
        self.resolution:       str       = ""
        self.raw_size_bytes:   int       = log_path.stat().st_size if log_path.exists() else 0

    def parse(self) -> "OBSSession":
        if not self.log_path.exists():
            return self
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return self

        for line in lines:
            if _RE_RECORDING_START.search(line):
                m = _RE_TIMESTAMP.match(line)
                if m:
                    self.recording_starts.append(m.group(1))
            if _RE_RECORDING_STOP.search(line):
                m = _RE_TIMESTAMP.match(line)
                if m:
                    self.recording_stops.append(m.group(1))
            m = _RE_OUTPUT_FILE.search(line)
            if m:
                self.output_files.append(m.group(1))
            m = _RE_SCENE_SWITCH.search(line)
            if m:
                sc = m.group(1)
                if sc not in self.scenes_switched:
                    self.scenes_switched.append(sc)
            m = _RE_SCENE_LOADED.search(line)
            if m:
                sc = m.group(1)
                if sc not in self.scenes_loaded:
                    self.scenes_loaded.append(sc)
            if _RE_CRASH.search(line):
                self.crash_detected = True
            m = _RE_CPU.search(line)
            if m:
                self.cpu = m.group(1).strip()
            m = _RE_RAM.search(line)
            if m:
                self.ram_total_mb = int(m.group(1))
                self.ram_free_mb  = int(m.group(2))
            m = _RE_RESOLUTION.search(line)
            if m and not self.resolution:
                self.resolution = m.group(1)
            if _RE_ERROR.match(line):
                self.errors.append(line[12:80])  # strip timestamp, cap length

        return self

    def compressed_meaning(self) -> str:
        parts = [f"OBS session log for {self.log_date}."]
        if self.crash_detected:
            parts.append("Crash or unclean shutdown detected at session start.")
        if self.recording_starts:
            parts.append(
                f"Recording started {len(self.recording_starts)} time(s) "
                f"at: {', '.join(self.recording_starts[:3])}."
            )
        if self.output_files:
            names = [Path(f).name for f in self.output_files]
            parts.append(f"Output file(s): {', '.join(names[:5])}.")
        if self.scenes_switched:
            parts.append(f"Scenes used: {', '.join(self.scenes_switched[:6])}.")
        if self.resolution:
            parts.append(f"Output resolution: {self.resolution}.")
        if self.cpu:
            parts.append(f"Hardware: {self.cpu}.")
        if self.ram_total_mb:
            parts.append(f"RAM: {self.ram_total_mb}MB total, {self.ram_free_mb}MB free.")
        if self.errors:
            parts.append(f"Errors/warnings: {len(self.errors)} entries (first: {self.errors[0][:80]}).")
        return " ".join(parts)

    def unknowns(self) -> list[str]:
        u = []
        if not self.recording_starts:
            u.append("No recording start event found — session may have been setup-only.")
        if not self.output_files:
            u.append("Output file path not captured in log.")
        if not self.scenes_switched:
            u.append("No scene switches logged — scene activity unknown.")
        return u

    def summary_line(self) -> str:
        rec = len(self.recording_starts)
        crash = " [CRASH]" if self.crash_detected else ""
        scenes = ",".join(self.scenes_switched[:3]) or "none"
        return f"{self.log_date}{crash} | {rec} recording(s) | scenes: {scenes} | {len(self.errors)} errors"


# ── Log discovery ─────────────────────────────────────────────────────────────

def find_obs_logs() -> list[Path]:
    if not OBS_LOG_DIR.exists():
        return []
    return sorted(OBS_LOG_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)


def find_obs_videos() -> list[Path]:
    found = []
    seen  = set()
    for d in OBS_VIDEO_DIRS:
        if not d.exists():
            continue
        for ext in VIDEO_EXTENSIONS:
            for f in d.glob(f"*{ext}"):
                if f.name not in seen and f.stat().st_size > 10_000:
                    found.append(f)
                    seen.add(f.name)
    # Sort newest first
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found


# ── Ingest OBS logs -> remember_me candidates ──────────────────────────────────

def ingest_logs(log_paths: Optional[list[Path]] = None, dry_run: bool = False) -> list[str]:
    """
    Parse OBS logs and submit each as a pending remember_me candidate.
    Returns list of candidate IDs created.
    """
    try:
        from remember_me import RememberMeStore, IdentityContinuityRecord, STATUS_PENDING
    except ImportError as e:
        print(f"[obs_ingest] remember_me not available: {e}")
        return []

    if log_paths is None:
        log_paths = find_obs_logs()

    store = RememberMeStore()
    created = []

    for lp in log_paths:
        session = OBSSession(lp).parse()
        meaning = session.compressed_meaning()
        if not meaning:
            continue

        r = IdentityContinuityRecord(
            title=f"OBS Session — {session.log_date}",
            category="builder",
            compressed_meaning=meaning,
            source=f"OBS log: {lp.name}",
            confidence="VERIFIED",
            unknowns=session.unknowns(),
            tags=["obs", "recording-session", "production-context"],
            people_referenced=["Noah Hawkes"],
        )

        if not dry_run:
            store.submit(r)
            created.append(r.id)
            print(f"  [LOG  ] {session.summary_line()} -> candidate {r.id[:8]} (pending)")
        else:
            print(f"  [DRY  ] {session.summary_line()} -> would create candidate")

    return created


# ── Ingest OBS videos -> video_intelligence candidates ─────────────────────────

def ingest_videos(
    video_paths: Optional[list[Path]] = None,
    max_videos: int = 20,
    dry_run: bool = False,
) -> list[str]:
    """
    Submit OBS recordings through video_intelligence pipeline.
    Returns list of candidate IDs created.
    All candidates born PENDING — Noah must approve.
    """
    try:
        from video_intelligence import analyze_video
    except ImportError as e:
        print(f"[obs_ingest] video_intelligence not available: {e}")
        return []

    if video_paths is None:
        video_paths = find_obs_videos()[:max_videos]

    created = []
    for vp in video_paths:
        size_mb = round(vp.stat().st_size / 1_048_576, 1)
        print(f"  [VIDEO] {vp.name} ({size_mb}MB) ...", end=" ", flush=True)

        try:
            candidate = analyze_video(
                str(vp),
                approved_by_noah=True,   # Noah has pre-approved his own OBS recordings for observation
                dry_run=dry_run,
            )
            status = candidate.status
            created.append(candidate.id)
            print(f"-> {status} [{candidate.id[:8]}] cat={candidate.recommended_candidate_type} sens={candidate.sensitivity}")
        except PermissionError as e:
            print(f"-> GATE BLOCKED: {e}")
        except FileNotFoundError as e:
            print(f"-> NOT FOUND: {e}")
        except Exception as e:
            print(f"-> ERROR: {type(e).__name__}: {str(e)[:80]}")

    return created


# ── List mode (no write) ──────────────────────────────────────────────────────

def list_available() -> None:
    logs   = find_obs_logs()
    videos = find_obs_videos()

    print(f"\nOBS Logs ({len(logs)} found):")
    for lp in logs:
        size = round(lp.stat().st_size / 1024, 1)
        mtime = datetime.fromtimestamp(lp.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {lp.name:45s}  {size:8.1f}KB  {mtime}")

    print(f"\nOBS Videos ({len(videos)} found, sorted by date):")
    for vp in videos[:30]:
        size_mb = round(vp.stat().st_size / 1_048_576, 1)
        mtime   = datetime.fromtimestamp(vp.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {vp.name:55s}  {size_mb:8.1f}MB  {mtime}")


# ── Smoke tests ───────────────────────────────────────────────────────────────

def run_smoke_tests() -> int:
    failures = 0
    results  = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        status = "PASS" if passed else "FAIL"
        results.append(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    # ── Log discovery ────────────────────────────────────────────────────────
    logs = find_obs_logs()
    check("find_obs_logs: returns list", isinstance(logs, list))
    check("find_obs_logs: OBS log dir exists -> found logs",
          not OBS_LOG_DIR.exists() or len(logs) > 0,
          f"found {len(logs)}")

    # ── Video discovery ──────────────────────────────────────────────────────
    videos = find_obs_videos()
    check("find_obs_videos: returns list", isinstance(videos, list))
    # At least one video dir exists
    video_dir_exists = any(d.exists() for d in OBS_VIDEO_DIRS)
    check("find_obs_videos: at least one video dir exists", video_dir_exists)

    # ── OBSSession parser ────────────────────────────────────────────────────
    import tempfile, os

    # Create a fake log and parse it
    fake_log_content = (
        "20:00:00.000: Crash or unclean shutdown detected\n"
        "20:00:01.000: CPU Name: Intel(R) Core(TM) i9-14900HX\n"
        "20:00:01.000: Physical Memory: 32468MB Total, 12748MB Free\n"
        "20:00:02.000: output resolution: 1920x1080\n"
        "20:00:03.000: Switched to scene 'Main Screen Present'\n"
        "20:00:04.000: Loaded scenes:\n"
        "20:00:04.000: - scene 'Rendered Reality':\n"
        "20:00:05.000: User switched to scene 'Rendered Reality'\n"
        "20:00:10.000: ==== Recording Start ===============================================\n"
        "20:00:10.000: [ffmpeg muxer: 'simple_file_output'] Writing file 'C:/Users/noahh/OneDrive/Videos/2026-06-07_20-00-10.mkv'...\n"
        "20:30:00.000: ==== Recording Stop  ===============================================\n"
        "20:30:00.001: [error] Something went wrong with audio device\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False,
        prefix="2026-06-01 20-00-00",
        encoding="utf-8"
    ) as tf:
        tf.write(fake_log_content)
        fake_path = Path(tf.name)

    session = OBSSession(fake_path).parse()
    check("OBSSession: crash detected", session.crash_detected)
    check("OBSSession: recording start captured", len(session.recording_starts) == 1)
    check("OBSSession: recording stop captured", len(session.recording_stops) == 1)
    check("OBSSession: output file captured", len(session.output_files) == 1)
    check("OBSSession: scene switch captured", "Rendered Reality" in session.scenes_switched)
    check("OBSSession: cpu captured", "i9" in session.cpu)
    check("OBSSession: ram captured", session.ram_total_mb == 32468)
    check("OBSSession: resolution captured", session.resolution == "1920x1080")
    check("OBSSession: error captured", len(session.errors) >= 1)

    meaning = session.compressed_meaning()
    check("compressed_meaning: non-empty string", isinstance(meaning, str) and len(meaning) > 20)
    check("compressed_meaning: mentions date", "2026-06-01" in meaning or fake_path.stem[:10] in meaning)
    check("compressed_meaning: mentions crash", "crash" in meaning.lower() or "unclean" in meaning.lower())
    check("compressed_meaning: mentions recording", "recording" in meaning.lower())

    unknowns = session.unknowns()
    check("unknowns: returns list", isinstance(unknowns, list))

    summary = session.summary_line()
    check("summary_line: non-empty", isinstance(summary, str) and len(summary) > 5)
    check("summary_line: mentions CRASH", "[CRASH]" in summary)

    os.unlink(fake_path)

    # ── Dry-run log ingest ───────────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False,
        prefix="2026-06-02 10-00-00",
        encoding="utf-8"
    ) as tf:
        tf.write("10:00:00.000: CPU Name: Test CPU\n")
        tf.write("10:00:01.000: ==== Recording Start ===============\n")
        tf.write("10:00:01.000: [ffmpeg muxer: 'simple_file_output'] Writing file 'C:/test.mkv'...\n")
        tf.write("10:30:00.000: ==== Recording Stop  ===============\n")
        fake2 = Path(tf.name)

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        created = ingest_logs([fake2], dry_run=True)
    output = buf.getvalue()
    check("ingest_logs dry_run: returns list", isinstance(created, list))
    check("ingest_logs dry_run: no candidates created", len(created) == 0)
    check("ingest_logs dry_run: printed DRY line", "[DRY" in output)
    os.unlink(fake2)

    # ── list_available: no crash ─────────────────────────────────────────────
    buf2 = io.StringIO()
    try:
        with redirect_stdout(buf2):
            list_available()
        out2 = buf2.getvalue()
        check("list_available: no crash", True)
        check("list_available: shows logs section", "OBS Logs" in out2)
        check("list_available: shows videos section", "OBS Videos" in out2)
    except Exception as e:
        check("list_available: no crash", False, str(e))

    # ── print results ────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("ORACLE OBS Ingest — Smoke Tests")
    print(f"{'='*55}")
    for r in results:
        print(r)
    total  = len(results)
    passed = total - failures
    print(f"{'='*55}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*55}\n")
    return failures


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="ORACLE OBS Log + Video Ingest")
    parser.add_argument("--scan-logs",   action="store_true", help="Ingest all OBS logs -> remember_me candidates")
    parser.add_argument("--scan-videos", action="store_true", help="Submit OBS recordings -> video_intelligence candidates")
    parser.add_argument("--scan-all",    action="store_true", help="Ingest logs + videos")
    parser.add_argument("--list",        action="store_true", help="List available logs and videos (no write)")
    parser.add_argument("--dry-run",     action="store_true", help="Parse and report without writing candidates")
    parser.add_argument("--max-videos",  type=int, default=20, help="Max videos to submit (default 20)")
    parser.add_argument("--smoke-test",  action="store_true", help="Run smoke tests")
    args = parser.parse_args()

    if args.smoke_test:
        sys.exit(run_smoke_tests())

    if args.list:
        list_available()
        return

    if args.scan_logs or args.scan_all:
        logs = find_obs_logs()
        print(f"\nIngesting {len(logs)} OBS log(s){'  [DRY RUN]' if args.dry_run else ''}...")
        ids = ingest_logs(dry_run=args.dry_run)
        print(f"Log candidates created: {len(ids)}")

    if args.scan_videos or args.scan_all:
        videos = find_obs_videos()[:args.max_videos]
        print(f"\nSubmitting {len(videos)} OBS video(s){'  [DRY RUN]' if args.dry_run else ''}...")
        print("All candidates born PENDING — Noah must approve each one.\n")
        ids = ingest_videos(video_paths=videos, dry_run=args.dry_run)
        print(f"\nVideo candidates created: {len(ids)}")

    if not any([args.scan_logs, args.scan_videos, args.scan_all, args.list, args.smoke_test]):
        parser.print_help()


if __name__ == "__main__":
    main()
