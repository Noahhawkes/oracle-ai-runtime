"""Thread-native continuity persistence for ORACLE.

This module gives ORACLE a durable thread object without wiring it into model
inference, external connectors, sandbox writes, or canon promotion. It is a
local SQLite layer for candidate thread state, source provenance, heartbeats,
and thread-to-thread relationships.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "thread_native_continuity.v1"

CANON_CANDIDATE = "candidate"
NO_CANON_PROMOTION = "not_promoted"
NOAH_AUTHORITY = "Noah.Physical"
DEFAULT_APPROVAL_STATE = "pending_review"

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = RUNTIME_ROOT / "Memory" / "thread_native_continuity.db"


class ThreadState(str, Enum):
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    MONITORING = "MONITORING"
    STALE = "STALE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class SourceDiscipline(str, Enum):
    OBSERVED = "OBSERVED"
    SOURCED = "SOURCED"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    CORRECTED = "CORRECTED"
    UNKNOWN = "UNKNOWN"


class ThreadItemType(str, Enum):
    DECISION = "decision"
    ACTIVE_QUESTION = "active_question"
    OPEN_PROBLEM = "open_problem"
    ASSUMPTION = "assumption"
    CONFIRMED_FACT = "confirmed_fact"
    CORRECTION = "correction"
    EVIDENCE = "evidence"
    TASK = "task"
    WAITING_ON = "waiting_on"
    NEXT_ACTION = "next_action"
    LINKED_DOCUMENT = "linked_document"
    LINKED_EMAIL = "linked_email"
    LINKED_VOICE_NOTE = "linked_voice_note"
    RELATED_GIT_COMMIT = "related_git_commit"
    RELATED_ISSUE = "related_issue"


FIELD_TO_ITEM_TYPE = {
    "decisions": ThreadItemType.DECISION,
    "active_questions": ThreadItemType.ACTIVE_QUESTION,
    "open_problems": ThreadItemType.OPEN_PROBLEM,
    "assumptions": ThreadItemType.ASSUMPTION,
    "confirmed_facts": ThreadItemType.CONFIRMED_FACT,
    "corrections": ThreadItemType.CORRECTION,
    "evidence": ThreadItemType.EVIDENCE,
    "tasks": ThreadItemType.TASK,
    "waiting_on": ThreadItemType.WAITING_ON,
    "next_actions": ThreadItemType.NEXT_ACTION,
    "linked_documents": ThreadItemType.LINKED_DOCUMENT,
    "linked_emails": ThreadItemType.LINKED_EMAIL,
    "linked_voice_notes": ThreadItemType.LINKED_VOICE_NOTE,
    "related_git_commits": ThreadItemType.RELATED_GIT_COMMIT,
    "related_issues": ThreadItemType.RELATED_ISSUE,
}

ITEM_TYPE_TO_FIELD = {item_type.value: field_name for field_name, item_type in FIELD_TO_ITEM_TYPE.items()}


INGEST_PATTERN = re.compile(
    r"^\s*"
    r"(?P<label>FACT|CONFIRMED_FACT|DECISION|TASK|CORRECTION|QUESTION|ACTIVE_QUESTION|"
    r"PROBLEM|OPEN_PROBLEM|ASSUMPTION|EVIDENCE|WAITING_ON|NEXT_ACTION|DOCUMENT|"
    r"LINKED_DOCUMENT|EMAIL|LINKED_EMAIL|VOICE_NOTE|LINKED_VOICE_NOTE|GIT_COMMIT|ISSUE)"
    r"\[(?P<key>[^\]]+)\]\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

INGEST_LABEL_TO_ITEM_TYPE = {
    "FACT": ThreadItemType.CONFIRMED_FACT,
    "CONFIRMED_FACT": ThreadItemType.CONFIRMED_FACT,
    "DECISION": ThreadItemType.DECISION,
    "TASK": ThreadItemType.TASK,
    "CORRECTION": ThreadItemType.CORRECTION,
    "QUESTION": ThreadItemType.ACTIVE_QUESTION,
    "ACTIVE_QUESTION": ThreadItemType.ACTIVE_QUESTION,
    "PROBLEM": ThreadItemType.OPEN_PROBLEM,
    "OPEN_PROBLEM": ThreadItemType.OPEN_PROBLEM,
    "ASSUMPTION": ThreadItemType.ASSUMPTION,
    "EVIDENCE": ThreadItemType.EVIDENCE,
    "WAITING_ON": ThreadItemType.WAITING_ON,
    "NEXT_ACTION": ThreadItemType.NEXT_ACTION,
    "DOCUMENT": ThreadItemType.LINKED_DOCUMENT,
    "LINKED_DOCUMENT": ThreadItemType.LINKED_DOCUMENT,
    "EMAIL": ThreadItemType.LINKED_EMAIL,
    "LINKED_EMAIL": ThreadItemType.LINKED_EMAIL,
    "VOICE_NOTE": ThreadItemType.LINKED_VOICE_NOTE,
    "LINKED_VOICE_NOTE": ThreadItemType.LINKED_VOICE_NOTE,
    "GIT_COMMIT": ThreadItemType.RELATED_GIT_COMMIT,
    "ISSUE": ThreadItemType.RELATED_ISSUE,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, payload: Mapping[str, Any] | Sequence[Any] | str) -> str:
    if isinstance(payload, str):
        raw = payload
    else:
        raw = canonical_json(payload)
    return f"{prefix}_{sha256_text(raw)[:24]}"


def as_tuple(value: Iterable[str] | None) -> tuple[str, ...]:
    if not value:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return tuple(result)


def json_tuple(value: Sequence[str]) -> str:
    return canonical_json(list(as_tuple(value)))


def load_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return ()
    return as_tuple(str(item) for item in loaded)


def load_mapping(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_") or "unknown"


def combine_unique(*groups: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            text = str(item).strip()
            if text and text not in seen:
                result.append(text)
                seen.add(text)
    return tuple(result)


@dataclass(frozen=True)
class ThreadRecord:
    thread_id: str
    human_title: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    creation_date: str = ""
    last_activity: str = ""
    participants: tuple[str, ...] = field(default_factory=tuple)
    related_organizations: tuple[str, ...] = field(default_factory=tuple)
    related_projects: tuple[str, ...] = field(default_factory=tuple)
    decisions: tuple[str, ...] = field(default_factory=tuple)
    active_questions: tuple[str, ...] = field(default_factory=tuple)
    open_problems: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    confirmed_facts: tuple[str, ...] = field(default_factory=tuple)
    corrections: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)
    linked_documents: tuple[str, ...] = field(default_factory=tuple)
    linked_emails: tuple[str, ...] = field(default_factory=tuple)
    linked_voice_notes: tuple[str, ...] = field(default_factory=tuple)
    related_git_commits: tuple[str, ...] = field(default_factory=tuple)
    related_issues: tuple[str, ...] = field(default_factory=tuple)
    related_threads: tuple[str, ...] = field(default_factory=tuple)
    tasks: tuple[str, ...] = field(default_factory=tuple)
    waiting_on: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    thread_health: str = "unknown"
    confidence: float = 0.0
    provenance: Mapping[str, Any] = field(default_factory=dict)
    approval_state: str = DEFAULT_APPROVAL_STATE
    canon_status: str = CANON_CANDIDATE
    promotion_status: str = NO_CANON_PROMOTION


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    timestamp: str
    origin: str
    source_identifier: str
    sha256: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    ingestion_metadata: Mapping[str, Any] = field(default_factory=dict)
    raw_content: str = ""
    evidence_status: SourceDiscipline = SourceDiscipline.SOURCED


@dataclass(frozen=True)
class ThreadItem:
    item_id: str
    thread_id: str
    item_type: ThreadItemType
    item_key: str
    value: str
    source_id: str
    evidence_status: SourceDiscipline = SourceDiscipline.SOURCED
    confidence: float = 0.5
    status: str = CANON_CANDIDATE
    superseded_by: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class ThreadHeartbeat:
    heartbeat_id: str
    thread_id: str
    state: ThreadState
    last_meaningful_change: str
    waiting_on: tuple[str, ...] = field(default_factory=tuple)
    urgency: str = "normal"
    downstream_dependencies: tuple[str, ...] = field(default_factory=tuple)
    next_expected_event: str = ""
    confidence: float = 0.0
    generated_at: str = ""


@dataclass(frozen=True)
class ThreadEdge:
    edge_id: str
    source_thread_id: str
    target_thread_id: str
    relation: str
    evidence_source_id: str = ""
    confidence: float = 0.5
    created_at: str = ""


@dataclass(frozen=True)
class IngestionResult:
    source: SourceRecord
    thread_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    audit_event_id: str
    canon_status: str = CANON_CANDIDATE
    promotion_status: str = NO_CANON_PROMOTION


def make_source_record(
    *,
    origin: str,
    source_identifier: str,
    raw_content: str,
    timestamp: str | None = None,
    provenance: Mapping[str, Any] | None = None,
    ingestion_metadata: Mapping[str, Any] | None = None,
    evidence_status: SourceDiscipline = SourceDiscipline.SOURCED,
) -> SourceRecord:
    observed_at = timestamp or utc_now()
    source_hash = sha256_text(raw_content)
    source_id = stable_id(
        "src",
        {
            "origin": origin,
            "source_identifier": source_identifier,
            "sha256": source_hash,
            "timestamp": observed_at,
        },
    )
    return SourceRecord(
        source_id=source_id,
        timestamp=observed_at,
        origin=origin,
        source_identifier=source_identifier,
        sha256=source_hash,
        provenance=dict(provenance or {}),
        ingestion_metadata=dict(ingestion_metadata or {}),
        raw_content=raw_content,
        evidence_status=evidence_status,
    )


class ThreadStore:
    """SQLite-backed, candidate-only thread continuity store."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, *, retain_raw_content: bool = True) -> None:
        self.db_path = Path(db_path)
        self.retain_raw_content = retain_raw_content

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    human_title TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    creation_date TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    participants_json TEXT NOT NULL,
                    related_organizations_json TEXT NOT NULL,
                    related_projects_json TEXT NOT NULL,
                    thread_health TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    provenance_json TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    canon_status TEXT NOT NULL,
                    promotion_status TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_records (
                    source_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    source_identifier TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    ingestion_metadata_json TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS thread_items (
                    item_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    superseded_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(thread_id),
                    FOREIGN KEY(source_id) REFERENCES source_records(source_id)
                );

                CREATE INDEX IF NOT EXISTS idx_thread_items_thread_type
                    ON thread_items(thread_id, item_type, status);
                CREATE INDEX IF NOT EXISTS idx_thread_items_key
                    ON thread_items(thread_id, item_key);

                CREATE TABLE IF NOT EXISTS thread_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_thread_id TEXT NOT NULL,
                    target_thread_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    evidence_source_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_thread_edges_source
                    ON thread_edges(source_thread_id);
                CREATE INDEX IF NOT EXISTS idx_thread_edges_target
                    ON thread_edges(target_thread_id);

                CREATE TABLE IF NOT EXISTS heartbeats (
                    heartbeat_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    last_meaningful_change TEXT NOT NULL,
                    waiting_on_json TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    downstream_dependencies_json TEXT NOT NULL,
                    next_expected_event TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    generated_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
                );

                CREATE INDEX IF NOT EXISTS idx_heartbeats_thread_generated
                    ON heartbeats(thread_id, generated_at);

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    reversible INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    schema_version TEXT NOT NULL
                );
                """
            )

    def upsert_thread(self, record: ThreadRecord) -> ThreadRecord:
        created = record.creation_date or utc_now()
        last_activity = record.last_activity or created
        normalized = ThreadRecord(
            thread_id=record.thread_id,
            human_title=record.human_title,
            aliases=as_tuple(record.aliases),
            creation_date=created,
            last_activity=last_activity,
            participants=as_tuple(record.participants),
            related_organizations=as_tuple(record.related_organizations),
            related_projects=as_tuple(record.related_projects),
            decisions=as_tuple(record.decisions),
            active_questions=as_tuple(record.active_questions),
            open_problems=as_tuple(record.open_problems),
            assumptions=as_tuple(record.assumptions),
            confirmed_facts=as_tuple(record.confirmed_facts),
            corrections=as_tuple(record.corrections),
            evidence=as_tuple(record.evidence),
            linked_documents=as_tuple(record.linked_documents),
            linked_emails=as_tuple(record.linked_emails),
            linked_voice_notes=as_tuple(record.linked_voice_notes),
            related_git_commits=as_tuple(record.related_git_commits),
            related_issues=as_tuple(record.related_issues),
            related_threads=as_tuple(record.related_threads),
            tasks=as_tuple(record.tasks),
            waiting_on=as_tuple(record.waiting_on),
            next_actions=as_tuple(record.next_actions),
            thread_health=record.thread_health,
            confidence=record.confidence,
            provenance=dict(record.provenance),
            approval_state=record.approval_state,
            canon_status=record.canon_status,
            promotion_status=record.promotion_status,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO threads (
                    thread_id, human_title, aliases_json, creation_date, last_activity,
                    participants_json, related_organizations_json, related_projects_json,
                    thread_health, confidence, provenance_json, approval_state,
                    canon_status, promotion_status, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    human_title=excluded.human_title,
                    aliases_json=excluded.aliases_json,
                    last_activity=excluded.last_activity,
                    participants_json=excluded.participants_json,
                    related_organizations_json=excluded.related_organizations_json,
                    related_projects_json=excluded.related_projects_json,
                    thread_health=excluded.thread_health,
                    confidence=excluded.confidence,
                    provenance_json=excluded.provenance_json,
                    approval_state=excluded.approval_state,
                    canon_status=excluded.canon_status,
                    promotion_status=excluded.promotion_status,
                    schema_version=excluded.schema_version
                """,
                (
                    normalized.thread_id,
                    normalized.human_title,
                    json_tuple(normalized.aliases),
                    normalized.creation_date,
                    normalized.last_activity,
                    json_tuple(normalized.participants),
                    json_tuple(normalized.related_organizations),
                    json_tuple(normalized.related_projects),
                    normalized.thread_health,
                    float(normalized.confidence),
                    canonical_json(dict(normalized.provenance)),
                    normalized.approval_state,
                    normalized.canon_status,
                    normalized.promotion_status,
                    SCHEMA_VERSION,
                ),
            )
            for field_name, item_type in FIELD_TO_ITEM_TYPE.items():
                for value in getattr(normalized, field_name):
                    self._add_item(
                        conn,
                        thread_id=normalized.thread_id,
                        item_type=item_type,
                        item_key=normalize_key(value),
                        value=value,
                        source_id="manual_thread_record",
                        evidence_status=SourceDiscipline.PROPOSED,
                        confidence=normalized.confidence,
                        created_at=last_activity,
                    )
        return self.get_thread(normalized.thread_id) or normalized

    def get_thread(self, thread_id: str) -> ThreadRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                return None
            grouped = self._active_item_values(conn, thread_id)
            related_threads = self._related_thread_ids(conn, thread_id)
        return ThreadRecord(
            thread_id=row["thread_id"],
            human_title=row["human_title"],
            aliases=load_tuple(row["aliases_json"]),
            creation_date=row["creation_date"],
            last_activity=row["last_activity"],
            participants=load_tuple(row["participants_json"]),
            related_organizations=load_tuple(row["related_organizations_json"]),
            related_projects=load_tuple(row["related_projects_json"]),
            decisions=grouped.get("decisions", ()),
            active_questions=grouped.get("active_questions", ()),
            open_problems=grouped.get("open_problems", ()),
            assumptions=grouped.get("assumptions", ()),
            confirmed_facts=grouped.get("confirmed_facts", ()),
            corrections=grouped.get("corrections", ()),
            evidence=grouped.get("evidence", ()),
            linked_documents=grouped.get("linked_documents", ()),
            linked_emails=grouped.get("linked_emails", ()),
            linked_voice_notes=grouped.get("linked_voice_notes", ()),
            related_git_commits=grouped.get("related_git_commits", ()),
            related_issues=grouped.get("related_issues", ()),
            related_threads=related_threads,
            tasks=grouped.get("tasks", ()),
            waiting_on=grouped.get("waiting_on", ()),
            next_actions=grouped.get("next_actions", ()),
            thread_health=row["thread_health"],
            confidence=float(row["confidence"]),
            provenance=load_mapping(row["provenance_json"]),
            approval_state=row["approval_state"],
            canon_status=row["canon_status"],
            promotion_status=row["promotion_status"],
        )

    def list_threads(self) -> tuple[ThreadRecord, ...]:
        with self._connect() as conn:
            ids = [row["thread_id"] for row in conn.execute("SELECT thread_id FROM threads ORDER BY last_activity DESC, thread_id")]
        return tuple(record for thread_id in ids if (record := self.get_thread(thread_id)) is not None)

    def record_source(self, source: SourceRecord) -> SourceRecord:
        raw_content = source.raw_content if self.retain_raw_content else ""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_records (
                    source_id, timestamp, origin, source_identifier, sha256,
                    provenance_json, ingestion_metadata_json, raw_content,
                    evidence_status, stored_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO NOTHING
                """,
                (
                    source.source_id,
                    source.timestamp,
                    source.origin,
                    source.source_identifier,
                    source.sha256,
                    canonical_json(dict(source.provenance)),
                    canonical_json(dict(source.ingestion_metadata)),
                    raw_content,
                    source.evidence_status.value,
                    utc_now(),
                    SCHEMA_VERSION,
                ),
            )
        return source

    def get_source(self, source_id: str) -> SourceRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM source_records WHERE source_id = ?", (source_id,)).fetchone()
        if row is None:
            return None
        return SourceRecord(
            source_id=row["source_id"],
            timestamp=row["timestamp"],
            origin=row["origin"],
            source_identifier=row["source_identifier"],
            sha256=row["sha256"],
            provenance=load_mapping(row["provenance_json"]),
            ingestion_metadata=load_mapping(row["ingestion_metadata_json"]),
            raw_content=row["raw_content"],
            evidence_status=SourceDiscipline(row["evidence_status"]),
        )

    def ingest_source(
        self,
        source: SourceRecord,
        *,
        candidate_thread_ids: Sequence[str] | None = None,
        default_thread_title: str | None = None,
    ) -> IngestionResult:
        self.record_source(source)
        thread_ids = as_tuple(candidate_thread_ids) or self._match_thread_ids(source.raw_content)
        if not thread_ids:
            thread_id = stable_id("thread", {"origin": source.origin, "source": source.source_identifier})
            title = default_thread_title or source.source_identifier or "Untitled Thread"
            self.upsert_thread(
                ThreadRecord(
                    thread_id=thread_id,
                    human_title=title,
                    aliases=(title,),
                    creation_date=source.timestamp,
                    last_activity=source.timestamp,
                    provenance={"created_from_source": source.source_id, "authority": NOAH_AUTHORITY},
                    approval_state=DEFAULT_APPROVAL_STATE,
                    canon_status=CANON_CANDIDATE,
                    promotion_status=NO_CANON_PROMOTION,
                )
            )
            thread_ids = (thread_id,)

        item_ids: list[str] = []
        parsed = parse_thread_items(source.raw_content)
        with self._connect() as conn:
            for thread_id in thread_ids:
                if self.get_thread(thread_id) is None:
                    self.upsert_thread(
                        ThreadRecord(
                            thread_id=thread_id,
                            human_title=default_thread_title or thread_id,
                            aliases=(thread_id,),
                            creation_date=source.timestamp,
                            last_activity=source.timestamp,
                            provenance={"created_from_source": source.source_id, "authority": NOAH_AUTHORITY},
                        )
                    )
                conn.execute("UPDATE threads SET last_activity = ? WHERE thread_id = ?", (source.timestamp, thread_id))
                for item_type, item_key, value in parsed:
                    item_id = self._add_item(
                        conn,
                        thread_id=thread_id,
                        item_type=item_type,
                        item_key=item_key,
                        value=value,
                        source_id=source.source_id,
                        evidence_status=source.evidence_status,
                        confidence=_confidence_for_source(source.evidence_status),
                        created_at=source.timestamp,
                    )
                    item_ids.append(item_id)
                    if item_type == ThreadItemType.CORRECTION:
                        self._supersede_items(conn, thread_id, item_key, item_id)

            audit_event_id = stable_id(
                "audit",
                {
                    "event_type": "source_to_thread_ingestion",
                    "source_id": source.source_id,
                    "thread_ids": thread_ids,
                    "item_ids": item_ids,
                },
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO audit_events (
                    event_id, event_type, thread_id, source_id, payload_json,
                    reversible, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_event_id,
                    "source_to_thread_ingestion",
                    ",".join(thread_ids),
                    source.source_id,
                    canonical_json({"thread_ids": thread_ids, "item_ids": item_ids}),
                    1,
                    utc_now(),
                    SCHEMA_VERSION,
                ),
            )
        return IngestionResult(
            source=source,
            thread_ids=thread_ids,
            item_ids=tuple(item_ids),
            audit_event_id=audit_event_id,
        )

    def link_threads(
        self,
        source_thread_id: str,
        target_thread_id: str,
        *,
        relation: str = "related_to",
        evidence_source_id: str = "",
        confidence: float = 0.5,
        created_at: str | None = None,
    ) -> ThreadEdge:
        created = created_at or utc_now()
        edge_id = stable_id(
            "edge",
            {
                "source_thread_id": source_thread_id,
                "target_thread_id": target_thread_id,
                "relation": relation,
                "evidence_source_id": evidence_source_id,
            },
        )
        edge = ThreadEdge(
            edge_id=edge_id,
            source_thread_id=source_thread_id,
            target_thread_id=target_thread_id,
            relation=relation,
            evidence_source_id=evidence_source_id,
            confidence=confidence,
            created_at=created,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO thread_edges (
                    edge_id, source_thread_id, target_thread_id, relation,
                    evidence_source_id, confidence, created_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.edge_id,
                    edge.source_thread_id,
                    edge.target_thread_id,
                    edge.relation,
                    edge.evidence_source_id,
                    edge.confidence,
                    edge.created_at,
                    SCHEMA_VERSION,
                ),
            )
        return edge

    def generate_heartbeat(
        self,
        thread_id: str,
        *,
        state: ThreadState | None = None,
        urgency: str = "normal",
        downstream_dependencies: Sequence[str] = (),
        next_expected_event: str = "",
        confidence: float | None = None,
        generated_at: str | None = None,
    ) -> ThreadHeartbeat:
        record = self.get_thread(thread_id)
        if record is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")
        resolved_state = state or infer_thread_state(record)
        generated = generated_at or utc_now()
        next_event = next_expected_event or (record.next_actions[0] if record.next_actions else "")
        resolved_confidence = record.confidence if confidence is None else confidence
        heartbeat_id = stable_id(
            "heartbeat",
            {
                "thread_id": thread_id,
                "state": resolved_state.value,
                "last_meaningful_change": record.last_activity,
                "waiting_on": record.waiting_on,
                "urgency": urgency,
                "downstream_dependencies": list(downstream_dependencies),
                "next_expected_event": next_event,
                "generated_at": generated,
            },
        )
        heartbeat = ThreadHeartbeat(
            heartbeat_id=heartbeat_id,
            thread_id=thread_id,
            state=resolved_state,
            last_meaningful_change=record.last_activity,
            waiting_on=record.waiting_on,
            urgency=urgency,
            downstream_dependencies=as_tuple(downstream_dependencies),
            next_expected_event=next_event,
            confidence=resolved_confidence,
            generated_at=generated,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO heartbeats (
                    heartbeat_id, thread_id, state, last_meaningful_change,
                    waiting_on_json, urgency, downstream_dependencies_json,
                    next_expected_event, confidence, generated_at, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    heartbeat.heartbeat_id,
                    heartbeat.thread_id,
                    heartbeat.state.value,
                    heartbeat.last_meaningful_change,
                    json_tuple(heartbeat.waiting_on),
                    heartbeat.urgency,
                    json_tuple(heartbeat.downstream_dependencies),
                    heartbeat.next_expected_event,
                    heartbeat.confidence,
                    heartbeat.generated_at,
                    SCHEMA_VERSION,
                ),
            )
        return heartbeat

    def latest_heartbeat(self, thread_id: str) -> ThreadHeartbeat | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM heartbeats
                WHERE thread_id = ?
                ORDER BY generated_at DESC, heartbeat_id DESC
                LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        if row is None:
            return None
        return ThreadHeartbeat(
            heartbeat_id=row["heartbeat_id"],
            thread_id=row["thread_id"],
            state=ThreadState(row["state"]),
            last_meaningful_change=row["last_meaningful_change"],
            waiting_on=load_tuple(row["waiting_on_json"]),
            urgency=row["urgency"],
            downstream_dependencies=load_tuple(row["downstream_dependencies_json"]),
            next_expected_event=row["next_expected_event"],
            confidence=float(row["confidence"]),
            generated_at=row["generated_at"],
        )

    def daily_operational_briefing(self) -> dict[str, Any]:
        threads = self.list_threads()
        entries: list[dict[str, Any]] = []
        for thread in threads:
            heartbeat = self.latest_heartbeat(thread.thread_id) or self.generate_heartbeat(thread.thread_id)
            if heartbeat.state in {ThreadState.ARCHIVED, ThreadState.COMPLETED}:
                continue
            entries.append(
                {
                    "thread_id": thread.thread_id,
                    "title": thread.human_title,
                    "state": heartbeat.state.value,
                    "last_meaningful_change": heartbeat.last_meaningful_change,
                    "waiting_on": heartbeat.waiting_on,
                    "next_expected_event": heartbeat.next_expected_event,
                    "confidence": heartbeat.confidence,
                    "approval_state": thread.approval_state,
                    "canon_status": thread.canon_status,
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "thread_count": len(threads),
            "active_entries": entries,
            "canon_promoted": False,
            "external_action_performed": False,
        }

    def _match_thread_ids(self, raw_content: str) -> tuple[str, ...]:
        needle = raw_content.lower()
        matches: list[str] = []
        for thread in self.list_threads():
            terms = (thread.human_title, *thread.aliases)
            if any(term and term.lower() in needle for term in terms):
                matches.append(thread.thread_id)
        return tuple(matches)

    def _active_item_values(self, conn: sqlite3.Connection, thread_id: str) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {field_name: [] for field_name in FIELD_TO_ITEM_TYPE}
        rows = conn.execute(
            """
            SELECT item_type, value FROM thread_items
            WHERE thread_id = ? AND superseded_by = ''
            ORDER BY created_at, item_id
            """,
            (thread_id,),
        ).fetchall()
        for row in rows:
            field_name = ITEM_TYPE_TO_FIELD.get(row["item_type"])
            if field_name:
                grouped[field_name].append(row["value"])
        return {field_name: as_tuple(values) for field_name, values in grouped.items()}

    def _related_thread_ids(self, conn: sqlite3.Connection, thread_id: str) -> tuple[str, ...]:
        rows = conn.execute(
            """
            SELECT target_thread_id AS related FROM thread_edges WHERE source_thread_id = ?
            UNION
            SELECT source_thread_id AS related FROM thread_edges WHERE target_thread_id = ?
            ORDER BY related
            """,
            (thread_id, thread_id),
        ).fetchall()
        return as_tuple(row["related"] for row in rows)

    def _add_item(
        self,
        conn: sqlite3.Connection,
        *,
        thread_id: str,
        item_type: ThreadItemType,
        item_key: str,
        value: str,
        source_id: str,
        evidence_status: SourceDiscipline,
        confidence: float,
        created_at: str,
    ) -> str:
        item_id = stable_id(
            "item",
            {
                "thread_id": thread_id,
                "item_type": item_type.value,
                "item_key": item_key,
                "value": value,
                "source_id": source_id,
            },
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO thread_items (
                item_id, thread_id, item_type, item_key, value, source_id,
                evidence_status, confidence, status, superseded_by, created_at,
                schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                thread_id,
                item_type.value,
                item_key,
                value,
                source_id,
                evidence_status.value,
                confidence,
                CANON_CANDIDATE,
                "",
                created_at,
                SCHEMA_VERSION,
            ),
        )
        return item_id

    def _supersede_items(self, conn: sqlite3.Connection, thread_id: str, item_key: str, superseded_by: str) -> None:
        conn.execute(
            """
            UPDATE thread_items
            SET superseded_by = ?
            WHERE thread_id = ?
              AND item_key = ?
              AND item_id != ?
              AND superseded_by = ''
              AND item_type != ?
            """,
            (superseded_by, thread_id, item_key, superseded_by, ThreadItemType.CORRECTION.value),
        )


def parse_thread_items(raw_content: str) -> tuple[tuple[ThreadItemType, str, str], ...]:
    parsed: list[tuple[ThreadItemType, str, str]] = []
    for match in INGEST_PATTERN.finditer(raw_content or ""):
        label = match.group("label").upper()
        item_type = INGEST_LABEL_TO_ITEM_TYPE[label]
        item_key = normalize_key(match.group("key"))
        value = match.group("value").strip()
        parsed.append((item_type, item_key, value))
    return tuple(parsed)


def infer_thread_state(record: ThreadRecord) -> ThreadState:
    health = record.thread_health.strip().lower()
    if health in {"archived", "complete", "completed"}:
        return ThreadState.ARCHIVED if health == "archived" else ThreadState.COMPLETED
    if record.open_problems:
        return ThreadState.BLOCKED
    if record.waiting_on:
        return ThreadState.WAITING
    if record.next_actions or record.tasks:
        return ThreadState.ACTIVE
    return ThreadState.MONITORING


def _confidence_for_source(evidence_status: SourceDiscipline) -> float:
    if evidence_status in {SourceDiscipline.OBSERVED, SourceDiscipline.SOURCED, SourceDiscipline.CORRECTED}:
        return 0.8
    if evidence_status == SourceDiscipline.PROPOSED:
        return 0.55
    if evidence_status == SourceDiscipline.INFERRED:
        return 0.35
    return 0.1


__all__ = [
    "CANON_CANDIDATE",
    "DEFAULT_DB_PATH",
    "DEFAULT_APPROVAL_STATE",
    "IngestionResult",
    "NO_CANON_PROMOTION",
    "NOAH_AUTHORITY",
    "SCHEMA_VERSION",
    "SourceDiscipline",
    "SourceRecord",
    "ThreadEdge",
    "ThreadHeartbeat",
    "ThreadItem",
    "ThreadItemType",
    "ThreadRecord",
    "ThreadState",
    "ThreadStore",
    "infer_thread_state",
    "make_source_record",
    "parse_thread_items",
]
