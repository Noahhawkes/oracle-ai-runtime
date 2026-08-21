"""prompt_witness.py — screen-recording witness for AI prompts/responses.

Samples the live OBS recording every INTERVAL seconds, reads the frame with
ORACLE's local vision model (qwen2.5vl:7b via ollama), and appends receipted
rows to a JSONL witness log. Local-only: no upload, no cloud, no mutation of
the recording. Provenance: every row carries the recording path, frame time,
and frame sha256. Extractions are INTERPRETED-state candidate text, not canon.

Stop: create C:\Oracle\state\prompt_witness\stop.flag
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import av

STATE = Path(r"C:\Oracle\state\prompt_witness")
FRAMES = STATE / "frames"
LOG = STATE / "witness_log.jsonl"
STOP_FLAG = STATE / "stop.flag"
OBS_LOGS = Path(r"C:\Users\noahh\AppData\Roaming\obs-studio\logs")
OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5vl:7b"
INTERVAL = 60  # seconds between samples
SCREENSHOT_CAPTURE_ENABLED = False

PROMPT = (
    "This is a screenshot of a desktop with one or more AI chat applications visible "
    "(ChatGPT, Claude, Copilot, Gemini, Meta AI, Grok, ORACLE, etc). For EACH visible AI chat "
    "window, report: 1) which AI system, 2) the most recent USER PROMPT visible (verbatim if "
    "readable), 3) the most recent AI RESPONSE visible (first ~50 words). "
    "If text is unreadable say UNREADABLE. If no AI chat is visible say NONE. "
    "Be literal - transcribe only what is actually visible on screen."
)


def active_recording() -> Path | None:
    """Newest 'Writing file' path from the newest OBS log, if not stopped after."""
    logs = sorted(OBS_LOGS.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return None
    text = logs[0].read_text(encoding="utf-8", errors="replace")
    writes = re.findall(r"Writing file '([^']+)'", text)
    if not writes:
        return None
    path = Path(writes[-1])
    # if a Recording Stop appears after the last Writing file line, not live
    last_write_pos = text.rfind(writes[-1])
    if "Recording Stop" in text[last_write_pos:]:
        return None
    return path if path.exists() else None


def grab_live_frame(rec: Path):
    """Frame near the live edge of a growing MKV. Returns (PIL.Image, t_seconds)."""
    f = av.open(str(rec))
    vs = f.streams.video[0]
    started = datetime.strptime(rec.stem, "%Y-%m-%d_%H-%M-%S")
    dur_guess = (datetime.now() - started).total_seconds()
    f.seek(int(max(0, dur_guess - 20) / vs.time_base), stream=vs)
    frame = next(f.decode(vs), None)
    if frame is None:
        return None, None
    return frame.to_image(), float(frame.time or 0)


def vision_read(img_b64: str) -> str:
    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": MODEL, "prompt": PROMPT, "images": [img_b64],
                         "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["response"]


def main():
    if not SCREENSHOT_CAPTURE_ENABLED:
        print(
            "prompt_witness disabled: screenshot extraction was replaced by "
            "obs_media_metadata_witness.py",
            flush=True,
        )
        return
    FRAMES.mkdir(parents=True, exist_ok=True)
    prev_extract_hash = None
    print(f"prompt_witness up. interval={INTERVAL}s log={LOG}", flush=True)
    while not STOP_FLAG.exists():
        try:
            rec = active_recording()
            if rec is None:
                print("no active recording; waiting", flush=True)
                time.sleep(INTERVAL)
                continue
            img, t = grab_live_frame(rec)
            if img is None:
                time.sleep(INTERVAL)
                continue
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            frame_path = FRAMES / f"frame_{ts}.png"
            img.save(frame_path)
            raw = frame_path.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            extraction = vision_read(base64.b64encode(raw).decode())
            ehash = hashlib.sha256(extraction.encode()).hexdigest()[:16]
            unchanged = ehash == prev_extract_hash
            if unchanged:
                frame_path.unlink()  # keep only frames with new content
            row = {
                "ts_utc": ts,
                "recording_file": str(rec),
                "frame_time_s": round(t, 1),
                "frame_sha256": sha,
                "frame_path": None if unchanged else str(frame_path),
                "model": MODEL,
                "state": "INTERPRETED",
                "canon_status": "candidate",
                "unchanged_from_previous": unchanged,
                "extraction": None if unchanged else extraction,
            }
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"[{ts}] frame@{t/60:.1f}min {'unchanged' if unchanged else 'NEW content logged'}",
                  flush=True)
            prev_extract_hash = ehash
        except Exception as exc:
            print(f"witness error: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(INTERVAL)
    print("stop.flag found - prompt_witness down.", flush=True)


if __name__ == "__main__":
    main()
