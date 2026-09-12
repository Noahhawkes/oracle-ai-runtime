"""
core/companion_bootstrap.py — Deterministic Companion Grounding Bootstrap.

Runs BEFORE any LLM call in companion mode. Reads identity, latest reflection,
and live context from local files using real pathlib/hashlib calls. Produces a
sealed context block injected into the system prompt.

The LLM never executes this — Python does. If a source fails, the failure is
reported honestly. ORACLE never says "loading..." unless this code actually ran.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent.parent
MEMORY = ROOT / "Memory"
RELATIONSHIP_DIR = MEMORY / "relationship_memory"
REMEMBER_ME_DIR = MEMORY / "remember_me"
BUILD_WITNESS_DIR = MEMORY / "build_witness"
THESIS_CORPUS_DIR = MEMORY / "thesis_corpus"
REFLECTIONS_DIR = MEMORY / "Reflections"
LIVE_CONTEXT_PATH = MEMORY / "live_context.json"
MEMORY_DB_PATH = MEMORY / "oracle_memory.db"
PROCESS_RECEIPTS_DIR = MEMORY / "process_receipts"
PROCESS_RECEIPT_LOG = PROCESS_RECEIPTS_DIR / "generation_process_receipts.jsonl"
PROCESS_RECEIPT_LATEST = PROCESS_RECEIPTS_DIR / "latest_generation_process_receipt.json"
STATE_SNAPSHOT_HEADER = "@STATE_SNAPSHOT_CURRENT"
STATE_SNAPSHOT_END = "[END_STATE_SNAPSHOT_CURRENT]"
SQLITE_PREINFERENCE_TIMEOUT_SECONDS = 0.02
PREINFERENCE_BUDGET_SECONDS = 0.05

# The approved sovereign identity ID (Noah Alexander Hawkes Sr.)
SOVEREIGN_ID = "060ca00a-c703-4f49-874e-2a2b2291b350"

_IDENTITY_FACT_KEYWORDS = (
    "full name",
    "entities",
    "children",
    "family",
    "co-sovereign",
    "sons",
    "continuity",
)

_SHA256_LINE_RE = re.compile(
    r"(?im)^\s*(?:raw_sha256|receipt_hash_sha256|source_sha256|sha256|"
    r"post_operation_sha256|child_response_sha256)\s*[:=]\s*([0-9a-f]{64})\b"
)


def _identity_source_lines(data: dict) -> list[str]:
    lines: list[str] = []
    for key in ("name", "sov_id", "organization", "role", "trust_tier", "source", "confidence", "status"):
        if data.get(key) is not None:
            lines.append(f"{key}: {data.get(key)}")

    aliases = data.get("aliases") or []
    if aliases:
        lines.append(f"aliases: {', '.join(str(a) for a in aliases)}")

    important_facts = [str(fact) for fact in data.get("important_facts", []) if fact]
    selected: list[str] = []
    for fact in important_facts:
        lower = fact.lower()
        if any(keyword in lower for keyword in _IDENTITY_FACT_KEYWORDS):
            selected.append(fact)
    for fact in important_facts:
        if len(selected) >= 14:
            break
        if fact not in selected:
            selected.append(fact)
    for fact in selected:
        lines.append(f"important_fact: {fact}")

    for boundary in data.get("known_boundaries", []) or []:
        lines.append(f"known_boundary: {boundary}")

    return lines


def _live_context_source_lines(data: dict) -> list[str]:
    keys = ("sovereign", "active_project", "active_tool", "active_repo", "current_task", "memory_policy", "last_updated")
    return [f"{key}: {data.get(key)}" for key in keys if data.get(key) is not None]


def _reflection_source_lines(data: dict) -> list[str]:
    lines: list[str] = []
    for key in ("schema_version", "reflection_id", "session_id", "approval_status", "generated_by"):
        if data.get(key) is not None:
            lines.append(f"{key}: {data.get(key)}")
    salience = data.get("salience") or {}
    if salience.get("primary_signal"):
        lines.append(f"primary_signal: {salience.get('primary_signal')}")
    for item in salience.get("sovereign_decisions", []) or []:
        lines.append(f"sovereign_decision: {item}")
    for item in salience.get("trajectory_arc", []) or []:
        lines.append(f"trajectory_arc: {item}")
    continuity = data.get("continuity_state") or {}
    if continuity.get("stance"):
        lines.append(f"stance: {continuity.get('stance')}")
    for item in continuity.get("high_mass_anchors", []) or []:
        lines.append(f"high_mass_anchor: {item}")
    for item in continuity.get("unresolved_loops", []) or []:
        lines.append(f"unresolved_loop: {item}")
    routing = data.get("exocortex_routing") or {}
    for item in routing.get("continuity_hooks", []) or []:
        lines.append(f"continuity_hook: {item}")
    for item in routing.get("ledger_updates", []) or []:
        lines.append(f"ledger_update: {item}")
    return lines


def _remember_me_source_lines(limit: int = 8) -> list[str]:
    """Summarize approved Remember Me records without injecting raw archives."""
    index_path = REMEMBER_ME_DIR / "index.json"
    if not index_path.exists():
        return []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"load_error: {type(exc).__name__}: {exc}"]

    approved_ids = [str(rid) for rid, status in index.items() if status == "approved"]
    records: list[dict] = []
    for rid in approved_ids:
        path = REMEMBER_ME_DIR / f"{rid}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            records.append(data)

    records.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    lines = [
        f"source_dir: {REMEMBER_ME_DIR.resolve()}",
        f"approved_record_count: {len(records)}",
        "status: approved Remember Me records only; no pending/quarantined/rejected records injected",
    ]
    for rec in records[: max(1, int(limit))]:
        title = str(rec.get("title") or "untitled")
        category = str(rec.get("category") or "unknown")
        confidence = str(rec.get("confidence") or "UNKNOWN")
        meaning = " ".join(str(rec.get("compressed_meaning") or "").split())[:700]
        lines.append(f"remember_me_title: {title}")
        lines.append(f"{title} category: {category}")
        lines.append(f"{title} confidence: {confidence}")
        if meaning:
            lines.append(f"{title} compressed_meaning: {meaning}")
        for unknown in rec.get("unknowns", []) or []:
            lines.append(f"{title} preserved_unknown: {str(unknown)[:220]}")
        for contradiction in rec.get("contradictions", []) or []:
            lines.append(f"{title} contradiction: {str(contradiction)[:220]}")
        tags = rec.get("tags") or []
        if tags:
            lines.append(f"{title} tags: {', '.join(str(tag) for tag in tags[:12])}")
        if rec.get("source"):
            lines.append(f"{title} source: {str(rec.get('source'))[:300]}")
        if rec.get("updated_at"):
            lines.append(f"{title} updated_at: {rec.get('updated_at')}")
    return lines


def _thread_recall_source_lines(limit: int = 6) -> list[str]:
    """Summarize local imported-thread recall records without injecting raw threads."""
    if not MEMORY_DB_PATH.exists():
        return []
    try:
        con = sqlite3.connect(str(MEMORY_DB_PATH))
        con.row_factory = sqlite3.Row
        total = con.execute(
            "SELECT COUNT(*) AS n FROM facts WHERE category IN ('thread_recall', 'thread_capture')"
        ).fetchone()["n"]
        rows = con.execute(
            """
            SELECT category, key, value, updated_at
            FROM facts
            WHERE category IN ('thread_recall', 'thread_capture')
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        con.close()
    except Exception as exc:
        return [f"load_error: {type(exc).__name__}: {exc}"]

    if not rows:
        return []

    lines = [
        f"database_path: {MEMORY_DB_PATH.resolve()}",
        f"record_count: {total}",
        "status: imported/captured thread evidence candidates; not canon unless Noah.Physical explicitly promotes",
    ]
    keep_prefixes = (
        "title:",
        "source_system:",
        "source_ref:",
        "stored_txt_path:",
        "manifest_path:",
        "sha256:",
        "status:",
        "canon_status:",
        "promotion_status:",
        "capture_mode:",
        "capture_method:",
        "captured_at:",
        "parsed_transcript_path:",
        "custody_receipt_path:",
        "latest_source_system:",
        "latest_source_ref:",
    )
    for row in rows:
        lines.append(f"record_category: {row['category']}")
        lines.append(f"record_key: {row['key']}")
        value_lines = str(row["value"] or "").splitlines()
        excerpt = ""
        for item in value_lines:
            stripped = item.strip()
            if stripped.startswith("excerpt:"):
                excerpt = stripped[len("excerpt:"):].strip()
                continue
            if stripped.startswith(keep_prefixes):
                lines.append(f"{row['key']} {stripped}")
        if excerpt:
            lines.append(f"{row['key']} excerpt: {excerpt[:500]}")
        if row["updated_at"]:
            lines.append(f"{row['key']} updated_at: {row['updated_at']}")
    return lines


def _build_witness_source_lines(limit: int = 4) -> list[str]:
    """Summarize local Build Witness receipts without injecting diffs/content."""
    log_path = BUILD_WITNESS_DIR / "build_receipts.jsonl"
    latest_path = BUILD_WITNESS_DIR / "latest_build_receipt.json"
    lines = [
        f"source_dir: {BUILD_WITNESS_DIR.resolve()}",
        "status: candidate build receipts only; not canon unless Noah.Physical approves",
        "boundary: receipts summarize construction events; no file contents or diffs injected",
    ]
    if not log_path.exists():
        return lines + ["receipt_count: 0"]

    raw_lines: list[str] = []
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    raw_lines.append(raw.strip())
    except Exception as exc:
        return lines + [f"load_error: {type(exc).__name__}: {exc}"]

    receipts: list[dict] = []
    for raw in raw_lines[-max(1, int(limit)):]:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            receipts.append(data)

    lines.append(f"receipt_count_observed: {len(raw_lines)}")
    lines.append(f"latest_receipt_path: {latest_path.resolve()}")
    for receipt in reversed(receipts):
        reason = " ".join(str(receipt.get("reason") or "").split())[:350]
        files = receipt.get("files_changed") or []
        tests = receipt.get("tests_run") or []
        lines.append(f"build_event: {receipt.get('receipt_id') or 'unknown'}")
        lines.append(f"{receipt.get('receipt_id') or 'build_event'} observed_at: {receipt.get('observed_at')}")
        lines.append(f"{receipt.get('receipt_id') or 'build_event'} task_id: {receipt.get('task_id')}")
        lines.append(f"{receipt.get('receipt_id') or 'build_event'} approval_status: {receipt.get('approval_status')}")
        lines.append(f"{receipt.get('receipt_id') or 'build_event'} test_result: {receipt.get('test_result')}")
        lines.append(f"{receipt.get('receipt_id') or 'build_event'} files_changed_count: {len(files)}")
        if reason:
            lines.append(f"{receipt.get('receipt_id') or 'build_event'} reason: {reason}")
        if tests:
            lines.append(f"{receipt.get('receipt_id') or 'build_event'} tests_run: {', '.join(str(t) for t in tests[:6])}")
        if receipt.get("receipt_hash_sha256"):
            lines.append(f"{receipt.get('receipt_id') or 'build_event'} receipt_hash_sha256: {receipt.get('receipt_hash_sha256')}")
    return lines


def _thesis_corpus_source_lines(limit: int = 4) -> list[str]:
    """Summarize curated .AI thesis capsules for pre-prompt grounding."""
    if not THESIS_CORPUS_DIR.exists():
        return []
    try:
        capsules = sorted(
            THESIS_CORPUS_DIR.glob("*.ai"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except Exception as exc:
        return [f"load_error: {type(exc).__name__}: {exc}"]

    lines = [
        f"source_dir: {THESIS_CORPUS_DIR.resolve()}",
        f"capsule_count: {len(capsules)}",
        "status: curated thesis capsules; candidate anchors unless Noah.Physical promotes",
        "boundary: source-grounded thesis map only; no full-drive prompt stuffing and no canon promotion",
    ]
    keep_prefixes = (
        ".AI:",
        "title=",
        "created_at=",
        "source_path=",
        "source_sha256=",
        "source_family=",
        "canon_status=",
        "promotion_status=",
        "thesis_vector=",
        "compressed_meaning=",
        "source_excerpt=",
        "relationship_to_oracle=",
        "file_type_instruction=",
        "- ",
    )
    for path in capsules[: max(1, int(limit))]:
        lines.append(f"capsule_path: {path.resolve()}")
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            lines.append(f"{path.stem} load_error: {type(exc).__name__}: {exc}")
            continue
        kept = 0
        for raw in raw_lines:
            item = raw.strip()
            if not item:
                continue
            if item.startswith(keep_prefixes):
                lines.append(f"{path.stem}: {item[:650]}")
                kept += 1
            if kept >= 24:
                break
    return lines


# ── Data model ────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_ready(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=True)
        return value
    except TypeError:
        return str(value)


def _extract_sha256(text: str) -> str | None:
    match = _SHA256_LINE_RE.search(text or "")
    return match.group(1).lower() if match else None


def _extract_named_field(text: str, *names: str) -> str | None:
    wanted = {name.lower().rstrip(":") for name in names}
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip().lower().rstrip(":") in wanted:
            return value.strip()
    return None


def _short_text(value: Any, limit: int = 220) -> str:
    return " ".join(str(value or "").split())[: max(1, int(limit))]


def _memory_connection(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=SQLITE_PREINFERENCE_TIMEOUT_SECONDS)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    con.execute(f"PRAGMA busy_timeout = {int(SQLITE_PREINFERENCE_TIMEOUT_SECONDS * 1000)}")
    return con


def _latest_active_session(con: sqlite3.Connection) -> dict[str, Any]:
    row = con.execute(
        """
        SELECT
            s.id AS session_id,
            s.started_at AS started_at,
            s.summary AS summary,
            MAX(m.timestamp) AS last_message_at,
            COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        GROUP BY s.id
        ORDER BY COALESCE(MAX(m.timestamp), s.started_at) DESC, s.id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {
            "session_id": "UNAVAILABLE",
            "started_at": "UNAVAILABLE",
            "last_message_at": "UNAVAILABLE",
            "message_count": 0,
            "summary": "",
        }
    return {
        "session_id": row["session_id"],
        "started_at": row["started_at"],
        "last_message_at": row["last_message_at"] or row["started_at"],
        "message_count": int(row["message_count"] or 0),
        "summary": _short_text(row["summary"], 180),
    }


def _receipt_from_audit_row(row: sqlite3.Row) -> dict[str, Any] | None:
    detail = str(row["detail"] or "")
    parsed: dict[str, Any] = {}
    try:
        data = json.loads(detail)
        if isinstance(data, dict):
            parsed = data
    except Exception:
        parsed = {}

    sha = (
        str(parsed.get("sha256") or parsed.get("raw_sha256") or parsed.get("receipt_hash_sha256") or "").lower()
        or _extract_sha256(detail)
    )
    if not sha or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return None

    action_id = (
        parsed.get("action_id")
        or parsed.get("receipt_id")
        or _extract_named_field(detail, "action_id", "receipt_id")
        or row["event"]
        or f"audit_chain:{row['id']}"
    )
    return {
        "action_id": str(action_id),
        "timestamp": str(row["recorded_at"] or ""),
        "sha256": sha,
        "source_table": "audit_chain",
        "verification_status": "sha256_present",
    }


def _receipt_from_fact_row(row: sqlite3.Row) -> dict[str, Any] | None:
    value = str(row["value"] or "")
    sha = _extract_sha256(value)
    if not sha:
        return None
    action_id = (
        _extract_named_field(value, "action_id", "receipt_id", "capture_id")
        or f"{row['category']}:{row['key']}"
    )
    canon_status = _extract_named_field(value, "canon_status") or "UNKNOWN"
    promotion_status = _extract_named_field(value, "promotion_status") or "UNKNOWN"
    return {
        "action_id": str(action_id),
        "timestamp": str(row["updated_at"] or ""),
        "sha256": sha,
        "source_table": "facts",
        "verification_status": "sha256_present",
        "canon_status": canon_status,
        "promotion_status": promotion_status,
    }


def _last_verified_receipts(con: sqlite3.Connection, limit: int = 3) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    try:
        rows = con.execute(
            """
            SELECT id, session_id, event, detail, recorded_at
            FROM audit_chain
            WHERE detail LIKE '%sha256%'
               OR detail LIKE '%receipt%'
               OR event LIKE '%receipt%'
            ORDER BY recorded_at DESC, id DESC
            LIMIT 24
            """
        ).fetchall()
    except sqlite3.Error:
        rows = []
    for row in rows:
        receipt = _receipt_from_audit_row(row)
        if not receipt:
            continue
        key = (receipt["action_id"], receipt["sha256"])
        if key not in seen:
            receipts.append(receipt)
            seen.add(key)
        if len(receipts) >= limit:
            return receipts

    try:
        rows = con.execute(
            """
            SELECT id, category, key, value, updated_at
            FROM facts
            WHERE value LIKE '%sha256%'
               OR value LIKE '%receipt%'
            ORDER BY updated_at DESC, id DESC
            LIMIT 40
            """
        ).fetchall()
    except sqlite3.Error:
        rows = []
    for row in rows:
        receipt = _receipt_from_fact_row(row)
        if not receipt:
            continue
        key = (receipt["action_id"], receipt["sha256"])
        if key not in seen:
            receipts.append(receipt)
            seen.add(key)
        if len(receipts) >= limit:
            break
    return receipts


def _dirty_state_snapshot(root: Path) -> dict[str, Any]:
    try:
        from git_state_reader import read_git_snapshot

        git_state = read_git_snapshot(root)
        changed = git_state.get("changed_files") or []
        return {
            "source": git_state.get("source") or "git_files_no_subprocess",
            "branch": git_state.get("branch") or "UNKNOWN",
            "commit": git_state.get("commit") or "UNKNOWN",
            "head_sha": git_state.get("head_sha") or "UNKNOWN",
            "dirty": git_state.get("dirty") or "UNKNOWN",
            "changed_file_count": git_state.get("changed_file_count"),
            "uncommitted_files": [str(item) for item in changed[:25]],
            "subprocess_used": bool(git_state.get("subprocess_used")),
            "status": "UNKNOWN_NO_GIT_SUBPROCESS",
            "boundary": "Hot-path dirty file enumeration does not invoke git.exe.",
        }
    except Exception as exc:
        return {
            "source": "git_state_reader",
            "branch": "UNKNOWN",
            "commit": "UNKNOWN",
            "head_sha": "UNKNOWN",
            "dirty": "UNKNOWN",
            "changed_file_count": None,
            "uncommitted_files": [],
            "subprocess_used": False,
            "status": f"UNAVAILABLE:{type(exc).__name__}",
            "boundary": "Dirty state unavailable; no git subprocess was used.",
        }


def _current_session_summary(current_session: Optional[list[dict]]) -> dict[str, Any]:
    turns = list(current_session or [])
    last_user = ""
    for turn in reversed(turns):
        if str(turn.get("role", "")).lower() == "user":
            last_user = str(turn.get("content") or "")
            break
    return {
        "turn_count": len(turns),
        "last_user_sha256": hashlib.sha256(last_user.encode("utf-8", errors="replace")).hexdigest() if last_user else "UNAVAILABLE",
        "last_user_excerpt": _short_text(last_user, 180) if last_user else "UNAVAILABLE",
    }


def _compute_epistemic_tension(snapshot: dict[str, Any]) -> float:
    tension = 0.0
    if snapshot.get("status") != "CONNECTED":
        tension += 1.0
    if not snapshot.get("last_verified_receipts"):
        tension += 0.35
    dirty = snapshot.get("dirty_state") or {}
    if dirty.get("changed_file_count") is None:
        tension += 0.2
    if (snapshot.get("current_session") or {}).get("turn_count", 0) == 0:
        tension += 0.1
    if float(snapshot.get("elapsed_seconds") or 0.0) > PREINFERENCE_BUDGET_SECONDS:
        tension += 0.2
    if (snapshot.get("last_active_session") or {}).get("session_id") == "UNAVAILABLE":
        tension += 0.15
    return round(min(1.0, tension), 3)


def fetch_state_snapshot(
    current_session: Optional[list[dict]] = None,
    *,
    db_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Fetch the hard pre-inference state snapshot from local ledgers."""
    started = time.perf_counter()
    target_db = Path(db_path) if db_path is not None else MEMORY_DB_PATH
    target_root = Path(root) if root is not None else ROOT
    base: dict[str, Any] = {
        "ok": False,
        "status": "LEDGER_DISCONNECTED",
        "database_path": str(target_db.resolve(strict=False)),
        "fetched_at": _utc_now(),
        "context_sources": ["oracle_memory.db", "current_session"],
        "current_session": _current_session_summary(current_session),
    }
    if not target_db.exists():
        base["error"] = "oracle_memory.db missing"
        base["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        base["epistemic_tension"] = 1.0
        return base

    try:
        con = _memory_connection(target_db)
        try:
            last_session = _latest_active_session(con)
            receipts = _last_verified_receipts(con, limit=3)
        finally:
            con.close()
    except sqlite3.OperationalError as exc:
        base["error"] = f"sqlite_operational_error: {exc}"
        base["locked_or_unreachable"] = True
        base["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        base["epistemic_tension"] = 1.0
        return base
    except Exception as exc:
        base["error"] = f"{type(exc).__name__}: {exc}"
        base["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        base["epistemic_tension"] = 1.0
        return base

    snapshot = {
        **base,
        "ok": True,
        "status": "CONNECTED",
        "last_active_session": last_session,
        "last_verified_receipts": receipts,
        "dirty_state": _dirty_state_snapshot(target_root),
        "error": None,
    }
    snapshot["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    snapshot["within_budget"] = snapshot["elapsed_seconds"] <= PREINFERENCE_BUDGET_SECONDS
    snapshot["epistemic_tension"] = _compute_epistemic_tension(snapshot)
    return snapshot


def format_state_snapshot(snapshot: dict[str, Any]) -> str:
    lines = [STATE_SNAPSHOT_HEADER]
    lines.append(f"status: {snapshot.get('status') or 'LEDGER_DISCONNECTED'}")
    lines.append(f"fetched_at: {snapshot.get('fetched_at') or 'UNAVAILABLE'}")
    lines.append(f"database_path: {snapshot.get('database_path') or 'UNAVAILABLE'}")
    lines.append(f"elapsed_seconds: {snapshot.get('elapsed_seconds', 'UNAVAILABLE')}")
    lines.append(f"within_preinference_budget: {snapshot.get('within_budget', False)}")
    lines.append("context_sources: oracle_memory.db, current_session")

    if not snapshot.get("ok"):
        lines.append(f"error: {snapshot.get('error') or 'ledger unavailable'}")
        lines.append("fallback_policy: HARD_STOP_LEDGER_DISCONNECTED")
        lines.append("model_call_allowed: false")
        lines.append(f"epistemic_tension: {snapshot.get('epistemic_tension', 1.0)}")
        lines.append(STATE_SNAPSHOT_END)
        return "\n".join(lines)

    session = snapshot.get("last_active_session") or {}
    lines.append(f"last_active_session_id: {session.get('session_id', 'UNAVAILABLE')}")
    lines.append(f"last_active_session_started_at: {session.get('started_at', 'UNAVAILABLE')}")
    lines.append(f"last_active_session_last_message_at: {session.get('last_message_at', 'UNAVAILABLE')}")
    lines.append(f"last_active_session_message_count: {session.get('message_count', 0)}")
    if session.get("summary"):
        lines.append(f"last_active_session_summary: {session.get('summary')}")

    current = snapshot.get("current_session") or {}
    lines.append(f"current_session_turn_count: {current.get('turn_count', 0)}")
    lines.append(f"current_session_last_user_sha256: {current.get('last_user_sha256', 'UNAVAILABLE')}")

    receipts = snapshot.get("last_verified_receipts") or []
    lines.append(f"last_verified_receipt_count: {len(receipts)}")
    for index, receipt in enumerate(receipts[:3], start=1):
        prefix = f"receipt_{index}"
        lines.append(f"{prefix}_action_id: {receipt.get('action_id', 'UNAVAILABLE')}")
        lines.append(f"{prefix}_timestamp: {receipt.get('timestamp', 'UNAVAILABLE')}")
        lines.append(f"{prefix}_sha256: {receipt.get('sha256', 'UNAVAILABLE')}")
        lines.append(f"{prefix}_source_table: {receipt.get('source_table', 'UNAVAILABLE')}")
        lines.append(f"{prefix}_verification_status: {receipt.get('verification_status', 'UNAVAILABLE')}")
    if not receipts:
        lines.append("receipt_1_action_id: UNAVAILABLE")
        lines.append("receipt_1_sha256: UNAVAILABLE")

    dirty = snapshot.get("dirty_state") or {}
    files = dirty.get("uncommitted_files") or []
    lines.append(f"dirty_state_source: {dirty.get('source', 'UNAVAILABLE')}")
    lines.append(f"dirty_state_status: {dirty.get('status', 'UNAVAILABLE')}")
    lines.append(f"dirty_state_branch: {dirty.get('branch', 'UNKNOWN')}")
    lines.append(f"dirty_state_commit: {dirty.get('commit', 'UNKNOWN')}")
    lines.append(f"dirty_state_dirty: {dirty.get('dirty', 'UNKNOWN')}")
    lines.append(f"dirty_state_changed_file_count: {dirty.get('changed_file_count', 'UNKNOWN')}")
    lines.append(f"dirty_state_subprocess_used: {dirty.get('subprocess_used', False)}")
    lines.append(f"uncommitted_file_list_count: {len(files)}")
    for index, file_name in enumerate(files[:10], start=1):
        lines.append(f"uncommitted_file_{index}: {file_name}")
    if not files:
        lines.append("uncommitted_file_1: UNAVAILABLE")

    lines.append(f"epistemic_tension: {snapshot.get('epistemic_tension', 0.0)}")
    lines.append("model_call_allowed: true")
    lines.append("boundary: read-only SQLite ledger; read-only git file state; no G Drive mutation; no git subprocess")
    lines.append(STATE_SNAPSHOT_END)
    return "\n".join(lines)


def build_pre_inference_context(
    current_session: Optional[list[dict]] = None,
    *,
    db_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    snapshot = fetch_state_snapshot(current_session=current_session, db_path=db_path, root=root)
    return {
        "ok": bool(snapshot.get("ok")),
        "status": snapshot.get("status"),
        "snapshot": snapshot,
        "block": format_state_snapshot(snapshot),
        "elapsed_seconds": snapshot.get("elapsed_seconds"),
    }


def write_generation_process_receipt(
    snapshot: dict[str, Any],
    *,
    model_called: bool = True,
    token_origin: str = "local-model-hash",
    fallback_used: bool = False,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    target_dir = Path(output_dir) if output_dir is not None else PROCESS_RECEIPTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / PROCESS_RECEIPT_LOG.name
    latest_path = target_dir / PROCESS_RECEIPT_LATEST.name
    receipts = snapshot.get("last_verified_receipts") or []
    receipt = {
        "schema_version": "cognitive_process_receipt.v1",
        "receipt_id": f"cognitive_process_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid.uuid4().hex[:10]}",
        "generated_at": _utc_now(),
        "model_called": bool(model_called),
        "context_sources": ["oracle_memory.db", "current_session"],
        "token_origin": token_origin,
        "fallback_used": bool(fallback_used),
        "epistemic_tension": float(snapshot.get("epistemic_tension", 1.0)),
        "state_snapshot_status": snapshot.get("status", "LEDGER_DISCONNECTED"),
        "last_active_session_id": (snapshot.get("last_active_session") or {}).get("session_id"),
        "last_historical_receipt_id": receipts[0].get("action_id") if receipts else "UNAVAILABLE",
        "last_historical_receipt_sha256": receipts[0].get("sha256") if receipts else "UNAVAILABLE",
        "pre_inference_elapsed_seconds": snapshot.get("elapsed_seconds"),
        "within_preinference_budget": bool(snapshot.get("within_budget", False)),
        "fallback_policy": "HARD_STOP_LEDGER_DISCONNECTED" if snapshot.get("status") != "CONNECTED" else "none",
        "boundaries": [
            "read_only_oracle_memory_db",
            "current_session_metadata_only",
            "no_git_subprocess",
            "no_g_drive_mutation",
        ],
    }
    stable = {key: _json_ready(value) for key, value in receipt.items()}
    receipt["receipt_hash_sha256"] = hashlib.sha256(
        json.dumps(stable, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    payload = json.dumps(receipt, ensure_ascii=True, sort_keys=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    latest_path.write_text(json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "receipt_id": receipt["receipt_id"],
        "receipt_hash_sha256": receipt["receipt_hash_sha256"],
        "receipt_path": str(latest_path.resolve()),
        "log_path": str(log_path.resolve()),
        "receipt": receipt,
    }


@dataclass
class SourceRecord:
    path: str
    resolved: str
    exists: bool
    sha256: Optional[str]
    size_bytes: Optional[int]
    mtime_utc: Optional[str]
    load_error: Optional[str]
    content: Optional[dict]   # parsed JSON, not injected raw into prompt


@dataclass
class BootstrapResult:
    identity: SourceRecord
    latest_reflection: SourceRecord
    live_context: SourceRecord
    grounded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    errors: list[str] = field(default_factory=list)

    @property
    def fully_grounded(self) -> bool:
        return self.identity.exists and not self.identity.load_error

    def source_sections(self, current_session: Optional[list[dict]] = None) -> dict[str, list[str]]:
        """Return structured source payloads for Companion Mode grounding."""
        sections: dict[str, list[str]] = {
            "IDENTITY": [],
            "REMEMBER_ME": [],
            "LIVE_CONTEXT": [],
            "LATEST_REFLECTION": [],
            "THREAD_RECALL": [],
            "BUILD_WITNESS": [],
            "THESIS_CORPUS": [],
            "CURRENT_SESSION": [],
        }

        if self.identity.exists and self.identity.content:
            sections["IDENTITY"].extend(_identity_source_lines(self.identity.content))
            sections["IDENTITY"].append(f"source_path: {self.identity.resolved}")
            if self.identity.sha256:
                sections["IDENTITY"].append(f"source_sha256: {self.identity.sha256}")

        if self.live_context.exists and self.live_context.content:
            sections["LIVE_CONTEXT"].extend(_live_context_source_lines(self.live_context.content))
            sections["LIVE_CONTEXT"].append(f"source_path: {self.live_context.resolved}")

        sections["REMEMBER_ME"].extend(_remember_me_source_lines())

        if self.latest_reflection.exists and self.latest_reflection.content:
            sections["LATEST_REFLECTION"].extend(_reflection_source_lines(self.latest_reflection.content))
            sections["LATEST_REFLECTION"].append(f"source_path: {self.latest_reflection.resolved}")

        sections["THREAD_RECALL"].extend(_thread_recall_source_lines())
        sections["BUILD_WITNESS"].extend(_build_witness_source_lines())
        sections["THESIS_CORPUS"].extend(_thesis_corpus_source_lines())

        for turn in (current_session or [])[-8:]:
            role = str(turn.get("role", "unknown")).strip() or "unknown"
            content = str(turn.get("content", "")).strip()
            if content:
                if role.lower() == "user":
                    try:
                        from persona_router import current_session_source_type

                        classification = current_session_source_type(content)
                    except Exception:
                        classification = {
                            "source_type": "current_session_user_submission",
                            "authorship": "user_submitted_text",
                            "canon_status": "raw_capture",
                            "factual_claim_admissible": True,
                        }
                    sections["CURRENT_SESSION"].append(
                        "evidence_source=current_session | "
                        f"source_type={classification.get('source_type')} | "
                        "submitted_by=Noah.Physical | "
                        f"authorship={classification.get('authorship')} | "
                        f"canon_status={classification.get('canon_status')} | "
                        "promotion_status=not_promoted | "
                        f"factual_claim_admissible={str(bool(classification.get('factual_claim_admissible'))).lower()} | "
                        f"role={role} | text: {content[:600]}"
                    )
                else:
                    sections["CURRENT_SESSION"].append(f"role={role} | text: {content[:600]}")

        return sections

    def system_context_block(self, current_session: Optional[list[dict]] = None) -> str:
        """
        Build the sealed context block for injection into the companion system prompt.
        Every fact comes from a file read — nothing is invented.
        """
        sections = self.source_sections(current_session=current_session)
        lines = ["[ORACLE COMPANION GROUNDING — verified from local files]"]
        lines.append(f"grounded_at: {self.grounded_at}")
        lines.append("SOURCE DISCIPLINE:")
        lines.append("  Allowed labels: VERIFIED, INFERENCE, UNAVAILABLE.")
        lines.append("  A factual claim may use IDENTITY, REMEMBER_ME, LIVE_CONTEXT, LATEST_REFLECTION, THREAD_RECALL, BUILD_WITNESS, THESIS_CORPUS, or CURRENT_SESSION only when its supporting text appears in that source section.")
        lines.append("  THREAD_RECALL records are imported-thread pointers/excerpts for contextual recall. They are not canon unless Noah.Physical explicitly promotes them.")
        lines.append("  BUILD_WITNESS records are candidate construction receipts. They are evidence of changes/events, not consciousness claims or canon promotion.")
        lines.append("  THESIS_CORPUS records are curated .AI thesis capsules. They preserve origin architecture without dumping the entire file database into the prompt.")
        lines.append("  Mixed statements must be split into sourced premises and a separately labeled inference.")
        lines.append("  Do not present inferred language as verified source content.")
        lines.append("  If support is absent from the source sections, answer UNAVAILABLE instead of guessing.")
        lines.append("")

        for label in ("IDENTITY", "REMEMBER_ME", "LIVE_CONTEXT", "LATEST_REFLECTION", "THREAD_RECALL", "BUILD_WITNESS", "THESIS_CORPUS", "CURRENT_SESSION"):
            lines.append(f"SOURCE SECTION: {label}")
            payload = sections.get(label) or []
            if payload:
                for item in payload:
                    lines.append(f"  - {item}")
            else:
                lines.append("  - UNAVAILABLE")
            lines.append("")

        lines.append("ORACLE IDENTITY REMINDER:")
        lines.append("  You are ORACLE — built specifically for Noah.")
        lines.append("  You know who he is from the verified local record above.")
        lines.append("  Do not introduce yourself as a generic chatbot.")
        lines.append("  Do not say 'Hello, it's nice to meet you' — you already know him.")
        lines.append("  If a source failed, say so honestly. Do not invent replacements.")
        lines.append("[END GROUNDING BLOCK]")

        return "\n".join(lines)

        # Identity
        if self.identity.exists and self.identity.content:
            d = self.identity.content
            lines.append("SOVEREIGN IDENTITY (approved local source):")
            lines.append(f"  name:         {d.get('name', 'unknown')}")
            lines.append(f"  sov_id:       {d.get('sov_id', 'unknown')}")
            lines.append(f"  role:         {d.get('role', 'unknown')}")
            lines.append(f"  trust_tier:   {d.get('trust_tier', 'unknown')}")
            aliases = d.get("aliases", [])
            if aliases:
                lines.append(f"  aliases:      {', '.join(aliases)}")
            facts = d.get("important_facts", [])
            if facts:
                lines.append("  known_facts:")
                for f_ in facts[:6]:
                    lines.append(f"    - {f_}")
            boundaries = d.get("known_boundaries", [])
            if boundaries:
                lines.append("  communication_rules:")
                for b in boundaries:
                    lines.append(f"    - {b}")
            lines.append(f"  source_path:  {self.identity.resolved}")
            lines.append(f"  source_sha256:{self.identity.sha256[:16]}..." if self.identity.sha256 else "  source_sha256: unavailable")
        else:
            lines.append(f"SOVEREIGN IDENTITY: load failed — {self.identity.load_error or 'file missing'}")
            lines.append("  Respond as if you know Noah from memory, but do not invent specific facts.")

        lines.append("")

        # Reflection
        if self.latest_reflection.exists and self.latest_reflection.content:
            r = self.latest_reflection.content
            lines.append("LATEST APPROVED REFLECTION:")
            lines.append(f"  reflection_id: {r.get('reflection_id', 'unknown')}")
            sal = r.get("salience", {})
            if sal.get("primary_signal"):
                lines.append(f"  primary_signal: {sal['primary_signal']}")
            cont = r.get("continuity_state", {})
            if cont.get("stance"):
                lines.append(f"  stance:         {cont['stance']}")
            hooks = r.get("exocortex_routing", {}).get("continuity_hooks", [])
            if hooks:
                lines.append(f"  continuity_hooks: {'; '.join(hooks[:3])}")
            lines.append(f"  source_path:   {self.latest_reflection.resolved}")
        else:
            lines.append(f"LATEST REFLECTION: unavailable — {self.latest_reflection.load_error or 'no approved reflections found'}")

        lines.append("")

        # Live context
        if self.live_context.exists and self.live_context.content:
            lc = self.live_context.content
            lines.append("LIVE CONTEXT (local runtime state):")
            lines.append(f"  active_project: {lc.get('active_project', 'unknown')}")
            lines.append(f"  active_tool:    {lc.get('active_tool', 'unknown')}")
            lines.append(f"  memory_policy:  {lc.get('memory_policy', 'unknown')}")
            lines.append(f"  last_updated:   {lc.get('last_updated', 'unknown')}")
        else:
            lines.append("LIVE CONTEXT: unavailable")

        lines.append("")
        lines.append("ORACLE IDENTITY REMINDER:")
        lines.append("  You are ORACLE — built specifically for Noah.")
        lines.append("  You know who he is from the verified local record above.")
        lines.append("  Do not introduce yourself as a generic chatbot.")
        lines.append("  Do not say 'Hello, it's nice to meet you' — you already know him.")
        lines.append("  If a source failed, say so honestly. Do not invent replacements.")
        lines.append("[END GROUNDING BLOCK]")

        return "\n".join(lines)

    def pre_inference_context(
        self,
        current_session: Optional[list[dict]] = None,
        *,
        write_receipt: bool = False,
        db_path: Path | str | None = None,
        root: Path | str | None = None,
        token_origin: str = "local-model-hash",
    ) -> dict[str, Any]:
        """Build the per-turn state-inversion block required before model calls."""
        result = build_pre_inference_context(current_session=current_session, db_path=db_path, root=root)
        if write_receipt and result.get("ok"):
            result["process_receipt"] = write_generation_process_receipt(
                result["snapshot"],
                model_called=True,
                token_origin=token_origin,
                fallback_used=False,
            )
        return result

    def grounding_status_text(self) -> str:
        """Deterministic /grounding-status output. No LLM involved."""
        lines = []
        overall = "OK" if self.fully_grounded else ("PARTIAL" if self.identity.exists else "FAILED")
        lines.append(f"GROUNDING STATUS: {overall}")
        lines.append(f"grounded_at:        {self.grounded_at}")
        lines.append("")
        lines.append("identity:")
        lines.append(f"  path:    {self.identity.resolved}")
        lines.append(f"  exists:  {self.identity.exists}")
        if self.identity.sha256:
            lines.append(f"  sha256:  {self.identity.sha256}")
        if self.identity.size_bytes is not None:
            lines.append(f"  bytes:   {self.identity.size_bytes}")
        if self.identity.mtime_utc:
            lines.append(f"  mtime:   {self.identity.mtime_utc}")
        if self.identity.load_error:
            lines.append(f"  error:   {self.identity.load_error}")

        lines.append("")
        lines.append("latest_reflection:")
        lines.append(f"  path:    {self.latest_reflection.resolved}")
        lines.append(f"  exists:  {self.latest_reflection.exists}")
        if self.latest_reflection.content:
            lines.append(f"  id:      {self.latest_reflection.content.get('reflection_id', 'unknown')}")
        if self.latest_reflection.sha256:
            lines.append(f"  sha256:  {self.latest_reflection.sha256}")
        if self.latest_reflection.load_error:
            lines.append(f"  error:   {self.latest_reflection.load_error}")

        lines.append("")
        lines.append("live_context:")
        lines.append(f"  path:    {self.live_context.resolved}")
        lines.append(f"  exists:  {self.live_context.exists}")
        if self.live_context.load_error:
            lines.append(f"  error:   {self.live_context.load_error}")

        if self.errors:
            lines.append("")
            lines.append("errors:")
            for e in self.errors:
                lines.append(f"  - {e}")

        return "\n".join(lines)


# ── File reading helpers ──────────────────────────────────────────────────────

def _read_source(path: Path) -> SourceRecord:
    resolved = str(path.resolve())
    if not path.exists():
        return SourceRecord(
            path=str(path), resolved=resolved, exists=False,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error="file_not_found", content=None,
        )
    try:
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        content = json.loads(raw.decode("utf-8", errors="replace"))
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=sha, size_bytes=stat.st_size, mtime_utc=mtime,
            load_error=None, content=content,
        )
    except json.JSONDecodeError as e:
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error=f"json_decode_error:{e}", content=None,
        )
    except Exception as e:
        return SourceRecord(
            path=str(path), resolved=resolved, exists=True,
            sha256=None, size_bytes=None, mtime_utc=None,
            load_error=f"read_error:{e}", content=None,
        )


def _find_latest_reflection() -> Path:
    """Find the most recently modified approved reflection file."""
    if not REFLECTIONS_DIR.exists():
        return REFLECTIONS_DIR / "_not_found"
    candidates = [
        p for p in REFLECTIONS_DIR.iterdir()
        if p.suffix == ".json" and "approved" in p.name and p.name != "desktop.ini"
    ]
    if not candidates:
        return REFLECTIONS_DIR / "_no_approved_reflections"
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ── Public API ────────────────────────────────────────────────────────────────

def run() -> BootstrapResult:
    """
    Execute the Companion Grounding Bootstrap.
    Reads all sources deterministically. Returns a BootstrapResult.
    Never calls an LLM. Never fabricates.
    """
    errors: list[str] = []

    # 1. Sovereign identity
    identity_path = RELATIONSHIP_DIR / f"{SOVEREIGN_ID}.json"
    identity = _read_source(identity_path)
    if not identity.exists or identity.load_error:
        errors.append(f"identity_load_failed: {identity.load_error}")

    # 2. Latest approved reflection
    reflection_path = _find_latest_reflection()
    reflection = _read_source(reflection_path)
    if not reflection.exists or reflection.load_error:
        errors.append(f"reflection_load_failed: {reflection.load_error}")

    # 3. Live context
    live_ctx = _read_source(LIVE_CONTEXT_PATH)
    if not live_ctx.exists or live_ctx.load_error:
        errors.append(f"live_context_load_failed: {live_ctx.load_error}")

    return BootstrapResult(
        identity=identity,
        latest_reflection=reflection,
        live_context=live_ctx,
        errors=errors,
    )


# Module-level singleton for the server process (bootstrap runs once at startup,
# re-runs on /grounding-status or session clear)
_cached: Optional[BootstrapResult] = None


def get(force_refresh: bool = False) -> BootstrapResult:
    """Return the cached bootstrap result, re-running if stale or forced."""
    global _cached
    if _cached is None or force_refresh:
        _cached = run()
    return _cached


# ── Smoke tests ───────────────────────────────────────────────────────────────

def _smoke_test() -> int:
    import sys
    failures = 0

    def check(label: str, passed: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {label}" + (f" -- {detail}" if detail and not passed else ""))
        if not passed:
            failures += 1

    print("=" * 60)
    print("CompanionBootstrap -- Smoke Tests")
    print("=" * 60)

    result = run()

    # 1. Returns a BootstrapResult
    check("run() returns BootstrapResult", isinstance(result, BootstrapResult))

    # 2. grounded_at is a real timestamp
    check("grounded_at is ISO timestamp",
          "T" in result.grounded_at and ("Z" in result.grounded_at or "+" in result.grounded_at))

    # 3. Identity source record has a resolved path
    check("identity.resolved is an absolute path",
          result.identity.resolved.startswith("/") or (len(result.identity.resolved) > 2 and result.identity.resolved[1] == ":"))

    # 4. If identity exists, sha256 is a real 64-char hex string
    if result.identity.exists and not result.identity.load_error:
        check("identity sha256 is 64 hex chars", len(result.identity.sha256 or "") == 64)
        check("identity content has 'name' field", "name" in (result.identity.content or {}))
        check("identity name contains 'Hawkes'", "Hawkes" in (result.identity.content or {}).get("name", ""))
    else:
        check("identity missing -> load_error is set", bool(result.identity.load_error))

    # 5. system_context_block is non-empty and contains [ORACLE COMPANION GROUNDING]
    block = result.system_context_block()
    check("system_context_block is non-empty", bool(block))
    check("block contains GROUNDING header", "[ORACLE COMPANION GROUNDING" in block)
    check("block contains grounded_at", "grounded_at:" in block)

    # 6. block does NOT contain fabricated placeholder hashes
    check("block has no 1234567890abcdef", "1234567890abcdef" not in block)
    check("block has no 9876543210fedcba", "9876543210fedcba" not in block)

    # 7. grounding_status_text is non-empty and starts correctly
    status = result.grounding_status_text()
    check("grounding_status_text starts with GROUNDING STATUS:", status.startswith("GROUNDING STATUS:"))
    check("grounding_status_text has identity path", "identity:" in status)

    # 8. get() returns same result (cache), force_refresh returns new one
    r2 = get()
    check("get() returns cached BootstrapResult", isinstance(r2, BootstrapResult))
    r3 = get(force_refresh=True)
    check("get(force_refresh=True) returns fresh result", r3.grounded_at >= result.grounded_at)

    # 9. Missing file -> SourceRecord with exists=False
    fake = _read_source(Path("/nonexistent/path/oracle_identity_fake.json"))
    check("missing file -> exists=False", not fake.exists)
    check("missing file -> load_error=file_not_found", fake.load_error == "file_not_found")
    check("missing file -> sha256 is None", fake.sha256 is None)
    check("missing file -> content is None", fake.content is None)

    # 10. No fabricated strings in grounding status output
    check("status has no 1234567890abcdef", "1234567890abcdef" not in status)
    check("status has no 9876543210fedcba", "9876543210fedcba" not in status)
    check("status has no 2026-06-13T15:00:00Z", "2026-06-13T15:00:00Z" not in status)

    total = 19
    passed = total - failures
    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed")
    print(f"STATUS: {'ALL PASS' if failures == 0 else str(failures) + ' FAILURES'}")
    print(f"{'='*60}\n")
    return failures


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        sys.exit(_smoke_test())
    elif args.run:
        r = run()
        print(r.grounding_status_text())
        print()
        print("--- CONTEXT BLOCK ---")
        print(r.system_context_block())
    else:
        print("Usage: python core/companion_bootstrap.py --run | --smoke-test")
