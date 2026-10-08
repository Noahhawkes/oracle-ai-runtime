from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

AUTHORSHIP_TAGS = {
    "system_witness_trace",
    "user_submitted_text",
}

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "state" / "artifact_harvest"


class PathIsolationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _path_within_root(root: Path, candidate: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        resolved = candidate_path.resolve()
    else:
        resolved = (root_resolved / candidate_path).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PathIsolationError("path_isolation_violation") from exc
    return resolved


def _blocked_receipt(*, source_path: str, target_name: str, authorship_tag: str, reason: str) -> dict:
    envelope = "|".join((source_path, target_name, authorship_tag, reason)).encode("utf-8")
    return {
        "receipt_id": f"RCPT-{uuid4().hex[:12].upper()}",
        "receipt_type": "candidate_trace_blocked",
        "receipt_sha256": sha256_bytes(envelope),
        "status": "BLOCKED",
        "blocked_reason": reason,
        "intercepted": True,
        "authorship_tag": authorship_tag,
        "source_path": source_path,
        "target_name": target_name,
        "unknown_state": "UNKNOWN",
        "created_at": utc_now(),
    }


def ingest_candidate_trace(
    source_path: str | Path,
    target_name: str | Path,
    *,
    corpus_root: str | Path | None = None,
    authorship_tag: str = "user_submitted_text",
) -> dict:
    if authorship_tag not in AUTHORSHIP_TAGS:
        raise ValueError("authorship_tag must be system_witness_trace or user_submitted_text")

    root = Path(corpus_root) if corpus_root is not None else CORPUS_ROOT
    root = root.resolve()
    source_input = str(source_path)
    target_input = str(target_name)

    try:
        source = _path_within_root(root, source_path)
        target = _path_within_root(root, target_name)
    except PathIsolationError:
        return _blocked_receipt(
            source_path=source_input,
            target_name=target_input,
            authorship_tag=authorship_tag,
            reason="path_isolation_violation",
        )

    if not source.exists() or not source.is_file():
        return {
            "receipt_id": f"RCPT-{uuid4().hex[:12].upper()}",
            "receipt_type": "candidate_trace_unknown",
            "receipt_sha256": sha256_bytes((source_input + "|" + target_input).encode("utf-8")),
            "status": "UNKNOWN",
            "unknown_state": "UNKNOWN",
            "unknown_reason": "missing_source_file",
            "authorship_tag": authorship_tag,
            "source_path": source_input,
            "target_path": str(target),
            "created_at": utc_now(),
        }

    raw_bytes = source.read_bytes()
    receipt_sha256 = sha256_bytes(raw_bytes)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw_bytes)

    return {
        "receipt_id": f"RCPT-{uuid4().hex[:12].upper()}",
        "receipt_type": "candidate_trace_verified",
        "receipt_sha256": receipt_sha256,
        "content_sha256": receipt_sha256,
        "status": "VERIFIED",
        "unknown_state": None,
        "authorship_tag": authorship_tag,
        "source_path": str(source),
        "target_path": str(target),
        "byte_count": len(raw_bytes),
        "lossless_retention": True,
        "created_at": utc_now(),
    }
