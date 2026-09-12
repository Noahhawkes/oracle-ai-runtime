"""
rendered_reality/pattern_buffer/seed_loader.py

Ingest thread-pass seed data as CANDIDATE records. Scans data/thread_passes for
<name>.md + <name>.meta.json pairs, validates required metadata, REJECTS records
missing metadata, SHA-256 hashes the markdown, and writes an ingestion receipt
per record to data/receipts/thread_passes.

Nothing is promoted to canon. Every record stays candidate_seed_record /
pending_noah_physical. No canon promotion occurs here.

CLI:
    python -m rendered_reality.pattern_buffer.seed_loader
    python -m rendered_reality.pattern_buffer.seed_loader --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# repo root = rendered_reality/pattern_buffer/seed_loader.py -> up 3
REPO_ROOT = Path(__file__).resolve().parents[2]
THREAD_PASSES_DIR = REPO_ROOT / "data" / "thread_passes"
RECEIPTS_DIR = REPO_ROOT / "data" / "receipts" / "thread_passes"

REQUIRED_META_FIELDS = (
    "record_id", "title", "source_date", "source_context", "submitted_by",
    "authorial_authority", "intent_owner", "produced_with", "token_origin",
    "origin_channel", "reviewed_by", "approved_by", "authorship_status",
    "transport_path", "confidence", "canon_status", "approval_status",
    "holes", "contradictions", "required_review",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _missing_fields(meta: dict) -> list[str]:
    return [f for f in REQUIRED_META_FIELDS if f not in meta]


def load_thread_passes(base=THREAD_PASSES_DIR, receipts_dir=RECEIPTS_DIR,
                       write: bool = True) -> dict:
    base = Path(base)
    receipts_dir = Path(receipts_dir)
    if write:
        receipts_dir.mkdir(parents=True, exist_ok=True)

    loaded_record_ids: list[str] = []
    rejected: list[dict] = []
    observed_holes: list[str] = []
    pending_approvals = 0

    md_files = sorted(base.rglob("*.md")) if base.exists() else []
    for md in md_files:
        meta_path = md.parent / (md.stem + ".meta.json")
        rec = {"file": str(md.relative_to(REPO_ROOT)).replace("\\", "/"),
               "record_id": md.stem}

        if not meta_path.exists():
            rejected.append({**rec, "reason": "missing .meta.json"})
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rejected.append({**rec, "reason": f"meta parse error: {type(exc).__name__}"})
            continue

        missing = _missing_fields(meta)
        if missing:
            rejected.append({**rec, "record_id": meta.get("record_id", md.stem),
                             "reason": f"missing required fields: {missing}"})
            continue

        content = md.read_text(encoding="utf-8")
        receipt = {
            "receipt_id": f"seed_{meta['record_id']}",
            "record_id": meta["record_id"],
            "title": meta["title"],
            "source_md": str(md.relative_to(REPO_ROOT)).replace("\\", "/"),
            "content_sha256": _sha256(content),
            "ingested_at": _utc(),
            "submitted_by": meta["submitted_by"],
            "authorial_authority": meta["authorial_authority"],
            "intent_owner": meta["intent_owner"],
            "produced_with": meta["produced_with"],
            "token_origin": meta["token_origin"],
            "origin_channel": meta["origin_channel"],
            "reviewed_by": meta["reviewed_by"],
            "approved_by": meta["approved_by"],
            "authorship_status": meta["authorship_status"],
            "transport_path": meta["transport_path"],
            "confidence": meta["confidence"],
            "canon_status": meta["canon_status"],
            "approval_status": meta["approval_status"],
            "holes": meta["holes"],
            "contradictions": meta["contradictions"],
            "required_review": meta["required_review"],
            "promoted_to_canon": False,
        }
        if write:
            (receipts_dir / f"{meta['record_id']}.receipt.json").write_text(
                json.dumps(receipt, indent=2), encoding="utf-8")

        loaded_record_ids.append(meta["record_id"])
        observed_holes.extend(meta.get("holes", []) or [])
        if str(meta.get("approval_status", "")).startswith("pending"):
            pending_approvals += 1

    return {
        "loaded_count": len(loaded_record_ids),
        "rejected_count": len(rejected),
        "pending_approvals": pending_approvals,
        "observed_holes": observed_holes,
        "loaded_record_ids": loaded_record_ids,
        "rejected": rejected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest thread-pass seed data as candidate records")
    parser.add_argument("--json", action="store_true", help="emit raw JSON summary")
    parser.add_argument("--no-write", action="store_true", help="dry run; do not write receipts")
    args = parser.parse_args(argv)

    summary = load_thread_passes(write=not args.no_write)

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("ORACLE thread-pass seed ingestion")
    print(f"  source: {THREAD_PASSES_DIR}")
    print(f"  loaded:   {summary['loaded_count']}")
    print(f"  rejected: {summary['rejected_count']}")
    print(f"  pending approvals: {summary['pending_approvals']}")
    print(f"  observed holes: {len(summary['observed_holes'])}")
    for rid in summary["loaded_record_ids"]:
        print(f"    + {rid}")
    for r in summary["rejected"]:
        print(f"    - REJECTED {r['record_id']}: {r['reason']}")
    print("  canon promotion: NONE (all records remain candidate / pending_noah_physical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
