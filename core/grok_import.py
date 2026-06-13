"""
grok_import.py — import a Grok (X) data export into ORACLE's memory.

Doctrine boundaries enforced here:
  * The authoritative, immutable archive is written to a LOCAL, non-synced path
    (ORACLE_IMPORT_ROOT, default C:\\Oracle\\imports\\grok) — never the Google
    Drive repo. Source conversations are preserved verbatim.
  * Personal account data (auth/sessions/IPs/geo/billing) is NEVER read or copied.
    Only conversation text is imported.
  * Provenance is preserved per message: Noah's own messages are 'human_stated'
    (approved); Grok's replies are 'generated' (external model, unverified). The
    distinction survives into durable memory so ORACLE never confuses Noah's
    intent with an external model's claims.

Two phases:
  parse   -> read the export, write the local archive (index.json,
             per-conversation markdown, atoms.jsonl). No DB writes.
  ingest  -> load atoms.jsonl into ORACLE's governed durable_facts memory.

Usage:
  python core/grok_import.py parse  --export "<path to prod-grok-backend.json>"
  python core/grok_import.py ingest [--force] [--limit N]
  python core/grok_import.py verify --query "continuity"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))


def import_root() -> Path:
    configured = os.environ.get("ORACLE_IMPORT_ROOT")
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(r"C:\Oracle\imports\grok")
    return Path.home() / ".oracle" / "imports" / "grok"


def _slugify(text: str, limit: int = 50) -> str:
    text = re.sub(r"[^\w\s-]", "", (text or "untitled").lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return (text or "untitled")[:limit]


def _sender_name(sender: str) -> str:
    return "Noah" if (sender or "").lower() == "human" else "Grok"


def _ts(value: Any) -> str:
    """Timestamps are normally ISO strings, but coerce anything else safely."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("$date", "value", "iso", "timestamp"):
            v = value.get(k)
            if isinstance(v, str):
                return v
    return ""


def _message_text(message: Any) -> str:
    """Grok 'message' is normally a string; coerce structured payloads safely."""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        for k in ("text", "content", "message", "value"):
            v = message.get(k)
            if isinstance(v, str) and v.strip():
                return v
        return json.dumps(message, ensure_ascii=False)
    if isinstance(message, list):
        parts = [_message_text(m) for m in message]
        return "\n".join(p for p in parts if p)
    return "" if message is None else str(message)


def _iter_messages(export_path: Path) -> Iterator[dict]:
    """Yield normalized message dicts from the export, with conversation context."""
    with open(export_path, encoding="utf-8") as f:
        data = json.load(f)
    for entry in data.get("conversations", []):
        conv = entry.get("conversation", {}) or {}
        conv_id = conv.get("id", "")
        title = (conv.get("title") or "").strip() or "(untitled)"
        for resp in entry.get("responses", []):
            r = resp.get("response", {}) or {}
            text = _message_text(r.get("message")).strip()
            if not text:
                continue
            sender = (r.get("sender") or "").lower()
            yield {
                "conversation_id": conv_id,
                "conversation_title": title,
                "conversation_created": _ts(conv.get("create_time")),
                "message_id": r.get("_id", ""),
                "sender": sender,
                "role": _sender_name(sender),
                "model": r.get("model", "") if isinstance(r.get("model"), str) else "",
                "observed_at": _ts(r.get("create_time")) or _ts(conv.get("create_time")),
                "text": text,
            }


def cmd_parse(export_path: Path) -> int:
    out = import_root()
    conv_dir = out / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)

    # Group messages by conversation, preserving order.
    convos: dict[str, dict] = {}
    total_msgs = 0
    senders: dict[str, int] = {}
    for m in _iter_messages(export_path):
        cid = m["conversation_id"]
        c = convos.setdefault(cid, {
            "id": cid,
            "title": m["conversation_title"],
            "created": m["conversation_created"],
            "messages": [],
        })
        c["messages"].append(m)
        total_msgs += 1
        senders[m["role"]] = senders.get(m["role"], 0) + 1

    atoms_path = out / "atoms.jsonl"
    index: list[dict] = []
    with open(atoms_path, "w", encoding="utf-8") as af:
        for cid, c in convos.items():
            msgs = c["messages"]
            date = (c["created"] or "")[:10] or "undated"
            slug = _slugify(c["title"])
            md_name = f"{date}_{slug}_{cid[:8]}.md"
            # Per-conversation markdown archive (verbatim, human-readable).
            lines = [
                f"# {c['title']}",
                "",
                f"- Source: Grok export",
                f"- Conversation ID: {cid}",
                f"- Created: {c['created']}",
                f"- Messages: {len(msgs)}",
                "",
                "---",
                "",
            ]
            models = set()
            for m in msgs:
                if m["model"]:
                    models.add(m["model"])
                stamp = (m["observed_at"] or "")[:19].replace("T", " ")
                who = m["role"] if m["role"] == "Noah" else f"Grok ({m['model']})" if m["model"] else "Grok"
                lines.append(f"## {who} — {stamp}")
                lines.append("")
                lines.append(m["text"])
                lines.append("")
                # Memory atom per message, with provenance distinction.
                is_human = m["sender"] == "human"
                af.write(json.dumps({
                    "source_id": f"grok:{cid}:{m['message_id']}",
                    "conversation_id": cid,
                    "conversation_title": c["title"],
                    "role": m["role"],
                    "model": m["model"],
                    "observed_at": m["observed_at"],
                    "text": m["text"],
                    "source_type": "human_stated" if is_human else "generated",
                    "approval_status": "approved" if is_human else "unverified",
                    "confidence": 0.9 if is_human else 0.4,
                }, ensure_ascii=False) + "\n")
            (conv_dir / md_name).write_text("\n".join(lines), encoding="utf-8")
            index.append({
                "id": cid,
                "title": c["title"],
                "created": c["created"],
                "messages": len(msgs),
                "models": sorted(models),
                "file": f"conversations/{md_name}",
            })

    index.sort(key=lambda x: x["created"] or "", reverse=True)
    (out / "index.json").write_text(
        json.dumps({
            "source": "Grok (X) data export",
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "export_file": str(export_path),
            "conversations": len(convos),
            "messages": total_msgs,
            "by_role": senders,
            "items": index,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[parse] archive root : {out}")
    print(f"[parse] conversations: {len(convos)}")
    print(f"[parse] messages     : {total_msgs}  {senders}")
    print(f"[parse] wrote        : index.json, atoms.jsonl, {len(convos)} markdown files")
    print(f"[parse] PII/assets   : excluded (auth/billing/images never read)")
    return 0


def cmd_ingest(force: bool, limit: int | None) -> int:
    import memory

    memory.init_db()
    atoms_path = import_root() / "atoms.jsonl"
    if not atoms_path.exists():
        print(f"[ingest] no atoms.jsonl at {atoms_path}. Run 'parse' first.")
        return 1

    existing = memory.search_durable_facts("[Grok import", limit=1)
    if existing and not force:
        print("[ingest] Grok facts already present. Use --force to ingest again.")
        return 1

    inserted = 0
    skipped = 0
    transform = ["exported_from_grok", "parsed_by_grok_import_v1"]
    with open(atoms_path, encoding="utf-8") as f:
        for line in f:
            if limit is not None and inserted >= limit:
                break
            try:
                a = json.loads(line)
            except Exception:
                skipped += 1
                continue
            text = (a.get("text") or "").strip()
            if not text:
                skipped += 1
                continue
            fact_text = f"[Grok import · {a['conversation_title']}] {a['role']}: {text}"
            provenance = {
                "source_type": a["source_type"],
                "source_id": a["source_id"],
                "observed_at": a.get("observed_at") or "",
                "confidence": a.get("confidence", 0.4),
                "transformation_history": transform,
                "canonical_status": "imported_grok",
                "approval_status": a.get("approval_status", "unverified"),
            }
            try:
                memory.insert_durable_fact(fact_text, provenance)
                inserted += 1
            except Exception as exc:
                print(f"[ingest] skip ({type(exc).__name__}): {exc}")
                skipped += 1

    print(f"[ingest] inserted durable facts: {inserted}  (skipped {skipped})")
    print(f"[ingest] memory db: {memory.DB_PATH}")
    return 0


def cmd_verify(query: str) -> int:
    import memory
    hits = memory.search_durable_facts(query, limit=8)
    grok = [h for h in hits if (h.get("canonical_status") == "imported_grok")]
    print(f"[verify] query {query!r}: {len(hits)} hits ({len(grok)} from Grok import)")
    for h in hits[:6]:
        st = h.get("source_type")
        print(f"  - [{st}] {h.get('fact_text','')[:120]}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Import a Grok export into ORACLE memory")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("parse", help="parse export into the local archive")
    pp.add_argument("--export", required=True, help="path to prod-grok-backend.json")
    pi = sub.add_parser("ingest", help="ingest atoms.jsonl into durable memory")
    pi.add_argument("--force", action="store_true")
    pi.add_argument("--limit", type=int, default=None)
    pv = sub.add_parser("verify", help="search durable facts")
    pv.add_argument("--query", required=True)
    args = p.parse_args()

    if args.cmd == "parse":
        return cmd_parse(Path(args.export))
    if args.cmd == "ingest":
        return cmd_ingest(args.force, args.limit)
    if args.cmd == "verify":
        return cmd_verify(args.query)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
