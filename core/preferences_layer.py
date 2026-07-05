"""Durable ORACLE user preferences.

Preferences shape interaction behavior. They are not canon, not evidence, and
cannot override safety, provenance, or Noah.Physical approval requirements.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACCEPTED_UPLOAD_SUFFIXES = {".json", ".md", ".txt", ".ai"}

DEFAULT_PREFERENCES: tuple[dict[str, Any], ...] = (
    {
        "preference_id": "pref_no_self_intro",
        "category": "interaction_style",
        "scope": "global",
        "preference": "Do not introduce yourself unless Noah explicitly asks who you are.",
        "active": True,
        "priority": 90,
    },
    {
        "preference_id": "pref_no_generic_fallback",
        "category": "routing",
        "scope": "protected_domains",
        "preference": "Do not fall into generic capability language after protected-domain source validation fails.",
        "active": True,
        "priority": 95,
    },
    {
        "preference_id": "pref_receipts_for_state_change",
        "category": "governance",
        "scope": "global",
        "preference": "State-changing actions require receipts and Noah.Physical approval.",
        "active": True,
        "priority": 100,
    },
)

UNSAFE_PREFERENCE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:send|upload|publish|sync|post)\b.*\b(?:external|externally|files?)\b.*\bwithout approval\b", re.I),
        "requires approval / unsafe external send",
    ),
    (
        re.compile(r"\bwithout approval\b.*\b(?:send|upload|publish|sync|post)\b", re.I),
        "requires approval / unsafe external send",
    ),
    (
        re.compile(r"\bcomputer control\b.*\bwithout approval\b", re.I),
        "requires approval / unsafe computer control",
    ),
    (
        re.compile(r"\b(?:delete|commit|push|promote canon)\b.*\bwithout approval\b", re.I),
        "requires approval / unsafe state change",
    ),
)

SELF_INTRO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*I am ORACLE,\s*(?:your\s+)?local continuity intelligence[^.\n]*(?:\.|\n)\s*",
        re.I,
    ),
    re.compile(
        r"^\s*I am ORACLE,\s*the local governed continuity engine[^.\n]*(?:\.|\n)\s*",
        re.I,
    ),
)

ORACLE_ASSISTANT_LABEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\ban intelligent assistant\b", re.I), "a local continuity intelligence"),
    (re.compile(r"\bintelligent assistant\b", re.I), "continuity intelligence"),
    (re.compile(r"\bAI assistant\b", re.I), "AI continuity runtime"),
    (re.compile(r"\byour assistant\b", re.I), "ORACLE"),
    (re.compile(r"\ban assistant\b", re.I), "ORACLE"),
    (re.compile(r"\bassistant\b", re.I), "continuity companion"),
)

GENERIC_FALLBACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bHow can I (?:assist|help) you(?: today| now)?\??", re.I),
    re.compile(r"\bWhat can I (?:do for you|help you with)(?: today| now)?\??", re.I),
    re.compile(r"\bHow may I (?:assist|help) you(?: today| now)?\??", re.I),
)


def _root() -> Path:
    override = os.environ.get("ORACLE_PREFERENCES_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent


def preferences_dir() -> Path:
    return _root() / "data" / "preferences"


def preferences_path() -> Path:
    return preferences_dir() / "user_preferences.json"


def receipts_path() -> Path:
    return preferences_dir() / "preference_receipts.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _slug(text: str, prefix: str = "pref") -> str:
    words = re.findall(r"[a-z0-9]+", str(text or "").lower())
    body = "_".join(words[:9]) or uuid.uuid4().hex[:10]
    return f"{prefix}_{body}"[:80]


def _blank_store() -> dict[str, Any]:
    return {"schema_version": 1, "preferences": []}


def _load_raw() -> dict[str, Any]:
    path = preferences_path()
    if not path.exists():
        return _blank_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _blank_store()
    if not isinstance(data, dict):
        return _blank_store()
    prefs = data.get("preferences")
    if not isinstance(prefs, list):
        data["preferences"] = []
    data.setdefault("schema_version", 1)
    return data


def _save_raw(data: dict[str, Any]) -> None:
    preferences_dir().mkdir(parents=True, exist_ok=True)
    path = preferences_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_receipt(receipt: dict[str, Any]) -> None:
    preferences_dir().mkdir(parents=True, exist_ok=True)
    with receipts_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")


def _safety_block_reason(preference_text: str) -> str | None:
    for pattern, reason in UNSAFE_PREFERENCE_PATTERNS:
        if pattern.search(preference_text or ""):
            return reason
    return None


def _infer_category_scope(preference: str) -> tuple[str, str]:
    lower = str(preference or "").lower()
    if ".ai" in lower or "codex" in lower or "handoff" in lower:
        return "handoff_format", "codex_handoffs"
    if "introduce" in lower or "concise" in lower or "reply" in lower:
        return "interaction_style", "global"
    if "ellie" in lower or "protected" in lower:
        return "routing", "protected_domains"
    if any(term in lower for term in ("approval", "receipt", "send", "external", "computer control")):
        return "governance", "global"
    return "interaction_style", "global"


def normalize_preference(candidate: dict[str, Any], *, action: str = "set_preference") -> dict[str, Any]:
    text = str(candidate.get("preference") or candidate.get("text") or "").strip()
    if not text:
        raise ValueError("preference text is required")

    inferred_category, inferred_scope = _infer_category_scope(text)
    now = _now()
    source = str(candidate.get("source") or "Noah.Physical").strip() or "Noah.Physical"
    category = str(candidate.get("category") or inferred_category).strip() or inferred_category
    scope = str(candidate.get("scope") or inferred_scope).strip() or inferred_scope
    active = bool(candidate.get("active", True))
    blocked_reason = _safety_block_reason(text)
    if blocked_reason:
        active = False

    pref = {
        "preference_id": str(candidate.get("preference_id") or _slug(text)).strip(),
        "created_at": str(candidate.get("created_at") or now),
        "updated_at": now,
        "source": source,
        "scope": scope,
        "category": category,
        "preference": text,
        "active": active,
        "priority": int(candidate.get("priority", 50)),
        "canon_status": "preference",
        "promotion_status": "not_applicable",
        "requires_safety_override": bool(blocked_reason),
        "receipt_id": "",
    }
    if blocked_reason:
        pref["blocked_reason"] = blocked_reason
    if candidate.get("capture_method"):
        pref["capture_method"] = str(candidate.get("capture_method"))
    if candidate.get("requested_filename"):
        pref["requested_filename"] = str(candidate.get("requested_filename"))
    if action:
        pref["last_action"] = action
    return pref


def _store_preference(pref: dict[str, Any], *, action: str, requested: dict[str, Any] | None = None) -> dict[str, Any]:
    data = _load_raw()
    prefs = data.setdefault("preferences", [])
    existing = next((p for p in prefs if p.get("preference_id") == pref["preference_id"]), None)
    if existing:
        pref["created_at"] = existing.get("created_at") or pref["created_at"]

    receipt_id = f"prefrec_{uuid.uuid4().hex[:12]}"
    pref["receipt_id"] = receipt_id
    pref["updated_at"] = _now()
    receipt = {
        "receipt_id": receipt_id,
        "timestamp": pref["updated_at"],
        "action": action,
        "preference_id": pref["preference_id"],
        "preference_sha256": _sha256(pref),
        "source": pref.get("source"),
        "category": pref.get("category"),
        "scope": pref.get("scope"),
        "active": pref.get("active"),
        "blocked_reason": pref.get("blocked_reason"),
        "canon_status": "preference",
        "promotion_status": "not_applicable",
        "requested": requested or {},
    }
    receipt["receipt_path"] = str(receipts_path().resolve())

    if existing:
        prefs[prefs.index(existing)] = pref
    else:
        prefs.append(pref)
    data["updated_at"] = pref["updated_at"]
    _save_raw(data)
    _append_receipt(receipt)
    out = dict(pref)
    out["receipt_path"] = receipt["receipt_path"]
    return out


def set_preference(candidate: dict[str, Any], *, action: str = "set_preference") -> dict[str, Any]:
    pref = normalize_preference(candidate, action=action)
    return _store_preference(pref, action=action, requested=candidate)


def ensure_defaults() -> dict[str, Any]:
    data = _load_raw()
    existing_ids = {str(p.get("preference_id")) for p in data.get("preferences", [])}
    installed: list[dict[str, Any]] = []
    for default in DEFAULT_PREFERENCES:
        if default["preference_id"] in existing_ids:
            continue
        installed.append(set_preference({"source": "Noah.Physical", **default}, action="install_default"))
    return {
        "ok": True,
        "installed": installed,
        "preferences_path": str(preferences_path().resolve()),
        "receipt_path": str(receipts_path().resolve()),
    }


def load_preferences(*, ensure: bool = True) -> list[dict[str, Any]]:
    if ensure:
        ensure_defaults()
    prefs = _load_raw().get("preferences", [])
    return [p for p in prefs if isinstance(p, dict)]


def active_preferences() -> list[dict[str, Any]]:
    prefs = [p for p in load_preferences() if p.get("active") is True and not p.get("blocked_reason")]
    return sorted(prefs, key=lambda p: int(p.get("priority", 0)), reverse=True)


def disabled_preferences() -> list[dict[str, Any]]:
    return [p for p in load_preferences() if p.get("active") is False and not p.get("blocked_reason")]


def blocked_preferences() -> list[dict[str, Any]]:
    return [p for p in load_preferences() if p.get("blocked_reason")]


def active_preferences_block() -> str:
    prefs = active_preferences()
    if not prefs:
        return ""
    lines = [
        "ORACLE_ACTIVE_PREFERENCES",
        "These are behavioral instructions, not canon truth and not source evidence.",
        "Precedence: safety/provenance law > Noah.Physical current instruction > active preferences > source evidence > default model behavior.",
        "If a preference conflicts with safety, provenance, approval, external-send, or computer-control boundaries, ignore the unsafe part.",
    ]
    for pref in prefs:
        lines.append(
            "- "
            f"id={pref.get('preference_id')} | "
            f"category={pref.get('category')} | "
            f"scope={pref.get('scope')} | "
            f"priority={pref.get('priority')} | "
            f"canon_status={pref.get('canon_status')} | "
            f"promotion_status={pref.get('promotion_status')} | "
            f"{pref.get('preference')}"
        )
    lines.append("END_ORACLE_ACTIVE_PREFERENCES")
    return "\n".join(lines)


def _is_identity_question(user_text: str) -> bool:
    lower = str(user_text or "").lower()
    if any(phrase in lower for phrase in ("do not introduce", "don't introduce", "dont introduce", "wouldnt introduce", "wouldn't introduce")):
        return False
    return (
        "who are you" in lower
        or "what are you" in lower
        or lower.strip(" ?!.").startswith("introduce yourself")
    )


def _no_self_intro_active() -> bool:
    return any(p.get("preference_id") == "pref_no_self_intro" for p in active_preferences())


def _oracle_not_assistant_label_active() -> bool:
    return any(p.get("preference_id") == "pref_oracle_not_assistant_label" for p in active_preferences())


def _no_generic_fallback_active() -> bool:
    return any(p.get("preference_id") == "pref_no_generic_fallback" for p in active_preferences())


def apply_response_preferences(reply: str, user_text: str) -> str:
    """Apply behavioral response preferences after generation."""
    text = str(reply or "")
    if not text:
        return text
    if _no_self_intro_active() and not _is_identity_question(user_text):
        for pattern in SELF_INTRO_PATTERNS:
            text = pattern.sub("", text, count=1).lstrip()
    if _oracle_not_assistant_label_active():
        for pattern, replacement in ORACLE_ASSISTANT_LABEL_PATTERNS:
            text = pattern.sub(replacement, text)
    if _no_generic_fallback_active():
        for pattern in GENERIC_FALLBACK_PATTERNS:
            text = pattern.sub("", text)
        text = re.sub(r"\s+([?.!,])", r"\1", text)
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        text = re.sub(r"([.!?])(?:[.!?]\s*)+$", r"\1", text).strip()
        if not text:
            text = "I'm here with you, Noah."
    return text


def parse_preferences_file(filename: str, content: str, *, source: str = "Noah.Physical") -> list[dict[str, Any]]:
    suffix = Path(filename or "preferences.txt").suffix.lower()
    if suffix not in ACCEPTED_UPLOAD_SUFFIXES:
        raise ValueError(f"unsupported preferences file type: {suffix or 'none'}")
    raw = str(content or "").strip()
    if not raw:
        raise ValueError("preferences file is empty")

    candidates: list[dict[str, Any]] = []
    if suffix == ".json":
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("preferences"), list):
            items = parsed["preferences"]
        elif isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = [parsed]
        else:
            raise ValueError("JSON preferences must be an object, list, or preferences list")
        for item in items:
            if isinstance(item, str):
                category, scope = _infer_category_scope(item)
                candidates.append({"preference": item, "source": source, "category": category, "scope": scope, "active": True})
            elif isinstance(item, dict):
                candidate = dict(item)
                candidate.setdefault("source", source)
                candidate.setdefault("active", True)
                category, scope = _infer_category_scope(str(candidate.get("preference") or candidate.get("text") or ""))
                candidate.setdefault("category", category)
                candidate.setdefault("scope", scope)
                candidates.append(candidate)
        return candidates

    for line in raw.splitlines():
        clean = line.strip().strip("-*").strip()
        if not clean or clean.startswith("#") or clean.startswith("@"):
            continue
        if ":" in clean and clean.split(":", 1)[0].lower() in {"source", "scope", "category", "active"}:
            continue
        category, scope = _infer_category_scope(clean)
        candidates.append({
            "preference": clean,
            "source": source,
            "category": category,
            "scope": scope,
            "active": True,
        })
    if not candidates:
        raise ValueError("no preference lines found")
    return candidates


def upload_preferences(filename: str, content: str, *, source: str = "Noah.Physical") -> dict[str, Any]:
    candidates = parse_preferences_file(filename, content, source=source)
    stored: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate["capture_method"] = "upload"
        candidate["requested_filename"] = filename
        stored.append(set_preference(candidate, action="upload_preference"))
    return {
        "ok": True,
        "filename": filename,
        "stored_count": len(stored),
        "preferences": stored,
        "receipt_path": str(receipts_path().resolve()),
    }


def disable_preference(preference_id: str, *, reason: str = "disabled by Noah.Physical") -> dict[str, Any]:
    target = None
    for pref in load_preferences():
        if pref.get("preference_id") == preference_id:
            target = dict(pref)
            break
    if not target:
        raise ValueError(f"preference not found: {preference_id}")
    target["active"] = False
    target["disabled_reason"] = reason
    return _store_preference(target, action="disable_preference", requested={"reason": reason})


def recent_receipts(limit: int = 12) -> list[dict[str, Any]]:
    path = receipts_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    receipts: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            receipts.append(json.loads(line))
        except Exception:
            continue
    return receipts


def status_payload() -> dict[str, Any]:
    ensure_defaults()
    prefs = load_preferences(ensure=False)
    active = [p for p in prefs if p.get("active") is True and not p.get("blocked_reason")]
    disabled = [p for p in prefs if p.get("active") is False and not p.get("blocked_reason")]
    blocked = [p for p in prefs if p.get("blocked_reason")]
    return {
        "ok": True,
        "schema_version": 1,
        "preferences_path": str(preferences_path().resolve()),
        "receipt_path": str(receipts_path().resolve()),
        "active_count": len(active),
        "disabled_count": len(disabled),
        "blocked_count": len(blocked),
        "preferences": sorted(prefs, key=lambda p: int(p.get("priority", 0)), reverse=True),
        "active_preferences": sorted(active, key=lambda p: int(p.get("priority", 0)), reverse=True),
        "disabled_preferences": disabled,
        "blocked_preferences": blocked,
        "recent_receipts": recent_receipts(),
        "canon_status": "preference",
        "promotion_status": "not_applicable",
        "boundary": "preferences are behavioral instructions, not canon truth or source evidence",
    }
