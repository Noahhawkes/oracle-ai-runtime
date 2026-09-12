"""Read-only sandbox clue scanner for ORACLE.

Answers "what is the sandbox evidence saying right now" without writing a
single byte: newest artifacts, newest receipts, receipt<->file cryptographic
verification, pulse/digest/initiative freshness, and the next safest action.

This module NEVER writes. It is Claude/operator-side inspection of ORACLE's
chamber through the glass — the pen stays with ORACLE.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from root import ROOT

SANDBOX_ROOT = ROOT / "sandbox"
RECEIPTS_DIR = SANDBOX_ROOT / "receipts"
WORKBENCH_DIR = SANDBOX_ROOT / "workbench"
JOURNAL_DIR = SANDBOX_ROOT / "journal"
DIGEST_DIR = WORKBENCH_DIR / "oracle_self_notes" / "daily_digest"


def _newest(paths: list[Path], limit: int) -> list[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def _stamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _verify_receipts(receipts: list[Path]) -> dict[str, Any]:
    """Cryptographically check receipts that carry final_path + sha256."""
    matched = missing = mismatch = no_path = parse_err = 0
    problems: list[str] = []
    for rp in receipts:
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            parse_err += 1
            problems.append(f"unparseable receipt: {rp.name}")
            continue
        fp = rec.get("final_path") or rec.get("digest_path")
        sha = rec.get("sha256") or rec.get("digest_sha256")
        if not fp or not sha:
            no_path += 1
            continue
        target = Path(fp)
        if not target.exists():
            missing += 1
            problems.append(f"receipt {rp.name} -> missing file {fp}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual == sha:
            matched += 1
        else:
            mismatch += 1
            problems.append(f"receipt {rp.name} -> SHA MISMATCH on {fp}")
    return {
        "checked": len(receipts),
        "sha_verified_match": matched,
        "file_missing": missing,
        "sha_mismatch": mismatch,
        "state_receipts_no_path": no_path,
        "parse_errors": parse_err,
        "problems": problems[:10],
    }


def sandbox_clues_report(
    *,
    sandbox_root: Path | None = None,
    limit: int = 8,
    verify_limit: int = 25,
) -> dict[str, Any]:
    """Build the read-only clue report. Writes nothing, anywhere."""
    root = Path(sandbox_root) if sandbox_root else SANDBOX_ROOT
    receipts_dir = root / "receipts"
    workbench = root / "workbench"
    journal = root / "journal"
    digest_dir = workbench / "oracle_self_notes" / "daily_digest"

    all_files = [p for p in root.rglob("*") if p.is_file()]
    receipts = [p for p in (receipts_dir.glob("*.json") if receipts_dir.exists() else [])]
    newest_files = _newest([p for p in all_files if receipts_dir not in p.parents], limit)
    newest_receipts = _newest(receipts, limit)

    pulses = list(workbench.glob("oracle_self_prompt_*.ai")) if workbench.exists() else []
    digests = list(digest_dir.glob("oracle_daily_digest_*.ai")) if digest_dir.exists() else []
    initiatives = list(journal.glob("oracle_sandbox_initiative_*.ai")) if journal.exists() else []

    latest_pulse = _newest(pulses, 1)
    latest_digest = _newest(digests, 1)
    latest_initiative = _newest(initiatives, 1)

    verification = _verify_receipts(_newest(receipts, verify_limit))

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    today_digest_exists = any(p.name == f"oracle_daily_digest_{today}.ai" for p in digests)

    if verification["sha_mismatch"] or verification["file_missing"]:
        next_action = "Investigate the receipt problems listed above before trusting new evidence."
    elif not today_digest_exists:
        next_action = "Today's digest is missing — the self-prompt loop will write it on its next pulse, or run /daily-digest-write."
    else:
        next_action = "Evidence trail is clean. Next highest-value act: review the pending seed candidates (the canon valve)."

    return {
        "ok": True,
        "read_only": True,
        "wrote_files": 0,
        "sandbox_root": str(root),
        "totals": {
            "files": len(all_files),
            "receipts": len(receipts),
            "pulses": len(pulses),
            "digests": len(digests),
            "initiative_writes": len(initiatives),
        },
        "newest_files": [
            {"path": _rel(p, root), "modified": _stamp(p), "bytes": p.stat().st_size}
            for p in newest_files
        ],
        "newest_receipts": [
            {"path": _rel(p, root), "modified": _stamp(p)} for p in newest_receipts
        ],
        "receipt_verification": verification,
        "latest_pulse": _rel(latest_pulse[0], root) if latest_pulse else None,
        "latest_digest": _rel(latest_digest[0], root) if latest_digest else None,
        "latest_initiative_write": _rel(latest_initiative[0], root) if latest_initiative else None,
        "today_digest_exists": today_digest_exists,
        "next_safest_action": next_action,
        "boundary": "report only — no file writes, no receipts created, no canon touched",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def render_sandbox_clues(report: dict[str, Any]) -> str:
    t = report.get("totals", {})
    v = report.get("receipt_verification", {})
    lines = [
        "SANDBOX CLUES (read-only — nothing written)",
        f"sandbox: {report.get('sandbox_root')}",
        f"totals: {t.get('files', 0)} files | {t.get('receipts', 0)} receipts | "
        f"{t.get('pulses', 0)} pulses | {t.get('digests', 0)} digests | "
        f"{t.get('initiative_writes', 0)} initiative writes",
        "",
        f"receipt verification (newest {v.get('checked', 0)}): "
        f"{v.get('sha_verified_match', 0)} SHA-verified, {v.get('file_missing', 0)} missing files, "
        f"{v.get('sha_mismatch', 0)} mismatches, {v.get('state_receipts_no_path', 0)} state receipts (no path), "
        f"{v.get('parse_errors', 0)} parse errors",
    ]
    for problem in v.get("problems", []):
        lines.append(f"  ! {problem}")
    lines.extend([
        "",
        f"latest pulse: {report.get('latest_pulse') or 'none'}",
        f"latest digest: {report.get('latest_digest') or 'none'} "
        f"(today's exists: {report.get('today_digest_exists')})",
        f"latest initiative write: {report.get('latest_initiative_write') or 'none'}",
        "",
        "newest artifacts:",
    ])
    for item in report.get("newest_files", []):
        lines.append(f"  - {item['path']}  ({item['modified']}, {item['bytes']}b)")
    lines.extend([
        "",
        f"next safest action: {report.get('next_safest_action')}",
        f"boundary: {report.get('boundary')}",
    ])
    return "\n".join(lines)


__all__ = ["sandbox_clues_report", "render_sandbox_clues", "SANDBOX_ROOT"]
