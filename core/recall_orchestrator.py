"""Read-only recall coordinator for ORACLE talk lane.

This module does not ingest, mutate, promote, execute, send, or read sandbox
files. It only summarizes already-built read-only indexes so conversational
answers can be grounded in specific backend records instead of memory-shaped
guessing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

THREAD_INDEX = RUNTIME_ROOT / "Memory" / "thread_ingest" / "search_index.jsonl"

MAX_RECORDS = 10
MAX_BLOCK_CHARS = 3200

STOPWORDS = {
    "about", "answer", "backend", "cited", "cites", "cite", "docs",
    "document", "documents", "evidence", "exact", "from", "gaps", "indexed",
    "known", "know", "only", "oracle", "paths", "prompt", "recall",
    "records", "search", "source", "sources", "test", "that", "the",
    "titles", "unknown", "use", "used", "what", "when", "where", "which",
    "who", "why", "writings",
}

RECALL_HINTS = re.compile(
    r"\b("
    r"recall|remember|backend|writings?|documents?|docs?|source|cite|atlas|"
    r"lockbox|drive|thread|who is noah|noah hawkes|jupiter station|avalon|"
    r"sov1|noah\.public|noah\.self|noah\.physical|max\.ai|five selves|"
    r"legacygi|legacy\.gi|truthwriter|return-from-dark|rendered reality|"
    r"ai compliance core|ai work audit kit|compression is identity|"
    r"federation ai|miracledrive|approval gates?|connector rules?|"
    r"qr tattoo|25-question|diagnostic spine"
    r")\b",
    re.IGNORECASE,
)

DOMAIN_QUERIES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"jupiter|avalon", re.I), ("Jupiter Station Avalon", "world bible Avalon Jupiter Station")),
    (re.compile(r"\bsov1\b|sov1\.ai|five selves|noah\.public|noah\.self|noah\.physical|max\.ai", re.I),
     ("SOV1.AI", "Noah.Public Noah.Self Noah.Physical Max.AI")),
    (re.compile(r"ai compliance|work audit|approval gate|connector rules?", re.I),
     ("AI Compliance Core", "AI Work Audit Kit", "approval gate provenance connector")),
    (re.compile(r"legacy\.?gi|truthwriter|return-from-dark|25-question|diagnostic spine", re.I),
     ("LegacyGI Truthwriter", "Return-from-Dark", "25-question diagnostic spine")),
    (re.compile(r"rendered reality", re.I), ("Rendered Reality",)),
    (re.compile(r"compression is identity", re.I), ("Compression Is Identity",)),
    (re.compile(r"federation ai", re.I), ("Federation AI",)),
    (re.compile(r"miracledrive|miracle drive", re.I), ("MiracleDrive", "Miracle Drive")),
    (re.compile(r"thread injection|thread pass|thread merge", re.I), ("thread injection", "ThreadMerge")),
    (re.compile(r"qr tattoo|qr code|tattoo", re.I), ("QR code tattoo SOV1", "SOV1.AI QR")),
    (re.compile(r"noah hawkes|who is noah", re.I), ("Noah Hawkes",)),
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_test_prefix(value: str) -> str:
    text = _clean(value)
    text = re.sub(r"^(?:pass|recall test)\s*\d{1,3}\s*[:.)-]\s*", "", text, flags=re.I)
    return text


def should_ground(user_text: str) -> bool:
    text = _strip_test_prefix(user_text)
    return bool(RECALL_HINTS.search(text))


def should_answer_deterministically(user_text: str) -> bool:
    raw = _clean(user_text)
    if raw.startswith("/"):
        return False
    lower = raw.lower()
    if lower.startswith("recall test"):
        return True
    if re.match(r"^(?:pass|recall test)\s*\d{1,3}\s*[:.)-]", lower):
        return True
    if "backend recall" in lower or "indexed records" in lower:
        return True
    if "cite" in lower and any(token in lower for token in ("document", "documents", "docs", "records", "sources", "paths", "titles")):
        return True
    return False


def _queries(user_text: str) -> list[str]:
    text = _strip_test_prefix(user_text)
    out: list[str] = []
    for pattern, queries in DOMAIN_QUERIES:
        if pattern.search(text):
            out.extend(queries)
    words = [
        word for word in re.findall(r"[A-Za-z0-9_.-]{3,}", text)
        if word.lower() not in STOPWORDS
    ]
    if words:
        out.append(" ".join(words[:5]))
        out.append(" ".join(words[:3]))
    deduped: list[str] = []
    seen: set[str] = set()
    for query in out:
        query = _clean(query)
        key = query.lower()
        if query and key not in seen:
            seen.add(key)
            deduped.append(query)
    return deduped[:8]


def _sandbox_path(value: str) -> bool:
    text = str(value or "").lower().replace("/", "\\")
    return "\\sandbox\\" in text


def _add_record(records: list[dict[str, Any]], seen: set[str], record: dict[str, Any]) -> None:
    path = str(record.get("path") or record.get("source_path") or "")
    if path and _sandbox_path(path):
        return
    key = "|".join([
        str(record.get("surface") or ""),
        str(record.get("path") or record.get("source_path") or ""),
        str(record.get("title") or record.get("name") or ""),
    ]).lower()
    if key in seen:
        return
    seen.add(key)
    records.append(record)


def _document_atlas_records(query: str, limit: int = 4) -> list[dict[str, Any]]:
    try:
        from document_atlas import search_atlas

        result = search_atlas(query, limit=limit)
    except Exception:
        return []
    records = []
    for item in result.get("results") or []:
        records.append({
            "surface": "document_atlas",
            "query": query,
            "title": item.get("name") or "UNKNOWN",
            "path": item.get("path") or "",
            "source_surface": item.get("source_surface") or "",
            "category": item.get("candidate_category") or "",
            "canon_status": item.get("canon_status") or "candidate",
        })
    return records


def _file_recall_records(query: str, limit: int = 3) -> list[dict[str, Any]]:
    try:
        from file_recall import search

        result = search(query, limit=limit, write_receipt=False, deep=False)
    except Exception:
        return []
    records = []
    for item in result.get("results") or []:
        records.append({
            "surface": "file_recall",
            "query": query,
            "title": item.get("name") or "UNKNOWN",
            "path": item.get("path") or "",
            "kind": item.get("kind") or "",
            "modified": item.get("modified") or "",
        })
    return records


def _lockbox_records(query: str, limit: int = 3) -> list[dict[str, Any]]:
    try:
        from ai_lockbox import search_lockbox

        result = search_lockbox(query, limit=limit)
    except Exception:
        return []
    records = []
    for item in result.get("results") or []:
        records.append({
            "surface": "ai_lockbox",
            "query": query,
            "title": item.get("name") or "UNKNOWN",
            "path": item.get("source_path") or "",
            "capsule_path": item.get("capsule_path") or "",
            "canon_status": item.get("canon_status") or "candidate",
        })
    return records


def _thread_records(query: str, limit: int = 3) -> list[dict[str, Any]]:
    if not THREAD_INDEX.exists():
        return []
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_.-]{3,}", query)]
    if not terms:
        return []
    hits: list[dict[str, Any]] = []
    try:
        with THREAD_INDEX.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                path = str(row.get("raw_file_path") or row.get("parsed_transcript_path") or "")
                if _sandbox_path(path):
                    continue
                haystack = " ".join([
                    str(row.get("message_text") or ""),
                    str(row.get("raw_file_path") or ""),
                    str(row.get("parsed_transcript_path") or ""),
                    str(row.get("source_system") or ""),
                ]).lower()
                if all(term in haystack for term in terms):
                    hits.append({
                        "surface": "thread_ingest",
                        "query": query,
                        "title": row.get("source_thread_id") or Path(path).name or "thread_ingest_record",
                        "path": path,
                        "source_system": row.get("source_system") or "",
                        "canon_status": row.get("canon_status") or "candidate",
                        "preview": _clean(row.get("message_text") or "")[:220],
                    })
                    if len(hits) >= limit:
                        break
    except Exception:
        return []
    return hits


WINDOWS_PATH_RE = re.compile(
    r"`([A-Za-z]:[\\/][^`]+)`|(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\r\n\"'<>|]+)"
)


def _mentioned_windows_paths(user_text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for match in WINDOWS_PATH_RE.finditer(str(user_text or "")):
        raw = (match.group(1) or match.group(2) or "").strip()
        candidate = raw.rstrip(" .,:;)]}")
        if not candidate:
            continue
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            paths.append(candidate)
    return paths


def build_context(user_text: str, *, max_chars: int = MAX_BLOCK_CHARS) -> dict[str, Any]:
    if not should_ground(user_text):
        return {"active": False, "block": "", "records": [], "queries": []}

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    mentioned_paths = _mentioned_windows_paths(user_text)
    unverified_paths: list[dict[str, str]] = []
    for candidate in mentioned_paths:
        if _sandbox_path(candidate):
            unverified_paths.append({"path": candidate, "status": "UNVERIFIED_SANDBOX_BOUNDARY"})
            continue
        try:
            exists = Path(candidate).exists()
        except Exception:
            exists = False
        if exists:
            _add_record(records, seen, {
                "surface": "path_verifier",
                "query": candidate,
                "title": Path(candidate).name or candidate,
                "path": candidate,
                "category": "existing_local_path",
            })
        else:
            unverified_paths.append({"path": candidate, "status": "MISSING_OR_UNVERIFIED"})

    exact_path_only = bool(mentioned_paths) and re.search(
        r"\b(what is in|open|read|cite it only if verified|only if verified)\b",
        str(user_text or ""),
        re.IGNORECASE,
    )
    queries = _queries(user_text)
    if not exact_path_only or records:
        for query in queries:
            for source in (
                _document_atlas_records(query),
                _file_recall_records(query),
                _lockbox_records(query),
                _thread_records(query),
            ):
                for record in source:
                    _add_record(records, seen, record)
                    if len(records) >= MAX_RECORDS:
                        break
                if len(records) >= MAX_RECORDS:
                    break
            if len(records) >= MAX_RECORDS:
                break

    lines = [
        "[RECALL_ORCHESTRATOR - read-only backend recall packet]",
        "Rules: use only listed records for source claims; cite title/path when used; if a requested fact is not listed, say UNKNOWN.",
        "Boundary: no source mutation, no external send, no canon promotion, no command execution, no sandbox inspection by this coordinator.",
        f"queries: {', '.join(queries) if queries else 'UNKNOWN'}",
    ]
    if not records:
        lines.append("records: NONE FOUND - answer UNKNOWN for requested source-grounded facts.")
    else:
        lines.append("records:")
        for idx, record in enumerate(records, start=1):
            title = _clean(record.get("title") or "UNKNOWN")
            path = _clean(record.get("path") or "")
            surface = _clean(record.get("surface") or "UNKNOWN")
            category = _clean(record.get("category") or record.get("source_surface") or record.get("source_system") or "")
            lines.append(f"{idx}. surface={surface}; title={title}; path={path or 'UNKNOWN'}; category={category or 'UNKNOWN'}")
            preview = _clean(record.get("preview") or "")
            if preview:
                lines.append(f"   preview={preview[:180]}")
    if unverified_paths:
        lines.append("unverified_paths:")
        for item in unverified_paths[:8]:
            lines.append(f"- {item['status']}: {item['path']}")
    block = "\n".join(lines)[:max_chars]
    return {
        "active": True,
        "block": block,
        "records": records,
        "queries": queries,
        "record_count": len(records),
        "sources": sorted({str(r.get("surface") or "UNKNOWN") for r in records}),
        "unverified_paths": unverified_paths,
    }


def context_block(user_text: str, *, max_chars: int = MAX_BLOCK_CHARS) -> str:
    return str(build_context(user_text, max_chars=max_chars).get("block") or "")


def format_recall_answer(user_text: str, context: dict[str, Any] | None = None) -> str:
    context = context or build_context(user_text)
    records = list(context.get("records") or [])
    queries = list(context.get("queries") or [])
    unverified_paths = list(context.get("unverified_paths") or [])
    lines = [
        "RECALL CHECK",
        "mode: deterministic backend recall, read-only",
        "boundary: no file mutation, no external send, no canon promotion, no command execution, no sandbox inspection by this coordinator",
        f"queries: {', '.join(queries) if queries else 'UNKNOWN'}",
        f"records_found: {len(records)}",
    ]
    if not records:
        if unverified_paths:
            lines.extend(["", "Unverified paths:"])
            for item in unverified_paths[:8]:
                lines.append(f"- {item.get('status')}: {item.get('path')}")
        lines.extend([
            "",
            "I do not have citable backend records for that request from the current read-only indexes.",
            "Answer: UNKNOWN until Document Atlas, File Recall, AI Lockbox, or thread ingest returns source rows.",
        ])
        return "\n".join(lines)

    lines.extend([
        "",
        "Citable records:",
    ])
    for idx, record in enumerate(records, start=1):
        surface = _clean(record.get("surface") or "UNKNOWN")
        title = _clean(record.get("title") or "UNKNOWN")
        path = _clean(record.get("path") or "")
        category = _clean(record.get("category") or record.get("source_surface") or record.get("source_system") or "")
        lines.append(f"{idx}. {title}")
        lines.append(f"   surface: {surface}")
        lines.append(f"   path: {path or 'UNKNOWN'}")
        if category:
            lines.append(f"   category: {category}")
        preview = _clean(record.get("preview") or "")
        if preview:
            lines.append(f"   preview: {preview[:220]}")

    lines.extend([
        "",
        "Plain answer:",
        "I found backend recall records for this topic. I can confirm the topic exists in the indexed corpus and can cite the records above. I will not fill missing meaning with invention; any detail not supported by those records remains UNKNOWN until a specific source is read or indexed.",
    ])
    if unverified_paths:
        lines.extend(["", "Unverified paths mentioned in the prompt:"])
        for item in unverified_paths[:8]:
            lines.append(f"- {item.get('status')}: {item.get('path')}")
    return "\n".join(lines)


def guard_unverified_paths(text: str) -> tuple[str, list[dict[str, str]]]:
    """Append a compact warning for local paths that do not exist.

    This guard is deliberately conservative. It does not read file contents; it
    only checks path existence. Sandbox paths are labeled unverified without
    inspection to respect the handoff boundary.
    """

    value = str(text or "")
    if "CITATION_GUARD" in value:
        return value, []
    findings: list[dict[str, str]] = []
    for candidate in _mentioned_windows_paths(value):
        if _sandbox_path(candidate):
            findings.append({"path": candidate, "status": "UNVERIFIED_SANDBOX_BOUNDARY"})
            continue
        try:
            exists = Path(candidate).exists()
        except Exception:
            exists = False
        if not exists:
            findings.append({"path": candidate, "status": "MISSING_OR_UNVERIFIED"})
    if not findings:
        return value, []
    lines = [
        "",
        "[CITATION_GUARD]",
        "These paths were mentioned but are not verified source evidence from this response:",
    ]
    for item in findings[:8]:
        lines.append(f"- {item['status']}: {item['path']}")
    return value.rstrip() + "\n" + "\n".join(lines), findings


def evidence_payload(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    records = list(context.get("records") or [])
    return {
        "ok": True,
        "surface": "recall_orchestrator",
        "records_used_count": len(records),
        "sources_proven_used": sorted({str(r.get("surface") or "UNKNOWN") for r in records}),
        "records_used": [
            {
                "surface": r.get("surface"),
                "title": r.get("title"),
                "path": r.get("path"),
                "query": r.get("query"),
            }
            for r in records[:MAX_RECORDS]
        ],
        "queries": list(context.get("queries") or []),
        "boundary": {
            "read_only": True,
            "source_mutation": False,
            "external_send": False,
            "canon_promotion": False,
            "command_exec": False,
            "sandbox_inspection": False,
        },
    }
