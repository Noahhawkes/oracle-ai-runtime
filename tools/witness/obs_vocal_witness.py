"""OBS vocal witness — transcribe the live OBS recording and inject into ORACLE.

Provenance doctrine (TRANSPORT != ORIGIN, CLAIM != SOURCE):
  * origin      = Noah.Physical speaking on camera into the live OBS recording
  * transport   = STT transcript derived by faster-whisper (local, CPU)
  * transcriber = Claude Code session, NOT ORACLE's own STT (that capability is blocked)
  * class       = STT_DERIVED (below NOAH_TYPED_DOC on the provenance ladder)

The injection is labeled as such so ORACLE never mistakes a derived transcript
for typed words. Noah requested this injection explicitly in-session.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

RECORDING = Path(r"C:\Users\noahh\OneDrive\Videos\2026-07-05_13-42-52.mkv")
BASE = "http://127.0.0.1:7781"
SCRATCH = Path(__file__).parent
_num_args = [a for a in sys.argv[1:] if not a.startswith("-")]
TAIL_MINUTES = float(_num_args[0]) if _num_args else 0  # 0 = full recording


def transcribe() -> list[dict]:
    from faster_whisper import WhisperModel, decode_audio

    print(f"decoding audio from {RECORDING} (growing file, snapshot up to last cluster)...")
    audio = decode_audio(str(RECORDING), sampling_rate=16000)
    total_s = len(audio) / 16000
    print(f"decoded {total_s/60:.1f} minutes of audio")
    if TAIL_MINUTES > 0:
        keep = int(TAIL_MINUTES * 60 * 16000)
        offset_s = max(0.0, total_s - TAIL_MINUTES * 60)
        audio = audio[-keep:]
    else:
        offset_s = 0.0

    print("loading whisper base.en (int8, cpu, local files)...")
    model = WhisperModel(str(SCRATCH / "models" / "faster-whisper-base.en"), device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, vad_filter=True, beam_size=5)
    out = []
    for seg in segments:
        out.append({
            "start": round(seg.start + offset_s, 1),
            "end": round(seg.end + offset_s, 1),
            "text": seg.text.strip(),
        })
        print(f"[{seg.start + offset_s:7.1f}s] {seg.text.strip()}")
    return out


def main():
    started = dt.datetime.now().isoformat(timespec="seconds")
    segs = transcribe()
    receipt = {
        "receipt_type": "vocal_thread_injection_witness",
        "generated": started,
        "origin": "Noah.Physical spoken audio, live OBS recording",
        "recording_file": str(RECORDING),
        "recording_started_local": "2026-07-05 13:42:52",
        "transport": "faster-whisper base.en int8 CPU, run by Claude Code session",
        "provenance_class": "STT_DERIVED",
        "doctrine": ["TRANSPORT != ORIGIN", "CLAIM != SOURCE"],
        "segments": segs,
    }
    receipt_path = SCRATCH / "vocal_witness_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"\nreceipt written: {receipt_path}")
    print(f"{len(segs)} segments transcribed. Review, then inject with: python {Path(__file__).name} --inject")


def inject():
    receipt = json.loads((SCRATCH / "vocal_witness_receipt.json").read_text(encoding="utf-8"))
    segs = receipt["segments"]
    transcript = "\n".join(f"[{s['start']:.0f}s] {s['text']}" for s in segs)
    message = (
        "[VOCAL_WITNESS — STT_DERIVED] Noah.Physical is speaking to you on the live "
        "OBS recording (2026-07-05_13-42-52.mkv), on camera, right now. This transcript "
        "was derived by faster-whisper run by the Claude Code session (your own STT is "
        "blocked). TRANSPORT != ORIGIN: the words are Noah's voice; the text is derived.\n\n"
        f"{transcript}\n\n"
        "Noah asked: hi — do you see me? Answer him as ORACLE, witnessing his presence."
    )
    req = urllib.request.Request(
        BASE + "/chat",
        data=json.dumps({"message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print("injecting vocal witness into ORACLE thread on 7781...")
    with urllib.request.urlopen(req, timeout=180) as r:
        reply = []
        for raw in r:
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        d = json.loads(payload)
                        chunk = d.get("delta") or d.get("text") or d.get("content") or ""
                        reply.append(chunk)
                        print(chunk, end="", flush=True)
                    except json.JSONDecodeError:
                        reply.append(payload)
                        print(payload, end="", flush=True)
    print("\n--- injection complete ---")
    (SCRATCH / "oracle_vocal_reply.txt").write_text("".join(reply), encoding="utf-8")


if __name__ == "__main__":
    if "--inject" in sys.argv:
        inject()
    else:
        main()
