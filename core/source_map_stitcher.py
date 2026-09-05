"""SourceMap Stitcher.

Builds a small, read-only capsule from the configured MiracleDrive index so
ORACLE's sandbox self-prompt loop can recall nearby local sources without
copying raw files, promoting canon, or touching the sandbox directly.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from root import ROOT


DEFAULT_ANCHOR_QUERIES: tuple[str, ...] = (
    "ORACLE",
    "SourceMap",
    "MiracleDrive",
    "SOV1",
    "Ellie",
    "Rendered Reality",
    "Jupiter Station",
    "continuity",
    "receipt",
    "canon",
)

DEFAULT_LIMIT_PER_QUERY = 12
MAX_ANCHORS = 24
MAX_LIMIT_PER_QUERY = 50
MAX_PREVIEW_CHARS = 500

CAPSULE_DIR = ROOT / "state" / "source_map_capsules"
LATEST_CAPSULE_PATH = ROOT / "state" / "source_map_capsule_latest.json"

SENSITIVE_PATH_TERMS = {
    ".env",
    ".ssh",
    "apikey",
    "api_key",
    "auth token",
    "browser profile",
    "client_secret",
    "cookie",
    "credential",
    "id_rsa",
    "login data",
    "oauth",
    "password",
    "private key",
    "refresh_token",
    "secret",
    "token.json",
}

SENSITIVE_PREVIEW_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|client[_-]?secret|password|refresh[_-]?token|access[_-]?token)\s*[:=]\s*[^\s,;}{]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_queries(anchor_queries: Iterable[str] | None) -> list[str]:
    raw = list(anchor_queries or DEFAULT_ANCHOR_QUERIES)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        query = " ".join(str(item or "").split())
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(query)
        if len(out) >= MAX_ANCHORS:
            break
    return out or list(DEFAULT_ANCHOR_QUERIES)


def _bounded_limit(limit_per_query: int | str | None) -> int:
    try:
        value = int(limit_per_query or DEFAULT_LIMIT_PER_QUERY)
    except Exception:
        value = DEFAULT_LIMIT_PER_QUERY
    return max(1, min(value, MAX_LIMIT_PER_QUERY))


def _record_path(record: dict[str, Any]) -> str:
    return str(record.get("path") or "").strip()


def _path_is_sensitive(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    return any(term in lower for term in SENSITIVE_PATH_TERMS)


def _record_key(record: dict[str, Any]) -> str:
    path = _record_path(record).lower()
    sha = str(record.get("sha256_prefix") or "").lower()
    size = str(record.get("size_bytes") or "")
    return f"{path}|{sha}|{size}"


def _source_id(record: dict[str, Any]) -> str:
    digest = hashlib.sha256(_record_key(record).encode("utf-8", errors="replace")).hexdigest()
    return f"src_{digest[:16]}"


def _collapse_preview(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split())
    if not text:
        return None
    for pattern in SENSITIVE_PREVIEW_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "=[REDACTED]" if match.groups() else "[REDACTED]", text)
    return text[:MAX_PREVIEW_CHARS]


def _record_to_source(record: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "source_id": _source_id(record),
        "query_hits": [query],
        "name": str(record.get("name") or Path(_record_path(record)).name),
        "path": _record_path(record),
        "extension": str(record.get("extension") or ""),
        "size_bytes": int(record.get("size_bytes") or 0),
        "mtime_utc": str(record.get("mtime_utc") or ""),
        "sha256_prefix": str(record.get("sha256_prefix") or ""),
        "category": str(record.get("category") or ""),
        "source_root": str(record.get("source_root") or ""),
        "content_available": bool(record.get("content_available")),
        "content_preview": _collapse_preview(record.get("content_preview")),
    }


def _default_search(query: str, limit: int) -> list[dict[str, Any]]:
    from miracledrive_index import query as md_query

    return list(md_query(query, limit=limit))


def build_capsule(
    anchor_queries: Iterable[str] | None = None,
    limit_per_query: int | str | None = None,
    *,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    force_build: bool = False,
    capsule_dir: Path | None = None,
    latest_path: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Build a read-only SourceMap anchor capsule from MiracleDrive search hits."""
    queries = _normalize_queries(anchor_queries)
    limit = _bounded_limit(limit_per_query)
    if search_fn is not None:
        finder = search_fn
    elif force_build:
        from miracledrive_index import build_index

        index = build_index()

        def finder(query: str, item_limit: int) -> list[dict[str, Any]]:
            return [asdict(record) for record in index.search(query, limit=item_limit)]
    else:
        finder = _default_search

    sources_by_key: dict[str, dict[str, Any]] = {}
    by_query: dict[str, list[str]] = {}
    raw_hits = 0
    excluded_sensitive = 0
    errors: list[dict[str, str]] = []

    for query in queries:
        by_query[query] = []
        try:
            hits = finder(query, limit)
        except Exception as exc:
            errors.append({"query": query, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for record in hits:
            if not isinstance(record, dict):
                continue
            raw_hits += 1
            path = _record_path(record)
            if not path or _path_is_sensitive(path):
                excluded_sensitive += 1
                continue
            key = _record_key(record)
            if key not in sources_by_key:
                source = _record_to_source(record, query)
                sources_by_key[key] = source
            else:
                source = sources_by_key[key]
                if query not in source["query_hits"]:
                    source["query_hits"].append(query)
            by_query[query].append(source["source_id"])

    sources = sorted(
        sources_by_key.values(),
        key=lambda item: (
            str(item.get("source_root") or "").lower(),
            str(item.get("path") or "").lower(),
        ),
    )
    source_ids = {source["source_id"] for source in sources}
    cleaned_by_query: dict[str, list[str]] = {}
    for query, ids in by_query.items():
        seen_ids: set[str] = set()
        cleaned_by_query[query] = []
        for source_id in ids:
            if source_id not in source_ids or source_id in seen_ids:
                continue
            seen_ids.add(source_id)
            cleaned_by_query[query].append(source_id)
    by_query = cleaned_by_query

    capsule = {
        "ok": True,
        "capsule_kind": "source_map_anchor_capsule",
        "schema_version": "source_map_stitcher.v1",
        "created_at": _utc_now(),
        "anchor_queries": queries,
        "limit_per_query": limit,
        "counts": {
            "queries": len(queries),
            "raw_hits": raw_hits,
            "deduped_sources": len(sources),
            "excluded_sensitive": excluded_sensitive,
            "query_errors": len(errors),
        },
        "sources": sources,
        "by_query": by_query,
        "errors": errors,
        "safety": {
            "read_only": True,
            "sandbox_write": False,
            "raw_file_copy": False,
            "external_send": False,
            "git_push": False,
            "gdrive_edit": False,
            "command_exec": False,
            "computer_control": False,
            "canon_promotion": False,
            "secret_terms_excluded": True,
        },
    }

    if write:
        out_dir = capsule_dir or CAPSULE_DIR
        latest = latest_path or LATEST_CAPSULE_PATH
        out_dir.mkdir(parents=True, exist_ok=True)
        latest.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        capsule_path = out_dir / f"source_map_capsule_{stamp}.json"
        capsule["capsule_path"] = str(capsule_path)
        capsule["latest_path"] = str(latest)
        payload = json.dumps(capsule, indent=2, ensure_ascii=True)
        capsule_path.write_text(payload + "\n", encoding="utf-8")
        latest.write_text(payload + "\n", encoding="utf-8")

    return capsule


def load_latest_capsule(*, latest_path: Path | None = None) -> dict[str, Any] | None:
    path = latest_path or LATEST_CAPSULE_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_capsule_prompt_context(
    *,
    latest_path: Path | None = None,
    max_sources: int = 8,
    max_chars: int = 3000,
) -> str:
    """Render compact SourceMap context for one autonomous self-prompt seed."""
    capsule = load_latest_capsule(latest_path=latest_path)
    if not capsule:
        return ""
    counts = capsule.get("counts") or {}
    sources = list(capsule.get("sources") or [])[:max(1, max_sources)]
    lines = [
        "source_map_capsule:",
        f"  created_at: {capsule.get('created_at')}",
        f"  deduped_sources: {counts.get('deduped_sources', 0)}",
        f"  excluded_sensitive: {counts.get('excluded_sensitive', 0)}",
        "  safety: read_only=true sandbox_write=false external_send=false canon_promotion=false",
        "  anchors: " + ", ".join(capsule.get("anchor_queries") or []),
        "  selected_sources:",
    ]
    for source in sources:
        preview = source.get("content_preview") or "metadata only"
        lines.append(
            "  - "
            f"{source.get('name')} | {source.get('category')} | "
            f"{source.get('sha256_prefix')} | {source.get('path')} | preview: {preview}"
        )
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n  [source_map_context_truncated]"
    return text


def format_capsule_summary(capsule: dict[str, Any]) -> str:
    counts = capsule.get("counts") or {}
    lines = [
        "SOURCE MAP CAPSULE",
        json.dumps({
            "ok": bool(capsule.get("ok")),
            "created_at": capsule.get("created_at"),
            "deduped_sources": counts.get("deduped_sources", 0),
            "raw_hits": counts.get("raw_hits", 0),
            "excluded_sensitive": counts.get("excluded_sensitive", 0),
            "query_errors": counts.get("query_errors", 0),
            "latest_path": capsule.get("latest_path"),
            "capsule_path": capsule.get("capsule_path"),
            "safety": capsule.get("safety"),
        }, indent=2, ensure_ascii=True),
    ]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_ANCHOR_QUERIES",
    "DEFAULT_LIMIT_PER_QUERY",
    "CAPSULE_DIR",
    "LATEST_CAPSULE_PATH",
    "build_capsule",
    "load_latest_capsule",
    "latest_capsule_prompt_context",
    "format_capsule_summary",
]
