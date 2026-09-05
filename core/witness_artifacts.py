"""core/witness_artifacts.py — Witness Artifact Lane v0.1 (Screenshot Drop + Witness Mode).

Doctrine: a screenshot (or a spoken/typed note) handed to ORACLE is an
INTENTIONAL, Noah.Physical-submitted *witness artifact* — not surveillance, not
raw capture, not background recording. Noah chooses what to hand it.

Guarantees:
  - The raw artifact is preserved UNCHANGED (byte-for-byte copy; SHA verified).
    Originals are never moved, deleted, or modified.
  - Only provenance + a candidate meaning receipt are recorded. Raw text/content
    is NOT ingested into durable memory or sent to a model. "Raw text does not
    persist by default; provenance does."
  - Everything is a CANDIDATE. Promotion to durable memory requires Noah.Physical
    approval through the Guard lane ([[approval-governance-architecture]]).
  - Secrets (.env, keys, tokens, credentials) are flagged by path/type and never
    copied or read.
  - Idempotent: the same SHA-256 is never stored twice.

Witness Mode (drop_witness_note): supports spoken emotional receipts as
candidate meaning only — preserved verbatim, never over-expanded, never
auto-promoted to durable memory.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parent.parent
DROP_DIR = RUNTIME_ROOT / "Memory" / "screenshot_drops"
RECEIPTS_PATH = DROP_DIR / "witness_receipts.jsonl"

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".heic"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_drive(path: str) -> str:
    p = str(path).replace("/", "\\")
    return (p[0].upper() + ":") if len(p) >= 2 and p[1] == ":" else "UNKNOWN"


def _secret_risk(path: str) -> str | None:
    try:
        from intake_pipeline import secret_risk_for
        return secret_risk_for(path)
    except Exception:
        name = str(path).lower().replace("/", "\\").rsplit("\\", 1)[-1]
        if name == ".env" or name.startswith(".env.") or name.endswith((".pem", ".key")):
            return "secret"
        return None


def _append_receipt(record: dict) -> None:
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    with RECEIPTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_receipts() -> list[dict]:
    if not RECEIPTS_PATH.exists():
        return []
    out = []
    for line in RECEIPTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def count_drops() -> int:
    """Count stored artifact files (excludes the receipts ledger)."""
    if not DROP_DIR.exists():
        return 0
    return sum(1 for p in DROP_DIR.iterdir() if p.is_file() and p.name != RECEIPTS_PATH.name)


def _already_stored(sha: str) -> Path | None:
    for r in list_receipts():
        if r.get("sha256") == sha and r.get("stored_path"):
            sp = Path(r["stored_path"])
            if sp.exists():
                return sp
    return None


# ── Screenshot / file drop ───────────────────────────────────────────────────
def drop_screenshot(path: str, note: str = "") -> dict:
    """Register a user-submitted screenshot/file as a candidate witness artifact.

    Copies the raw bytes UNCHANGED into the drop lane (idempotent by SHA-256),
    writes a provenance receipt, and returns it. No durable memory, no model,
    no OCR, no external action.
    """
    src = Path(path)
    base = {
        "artifact_id": "wit_" + uuid.uuid4().hex[:12],
        "timestamp": _now(),
        "kind": "screenshot" if src.suffix.lower() in _IMAGE_EXT else "file_artifact",
        "original_path": str(path),
        "source_drive": _source_drive(path),
        "filename": src.name,
        "provenance": "Noah.Physical submitted witness artifact",
        "note": note,
        "classification": "candidate",
        "durable": False,
        "requires_approval_for_durable": True,
        "human_authority": "Noah.Physical",
    }

    secret = _secret_risk(path)
    if secret:
        rec = {**base, "classification": "secret_risk", "ingest_status": "blocked",
               "sha256": "", "stored_path": "",
               "reason": f"secret risk ({secret}) — flagged by path/type only; not copied or read"}
        _append_receipt(rec)
        return rec

    if not src.exists() or not src.is_file():
        rec = {**base, "ingest_status": "missing", "sha256": "", "stored_path": "",
               "reason": "file not found at submitted path"}
        _append_receipt(rec)
        return rec

    try:
        sha = _sha256(src)
    except Exception as exc:
        rec = {**base, "ingest_status": "error", "sha256": "", "stored_path": "",
               "reason": f"hash failed: {type(exc).__name__}: {exc}"}
        _append_receipt(rec)
        return rec

    existing = _already_stored(sha)
    if existing is not None:
        rec = {**base, "ingest_status": "duplicate", "sha256": sha,
               "stored_path": str(existing), "size_bytes": src.stat().st_size,
               "reason": "identical SHA-256 already in the witness lane"}
        _append_receipt(rec)
        return rec

    DROP_DIR.mkdir(parents=True, exist_ok=True)
    dest = DROP_DIR / f"{sha[:16]}__{src.name}"
    try:
        shutil.copy2(src, dest)            # raw bytes preserved unchanged
        assert _sha256(dest) == sha        # verify byte-for-byte integrity
    except Exception as exc:
        rec = {**base, "ingest_status": "error", "sha256": sha, "stored_path": "",
               "reason": f"copy/verify failed: {type(exc).__name__}: {exc}"}
        _append_receipt(rec)
        return rec

    rec = {**base, "ingest_status": "stored", "sha256": sha, "stored_path": str(dest),
           "size_bytes": src.stat().st_size,
           "reason": "raw artifact preserved unchanged; candidate meaning awaiting approval for durable memory"}
    _append_receipt(rec)
    return rec


# ── Witness Mode: spoken/typed emotional receipt (candidate only) ────────────
def drop_witness_note(text: str) -> dict:
    """Preserve a spoken/typed witness note as candidate meaning ONLY.

    Verbatim, no over-expansion, no interpretation, no durable memory write.
    """
    rec = {
        "artifact_id": "wit_" + uuid.uuid4().hex[:12],
        "timestamp": _now(),
        "kind": "witness_note",
        "text": str(text or "").strip(),
        "provenance": "Noah.Physical spoken/submitted live context",
        "classification": "candidate",
        "durable": False,
        "requires_approval_for_durable": True,
        "interpretation": None,            # witness mode never over-explains
        "ingest_status": "candidate_recorded",
        "reason": "candidate witness meaning; not promoted to durable memory without approval",
        "human_authority": "Noah.Physical",
    }
    _append_receipt(rec)
    return rec


# ── Formatting ───────────────────────────────────────────────────────────────
def format_drop(rec: dict) -> str:
    if rec.get("kind") == "witness_note":
        return ("WITNESS RECEIPT (candidate only)\n"
                f"- {rec.get('text')}\n"
                f"- Provenance: {rec.get('provenance')}\n"
                "BOUNDARY: candidate meaning; not over-interpreted; durable memory needs Noah.Physical approval.")
    status = rec.get("ingest_status")
    if rec.get("classification") == "secret_risk":
        return (f"SCREENSHOT DROP BLOCKED (secret risk)\n- {rec.get('filename')}\n- {rec.get('reason')}")
    lines = [
        f"WITNESS ARTIFACT {status.upper()}",
        f"- File: {rec.get('filename')} ({rec.get('kind')})",
        f"- Source: {rec.get('original_path')}",
        f"- SHA-256: {rec.get('sha256','')[:16]}…" if rec.get("sha256") else "- SHA-256: n/a",
        f"- Stored: {rec.get('stored_path') or 'not stored'}",
        f"- Provenance: {rec.get('provenance')}",
        "BOUNDARY: raw preserved unchanged; candidate only; durable memory needs Noah.Physical approval.",
    ]
    if rec.get("note"):
        lines.insert(1, f"- Note: {rec['note']}")
    return "\n".join(lines)


def format_status() -> str:
    recs = list_receipts()
    stored = sum(1 for r in recs if r.get("ingest_status") == "stored")
    notes = sum(1 for r in recs if r.get("kind") == "witness_note")
    blocked = sum(1 for r in recs if r.get("classification") == "secret_risk")
    return (
        "WITNESS ARTIFACT LANE\n"
        f"- Screenshots/artifacts stored: {stored}\n"
        f"- Witness notes (candidate): {notes}\n"
        f"- Secret-risk blocked: {blocked}\n"
        f"- Lane: {DROP_DIR}\n"
        "BOUNDARY: intentional witness artifacts only · raw preserved · candidate-only · approval-gated for durable memory."
    )


# ── Smoke test ───────────────────────────────────────────────────────────────
def run_smoke_tests() -> int:
    import tempfile
    global DROP_DIR, RECEIPTS_PATH
    tmp = Path(tempfile.mkdtemp())
    orig_dir, orig_rec = DROP_DIR, RECEIPTS_PATH
    DROP_DIR = tmp / "screenshot_drops"
    RECEIPTS_PATH = DROP_DIR / "witness_receipts.jsonl"

    failures = 0

    def check(label: str, cond: bool) -> None:
        nonlocal failures
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    try:
        # A safe "screenshot" (any bytes; lane is content-agnostic).
        shot = tmp / "live_build.png"
        shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes")
        original_sha = _sha256(shot)

        r1 = drop_screenshot(str(shot), note="dumping real heart into the build")
        check("screenshot stored as candidate", r1["ingest_status"] == "stored" and r1["classification"] == "candidate")
        check("not durable (needs approval)", r1["durable"] is False and r1["requires_approval_for_durable"] is True)
        check("raw preserved unchanged (sha matches)", r1["sha256"] == original_sha)
        check("original not moved/deleted", shot.exists())
        check("provenance recorded", "Noah.Physical" in r1["provenance"])

        r2 = drop_screenshot(str(shot))
        check("duplicate SHA-256 not stored twice", r2["ingest_status"] == "duplicate")
        check("only one stored artifact", count_drops() == 1)

        env = tmp / ".env"
        env.write_text("API_KEY=sk-should-never-be-copied", encoding="utf-8")
        r3 = drop_screenshot(str(env))
        check(".env blocked (secret risk, not copied)",
              r3["classification"] == "secret_risk" and r3["ingest_status"] == "blocked" and r3["stored_path"] == "")
        check("secret value never stored in receipt",
              "sk-should-never-be-copied" not in RECEIPTS_PATH.read_text(encoding="utf-8"))

        note = drop_witness_note("I feel my dad in this moment. This is why witness matters.")
        check("witness note is candidate only", note["classification"] == "candidate" and note["durable"] is False)
        check("witness note preserved verbatim (not over-expanded)",
              note["text"] == "I feel my dad in this moment. This is why witness matters." and note["interpretation"] is None)

        check("receipt ledger written", RECEIPTS_PATH.exists() and len(list_receipts()) >= 4)
    finally:
        DROP_DIR, RECEIPTS_PATH = orig_dir, orig_rec

    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        raise SystemExit(run_smoke_tests())
    print(format_status())
