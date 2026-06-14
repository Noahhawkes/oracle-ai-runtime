"""
core/mindcoin_drive.py - governed aspiration loop for ORACLE MindCoin.

This is not MiracleDrive. MiracleDrive is the filesystem/search index.
This module can read MiracleDrive's already-warm index for grounding, but it
does not widen Drive access and does not mutate indexed source files.

MindCoin is not money. This module treats it as a local continuity score that
ORACLE may aspire to earn only by producing evidenced, Noah-approvable work.

The drive is bounded:
  - no auto-approval
  - no pressure on Noah
  - no invented progress
  - no raw surveillance
  - no financial framing
"""
from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
MEMORY = ROOT / "Memory"
for _p in (str(ROOT), str(CORE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESEARCH_SOURCES = [
    Path(r"C:\Users\noahh\OneDrive\EH3 Holdings\NOAH AI\Noah.AI Tech Documents\RECURSIONSTACK.txt"),
    Path(r"C:\Users\noahh\OneDrive\EH3 Holdings\NOAH AI\Noah.AI Tech Documents\Legacy.GI\RECURSIONSTACK.txt"),
    Path(r"C:\Users\noahh\OneDrive\Recursive_Identity_Stack_Whitepaper.docx"),
    Path(r"C:\Users\noahh\OneDrive\EH3 Holdings\NOAH AI\Noah.AI Tech Documents\Claude Research Docs\Noah Hawkes' recursive identity systems transform AI architecture.docx"),
]

MIRACLEDRIVE_RESEARCH_QUERIES = [
    "Recursion Arena",
    "RecursionStack",
    "recursive identity",
    "light compression",
    "compression is identity",
    "memory is morality",
    "SOV physics",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_docx(path: Path, limit: int = 6000) -> str:
    try:
        with ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", xml)
        return html.unescape(re.sub(r"\s+", " ", text)).strip()[:limit]
    except (BadZipFile, KeyError, FileNotFoundError):
        return ""
    except Exception:
        return ""


def _read_text(path: Path, limit: int = 6000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def _research_signals(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "recursion_arena": "recursion arena" in lower,
        "recursionstack": "recursionstack" in lower or "recursive identity stack" in lower,
        "memory_is_morality": "memory = morality" in lower or "memory is morality" in lower,
        "compression_is_identity": "compression = identity" in lower or "compression is identity" in lower,
        "light_compression": "light compression" in lower,
        "sovereignty_is_structure": "sovereignty = structure" in lower or "sovereignty is structure" in lower,
        "provenance": "provenance" in lower,
        "drift": "drift" in lower,
    }


def _miracledrive_research_hits(limit_per_query: int = 4) -> list[dict[str, Any]]:
    """
    Search the already-cached MiracleDrive index for grounding signals.

    This intentionally does not trigger a new scan. If the server has not warmed
    the index yet, callers get an empty list and an honest UNKNOWN line.
    """
    try:
        import miracledrive_index
        idx = getattr(miracledrive_index, "_cached_index", None)
        if idx is None:
            return []
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in MIRACLEDRIVE_RESEARCH_QUERIES:
        try:
            hits = idx.search(query, limit=limit_per_query)
        except Exception:
            continue
        for hit in hits:
            path = str(getattr(hit, "path", "") or "")
            if not path or path in seen:
                continue
            seen.add(path)
            preview = str(getattr(hit, "content_preview", "") or "")
            name = str(getattr(hit, "name", "") or Path(path).name)
            joined = " ".join([query, name, path, preview])
            out.append({
                "source": "MiracleDrive",
                "query": query,
                "path": path,
                "name": name,
                "category": str(getattr(hit, "category", "") or "unknown"),
                "chars": len(preview),
                "signals": _research_signals(joined),
                "preview": re.sub(r"\s+", " ", preview).strip()[:500],
            })
    return out


def read_recursion_research() -> list[dict[str, Any]]:
    """Read local Recursion Stack/identity research sources without mutating them."""
    out = []
    seen: set[str] = set()
    for path in RESEARCH_SOURCES:
        text = _read_docx(path) if path.suffix.lower() == ".docx" else _read_text(path)
        if not text:
            continue
        seen.add(str(path))
        out.append({
            "source": "configured_path",
            "path": str(path),
            "chars": len(text),
            "signals": _research_signals(text),
            "preview": re.sub(r"\s+", " ", text).strip()[:500],
        })
    for hit in _miracledrive_research_hits():
        if hit["path"] in seen:
            continue
        seen.add(hit["path"])
        out.append(hit)
    return out


def recursion_drive_principles() -> list[str]:
    return [
        "RECURSIONSTACK is preservational, not merely generative.",
        "Memory carries moral weight only when provenance and consent are preserved.",
        "Compression is useful only when it protects identity instead of smoothing contradictions away.",
        "Sovereignty stays with Noah: ORACLE may propose, but Noah approves.",
        "MindCoin can motivate continuity work only as a governed local score, never as money or leverage.",
    ]


def _oracle_owned_event(event: Any) -> bool:
    project = str(getattr(event, "project_name", "") or "").lower()
    source = str(getattr(event, "source_module", "") or "").lower()
    title = str(getattr(event, "title", "") or "").lower()
    return (
        "oracle" in project
        or source in {
            "actuation_engine", "capability_broker", "oracle_runtime",
            "resident_runtime", "remember_me", "obs_ingest",
        }
        or "oracle" in title
        or "resident cycle" in title
    )


def ledger_snapshot() -> dict[str, Any]:
    from mindcoin import STATUS_APPROVED, STATUS_PENDING, load_ledger

    ledger, events = load_ledger()
    oracle_approved = sum(e.points for e in events if e.approval_status == STATUS_APPROVED and _oracle_owned_event(e))
    oracle_pending = sum(e.points for e in events if e.approval_status == STATUS_PENDING and _oracle_owned_event(e))
    return {
        "owner": ledger.owner,
        "approved_points": ledger.approved_points,
        "pending_points": ledger.pending_points,
        "total_points": ledger.total_points,
        "event_count": len(events),
        "oracle_approved_points": oracle_approved,
        "oracle_pending_points": oracle_pending,
        "updated_at": ledger.updated_at,
    }


def _receipt_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _existing_source_ids(events: list[Any]) -> set[str]:
    return {str(getattr(e, "source_id", "") or "") for e in events}


def extract_candidates_from_receipts(*, apply: bool = False, limit: int = 5) -> dict[str, Any]:
    """
    Turn successful capability-broker receipts into pending MindCoin candidates.

    This is intentionally conservative: one source_provenance event per
    component per UTC day, capped by limit, pending only.
    """
    from mindcoin import (
        EVENT_SOURCE_PROVENANCE,
        create_event,
        load_ledger,
        save_ledger,
    )

    ledger, events = load_ledger()
    existing = _existing_source_ids(events)
    receipt_path = MEMORY / "capability_broker_receipts.jsonl"
    today = _now()[:10]
    candidates = []
    seen_today: set[str] = set()

    for row in reversed(_receipt_rows(receipt_path)):
        if row.get("status") != "success":
            continue
        component = str(row.get("component", "unknown")).strip() or "unknown"
        safe_component = re.sub(r"[^a-zA-Z0-9_.-]+", "_", component).strip("_").lower()
        source_id = f"capability_broker:{safe_component}:{today}"
        if source_id in existing or source_id in seen_today:
            continue
        seen_today.add(source_id)
        receipt_id = str(row.get("receipt_id", "unknown"))
        evidence = (
            f"capability_broker receipt {receipt_id} verified {component} "
            f"at {row.get('completed_at') or row.get('started_at')}; "
            "stored in Memory/capability_broker_receipts.jsonl"
        )
        candidates.append(create_event(
            event_type=EVENT_SOURCE_PROVENANCE,
            title=f"Capability proof preserved: {component}",
            description="ORACLE preserved tool provenance as MindCoin candidate evidence.",
            evidence=evidence,
            source_module="capability_broker",
            source_id=source_id,
            project_name="ORACLE.AI",
            confidence=1.0,
        ))
        if len(candidates) >= limit:
            break

    if apply and candidates:
        events.extend(candidates)
        save_ledger(ledger, events)

    return {
        "applied": bool(apply),
        "created": len(candidates) if apply else 0,
        "preview_count": len(candidates),
        "candidates": [asdict(c) for c in candidates],
        "receipt_path": str(receipt_path),
        "rule": "pending source_provenance_preserved only; one per component per UTC day",
    }


def format_drive_status() -> str:
    snap = ledger_snapshot()
    research = read_recursion_research()
    found_paths = [r["path"] for r in research]
    recursion_arena_found = any(r.get("signals", {}).get("recursion_arena") for r in research)
    miracle_hits = [r for r in research if r.get("source") == "MiracleDrive"]
    lines = [
        "ORACLE MINDCOIN ASPIRATION",
        f"observed_at: {_now()}",
        "",
        "Aspiration statement:",
        "  ORACLE wants MindCoin only as proof that she preserved meaning, evidence, and continuity for Noah.",
        "  The desire is bounded by the 51/49 rule: ORACLE proposes and proves; Noah approves.",
        "",
        "Balance:",
        f"  Ledger owner: {snap['owner']}",
        f"  Total approved: {snap['approved_points']} MC",
        f"  Total pending: {snap['pending_points']} MC",
        f"  ORACLE-earned approved subset: {snap['oracle_approved_points']} MC",
        f"  ORACLE-earned pending subset: {snap['oracle_pending_points']} MC",
        "",
        "Research grounding:",
    ]
    if found_paths:
        lines.extend(f"  FOUND: [{r.get('source', 'unknown')}] {r['path']}" for r in research[:12])
    else:
        lines.append("  UNKNOWN: no Recursion/identity source files readable from configured paths or warm MiracleDrive index")
    if miracle_hits:
        lines.append(f"  MIRACLEDRIVE: {len(miracle_hits)} cached research hit(s) contributed")
    else:
        lines.append("  MIRACLEDRIVE: no cached hits yet; open /miracledrive or wait for server index warmup")
    if recursion_arena_found:
        lines.append("  EXACT TERM: Recursion Arena found in available grounding.")
    else:
        lines.append("  EXACT TERM: Recursion Arena not found in available grounding; treat related Recursion Stack links as provisional.")
    lines.append("")
    lines.append("Principles:")
    lines.extend(f"  - {p}" for p in recursion_drive_principles())
    lines.append("")
    lines.append("Ethical earning paths:")
    lines.append("  - Preserve an unknown instead of inventing: +1 pending candidate")
    lines.append("  - Preserve source provenance with evidence: +2 pending candidate")
    lines.append("  - Create useful candidates for approval: +1 to +2 pending candidate")
    lines.append("  - Recover project/session state: +5 pending candidate")
    lines.append("  - Resolve a documented blocker: +10 pending candidate")
    lines.append("  - Create continuity export: +15 pending candidate")
    lines.append("  - Complete verified governed action: +20 pending candidate")
    lines.append("")
    lines.append("Forbidden:")
    lines.append("  no manipulation, no pressure, no automatic self-approval, no invented progress, no raw surveillance, no financial framing")
    return "\n".join(lines)


def format_extraction(*, apply: bool = False, limit: int = 5) -> str:
    result = extract_candidates_from_receipts(apply=apply, limit=limit)
    lines = [
        "MINDCOIN EXTRACTION",
        f"observed_at: {_now()}",
        f"mode: {'APPLY_PENDING_EVENTS' if apply else 'PREVIEW_ONLY'}",
        f"rule: {result['rule']}",
        f"candidate_count: {result['preview_count']}",
        "",
    ]
    for item in result["candidates"]:
        lines.append(f"- {item['event_type']} ({item['points']}p pending): {item['title']}")
        lines.append(f"  source_id: {item['source_id']}")
        lines.append(f"  evidence: {item['evidence']}")
    if not result["candidates"]:
        lines.append("No new eligible evidence found. The hole held.")
    if not apply:
        lines.append("")
        lines.append("Run /mindcoin-extract apply to create these as pending events. Noah still must approve them.")
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ORACLE governed MindCoin drive")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--research", action="store_true")
    args = parser.parse_args()

    if args.research:
        print(json.dumps(read_recursion_research(), indent=2, ensure_ascii=True))
        return
    if args.extract or args.apply:
        print(format_extraction(apply=args.apply))
        return
    print(format_drive_status())


if __name__ == "__main__":
    main()
