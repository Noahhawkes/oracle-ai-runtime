"""Governed read-only local file recall for ORACLE.

Gives ORACLE's front-end talk lane real read-only access to Noah's local PC
files, documents, and folders: search, list, metadata read, supported text/docx
preview, and automatic conversation grounding. Every operation appends a receipt
to Memory/file_recall_receipts.jsonl.

Boundary: READ ONLY. No write, no delete, no move, no rename, no upload, no
external send, no execution, no Git/Drive mutation, no canon promotion. Secret
material is not auto-ingested or copied into receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIR = RUNTIME_ROOT / "Memory"
RECEIPT_FILE = MEMORY_DIR / "file_recall_receipts.jsonl"

HOME = Path.home()

# Fallback roots if the durable full-PC read-only grant module is unavailable.
# Order matters: earlier roots are searched first.
_BASE_DEFAULT_ROOTS = [
    RUNTIME_ROOT,
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Downloads",
    Path(r"G:\My Drive"),
]
DEFAULT_ROOTS = list(_BASE_DEFAULT_ROOTS)

# Content search only runs on fast local roots; Drive File Stream roots are
# filename-search only so recall never bulk-downloads cloud content.
FILENAME_ONLY_ROOTS = {str(Path(r"G:\My Drive")).lower(), str(Path("G:\\")).lower()}

TEXT_EXTS = {
    ".md", ".txt", ".json", ".jsonl", ".ai", ".py", ".html", ".css", ".js",
    ".yaml", ".yml", ".csv", ".log", ".xml", ".ini", ".cfg", ".toml", ".bat",
    ".ps1",
}
DOCX_EXTS = {".docx"}
READABLE_EXTS = TEXT_EXTS | DOCX_EXTS

# Hard blocks: credential and secret material, plus noise directories.
SENSITIVE_DIR_NAMES = {
    ".ssh", ".aws", ".gnupg", ".gpg", ".azure", ".docker", ".kube",
    "obs_captures",  # held a live OAuth token historically
    "credentials", "secrets",
}
NOISE_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", "sandbox.trash"}
BLOCKED_DIR_NAMES = SENSITIVE_DIR_NAMES | NOISE_DIR_NAMES
BLOCKED_NAME_PATTERNS = re.compile(
    r"(id_rsa|id_ed25519|\.pem$|\.key$|\.pfx$|\.p12$|\.keystore$|"
    r"credential|secret|password|passwd|api[_-]?key|token|\.env$|oauth)",
    re.IGNORECASE,
)
BLOCKED_PATH_PATTERNS = re.compile(
    r"\\windows\\system32\\config\\(sam|security|software|system|default)$",
    re.IGNORECASE,
)
MAX_FILE_BYTES = 2_000_000
MAX_TEXT_CHARS = 8000
MAX_SEARCH_FILES = 40_000       # walk cap per search
MAX_CONTENT_GREP_FILES = 400    # content-inspection cap per search
DEFAULT_RESULT_LIMIT = 8


class FileRecallError(ValueError):
    """Raised when file recall would violate the read-only or secret boundary."""


@dataclass
class FileHit:
    path: str
    name: str
    kind: str          # filename_match | content_match
    size: int
    modified: str
    snippet: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _default_roots_overridden() -> bool:
    return [str(r) for r in DEFAULT_ROOTS] != [str(r) for r in _BASE_DEFAULT_ROOTS]


def allowed_roots() -> list[Path]:
    roots: list[Path] = []
    if not _default_roots_overridden():
        try:
            from readonly_access import discovered_read_roots

            roots.extend(discovered_read_roots())
        except Exception:
            pass
    roots.extend(DEFAULT_ROOTS)

    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
            key = str(resolved).lower()
            if key in seen or not resolved.exists():
                continue
            seen.add(key)
            out.append(resolved)
        except Exception:
            continue
    return out


def _is_blocked(path: Path) -> bool:
    parts_lower = {p.lower() for p in path.parts}
    if parts_lower & BLOCKED_DIR_NAMES:
        return True
    if BLOCKED_PATH_PATTERNS.search(str(path)):
        return True
    return bool(BLOCKED_NAME_PATTERNS.search(path.name))


def secret_risk_reason(path: Path) -> str | None:
    """Classify credential-risk paths without reading content."""

    parts_lower = {p.lower() for p in path.parts}
    sensitive_dirs = sorted(parts_lower & SENSITIVE_DIR_NAMES)
    if sensitive_dirs:
        return f"sensitive directory: {sensitive_dirs[0]}"
    if BLOCKED_PATH_PATTERNS.search(str(path)):
        return "protected Windows credential hive"
    if BLOCKED_NAME_PATTERNS.search(path.name):
        return "sensitive filename pattern"
    return None


def _inside_allowed_root(path: Path) -> bool:
    resolved = path.resolve()
    for root in allowed_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def validate_readable_path(path_text: str) -> Path:
    value = str(path_text or "").strip().strip('"')
    if not value:
        raise FileRecallError("path is required")
    path = Path(value)
    if not path.is_absolute():
        path = RUNTIME_ROOT / path
    if not _inside_allowed_root(path):
        raise FileRecallError("path is outside ORACLE's read-only granted roots")
    if _is_blocked(path):
        raise FileRecallError("path is blocked by the secret/credential boundary")
    if not path.exists():
        raise FileRecallError("path does not exist")
    if not path.is_file():
        raise FileRecallError("path is not a file (folders: use search)")
    return path


def _write_receipt(payload: dict[str, Any]) -> str:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "receipt_kind": "file_recall_receipt",
        "schema_version": "file_recall.v1",
        "timestamp": _now(),
        "boundary": {
            "read_only": True,
            "write": False,
            "delete": False,
            "upload": False,
            "external_send": False,
            "canon_promotion": False,
            "secret_paths_blocked": True,
        },
        **payload,
    }
    receipt["receipt_hash_sha256"] = _sha256_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
    with RECEIPT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")
    return str(RECEIPT_FILE)


def _read_docx_text(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:
        return ""
    # paragraph boundaries become spaces; tags stripped
    xml = re.sub(r"</w:p>", " \n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return _clean_text(text)[:max_chars]


def _read_text_file(path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    try:
        raw = path.read_bytes()[:MAX_FILE_BYTES]
    except OSError:
        return ""
    return _clean_text(raw.decode("utf-8", errors="replace"))[:max_chars]


def read_file(path_text: str, *, write_receipt: bool = True) -> dict[str, Any]:
    path = validate_readable_path(path_text)
    ext = path.suffix.lower()
    if ext in DOCX_EXTS:
        text = _read_docx_text(path)
    elif ext in TEXT_EXTS:
        text = _read_text_file(path)
    else:
        raise FileRecallError(f"unsupported file type for recall: {ext or 'no extension'}")
    st = path.stat()
    response = {
        "ok": True,
        "operation_type": "file_recall_read",
        "path": str(path),
        "name": path.name,
        "size": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "text_preview": text,
        "truncated": st.st_size > MAX_FILE_BYTES or len(text) >= MAX_TEXT_CHARS,
        "fetched_at": _now(),
        "boundary": {"read_only": True, "write": False, "external_send": False, "canon_promotion": False},
    }
    if write_receipt:
        response["receipt_path"] = _write_receipt({
            "operation_type": "file_recall_read",
            "path": str(path),
            "size": st.st_size,
            "text_sha256": _sha256_text(text),
        })
    return response


def _iter_candidate_files(roots: list[Path]):
    seen = 0
    for root in roots:
        root_str = str(root).lower()
        filename_only = root_str in FILENAME_ONLY_ROOTS
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [d for d in dirnames if d.lower() not in BLOCKED_DIR_NAMES]
            for fname in filenames:
                seen += 1
                if seen > MAX_SEARCH_FILES:
                    return
                p = Path(dirpath) / fname
                if BLOCKED_NAME_PATTERNS.search(fname):
                    continue
                yield p, filename_only


def _iter_sensitive_candidate_files(roots: list[Path]):
    seen = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            # Keep sensitive directories visible for metadata inventory; skip only
            # high-volume implementation/noise folders.
            dirnames[:] = [d for d in dirnames if d.lower() not in NOISE_DIR_NAMES]
            current_dir = Path(dirpath)
            dir_reason = secret_risk_reason(current_dir)
            for fname in filenames:
                seen += 1
                if seen > MAX_SEARCH_FILES:
                    return
                p = current_dir / fname
                reason = secret_risk_reason(p) or dir_reason
                if reason:
                    yield p, reason


def search(query: str, *, limit: int = DEFAULT_RESULT_LIMIT, write_receipt: bool = True,
           deep: bool = True) -> dict[str, Any]:
    q = _clean_text(str(query or ""))
    if not q:
        raise FileRecallError("query is required")
    terms = [t.lower() for t in q.split() if len(t) > 1]
    if not terms:
        raise FileRecallError("query has no usable terms")
    bounded_limit = max(1, min(int(limit or DEFAULT_RESULT_LIMIT), 25))

    name_hits: list[FileHit] = []
    content_candidates: list[Path] = []
    for p, filename_only in _iter_candidate_files(allowed_roots()):
        name_l = p.name.lower()
        path_l = str(p).lower()
        if all(t in path_l for t in terms) or all(t in name_l for t in terms):
            try:
                st = p.stat()
            except OSError:
                continue
            name_hits.append(FileHit(
                path=str(p), name=p.name, kind="filename_match", size=st.st_size,
                modified=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            ))
        elif (not filename_only and p.suffix.lower() in TEXT_EXTS
              and any(t in name_l for t in terms)):
            content_candidates.append(p)
        if len(name_hits) >= bounded_limit * 3:
            break

    # newest first — Noah's current work surfaces on top
    name_hits.sort(key=lambda h: h.modified, reverse=True)
    results = name_hits[:bounded_limit]

    # content grep pass only if filename matching found nothing; deep pass
    # walks fast local roots only (never cloud/File Stream roots)
    if not results and deep:
        local_roots = [r for r in allowed_roots() if str(r).lower() not in FILENAME_ONLY_ROOTS]
        inspected = 0
        for p, filename_only in _iter_candidate_files(local_roots):
            if filename_only or p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            inspected += 1
            if inspected > MAX_CONTENT_GREP_FILES:
                break
            text = _read_text_file(p, max_chars=200_000)
            text_l = text.lower()
            if all(t in text_l for t in terms):
                idx = text_l.find(terms[0])
                snippet = _clean_text(text[max(0, idx - 80): idx + 160])
                st = p.stat()
                results.append(FileHit(
                    path=str(p), name=p.name, kind="content_match", size=st.st_size,
                    modified=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                    snippet=snippet,
                ))
                if len(results) >= bounded_limit:
                    break

    response = {
        "ok": True,
        "operation_type": "file_recall_search",
        "query": q,
        "result_count": len(results),
        "results": [asdict(r) for r in results],
        "roots_searched": [str(r) for r in allowed_roots()],
        "fetched_at": _now(),
        "boundary": {"read_only": True, "write": False, "external_send": False, "canon_promotion": False},
    }
    if write_receipt:
        response["receipt_path"] = _write_receipt({
            "operation_type": "file_recall_search",
            "query_preview": q,
            "result_count": len(results),
            "paths": [r["path"] for r in response["results"]],
        })
    return response


def sensitive_inventory(
    query: str = "",
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Inventory credential-risk paths by metadata only.

    This is the owner-sovereign recall posture: ORACLE may know that sensitive
    artifacts exist and where they are, while ordinary recall still refuses to
    read, prompt-inject, receipt, or externally send raw secret values.
    """

    q = _clean_text(str(query or ""))
    terms = [t.lower() for t in q.split() if len(t) > 1]
    bounded_limit = max(1, min(int(limit or DEFAULT_RESULT_LIMIT), 50))
    results: list[dict[str, Any]] = []

    for p, reason in _iter_sensitive_candidate_files(allowed_roots()):
        path_l = str(p).lower()
        if terms and not all(term in path_l for term in terms):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        results.append({
            "path": str(p),
            "name": p.name,
            "risk_reason": reason,
            "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            "content_available": False,
            "recall_mode": "metadata_only",
        })
        if len(results) >= bounded_limit:
            break

    response = {
        "ok": True,
        "operation_type": "file_recall_sensitive_inventory",
        "query": q,
        "result_count": len(results),
        "results": results,
        "roots_searched": [str(r) for r in allowed_roots()],
        "fetched_at": _now(),
        "owner_privacy_boundary": (
            "Noah.Physical controls privacy settings; sensitive files are metadata-only here. "
            "Raw values are not read, auto-ingested, prompt-injected, copied to receipts, or sent externally."
        ),
        "boundary": {
            "read_only": True,
            "metadata_only": True,
            "raw_secret_read": False,
            "raw_secret_prompt_injection": False,
            "raw_secret_receipt": False,
            "write": False,
            "external_send": False,
            "canon_promotion": False,
        },
    }
    if write_receipt:
        response["receipt_path"] = _write_receipt({
            "operation_type": "file_recall_sensitive_inventory",
            "query_preview": q,
            "result_count": len(results),
            "secret_content_stored": False,
            "paths": [
                {"path": item["path"], "risk_reason": item["risk_reason"]}
                for item in results
            ],
        })
    return response


def parse_file_request(text: str) -> dict[str, str] | None:
    raw = str(text or "").strip()
    lower = raw.lower()
    if not raw:
        return None
    sensitive_exact = (
        "/sensitive-inventory",
        "/file-sensitive-inventory",
        "inventory sensitive files",
        "show sensitive file inventory",
        "show credential inventory",
    )
    if lower in sensitive_exact:
        return {"mode": "sensitive_inventory", "value": ""}
    sensitive_prefixes = (
        "/sensitive-inventory ",
        "/file-sensitive-inventory ",
        "inventory sensitive files for ",
        "show sensitive file inventory for ",
        "show credential inventory for ",
    )
    for prefix in sensitive_prefixes:
        if lower.startswith(prefix):
            return {"mode": "sensitive_inventory", "value": raw[len(prefix):].strip()}
    read_prefixes = ("/file-read ", "/read-file ", "read file ", "read the file ", "open file ", "show me the file ")
    for prefix in read_prefixes:
        if lower.startswith(prefix):
            return {"mode": "read", "value": raw[len(prefix):].strip()}
    search_prefixes = (
        "/file-search ", "/find-file ", "search my files for ", "search my documents for ",
        "search my drive for ", "find file ", "find the file ", "find my file ",
        "look in my files for ", "search files for ",
    )
    for prefix in search_prefixes:
        if lower.startswith(prefix):
            return {"mode": "search", "value": raw[len(prefix):].strip()}
    return None


_FILE_TALK_HINTS = re.compile(
    r"\b(my (files?|documents?|folders?|notes?|drive|novels?|stories|manuscripts?)|"
    r"that (file|document|doc|folder)|the file|\.md\b|\.docx\b|\.txt\b|\.json\b|"
    r"in my (repo|runtime|sandbox|workbench))\b",
    re.IGNORECASE,
)


def context_block(user_text: str, *, max_chars: int = 1400) -> str:
    """Automatic grounding: when Noah's message references his files, return a
    compact block of matching files (+tiny previews) for the talk-lane prompt.
    Returns '' when the message doesn't look file-referential. Read-only."""
    text = str(user_text or "")
    if not _FILE_TALK_HINTS.search(text):
        return ""
    words = [w for w in re.findall(r"[A-Za-z0-9_\-]{3,}", text)
             if w.lower() not in {
                 "the", "and", "for", "with", "that", "this", "file", "files",
                 "document", "documents", "folder", "folders", "read", "open",
                 "show", "find", "search", "look", "what", "about", "have",
                 "you", "your", "her", "she", "can", "does", "all", "any",
                 "say", "says", "tell", "know", "when", "where", "how", "why",
                 "our", "his", "hers", "them", "was", "are", "will",
             }]
    if not words:
        return ""
    try:
        # deep=False keeps auto-grounding fast (filename recall only, no
        # content scan) so conversation never lags waiting on a disk walk
        result = search(" ".join(words[:4]), limit=5, write_receipt=True, deep=False)
    except Exception:
        return ""
    hits = result.get("results") or []
    if not hits:
        return ""
    lines = ["[FILE_RECALL - real files matching what Noah mentioned; read-only granted; cite paths when you use them]"]
    for h in hits:
        lines.append(f"- {h['name']}  ({h['path']}, modified {h['modified'][:10]})")
        if h.get("snippet"):
            lines.append(f"    {h['snippet'][:180]}")
    block = "\n".join(lines)
    return block[:max_chars]


def format_recall(result: dict[str, Any]) -> str:
    boundary = "boundary: full-PC read-only local recall, no write, no delete, no move, no rename, no upload, no external send, no execution, no canon promotion"
    if result.get("operation_type") == "file_recall_sensitive_inventory":
        lines = [
            "SENSITIVE FILE INVENTORY",
            boundary,
            "secret_boundary: metadata only; raw values not read, not prompt-injected, not stored in receipts",
            f"query: {result.get('query') or '(none)'}",
            f"result_count: {result.get('result_count', 0)}",
        ]
        for idx, item in enumerate(result.get("results") or [], start=1):
            lines.append(f"{idx}. {item.get('name')}  [{item.get('risk_reason')}]")
            lines.append(f"   {item.get('path')}")
            lines.append(f"   size: {item.get('size')} bytes | modified: {item.get('modified')}")
        if not result.get("results"):
            lines.append("no_results: no credential-risk paths matched inside the read-only granted roots")
        if result.get("receipt_path"):
            lines.append(f"\nreceipt_path: {result['receipt_path']}")
        return "\n".join(lines)

    if result.get("operation_type") == "file_recall_read":
        lines = [
            "FILE RECALL READ",
            boundary,
            f"path: {result.get('path')}",
            f"size: {result.get('size')} bytes | modified: {result.get('modified')}",
        ]
        if result.get("text_preview"):
            lines.append("")
            lines.append(str(result["text_preview"])[:2400])
        if result.get("truncated"):
            lines.append("\n[preview truncated — ask for a specific section]")
        if result.get("receipt_path"):
            lines.append(f"\nreceipt_path: {result['receipt_path']}")
        return "\n".join(lines)

    lines = [
        "FILE RECALL SEARCH",
        boundary,
        f"query: {result.get('query')}",
        f"result_count: {result.get('result_count', 0)}",
    ]
    for idx, item in enumerate(result.get("results") or [], start=1):
        lines.append(f"{idx}. {item.get('name')}  [{item.get('kind')}]")
        lines.append(f"   {item.get('path')}")
        if item.get("snippet"):
            lines.append(f"   {item.get('snippet')}")
    if not result.get("results"):
        lines.append("no_results: no readable files matched inside the read-only granted roots")
    if result.get("receipt_path"):
        lines.append(f"\nreceipt_path: {result['receipt_path']}")
    return "\n".join(lines)


def self_check() -> dict[str, Any]:
    try:
        from readonly_access import status_payload

        grant = status_payload(ensure=True)
    except Exception as exc:
        grant = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "module": "file_recall",
        "allowed_roots": [str(r) for r in allowed_roots()],
        "receipt_file": str(RECEIPT_FILE),
        "read_access_grant": grant,
        "sensitive_inventory": "available; metadata only; no raw secret read or receipt storage",
        "boundary": "full-PC read-only; secret material not auto-ingested; no write/delete/move/rename/upload/send/execute",
    }
