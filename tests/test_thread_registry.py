from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import thread_registry as tr  # noqa: E402


def _seed(path):
    """Build a minimal DB mirroring the real messages/sessions schema."""
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp TEXT)")
    c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT, summary TEXT)")
    for sid in ("s1", "s2", "empty"):
        c.execute("INSERT INTO sessions VALUES (?,?,?)", (sid, "t", None))
    c.executemany("INSERT INTO messages (session_id,role,content,timestamp) VALUES (?,?,?,?)", [
        ("s1", "user", "Who is Ashley?", "t1"), ("s1", "assistant", "your wife", "t2"),
        ("s2", "user", "where were we", "t3")])
    c.commit()
    return c


def test_schema_is_additive(tmp_path):
    c = _seed(tmp_path / "m.db")
    did = tr.ensure_schema(c)
    assert did["threads_table_created"] is True
    assert did["thread_id_column_added"] is True
    cols = {r[1] for r in c.execute("PRAGMA table_info(messages)")}
    assert "thread_id" in cols
    # idempotent: second call does nothing
    did2 = tr.ensure_schema(c)
    assert did2 == {"threads_table_created": False, "thread_id_column_added": False,
                    "session_id_column_added": False}
    # no message data was lost
    assert c.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 3


def test_thread_is_durable_object(tmp_path):
    dbp = tmp_path / "m.db"
    c = _seed(dbp)
    tid = tr.create_thread(c, title="Ashley repair")
    assert tr.attach_message(c, thread_id=tid, message_id=1) is True
    assert tr.attach_message(c, thread_id=tid, message_id=2) is True
    c.close()
    # reopen a FRESH connection -> the thread + its messages survive (durability)
    c2 = sqlite3.connect(dbp)
    t = tr.get_thread(c2, tid)
    assert t is not None and t["turn_count"] == 2
    msgs = tr.thread_messages(c2, tid)
    assert [m["content"] for m in msgs] == ["Who is Ashley?", "your wife"]


def test_new_thread_does_not_claim_noah_as_participant_without_source(tmp_path):
    c = _seed(tmp_path / "m.db")

    tid = tr.create_thread(c, title="unattributed turn")
    thread = tr.get_thread(c, tid)

    assert json.loads(thread["participants_json"]) == ["UNKNOWN"]


def test_session_thread_records_session_without_fabricated_participant(tmp_path):
    c = _seed(tmp_path / "m.db")

    tid = tr.get_or_create_thread_for_session(c, "s1")
    thread = tr.get_thread(c, tid)

    assert thread["session_id"] == "s1"
    assert json.loads(thread["participants_json"]) == ["UNKNOWN"]


def test_message_save_hook_makes_a_durable_thread(tmp_path):
    """Simulate the live save path: each saved message flows through on_message_saved.
    Same session -> one durable thread that survives a fresh reopen (the real fix)."""
    dbp = tmp_path / "m.db"
    c = _seed(dbp)
    tr.ensure_schema(c)
    # session s3: an assistant greeting created first, then the first user turn
    c.execute("INSERT INTO messages (session_id,role,content,timestamp) VALUES ('s3','assistant','hi there','t')")
    m1 = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    t1 = tr.on_message_saved(c, session_id="s3", message_id=m1, role="assistant", content="hi there")
    c.execute("INSERT INTO messages (session_id,role,content,timestamp) VALUES ('s3','user','remember the seed',?)", ("t",))
    m2 = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    t2 = tr.on_message_saved(c, session_id="s3", message_id=m2, role="user", content="remember the seed")
    assert t1 == t2  # one durable thread for the session, not two shards
    c.close()
    c2 = sqlite3.connect(dbp)  # restart: nothing in memory carried over
    t = tr.get_thread(c2, t1)
    assert t["turn_count"] == 2
    assert t["title"] == "remember the seed"  # titled from the first USER turn
    assert [m["content"] for m in tr.thread_messages(c2, t1)] == ["hi there", "remember the seed"]


def test_attach_unknown_message_fails_cleanly(tmp_path):
    c = _seed(tmp_path / "m.db")
    tid = tr.create_thread(c, title="x")
    assert tr.attach_message(c, thread_id=tid, message_id=9999) is False


def test_attach_unknown_thread_fails_without_mutating_message(tmp_path):
    c = _seed(tmp_path / "m.db")
    tr.ensure_schema(c)

    assert tr.attach_message(c, thread_id="thread_missing", message_id=1) is False
    row = c.execute("SELECT thread_id FROM messages WHERE id=1").fetchone()
    assert row["thread_id"] is None


def test_discovery_invents_nothing(tmp_path):
    c = _seed(tmp_path / "m.db")
    tr.ensure_schema(c)
    d = tr.discover_threads_from_sessions(c)
    # s1 and s2 have messages -> recoverable; 'empty' session has none
    sids = {r["session_id"] for r in d["recoverable"]}
    assert sids == {"s1", "s2"}
    assert d["unrecoverable_or_empty_sessions"] == 1  # the empty session
    # title comes from real first user message, not fabricated
    s1 = next(r for r in d["recoverable"] if r["session_id"] == "s1")
    assert s1["suggested_title"] == "Who is Ashley?"
    assert s1["message_count"] == 2
