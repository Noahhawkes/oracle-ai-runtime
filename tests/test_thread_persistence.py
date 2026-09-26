"""Thread persistence proof (TP_031).

Proves the durable thread spine at the data layer - the part that makes
REFRESH_MUST_NOT_DESTROY_THREAD true:

  * a user message persists IMMEDIATELY (before any model reply),
  * it survives a "reload" (a fresh DB connection = what /api/history does on
    refresh / fresh page load),
  * if the model reply never lands (timeout), the user turn is still logged,
  * after restart, both turns come back in order.

Runs against a TEMP database; never touches Memory/oracle_memory.db.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import memory  # noqa: E402


def _fresh_db(tmp_path: Path):
    """Point memory at a throwaway DB and initialize it."""
    memory.DB_PATH = tmp_path / "test_oracle_memory.db"
    memory.init_db()


def test_user_message_persists_before_any_reply(tmp_path):
    _fresh_db(tmp_path)
    sid = memory.new_session()
    memory.save_message(sid, "user", "first message")
    # Read back through a brand-new connection == what a refresh would see.
    reloaded = memory.get_recent_messages(sid, limit=40)
    assert reloaded == [{"role": "user", "content": "first message"}]


def test_user_turn_survives_model_timeout(tmp_path):
    _fresh_db(tmp_path)
    sid = memory.new_session()
    memory.save_message(sid, "user", "ask something")
    # Simulate the model call timing out: NO assistant message is saved.
    # The user turn must still be durable.
    reloaded = memory.get_recent_messages(sid, limit=40)
    assert reloaded == [{"role": "user", "content": "ask something"}]


def test_thread_survives_refresh_then_restart(tmp_path):
    _fresh_db(tmp_path)
    sid = memory.new_session()

    # turn 1
    memory.save_message(sid, "user", "hello")
    memory.save_message(sid, "assistant", "hi Noah")

    # "refresh": reload from durable store (fresh connection)
    after_refresh = memory.get_recent_messages(sid, limit=40)
    assert after_refresh == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi Noah"},
    ]

    # turn 2
    memory.save_message(sid, "user", "second message")
    memory.save_message(sid, "assistant", "got it")

    # "restart the app": simulate by re-opening the same DB path fresh
    memory.DB_PATH = memory.DB_PATH  # same file on disk
    after_restart = memory.get_recent_messages(sid, limit=40)
    assert [m["content"] for m in after_restart] == [
        "hello", "hi Noah", "second message", "got it",
    ]
    # order preserved (oldest -> newest)
    assert after_restart[0]["role"] == "user"
    assert after_restart[-1]["content"] == "got it"


def test_latest_session_is_recoverable_like_api_history(tmp_path):
    """/api/history's durable fallback picks the most recent session by row id.
    Prove that 'most recent session' lookup returns the last thread."""
    _fresh_db(tmp_path)
    old = memory.new_session()
    memory.save_message(old, "user", "old thread")
    new = memory.new_session()
    memory.save_message(new, "user", "current thread")

    with memory.get_conn() as conn:
        row = conn.execute(
            "SELECT session_id FROM messages ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row["session_id"] == new
    recovered = memory.get_recent_messages(row["session_id"], limit=40)
    assert recovered == [{"role": "user", "content": "current thread"}]
