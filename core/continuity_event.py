"""Central Continuity Event Packet V1 schema and append-only ledger writer.

The ledger is a local witness record for turns accepted by the ORACLE web
runtime.  It records facts about the turn; it does not execute actions, mutate
source material, promote memory, or contact external systems.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import threading
import uuid


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = RUNTIME_ROOT / "data" / "ledger" / "events.jsonl"

AUTHORITY_STATUSES = frozenset({
    "VERIFIED",
    "UNVERIFIED",
    "DEGRADED",
    "CONFLICT",
    "SOURCE_UNAVAILABLE",
})
MEMORY_EFFECTS = frozenset({
    "NONE",
    "THREAD_APPEND",
    "LEDGER_SEAL",
    "CORRECTION_APPLIED",
})


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContinuityEventPacket:
    """Durable record tying one prompt and response to evidence and effects."""

    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=_utc_timestamp)
    source: str = "Noah.Physical"
    speaker: str = "user"
    channel: str = "localhost_7781"
    visible_context: List[str] = field(default_factory=list)
    user_intent: str = ""
    assistant_response: str = ""
    evidence_used: List[Dict[str, Any]] = field(default_factory=list)
    claims_extracted: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)
    corrections: List[Dict[str, str]] = field(default_factory=list)
    actions_proposed: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    authority_status: str = "VERIFIED"
    memory_effect: str = "NONE"
    return_pointer: Optional[str] = None

    def validate(self) -> None:
        if not self.event_id.startswith("evt_"):
            raise ValueError("event_id must start with 'evt_'")
        try:
            datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
        if self.speaker not in {"user", "assistant", "system"}:
            raise ValueError("speaker must be user, assistant, or system")
        if self.authority_status not in AUTHORITY_STATUSES:
            raise ValueError(f"unsupported authority_status: {self.authority_status}")
        if self.memory_effect not in MEMORY_EFFECTS:
            raise ValueError(f"unsupported memory_effect: {self.memory_effect}")
        for name in (
            "visible_context",
            "evidence_used",
            "claims_extracted",
            "uncertainties",
            "corrections",
            "actions_proposed",
            "actions_taken",
        ):
            if not isinstance(getattr(self, name), list):
                raise ValueError(f"{name} must be a list")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContinuityEventPacket":
        packet = cls(**data)
        packet.validate()
        return packet


class ContinuityLedgerWriter:
    """Append validated packets to the local JSONL ledger, one atomic line."""

    _write_lock = threading.Lock()

    def __init__(self, ledger_path: Path = DEFAULT_LEDGER_PATH):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def record_event(self, packet: ContinuityEventPacket) -> Path:
        if not isinstance(packet, ContinuityEventPacket):
            raise TypeError("packet must be a ContinuityEventPacket")
        packet.validate()
        line = packet.to_json() + "\n"
        with self._write_lock:
            with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        return self.ledger_path

