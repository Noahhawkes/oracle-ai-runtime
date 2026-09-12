"""ORACLE Reachability Broker (V1).

Lets ORACLE request bounded, receipted contact with Noah.Physical through an
approved channel. This build ships adapters only: GitHub and Email are MOCK
(no live send). Nothing here sends real email, posts to real GitHub, or touches
credentials. The point is the governed machinery: policy, dedup/coalescing,
public-safe secret guard, delivery receipts, and contact memory.

Design rules honored:
  * ORACLE is never hardwired to Gmail/SMS/web APIs — only through adapters.
  * A failing send never reports success.
  * One unresolved condition => one active attention item (no 47-message spam).
  * Public channels refuse secret content.
  * Every contact attempt becomes a durable, inspectable record.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

UNKNOWN = "UNKNOWN"

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-]{6,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ya29\.[A-Za-z0-9_\-]+"),
    re.compile(r"ANTHROPIC_API_KEY\s*[=:]\s*\S+"),
    re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def contains_secret(text: str) -> bool:
    return any(p.search(text or "") for p in _SECRET_PATTERNS)


# ── channel adapters ─────────────────────────────────────────────────────────

class ChannelAdapter:
    name = "base"
    public_safe = True

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - base
        raise NotImplementedError


class GitHubAttentionChannel(ChannelAdapter):
    """Mock of the 'ORACLE -> Noah: Attention Queue' issue-comment channel.

    In production this would append a structured comment to one dedicated issue.
    Here it only formats + returns a delivery receipt. It does NOT call gh.
    """
    name = "github"
    public_safe = True

    def __init__(self, sender: Callable[[str], dict[str, Any]] | None = None):
        self._sender = sender  # optional injected real sender; default = mock

    def format_comment(self, payload: dict[str, Any]) -> str:
        return (
            "ORACLE ATTENTION EVENT\n"
            f"TIME = {payload.get('requested_at')}\n"
            f"URGENCY = {payload.get('urgency')}\n"
            f"NEED_TYPE = {payload.get('need_type')}\n"
            f"SUMMARY = {payload.get('summary')}\n"
            f"WHY_NOAH_IS_NEEDED = {payload.get('why')}\n"
            f"WHAT_ORACLE_ALREADY_TRIED = {payload.get('tried')}\n"
            f"WHAT_HAPPENS_IF_NOAH_WAITS = {payload.get('what_if_waits')}\n"
            f"RECOMMENDED_ACTION = {payload.get('recommended_action')}\n"
            f"EVIDENCE = {', '.join(payload.get('evidence_refs') or []) or 'UNKNOWN'}\n"
        )

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = self.format_comment(payload)
        if self._sender is not None:
            result = self._sender(body)
            ok = bool(result.get("ok"))
            return {
                "ok": ok,
                "channel": self.name,
                "delivery_status": "delivered" if ok else "failed",
                "receipt": {"body_sha256": _sha256(body), **result},
            }
        # Mock delivery (no live post).
        return {
            "ok": True,
            "channel": self.name,
            "delivery_status": "delivered_mock",
            "receipt": {"mock": True, "body_sha256": _sha256(body),
                        "target": "ORACLE -> Noah: Attention Queue (issue)"},
        }


class EmailChannel(ChannelAdapter):
    """Staged mock. No safely governed outbound-email adapter is live in V1."""
    name = "email"
    public_safe = False

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = (
            f"Noah,\n\nI need you for one thing.\n\n"
            f"What happened:\n{payload.get('summary')}\n\n"
            f"Why I cannot resolve it myself:\n{payload.get('why')}\n\n"
            f"What I checked:\n{payload.get('tried')}\n\n"
            f"What I recommend:\n{payload.get('recommended_action')}\n\n"
            f"Urgency:\n{payload.get('urgency')}\n\n- ORACLE\n"
        )
        return {
            "ok": True,
            "channel": self.name,
            "delivery_status": "staged_mock",
            "receipt": {"staged": True, "body_sha256": _sha256(body),
                        "note": "email adapter is interface + mock only; no live send in V1"},
        }


# ── broker ───────────────────────────────────────────────────────────────────

class ReachabilityBroker:
    def __init__(self, store_dir: str | Path | None = None,
                 channels: dict[str, ChannelAdapter] | None = None):
        self.store_path = Path(store_dir) / "contact_memory.jsonl" if store_dir else None
        self.channels: dict[str, ChannelAdapter] = channels or {
            "github": GitHubAttentionChannel(),
            "email": EmailChannel(),
        }
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    # persistence -------------------------------------------------------------
    def _load(self) -> None:
        if not self.store_path or not self.store_path.exists():
            return
        try:
            for line in self.store_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self._records[rec["contact_id"]] = rec
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        if not self.store_path:
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("w", encoding="utf-8") as fh:
            for rec in self._records.values():
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # queries -----------------------------------------------------------------
    def register_channel(self, name: str, adapter: ChannelAdapter) -> None:
        self.channels[name] = adapter

    def list_open(self) -> list[dict[str, Any]]:
        return [r for r in self._records.values() if not r.get("resolved_at")]

    def open_for_need(self, need_key: str) -> dict[str, Any] | None:
        for r in self._records.values():
            if r.get("need_key") == need_key and not r.get("resolved_at"):
                return r
        return None

    def has_open_attention(self, need_key: str) -> bool:
        return self.open_for_need(need_key) is not None

    # main entry --------------------------------------------------------------
    def request_contact(
        self,
        *,
        need_type: str,
        summary: str,
        why: str,
        urgency: str | int = "normal",
        tried: str = "",
        what_if_waits: str = "",
        recommended_action: str = "",
        evidence_refs: list[str] | None = None,
        need_state_id: str | None = None,
        recipient: str = "Noah.Physical",
        channel: str = "github",
        need_key: str | None = None,
    ) -> dict[str, Any]:
        requested_at = _now()
        need_key = need_key or _sha256(f"{need_type}|{summary}")[:16]

        # Coalesce: one unresolved condition => one active attention item.
        existing = self.open_for_need(need_key)
        if existing:
            existing.setdefault("coalesced_count", 1)
            existing["coalesced_count"] += 1
            existing["last_seen_at"] = requested_at
            self._save()
            return {"status": "suppressed_duplicate", "contact_id": existing["contact_id"],
                    "need_key": need_key, "reason": "an open attention item already exists"}

        payload = {
            "requested_at": requested_at, "recipient": recipient, "need_type": need_type,
            "summary": summary, "why": why, "urgency": urgency, "tried": tried,
            "what_if_waits": what_if_waits, "recommended_action": recommended_action,
            "evidence_refs": evidence_refs or [],
        }
        message_blob = _stable_message(payload)
        message_hash = _sha256(message_blob)

        adapter = self.channels.get(channel)
        if adapter is None:
            rec = self._record(need_key, need_state_id, channel, message_hash, need_type,
                               urgency, requested_at, send_status="unavailable",
                               delivery_status="unavailable", receipt_ref=None)
            return {"status": "unavailable", "channel": channel, "contact_id": rec["contact_id"],
                    "reason": f"channel '{channel}' is not supported"}

        # Public-safe guard: refuse secret content on public channels.
        if adapter.public_safe and contains_secret(message_blob):
            rec = self._record(need_key, need_state_id, channel, message_hash, need_type,
                               urgency, requested_at, send_status="blocked_secret",
                               delivery_status="not_sent", receipt_ref=None)
            return {"status": "blocked_secret", "channel": channel, "contact_id": rec["contact_id"],
                    "reason": "payload contained secret-like content; refused on public-safe channel"}

        delivery = adapter.send(payload)
        ok = bool(delivery.get("ok"))
        send_status = "sent" if ok else "failed"
        rec = self._record(need_key, need_state_id, channel, message_hash, need_type,
                           urgency, requested_at,
                           send_status=send_status,
                           delivery_status=delivery.get("delivery_status", UNKNOWN),
                           receipt_ref=delivery.get("receipt"))
        return {"status": send_status, "channel": channel, "contact_id": rec["contact_id"],
                "delivery": delivery, "need_key": need_key}

    def _record(self, need_key, need_state_id, channel, message_hash, need_type, urgency,
                requested_at, *, send_status, delivery_status, receipt_ref) -> dict[str, Any]:
        contact_id = f"contact_{uuid.uuid4().hex[:12]}"
        rec = {
            "contact_id": contact_id,
            "need_key": need_key,
            "need_state_id": need_state_id or UNKNOWN,
            "requested_at": requested_at,
            "channel": channel,
            "message_hash": message_hash,
            "reason": need_type,
            "urgency": urgency,
            "send_status": send_status,
            "delivery_status": delivery_status,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_event": None,
            "receipt_ref": receipt_ref,
            "coalesced_count": 1,
        }
        # A blocked/unavailable/failed attempt is NOT an open attention item that
        # would suppress future real sends once conditions change.
        self._records[contact_id] = rec
        self._save()
        return rec

    def acknowledge(self, contact_id: str, *, at: str | None = None) -> bool:
        rec = self._records.get(contact_id)
        if not rec:
            return False
        rec["acknowledged_at"] = at or _now()
        self._save()
        return True

    def resolve(self, contact_id: str, *, resolution_event: str = "resolved", at: str | None = None) -> bool:
        rec = self._records.get(contact_id)
        if not rec:
            return False
        rec["resolved_at"] = at or _now()
        rec["resolution_event"] = resolution_event
        self._save()
        return True


def _stable_message(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
