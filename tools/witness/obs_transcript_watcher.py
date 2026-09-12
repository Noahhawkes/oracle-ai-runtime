"""obs_transcript_watcher.py — ongoing daily transcript of OBS recordings.

Catches up on every recording from today, then follows the active recording,
transcribing new audio increments as they land. Appends to one dated markdown
transcript with wall-clock timestamps. Local-only (faster-whisper on CPU).

Provenance: audio source is desktop-audio + mic mix as OBS recorded it.
Speaker attribution is NOT performed — before 14:42 local today the mic was
dead, so earlier speech is system/desktop audio (videos, calls, media), not
necessarily Noah's voice. Marked in the transcript header.

Stop: create C:\Oracle\state\transcripts\obs\stop.flag
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel, decode_audio
from source_thread import THREAD_ID, THREAD_PATH, append_event

VIDEOS = Path(r"C:\Users\noahh\OneDrive\Videos")
OUT_DIR = Path(r"C:\Oracle\state\transcripts\obs")
STOP_FLAG = OUT_DIR / "stop.flag"
PROGRESS = OUT_DIR / "progress.json"
MODEL_DIR = Path("C:/Oracle/state/models/faster-whisper-base.en")
OBS_LOGS = Path(r"C:\Users\noahh\AppData\Roaming\obs-studio\logs")
INTERVAL = 120  # seconds between live increments
SR = 16000

_model = None


def model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
    return _model


def rec_start(path: Path) -> datetime:
    return datetime.strptime(path.stem, "%Y-%m-%d_%H-%M-%S")


def today_recordings() -> list[Path]:
    stamp = datetime.now().strftime("%Y-%m-%d")
    return sorted(VIDEOS.glob(f"{stamp}_*.mkv"))


def active_recording() -> Path | None:
    logs = sorted(OBS_LOGS.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return None
    text = logs[0].read_text(encoding="utf-8", errors="replace")
    writes = re.findall(r"Writing file '([^']+)'", text)
    if not writes:
        return None
    if "Recording Stop" in text[text.rfind(writes[-1]):]:
        return None
    p = Path(writes[-1])
    return p if p.exists() else None


def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {}


def save_progress(prog: dict) -> None:
    PROGRESS.write_text(json.dumps(prog, indent=2), encoding="utf-8")


def out_file() -> Path:
    return OUT_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_obs_transcript.md"


def ensure_header(fh_path: Path) -> None:
    if fh_path.exists():
        return
    fh_path.write_text(
        f"# OBS Recording Transcript — {datetime.now().strftime('%Y-%m-%d')}\n\n"
        "Source: OBS recordings, desktop-audio + mic mix. Transcribed locally by\n"
        "faster-whisper base.en (STT_DERIVED — transport, not origin).\n"
        "NOTE: microphone was DEAD until ~14:42 local; audio before that is\n"
        "system/desktop sound (videos, calls, media), not necessarily Noah's voice.\n"
        "Speaker attribution not performed. canon_status: candidate.\n",
        encoding="utf-8",
    )


def transcribe_span(audio: np.ndarray, wall_base: datetime, offset_s: float) -> list[str]:
    segs, _ = model().transcribe(audio, vad_filter=True, beam_size=5)
    lines = []
    for s in segs:
        wall = wall_base + timedelta(seconds=offset_s + s.start)
        txt = s.text.strip()
        if txt:
            lines.append(f"- **{wall.strftime('%H:%M:%S')}** {txt}")
    return lines


def process_increment(rec: Path, prog: dict) -> int:
    key = rec.name
    done_s = float(prog.get(key, 0.0))
    audio = decode_audio(str(rec), sampling_rate=SR)
    total_s = len(audio) / SR
    if total_s - done_s < 30:
        return 0
    chunk = audio[int(done_s * SR):]
    peak = float(np.abs(chunk).max()) if len(chunk) else 0.0
    lines: list[str] = []
    if peak > 0.001:
        lines = transcribe_span(chunk, rec_start(rec), done_s)
    out = out_file()
    ensure_header(out)
    with out.open("a", encoding="utf-8") as fh:
        if done_s == 0:
            fh.write(f"\n## Recording {rec.name} (started {rec_start(rec).strftime('%H:%M:%S')})\n\n")
        if lines:
            fh.write("\n".join(lines) + "\n")
        elif done_s == 0 and peak <= 0.001:
            fh.write("*(no audio signal in this span)*\n")
    append_event(
        "obs_transcript_segment",
        source_path=rec,
        content={
            "recording": rec.name,
            "offset_start_s": round(done_s, 3),
            "offset_end_s": round(total_s, 3),
            "audio_peak": round(peak, 6),
            "transcript_lines": lines,
            "speaker_attribution": None,
        },
        provenance={
            "method": "local_faster_whisper_audio_extraction",
            "model": str(MODEL_DIR),
            "raw_audio_stored": False,
            "screenshot_created": False,
        },
    )
    prog[key] = total_s
    save_progress(prog)
    return len(lines)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prog = load_progress()
    print(
        f"transcript watcher up. canonical_thread={THREAD_ID} path={THREAD_PATH}; "
        f"derived_view={out_file()}",
        flush=True,
    )
    # catch-up pass over all of today's recordings
    for rec in today_recordings():
        try:
            n = process_increment(rec, prog)
            print(f"catch-up {rec.name}: +{n} lines", flush=True)
        except Exception as exc:
            print(f"catch-up error {rec.name}: {type(exc).__name__}: {exc}", flush=True)
    # follow the live recording
    while not STOP_FLAG.exists():
        try:
            rec = active_recording()
            if rec is not None:
                n = process_increment(rec, prog)
                if n:
                    print(f"live {rec.name}: +{n} lines", flush=True)
        except Exception as exc:
            print(f"live error: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(INTERVAL)
    print("stop.flag found - transcript watcher down.", flush=True)


if __name__ == "__main__":
    main()
