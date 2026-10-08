import sqlite3
import json
from datetime import datetime
from pathlib import Path
from root import ROOT

DB_PATH = ROOT / "Memory" / "oracle_memory.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(category, key)
            );
            CREATE TABLE IF NOT EXISTS projects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER NOT NULL,
                note        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE TABLE IF NOT EXISTS people (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                role        TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS person_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id   INTEGER NOT NULL,
                note        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (person_id) REFERENCES people(id)
            );
            CREATE TABLE IF NOT EXISTS durable_facts (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_text            TEXT NOT NULL,
                source_type          TEXT NOT NULL,
                source_id            TEXT NOT NULL,
                observed_at          TEXT NOT NULL,
                confidence           REAL NOT NULL,
                transformation_history TEXT NOT NULL DEFAULT '[]',
                canonical_status     TEXT NOT NULL DEFAULT 'staged',
                approval_status      TEXT NOT NULL DEFAULT 'pending',
                provenance_json      TEXT NOT NULL DEFAULT '{}',
                created_at           TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_chain (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                event        TEXT NOT NULL,
                detail       TEXT NOT NULL DEFAULT '{}',
                recorded_at  TEXT NOT NULL
            );
        """)
    # Older durable_facts rows predate actor-aware provenance. Keep those rows,
    # but mark their identity UNKNOWN/provenance-suspect instead of allowing a
    # caller to infer that the account owner authored them (GitHub #16).
    migrate_durable_fact_provenance()
    # Ensure the L2 index schema exists on boot (cheap, additive). Does NOT
    # rebuild the index here — rebuild is explicit (/rebuild-memory-index) to
    # keep boot fast on slow (Drive-synced) storage.
    try:
        migrate_memory_index(rebuild_if_stale=False)
    except Exception:
        pass


def new_session():
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)",
            (datetime.now().isoformat(),)
        )
        return cur.lastrowid


def save_message(session_id, role, content):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )
        message_id = cur.lastrowid
        # Attach the message to its session's durable thread so a conversation
        # survives restarts. Best-effort: chat must never break if this fails.
        try:
            import thread_registry as _thread_registry
            _thread_registry.on_message_saved(
                conn, session_id=session_id, message_id=message_id,
                role=role, content=content)
        except Exception:
            pass
        return message_id


def get_recent_messages(session_id, limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return list(reversed([{"role": r["role"], "content": r["content"]} for r in rows]))


def upsert_fact(category, key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO facts (category, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (category, key, str(value), datetime.now().isoformat())
        )


def get_facts(category=None):
    with get_conn() as conn:
        if category:
            rows = conn.execute("SELECT category, key, value FROM facts WHERE category = ?", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT category, key, value FROM facts").fetchall()
        return [{"category": r["category"], "key": r["key"], "value": r["value"]} for r in rows]


# --- Projects ---

def add_project(name):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO projects (name, created_at) VALUES (?, ?)",
                (name.strip(), datetime.now().isoformat())
            )
            return True
        except Exception:
            return False  # already exists


def add_project_note(name, note):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM projects WHERE name = ?", (name.strip(),)).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT INTO project_notes (project_id, note, created_at) VALUES (?, ?, ?)",
            (row["id"], note.strip(), datetime.now().isoformat())
        )
        return True


def recall_project(name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, status, created_at FROM projects WHERE name = ?",
            (name.strip(),)
        ).fetchone()
        if not row:
            return None
        notes = conn.execute(
            "SELECT note, created_at FROM project_notes WHERE project_id = ? ORDER BY id DESC",
            (row["id"],)
        ).fetchall()
    return {
        "name": row["name"],
        "status": row["status"],
        "notes": [{"note": n["note"], "date": n["created_at"][:10]} for n in notes]
    }


def list_projects():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, status FROM projects ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# --- People ---

def add_person(name, role=None):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?)",
                (name.strip(), role, datetime.now().isoformat())
            )
            return True
        except Exception:
            return False  # already exists


def add_person_note(name, note):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM people WHERE name = ?", (name.strip(),)).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT INTO person_notes (person_id, note, created_at) VALUES (?, ?, ?)",
            (row["id"], note.strip(), datetime.now().isoformat())
        )
        return True


def recall_person(name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, role FROM people WHERE name = ?", (name.strip(),)
        ).fetchone()
        if not row:
            return None
        notes = conn.execute(
            "SELECT note, created_at FROM person_notes WHERE person_id = ? ORDER BY id DESC",
            (row["id"],)
        ).fetchall()
    return {
        "name": row["name"],
        "role": row["role"],
        "notes": [{"note": n["note"], "date": n["created_at"][:10]} for n in notes]
    }


# ── Durable Facts (provenance-tagged, governance-gated) ──────────────────────

_REQUIRED_PROVENANCE_FIELDS = {
    "source_type", "source_id", "observed_at", "confidence",
    "transformation_history", "canonical_status", "approval_status",
}

_VALID_SOURCE_TYPES = {"human_stated", "inferred", "observed", "generated"}

_ACTOR_PROVENANCE_FIELDS = (
    "speaker_id",
    "author_id",
    "submitter_id",
    "account_owner_id",
    "project_owner_id",
    "human_source_id",
    "source_agent_type",
    "source_model",
    "participant_role",
    "intended_audience",
    "transport_channel",
    "source_reference",
    "identity_resolution_status",
)


def _legacy_unknown_provenance() -> dict:
    """Honest read/migration shape for rows written before actor custody."""
    return {
        **{field: "UNKNOWN" for field in _ACTOR_PROVENANCE_FIELDS},
        "identity_resolution_status": "legacy_unresolved",
        "provenance_evidence": [],
        "correction_history": [],
        "provenance_suspect": True,
        "provenance_note": (
            "Legacy durable fact predates actor-aware persistence; speaker, author, "
            "submitter, and owner identities must not be inferred."
        ),
    }


def _normalize_durable_provenance(provenance: dict) -> dict:
    """Fill missing actor dimensions with UNKNOWN without conflating identities."""
    normalized = dict(provenance or {})
    for field in _ACTOR_PROVENANCE_FIELDS:
        value = normalized.get(field)
        normalized[field] = str(value).strip() if value not in (None, "") else "UNKNOWN"
    normalized.setdefault("provenance_evidence", [])
    normalized.setdefault("correction_history", [])
    normalized.setdefault("provenance_suspect", False)
    return normalized


def migrate_durable_fact_provenance() -> dict:
    """Add full-provenance storage and downgrade unattributed legacy rows.

    This migration is additive and idempotent. It never rewrites fact text or
    claims that an old row belonged to Noah.Physical.
    """
    with get_conn() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(durable_facts)")}
        column_added = False
        if "provenance_json" not in columns:
            conn.execute("ALTER TABLE durable_facts ADD COLUMN provenance_json TEXT NOT NULL DEFAULT '{}'")
            column_added = True
        legacy = json.dumps(_legacy_unknown_provenance(), sort_keys=True)
        cursor = conn.execute(
            """
            UPDATE durable_facts
            SET provenance_json=?
            WHERE provenance_json IS NULL OR trim(provenance_json) IN ('', '{}')
            """,
            (legacy,),
        )
        conn.commit()
        return {
            "provenance_column_added": column_added,
            "legacy_rows_marked_suspect": cursor.rowcount,
        }


def _inflate_durable_fact(row) -> dict:
    """Decode actor provenance and expose its dimensions on recall records."""
    record = dict(row)
    try:
        provenance = json.loads(record.get("provenance_json") or "{}")
        if not isinstance(provenance, dict) or not provenance:
            provenance = _legacy_unknown_provenance()
    except (TypeError, json.JSONDecodeError):
        provenance = _legacy_unknown_provenance()
        provenance["provenance_note"] = (
            "Stored provenance JSON was unreadable; actor identities are UNKNOWN."
        )
    provenance = _normalize_durable_provenance(provenance)
    record["provenance"] = provenance
    for field in _ACTOR_PROVENANCE_FIELDS:
        record[field] = provenance[field]
    record["provenance_suspect"] = bool(provenance.get("provenance_suspect"))
    return record


def _validate_provenance(provenance: dict) -> None:
    """Raise ValueError if any required provenance field is absent or invalid."""
    missing = _REQUIRED_PROVENANCE_FIELDS - set(provenance.keys())
    if missing:
        raise ValueError(f"Missing required provenance fields: {sorted(missing)}")
    if provenance["source_type"] not in _VALID_SOURCE_TYPES:
        raise ValueError(
            f"Invalid source_type {provenance['source_type']!r}. "
            f"Must be one of: {sorted(_VALID_SOURCE_TYPES)}"
        )
    confidence = provenance["confidence"]
    if not (isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence must be 0.0–1.0, got {confidence!r}")
    if not isinstance(provenance["transformation_history"], list):
        raise ValueError("transformation_history must be a list")


def insert_durable_fact(fact_text: str, provenance: dict) -> int:
    """
    Insert a provenance-tagged durable fact.
    Raises ValueError if provenance is incomplete.
    Returns the row id.
    """
    provenance = _normalize_durable_provenance(provenance)
    _validate_provenance(provenance)
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO durable_facts
              (fact_text, source_type, source_id, observed_at, confidence,
               transformation_history, canonical_status, approval_status,
               provenance_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_text,
                provenance["source_type"],
                provenance["source_id"],
                provenance["observed_at"],
                float(provenance["confidence"]),
                json.dumps(provenance["transformation_history"]),
                provenance["canonical_status"],
                provenance["approval_status"],
                json.dumps(provenance, ensure_ascii=True, sort_keys=True),
                now,
            ),
        )
        row_id = cur.lastrowid
    # Keep the FTS index current for live single inserts. Best-effort: indexing
    # must never break a durable write.
    try:
        index_durable_fact(row_id)
    except Exception:
        pass
    return row_id


def search_durable_facts(query: str, limit: int = 10) -> list[dict]:
    """
    Full-text keyword search over durable facts.
    Returns records as dicts with full provenance.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM durable_facts WHERE fact_text LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        results = []
        for row in rows:
            r = _inflate_durable_fact(row)
            try:
                r["transformation_history"] = json.loads(r.get("transformation_history") or "[]")
            except Exception:
                r["transformation_history"] = []
            results.append(r)
        return results


def append_audit_chain(session_id: str, event: str, detail: dict | None = None) -> None:
    """Write a structured audit chain entry."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_chain (session_id, event, detail, recorded_at) VALUES (?, ?, ?, ?)",
            (
                session_id,
                event,
                json.dumps(detail or {}),
                datetime.now().isoformat(),
            ),
        )


def get_audit_chain(session_id: str) -> list[dict]:
    """Return ordered audit events for a session."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT event, detail, recorded_at FROM audit_chain WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            try:
                r["detail"] = json.loads(r.get("detail") or "{}")
            except Exception:
                r["detail"] = {}
            results.append(r)
        return results


# ── L2 indexed continuity memory (FTS5) ────────────────────────────────────────
# Real recall over durable_facts: full-text (FTS5) + authority/confidence ranking,
# supersession-aware. Additive and idempotent — never drops or rewrites facts.

import re as _re

_FTS_AVAILABLE: bool | None = None


def _fts_available(conn) -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is None:
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)")
            conn.execute("DROP TABLE IF EXISTS _fts_probe")
            _FTS_AVAILABLE = True
        except Exception:
            _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _normalize(text: str) -> str:
    return _re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _authority_rank(source_type: str, approval_status: str, canonical_status: str = "") -> int:
    """Higher = more authoritative. Noah's approved words outrank external/inferred text."""
    st = (source_type or "").lower()
    ap = (approval_status or "").lower()
    if st == "human_stated" and ap == "approved":
        return 100
    if st == "human_stated":
        return 80
    if st == "observed":
        return 60
    if st == "generated" and ap == "approved":
        return 50
    if st == "inferred":
        return 40
    if st == "generated":
        return 20
    return 30


def _column_exists(conn, table: str, col: str) -> bool:
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def migrate_memory_index(*, rebuild_if_stale: bool = True) -> dict:
    """
    Idempotent, additive migration:
      * adds authority_rank / supersedes_id / superseded_by columns to durable_facts
      * creates the durable_fts FTS5 index table
      * rebuilds the index if it is empty or out of sync with durable_facts
    Returns a summary dict. Never destroys durable_facts rows.
    """
    with get_conn() as conn:
        if not _fts_available(conn):
            return {"fts5": False, "indexed": 0, "reason": "FTS5 unavailable"}
        for col, ddl in (("authority_rank", "INTEGER DEFAULT 0"),
                         ("supersedes_id", "INTEGER"),
                         ("superseded_by", "INTEGER")):
            if not _column_exists(conn, "durable_facts", col):
                conn.execute(f"ALTER TABLE durable_facts ADD COLUMN {col} {ddl}")
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS durable_fts "
            "USING fts5(memory_id UNINDEXED, fact_text, normalized_text)"
        )
        conn.commit()
        fact_n = conn.execute("SELECT COUNT(*) AS n FROM durable_facts").fetchone()["n"]
        idx_n = conn.execute("SELECT COUNT(*) AS n FROM durable_fts").fetchone()["n"]
    if rebuild_if_stale and idx_n != fact_n:
        indexed = rebuild_memory_index()
        return {"fts5": True, "indexed": indexed, "rebuilt": True}
    return {"fts5": True, "indexed": idx_n, "rebuilt": False}


def rebuild_memory_index() -> int:
    """Rebuild the FTS index + authority ranks from durable_facts in one transaction."""
    with get_conn() as conn:
        if not _fts_available(conn):
            return 0
        conn.execute("DELETE FROM durable_fts")
        rows = conn.execute(
            "SELECT id, fact_text, source_type, approval_status, canonical_status FROM durable_facts"
        ).fetchall()
        conn.executemany(
            "INSERT INTO durable_fts(memory_id, fact_text, normalized_text) VALUES (?, ?, ?)",
            [(r["id"], r["fact_text"], _normalize(r["fact_text"])) for r in rows],
        )
        conn.executemany(
            "UPDATE durable_facts SET authority_rank=? WHERE id=?",
            [(_authority_rank(r["source_type"], r["approval_status"], r["canonical_status"]), r["id"]) for r in rows],
        )
        conn.commit()
        return len(rows)


def index_durable_fact(row_id: int) -> None:
    """Index/refresh a single durable fact (called after insert)."""
    with get_conn() as conn:
        if not _fts_available(conn):
            return
        r = conn.execute(
            "SELECT id, fact_text, source_type, approval_status, canonical_status FROM durable_facts WHERE id=?",
            (row_id,),
        ).fetchone()
        if not r:
            return
        conn.execute("DELETE FROM durable_fts WHERE memory_id=?", (row_id,))
        conn.execute(
            "INSERT INTO durable_fts(memory_id, fact_text, normalized_text) VALUES (?, ?, ?)",
            (r["id"], r["fact_text"], _normalize(r["fact_text"])),
        )
        conn.execute(
            "UPDATE durable_facts SET authority_rank=? WHERE id=?",
            (_authority_rank(r["source_type"], r["approval_status"], r["canonical_status"]), r["id"]),
        )
        conn.commit()


def search_memory_index(query: str, *, limit: int = 10, source_type: str | None = None,
                        canonical_status: str | None = None, min_confidence: float = 0.0,
                        min_authority: int = 0, order: str = "relevance",
                        exclude_superseded: bool = True) -> list[dict]:
    """
    Indexed recall. order='relevance' (FTS bm25 + authority + confidence) or 'recent'.
    Falls back to a LIKE scan if FTS5 is unavailable.
    """
    words = [w for w in _re.findall(r"[a-z0-9]+", (query or "").lower()) if len(w) > 1]
    if not words:
        return []
    with get_conn() as conn:
        if not _fts_available(conn):
            rows = conn.execute(
                "SELECT * FROM durable_facts WHERE lower(fact_text) LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{words[0]}%", limit),
            ).fetchall()
            return [_inflate_durable_fact(r) for r in rows]
        match = " OR ".join(f'"{w}"' for w in words[:20])
        sql = [
            "SELECT f.*, bm25(durable_fts) AS bm25_rank",
            "FROM durable_fts JOIN durable_facts f ON f.id = durable_fts.memory_id",
            "WHERE durable_fts MATCH ?",
        ]
        params: list = [match]
        if source_type:
            sql.append("AND f.source_type=?"); params.append(source_type)
        if canonical_status:
            sql.append("AND f.canonical_status=?"); params.append(canonical_status)
        if min_confidence:
            sql.append("AND f.confidence>=?"); params.append(min_confidence)
        if min_authority:
            sql.append("AND COALESCE(f.authority_rank,0)>=?"); params.append(min_authority)
        if exclude_superseded:
            sql.append("AND f.superseded_by IS NULL")
        if order == "recent":
            sql.append("ORDER BY f.id DESC")
        else:
            # bm25 lower=better; subtract authority/confidence so authoritative, confident facts rank higher.
            sql.append("ORDER BY (bm25(durable_fts) - COALESCE(f.authority_rank,0)/40.0 - f.confidence) ASC")
        sql.append("LIMIT ?"); params.append(limit)
        rows = conn.execute(" ".join(sql), params).fetchall()
        return [_inflate_durable_fact(r) for r in rows]


def get_memory_by_id(memory_id: int) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM durable_facts WHERE id=?", (memory_id,)).fetchone()
        return _inflate_durable_fact(r) if r else None


def mark_superseded(old_id: int, by_id: int) -> None:
    """Mark old_id as superseded by by_id (corrections/updates)."""
    with get_conn() as conn:
        conn.execute("UPDATE durable_facts SET superseded_by=? WHERE id=?", (by_id, old_id))
        conn.execute("UPDATE durable_facts SET supersedes_id=? WHERE id=?", (old_id, by_id))
        conn.commit()


def find_contradictions(query: str, limit: int = 10) -> list[dict]:
    """Surface candidate contradictions among matches: same topic, opposite negation polarity."""
    hits = search_memory_index(query, limit=max(limit * 2, 12), exclude_superseded=False)
    neg = _re.compile(r"\b(no|not|never|cannot|can't|won't|don't|isn't|aren't|false|wrong)\b")
    seen: list[dict] = []
    out: list[dict] = []
    for h in hits:
        polarity = bool(neg.search((h.get("fact_text") or "").lower()))
        for prev in seen:
            if prev["polarity"] != polarity:
                out.append({"type": "negation_polarity",
                            "a_id": prev["fact"]["id"], "b_id": h["id"],
                            "a": prev["fact"]["fact_text"][:120], "b": h["fact_text"][:120]})
                break
        seen.append({"polarity": polarity, "fact": h})
    return out[:limit]
