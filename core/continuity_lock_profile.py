"""
core/continuity_lock_profile.py — Phase 1.5 Continuity Lock Profile schema.

Represent high-value architecture CONCEPTS as labeled, non-canon, non-executing
continuity-lock candidates. This module holds speculative architecture without
confusing it with verified reality.

Hard boundaries (enforced):
  - canon_status is always False (no canon promotion here).
  - mindcoin_financial_value is always 0 (MindCoin is NOT money / not a token).
  - No execution. No external/network calls. No cryptography beyond SHA-256 of the
    local JSON record. No quantum hardware, biometric, or identity-proof claims.

Doctrine:
  Quantum Entanglement Authentication is not a runtime capability. It is a deferred
  continuity-lock candidate requiring physical evidence before activation.
  MindCoin Sigma is not money. It is internal salience accounting for witnessed
  continuity work.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Reuse the RedInk custody layout if it is importable; otherwise fall back to the
# same on-disk path so storage stays consistent.
_REDINK = None
try:
    from core import ingest_engine as _REDINK  # type: ignore
except Exception:
    try:
        import ingest_engine as _REDINK  # type: ignore
    except Exception:
        _REDINK = None

_FALLBACK_WORKSPACE = Path("./noah_exocortex").resolve()

MINDCOIN_UNIT_DEFINITION = (
    "internal non-financial salience metric for witnessed continuity work; "
    "not money, not a token, not a currency, not transferable, no external value"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ledger_dir() -> Path:
    if _REDINK is not None and hasattr(_REDINK, "LEDGER_DIR"):
        return Path(_REDINK.LEDGER_DIR)
    return _FALLBACK_WORKSPACE / ".oracle" / "ledger"


def _locks_dir() -> Path:
    return _ledger_dir() / "continuity_locks"


@dataclass
class ContinuityLockProfile:
    title: str
    summary: str = ""
    category: str = "speculative_architecture"
    source_basis: str = ""
    basis_label: str = "GENERATED_SYNTHESIS"
    verification_status: str = "UNVERIFIED"
    implementation_status: str = "DEFERRED"
    canon_status: bool = False
    mindcoin_salience_score: int = 0
    mindcoin_unit_definition: str = MINDCOIN_UNIT_DEFINITION
    mindcoin_financial_value: float = 0
    continuity_contributions: list = field(default_factory=list)
    boundary_warnings: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    required_evidence_before_activation: list = field(default_factory=list)
    related_artifact_ids: list = field(default_factory=list)
    transformation_chain: list = field(default_factory=list)
    open_holes: list = field(default_factory=list)
    notes: str = ""
    lock_id: str = field(default_factory=lambda: "LOCK-" + uuid4().hex[:12].upper())
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        # Hard invariants — cannot be overridden by callers.
        self.canon_status = False
        self.mindcoin_financial_value = 0
        self.mindcoin_unit_definition = MINDCOIN_UNIT_DEFINITION


def create_continuity_lock_profile(profile_data: dict) -> dict:
    """Validate, fill safe defaults, write the profile JSON, hash it, and (if
    RedInk is available) append a provenance receipt. Never promotes canon."""
    if not isinstance(profile_data, dict):
        raise TypeError("profile_data must be a dict")
    if not str(profile_data.get("title") or "").strip():
        raise ValueError("title is required")

    known = {f.name for f in fields(ContinuityLockProfile)}
    # Caller may not set identity/timestamps or the forced-invariant fields.
    reserved = {"lock_id", "created_at", "updated_at",
                "canon_status", "mindcoin_financial_value", "mindcoin_unit_definition"}
    kwargs = {k: v for k, v in profile_data.items() if k in known and k not in reserved}

    profile = ContinuityLockProfile(**kwargs)
    record = asdict(profile)

    locks = _locks_dir()
    locks.mkdir(parents=True, exist_ok=True)
    path = locks / f"{profile.lock_id}.json"
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")

    record_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    result = dict(record)
    result["record_sha256"] = record_sha256
    result["profile_path"] = str(path)
    result["warning"] = None

    if _REDINK is not None and hasattr(_REDINK, "append_ledger"):
        try:
            _REDINK.append_ledger({
                "receipt_id": "RCPT-" + uuid4().hex[:10].upper(),
                "receipt_type": "continuity_lock_profile_created",
                "created_at": _utc_now(),
                "basis_label": profile.basis_label,
                "lock_id": profile.lock_id,
                "lock_path": str(path),
                "record_sha256": record_sha256,
                "canon_status": False,
                "implementation_status": profile.implementation_status,
                "verification_status": profile.verification_status,
                "mindcoin_salience_score": profile.mindcoin_salience_score,
                "mindcoin_financial_value": 0,
                "summary": f"Continuity lock candidate: {profile.title}",
                "open_holes": list(profile.open_holes),
            })
        except Exception as exc:
            result["warning"] = f"RedInk ledger append failed: {type(exc).__name__}: {exc}"
    else:
        result["warning"] = ("RedInk unavailable: wrote local profile only; "
                             "no provenance receipt appended.")
    return result


def get_continuity_lock_profile(lock_id: str) -> dict | None:
    """Read-only. Returns the profile dict, or None if absent/unreadable."""
    path = _locks_dir() / f"{lock_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_continuity_lock_profiles() -> list:
    """Read-only. Returns all stored continuity-lock profiles (empty if none)."""
    locks = _locks_dir()
    if not locks.exists():
        return []
    out = []
    for p in sorted(locks.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out
