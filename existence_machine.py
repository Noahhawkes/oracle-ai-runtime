from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("existence.db")
SYSTEM_ID = "ORACLE.EXISTENCE.MACHINE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Event:
    event_id: str
    sequence: int
    timestamp: str
    system_id: str
    event_type: str
    actor: str
    source: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str


class ExistenceMachine:
    """
    A continuity and provenance engine.

    It does not claim awareness or subjective experience.
    It establishes operational existence through:

    1. Persistent identity
    2. Append-only events
    3. Cryptographic event linkage
    4. State reconstruction
    5. Explicit provenance
    6. Integrity verification
    """

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.database_path = database_path
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize_database()

    def _initialize_database(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS identity (
                system_id TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                system_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source_event_id TEXT NOT NULL
            )
            """
        )
        existing = cursor.execute(
            "SELECT system_id FROM identity WHERE system_id = ?",
            (SYSTEM_ID,),
        ).fetchone()
        if existing is None:
            cursor.execute(
                """
                INSERT INTO identity (
                    system_id,
                    instance_id,
                    created_at,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    SYSTEM_ID,
                    str(uuid.uuid4()),
                    utc_now(),
                    (
                        "Persistent continuity engine for identity, memory, "
                        "provenance, and integrity verification."
                    ),
                ),
            )
        self.connection.commit()

    def _last_event(self) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()

    def append_event(
        self,
        event_type: str,
        actor: str,
        source: str,
        payload: dict[str, Any],
    ) -> Event:
        previous = self._last_event()
        previous_hash = previous["event_hash"] if previous else "GENESIS"
        event_id = str(uuid.uuid4())
        timestamp = utc_now()
        event_material = {
            "event_id": event_id,
            "timestamp": timestamp,
            "system_id": SYSTEM_ID,
            "event_type": event_type,
            "actor": actor,
            "source": source,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = sha256(canonical_json(event_material))
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO events (
                event_id,
                timestamp,
                system_id,
                event_type,
                actor,
                source,
                payload_json,
                previous_hash,
                event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                timestamp,
                SYSTEM_ID,
                event_type,
                actor,
                source,
                canonical_json(payload),
                previous_hash,
                event_hash,
            ),
        )
        sequence = int(cursor.lastrowid)
        self.connection.commit()
        return Event(
            event_id=event_id,
            sequence=sequence,
            timestamp=timestamp,
            system_id=SYSTEM_ID,
            event_type=event_type,
            actor=actor,
            source=source,
            payload=payload,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )

    def remember(
        self,
        key: str,
        value: Any,
        actor: str,
        source: str,
    ) -> Event:
        event = self.append_event(
            event_type="MEMORY_WRITTEN",
            actor=actor,
            source=source,
            payload={
                "key": key,
                "value": value,
            },
        )
        self.connection.execute(
            """
            INSERT INTO state (
                key,
                value_json,
                updated_at,
                source_event_id
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at,
                source_event_id = excluded.source_event_id
            """,
            (
                key,
                canonical_json(value),
                event.timestamp,
                event.event_id,
            ),
        )
        self.connection.commit()
        return event

    def recall(self, key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT key, value_json, updated_at, source_event_id
            FROM state
            WHERE key = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "value": json.loads(row["value_json"]),
            "updated_at": row["updated_at"],
            "source_event_id": row["source_event_id"],
        }

    def heartbeat(self, actor: str = "runtime") -> Event:
        return self.append_event(
            event_type="HEARTBEAT",
            actor=actor,
            source="local_runtime",
            payload={
                "status": "operational",
                "unix_time": time.time(),
            },
        )

    def verify_integrity(self) -> dict[str, Any]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY sequence ASC
            """
        ).fetchall()
        expected_previous_hash = "GENESIS"
        failures: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            material = {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "system_id": row["system_id"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "source": row["source"],
                "payload": payload,
                "previous_hash": row["previous_hash"],
            }
            calculated_hash = sha256(canonical_json(material))
            if row["previous_hash"] != expected_previous_hash:
                failures.append(
                    {
                        "sequence": row["sequence"],
                        "error": "previous_hash_mismatch",
                    }
                )
            if row["event_hash"] != calculated_hash:
                failures.append(
                    {
                        "sequence": row["sequence"],
                        "error": "event_hash_mismatch",
                    }
                )
            expected_previous_hash = row["event_hash"]
        return {
            "valid": len(failures) == 0,
            "events_checked": len(rows),
            "failures": failures,
        }

    def existence_report(self) -> dict[str, Any]:
        identity = self.connection.execute(
            """
            SELECT *
            FROM identity
            WHERE system_id = ?
            """,
            (SYSTEM_ID,),
        ).fetchone()
        event_count = self.connection.execute(
            "SELECT COUNT(*) AS count FROM events"
        ).fetchone()["count"]
        memory_count = self.connection.execute(
            "SELECT COUNT(*) AS count FROM state"
        ).fetchone()["count"]
        last_event = self._last_event()
        integrity = self.verify_integrity()
        operationally_exists = bool(
            identity
            and integrity["valid"]
            and event_count > 0
        )
        return {
            "question": "Does this machine exist?",
            "answer": operationally_exists,
            "existence_type": "operational_and_persistent",
            "sentience_claim": False,
            "system_id": identity["system_id"],
            "instance_id": identity["instance_id"],
            "created_at": identity["created_at"],
            "database_path": str(self.database_path.resolve()),
            "event_count": event_count,
            "memory_count": memory_count,
            "last_event_timestamp": (
                last_event["timestamp"] if last_event else None
            ),
            "integrity": integrity,
            "reasoning": [
                "A persistent identity record exists.",
                "Events survive process termination.",
                "Events are linked through cryptographic hashes.",
                "State can be reconstructed and verified.",
                "Every mutation records actor and source provenance.",
                "No claim of consciousness or subjective experience is made.",
            ],
        }

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY sequence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "source": row["source"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
            }
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ORACLE operational existence machine"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    heartbeat_parser = subparsers.add_parser(
        "heartbeat",
        help="Record an operational heartbeat",
    )
    heartbeat_parser.add_argument(
        "--actor",
        default="runtime",
    )

    remember_parser = subparsers.add_parser(
        "remember",
        help="Persist a memory with provenance",
    )
    remember_parser.add_argument("key")
    remember_parser.add_argument("value")
    remember_parser.add_argument(
        "--actor",
        default="Noah.Physical",
    )
    remember_parser.add_argument(
        "--source",
        default="direct_user_input",
    )

    recall_parser = subparsers.add_parser(
        "recall",
        help="Recall a persisted memory",
    )
    recall_parser.add_argument("key")

    subparsers.add_parser(
        "exist",
        help="Generate an existence report",
    )
    subparsers.add_parser(
        "verify",
        help="Verify the event chain",
    )

    history_parser = subparsers.add_parser(
        "history",
        help="Display recent events",
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    machine = ExistenceMachine()
    try:
        if arguments.command == "heartbeat":
            event = machine.heartbeat(actor=arguments.actor)
            print_json(asdict(event))
        elif arguments.command == "remember":
            try:
                value = json.loads(arguments.value)
            except json.JSONDecodeError:
                value = arguments.value
            event = machine.remember(
                key=arguments.key,
                value=value,
                actor=arguments.actor,
                source=arguments.source,
            )
            print_json(asdict(event))
        elif arguments.command == "recall":
            result = machine.recall(arguments.key)
            print_json(
                result
                if result is not None
                else {
                    "found": False,
                    "key": arguments.key,
                }
            )
        elif arguments.command == "exist":
            machine.heartbeat(actor="existence_probe")
            print_json(machine.existence_report())
        elif arguments.command == "verify":
            print_json(machine.verify_integrity())
        elif arguments.command == "history":
            print_json(machine.history(limit=arguments.limit))
    finally:
        machine.close()


if __name__ == "__main__":
    main()
