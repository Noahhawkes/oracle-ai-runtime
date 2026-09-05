"""Read-only thread burden reporting for ORACLE captures.

This module summarizes the thread_capture custody manifest and search index so
ORACLE can help Noah orient across many imported AI threads without promoting
anything to canon or inventing continuity.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import thread_capture

    SOURCE_MANIFEST_JSONL = thread_capture.SOURCE_MANIFEST_JSONL
    SEARCH_INDEX_JSONL = thread_capture.SEARCH_INDEX_JSONL
except Exception:  # pragma: no cover
    try:
        from root import ROOT
    except Exception:
        ROOT = Path(__file__).resolve().parents[1]

    SOURCE_MANIFEST_JSONL = ROOT / "Memory" / "thread_ingest" / "source_manifests" / "source_manifest.jsonl"
    SEARCH_INDEX_JSONL = ROOT / "Memory" / "thread_ingest" / "search_index.jsonl"


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?")

DEFAULT_CARRY_BUCKETS = [
    {
        "bucket_id": "ellie",
        "label": "Ellie / Drakin / Dragonkin",
        "terms": ["ellie", "ellie.ai", "drakin", "dragonkin"],
    },
    {
        "bucket_id": "userpath",
        "label": "UserPath / User.AI lineage",
        "terms": ["userpath", "user.ai", "noah.ai", "identity node", "brother connect"],
    },
    {
        "bucket_id": "rendered_reality",
        "label": "Rendered Reality",
        "terms": ["rendered reality", "observe.copy.store", "observe copy store"],
    },
    {
        "bucket_id": "mobile_tech_coach",
        "label": "Mobile Tech Coach",
        "terms": ["mobile tech coach", "coach the owl"],
    },
    {
        "bucket_id": "routing_repair",
        "label": "Routing / source admission",
        "terms": ["routing", "noah_direct", "guard lane", "talk_lane", "source admission"],
    },
    {
        "bucket_id": "preferences",
        "label": "Preferences / interaction behavior",
        "terms": ["preference", "preferences", "dont introduce", "don't introduce", "pref_no_self_intro"],
    },
    {
        "bucket_id": "epistemic_audit",
        "label": "Epistemic audit / drift",
        "terms": ["epistemic audit", "eal", "drift_velocity", "narrative smoothing"],
    },
    {
        "bucket_id": "obs_runtime",
        "label": "OBS / live runtime visibility",
        "terms": ["obs", "rendered reality scene", "captain", "workstation"],
    },
    {
        "bucket_id": "chris_node",
        "label": "Chris / Chris.Node",
        "terms": ["chris", "chris.node", "brother"],
    },
    {
        "bucket_id": "github_drive",
        "label": "GitHub / Drive connectors",
        "terms": ["github", "google drive", "g drive", "onedrive", "connector"],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    if not path.exists():
        return rows, malformed
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            malformed += 1
    return rows, malformed


def _word_count(text: Any) -> int:
    return len(WORD_RE.findall(str(text or "")))


def _source_system(row: dict[str, Any]) -> str:
    return str(row.get("source_system") or "unknown")


def _is_noah_row(row: dict[str, Any]) -> bool:
    speaker = str(row.get("speaker") or "").strip().lower()
    return (
        str(row.get("authorial_authority") or "") == "Noah.Physical"
        or speaker in {"noah", "noah.physical", "noah a. hawkes", "noah hawkes"}
    )


def _is_ai_row(row: dict[str, Any]) -> bool:
    return str(row.get("token_origin") or "") == "ai_generated_text"


def _excerpt(text: Any, limit: int = 220) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _recent_captures(manifests: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = sorted(
        manifests,
        key=lambda row: str(row.get("captured_at") or row.get("recorded_at") or ""),
        reverse=True,
    )
    recent: list[dict[str, Any]] = []
    for row in rows[:limit]:
        recent.append(
            {
                "source_system": _source_system(row),
                "source_thread_id": row.get("source_thread_id"),
                "captured_at": row.get("captured_at"),
                "message_count": row.get("message_count"),
                "raw_sha256": row.get("raw_sha256"),
                "custody_receipt_path": row.get("custody_receipt_path"),
                "canon_status": row.get("canon_status"),
                "promotion_status": row.get("promotion_status"),
            }
        )
    return recent


def _duplicate_groups(manifests: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifests:
        raw_sha = str(row.get("raw_sha256") or "").strip()
        if raw_sha:
            grouped[raw_sha].append(row)

    duplicates: list[dict[str, Any]] = []
    for raw_sha, rows in grouped.items():
        if len(rows) < 2:
            continue
        duplicates.append(
            {
                "raw_sha256": raw_sha,
                "count": len(rows),
                "captures": [
                    {
                        "source_system": _source_system(row),
                        "source_thread_id": row.get("source_thread_id"),
                        "captured_at": row.get("captured_at"),
                        "custody_receipt_path": row.get("custody_receipt_path"),
                    }
                    for row in rows[:6]
                ],
            }
        )
    duplicates.sort(key=lambda row: (-int(row["count"]), str(row["raw_sha256"])))
    return duplicates[:limit]


def _haystack(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "source_system",
            "source_thread_id",
            "speaker",
            "message_text",
            "claim_type",
            "token_origin",
            "authorial_authority",
        )
    ).lower()


def _carry_buckets(
    search_rows: list[dict[str, Any]],
    *,
    sample_per_bucket: int,
) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for bucket in DEFAULT_CARRY_BUCKETS:
        matched_rows: list[dict[str, Any]] = []
        matched_terms: Counter[str] = Counter()
        terms = [str(term).lower() for term in bucket["terms"]]
        for row in search_rows:
            haystack = _haystack(row)
            row_matched = False
            for term in terms:
                if term and term in haystack:
                    matched_terms[term] += 1
                    row_matched = True
            if row_matched:
                matched_rows.append(row)

        samples = []
        for row in matched_rows[:sample_per_bucket]:
            samples.append(
                {
                    "source_system": _source_system(row),
                    "source_thread_id": row.get("source_thread_id"),
                    "message_index": row.get("message_index"),
                    "speaker": row.get("speaker"),
                    "claim_type": row.get("claim_type"),
                    "canon_status": row.get("canon_status"),
                    "promotion_status": row.get("promotion_status"),
                    "parsed_transcript_path": row.get("parsed_transcript_path"),
                    "excerpt": _excerpt(row.get("message_text")),
                }
            )

        buckets.append(
            {
                "bucket_id": bucket["bucket_id"],
                "label": bucket["label"],
                "matching_messages": len(matched_rows),
                "matched_terms": _sorted_counter(matched_terms),
                "samples": samples,
            }
        )
    buckets.sort(key=lambda row: (-int(row["matching_messages"]), str(row["bucket_id"])))
    return buckets


def _word_metrics(search_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_words = 0
    noah_words = 0
    ai_words = 0
    words_by_source: Counter[str] = Counter()
    noah_words_by_source: Counter[str] = Counter()
    ai_words_by_source: Counter[str] = Counter()

    for row in search_rows:
        count = _word_count(row.get("message_text"))
        source = _source_system(row)
        total_words += count
        words_by_source[source] += count
        if _is_noah_row(row):
            noah_words += count
            noah_words_by_source[source] += count
        if _is_ai_row(row):
            ai_words += count
            ai_words_by_source[source] += count

    ratio = None
    if ai_words:
        ratio = round(noah_words / ai_words, 4)

    return {
        "total_indexed_words": total_words,
        "noah_authored_words": noah_words,
        "ai_generated_words": ai_words,
        "noah_to_ai_word_ratio": ratio,
        "words_by_source_system": _sorted_counter(words_by_source),
        "noah_words_by_source_system": _sorted_counter(noah_words_by_source),
        "ai_words_by_source_system": _sorted_counter(ai_words_by_source),
    }


def build_thread_burden_report(
    *,
    recent_limit: int = 8,
    duplicate_limit: int = 8,
    sample_per_bucket: int = 2,
) -> dict[str, Any]:
    manifests, malformed_manifest_rows = _read_jsonl(SOURCE_MANIFEST_JSONL)
    search_rows, malformed_search_rows = _read_jsonl(SEARCH_INDEX_JSONL)

    source_counts = Counter(_source_system(row) for row in manifests)
    message_source_counts = Counter(_source_system(row) for row in search_rows)
    unique_hashes = {str(row.get("raw_sha256") or "") for row in manifests if row.get("raw_sha256")}
    duplicate_groups = _duplicate_groups(manifests, duplicate_limit)

    return {
        "ok": True,
        "report_kind": "thread_burden_report",
        "generated_at": _now(),
        "source_manifest_jsonl": str(SOURCE_MANIFEST_JSONL.resolve()),
        "search_index_jsonl": str(SEARCH_INDEX_JSONL.resolve()),
        "source_manifest_rows": len(manifests),
        "search_index_rows": len(search_rows),
        "malformed_manifest_rows": malformed_manifest_rows,
        "malformed_search_rows": malformed_search_rows,
        "unique_raw_hashes": len(unique_hashes),
        "duplicate_group_count": len(duplicate_groups),
        "counts_by_capture_source_system": _sorted_counter(source_counts),
        "message_count_by_source_system": _sorted_counter(message_source_counts),
        "word_metrics": _word_metrics(search_rows),
        "recent_captures": _recent_captures(manifests, recent_limit),
        "duplicate_groups": duplicate_groups,
        "carry_buckets": _carry_buckets(search_rows, sample_per_bucket=sample_per_bucket),
        "boundary": {
            "canon_status": "candidate",
            "promotion_status": "not_promoted",
            "cloud_upload": False,
            "git_commit": False,
            "git_push": False,
            "source_rule": "Captured threads are searchable evidence candidates, not canon.",
        },
        "next_actions": [
            "Use /thread-capture-search <term> for narrow retrieval.",
            "Use /thread-capture-status before trusting memory counts.",
            "Promote nothing without Noah.Physical approval.",
        ],
    }


def format_thread_burden_report(report: dict[str, Any]) -> str:
    word_metrics = report.get("word_metrics") or {}
    lines = [
        "THREAD BURDEN REPORT",
        f"generated_at: {report.get('generated_at')}",
        f"source_manifest_rows: {report.get('source_manifest_rows')}",
        f"search_index_rows: {report.get('search_index_rows')}",
        f"unique_raw_hashes: {report.get('unique_raw_hashes')}",
        f"duplicate_group_count: {report.get('duplicate_group_count')}",
        f"total_indexed_words: {word_metrics.get('total_indexed_words', 0)}",
        f"noah_authored_words: {word_metrics.get('noah_authored_words', 0)}",
        f"ai_generated_words: {word_metrics.get('ai_generated_words', 0)}",
        f"noah_to_ai_word_ratio: {word_metrics.get('noah_to_ai_word_ratio')}",
        "",
        "CAPTURE SOURCES",
    ]

    for source, count in (report.get("counts_by_capture_source_system") or {}).items():
        lines.append(f"- {source}: {count}")

    lines.append("")
    lines.append("CARRY BUCKETS")
    for bucket in (report.get("carry_buckets") or [])[:8]:
        lines.append(f"- {bucket.get('label')}: {bucket.get('matching_messages')} matching messages")
        terms = bucket.get("matched_terms") or {}
        if terms:
            compact_terms = ", ".join(f"{term}={count}" for term, count in list(terms.items())[:5])
            lines.append(f"  terms: {compact_terms}")
        samples = bucket.get("samples") or []
        for sample in samples[:1]:
            lines.append(
                "  sample: "
                f"{sample.get('source_system')} / {sample.get('source_thread_id')} "
                f"#{sample.get('message_index')} - {sample.get('excerpt')}"
            )

    lines.append("")
    lines.append("RECENT CAPTURES")
    for capture in (report.get("recent_captures") or [])[:5]:
        lines.append(
            "- "
            f"{capture.get('captured_at')} | {capture.get('source_system')} | "
            f"{capture.get('source_thread_id')} | receipt={capture.get('custody_receipt_path')}"
        )

    duplicate_groups = report.get("duplicate_groups") or []
    if duplicate_groups:
        lines.append("")
        lines.append("DUPLICATE RAW HASHES")
        for group in duplicate_groups[:5]:
            lines.append(f"- {group.get('raw_sha256')}: {group.get('count')} captures")

    boundary = report.get("boundary") or {}
    lines.extend(
        [
            "",
            "BOUNDARY",
            f"canon_status: {boundary.get('canon_status')}",
            f"promotion_status: {boundary.get('promotion_status')}",
            f"source_rule: {boundary.get('source_rule')}",
        ]
    )
    return "\n".join(lines)

