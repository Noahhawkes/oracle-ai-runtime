"""Pytest coverage for core/meaning_engine.py.

The module has no dedicated test file. It is the OBS-session-to-memory-candidate
bridge (log detected -> ingest -> PENDING candidate -> Noah approval) and has
had zero automated coverage of its seen-log bookkeeping, ingest dispatch, or
poll logic. These tests exercise only the pure/state-file logic, with every
filesystem touch redirected into tmp_path via monkeypatch — nothing here reads
or writes the real state/ dir, the real Messages/ dir, or the real OBS log
directory. `watch()` (infinite poll loop) and `show_status()` (touches the
live remember_me store) are intentionally left uncovered here.
"""

import json
from pathlib import Path

import pytest

import core.meaning_engine as meaning_engine


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Redirect every module-level path the tested functions touch into tmp_path."""
    monkeypatch.setattr(meaning_engine, "ROOT", tmp_path)
    monkeypatch.setattr(meaning_engine, "STATE_FILE", tmp_path / "state" / "meaning_engine_state.json")
    monkeypatch.setattr(meaning_engine, "OBS_LOG_DIR", tmp_path / "obs_logs")
    return tmp_path


def test_load_seen_logs_missing_file_returns_empty_set():
    assert meaning_engine._load_seen_logs() == set()


def test_save_then_load_seen_logs_round_trips():
    meaning_engine._save_seen_logs({"a.txt", "b.txt"})
    assert meaning_engine._load_seen_logs() == {"a.txt", "b.txt"}


def test_save_seen_logs_creates_parent_directory(tmp_path):
    assert not (tmp_path / "state").exists()
    meaning_engine._save_seen_logs({"a.txt"})
    assert (tmp_path / "state" / "meaning_engine_state.json").exists()


def test_load_seen_logs_tolerates_corrupt_json(tmp_path):
    state_path = tmp_path / "state" / "meaning_engine_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not valid json", encoding="utf-8")
    assert meaning_engine._load_seen_logs() == set()


def test_save_seen_logs_writes_sorted_list_and_timestamp(tmp_path):
    meaning_engine._save_seen_logs({"b.txt", "a.txt"})
    payload = json.loads((tmp_path / "state" / "meaning_engine_state.json").read_text(encoding="utf-8"))
    assert payload["seen_logs"] == ["a.txt", "b.txt"]
    assert "updated" in payload


def test_ingest_new_logs_empty_input_short_circuits(monkeypatch):
    called = {"count": 0}

    def fake_ingest_logs(**kwargs):
        called["count"] += 1
        return []

    monkeypatch.setattr("obs_ingest.ingest_logs", fake_ingest_logs)
    assert meaning_engine.ingest_new_logs([]) == []
    assert called["count"] == 0


def test_ingest_new_logs_missing_obs_ingest_module_returns_empty(monkeypatch, capsys):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "obs_ingest":
            raise ImportError("simulated missing module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    result = meaning_engine.ingest_new_logs([Path("fake.txt")])
    assert result == []
    assert "obs_ingest not available" in capsys.readouterr().out


def test_ingest_new_logs_delegates_to_obs_ingest_and_reports_ids(monkeypatch, capsys):
    seen_paths = []

    def fake_ingest_logs(log_paths=None, dry_run=False):
        seen_paths.extend(log_paths)
        return ["cand-1", "cand-2"]

    monkeypatch.setattr("obs_ingest.ingest_logs", fake_ingest_logs)
    paths = [Path("one.txt"), Path("two.txt")]
    ids = meaning_engine.ingest_new_logs(paths, dry_run=True)
    assert ids == ["cand-1", "cand-2"]
    assert seen_paths == paths
    out = capsys.readouterr().out
    assert "ingesting 2 new OBS log" in out
    assert "created 2 memory candidate" in out


def test_poll_once_no_log_dir_is_a_noop(tmp_path):
    # OBS_LOG_DIR points at a path that does not exist.
    seen = set()
    meaning_engine._poll_once(seen)
    assert seen == set()


def test_poll_once_detects_and_records_new_logs(monkeypatch, tmp_path):
    log_dir = tmp_path / "obs_logs"
    log_dir.mkdir()
    (log_dir / "session1.txt").write_text("log", encoding="utf-8")

    monkeypatch.setattr(meaning_engine, "ingest_new_logs", lambda paths: ["cand-1"])
    notified = {}
    monkeypatch.setattr(meaning_engine, "_notify_oracle", lambda ids: notified.setdefault("ids", ids))

    seen = set()
    meaning_engine._poll_once(seen)

    assert seen == {"session1.txt"}
    assert notified["ids"] == ["cand-1"]
    assert meaning_engine._load_seen_logs() == {"session1.txt"}


def test_poll_once_skips_already_seen_logs(monkeypatch, tmp_path):
    log_dir = tmp_path / "obs_logs"
    log_dir.mkdir()
    (log_dir / "session1.txt").write_text("log", encoding="utf-8")

    called = {"count": 0}
    monkeypatch.setattr(meaning_engine, "ingest_new_logs", lambda paths: called.__setitem__("count", called["count"] + 1) or [])

    seen = {"session1.txt"}
    meaning_engine._poll_once(seen)
    assert called["count"] == 0


def test_notify_oracle_appends_entry_when_messages_file_exists(tmp_path):
    messages_dir = tmp_path / "Messages"
    messages_dir.mkdir()
    msg_path = messages_dir / "oracle_inner.md"
    msg_path.write_text("existing content\n", encoding="utf-8")

    meaning_engine._notify_oracle(["abcdef1234567890"])

    content = msg_path.read_text(encoding="utf-8")
    assert "existing content" in content
    assert "MEANING ENGINE" in content
    assert "abcdef12" in content


def test_notify_oracle_silent_when_messages_file_absent(tmp_path):
    # No Messages/ dir created — should not raise.
    meaning_engine._notify_oracle(["abcdef1234567890"])
    assert not (tmp_path / "Messages").exists()
