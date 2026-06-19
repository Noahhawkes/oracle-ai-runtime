import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def _patch_paths(monkeypatch, tmp_path):
    import obs_live_transcript as obs

    monkeypatch.setattr(obs, "TRANSCRIPTS_DIR", tmp_path / "state" / "transcripts" / "obs")
    monkeypatch.setattr(obs, "RECEIPTS_DIR", tmp_path / "state" / "receipts")
    monkeypatch.setattr(obs, "OBS_LOG_DIR", tmp_path / "obs" / "logs")
    monkeypatch.setattr(obs.shutil, "which", lambda _name: None)
    monkeypatch.setattr(obs.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.delenv("ORACLE_LOCAL_WHISPER_MODEL_PATH", raising=False)
    monkeypatch.delenv("ORACLE_WHISPER_CPP_EXE", raising=False)
    monkeypatch.delenv("ORACLE_WHISPER_CPP_MODEL", raising=False)
    monkeypatch.delenv("ORACLE_VOSK_MODEL_PATH", raising=False)
    return obs


def _obs_path(path):
    return str(path).replace("\\", "/")


def test_detects_active_obs_recording_from_bounded_log(monkeypatch, tmp_path):
    obs = _patch_paths(monkeypatch, tmp_path)
    log_dir = tmp_path / "obs" / "logs"
    log_dir.mkdir(parents=True)
    recording = tmp_path / "Videos" / "session.mkv"
    recording.parent.mkdir()
    recording.write_bytes(b"fake mkv bytes")
    (log_dir / "2026-06-19 16-45-06.txt").write_text(
        f"16:45:15.077: [ffmpeg muxer: 'simple_file_output'] Writing file '{_obs_path(recording)}'...\n",
        encoding="utf-8",
    )

    scan = obs.scan_obs_recordings(log_dir)

    assert scan["recording_active"] is True
    assert Path(scan["active_recording_path"]) == recording
    assert scan["active_recording"]["exists"] is True


def test_stopped_obs_recording_is_not_reported_active(monkeypatch, tmp_path):
    obs = _patch_paths(monkeypatch, tmp_path)
    log_dir = tmp_path / "obs" / "logs"
    log_dir.mkdir(parents=True)
    recording = tmp_path / "Videos" / "session.mkv"
    recording.parent.mkdir()
    recording.write_bytes(b"fake mkv bytes")
    log_text = "\n".join(
        [
            f"16:45:15.077: [ffmpeg muxer: 'simple_file_output'] Writing file '{_obs_path(recording)}'...",
            f"16:46:00.000: [ffmpeg muxer: 'simple_file_output'] Output of file '{_obs_path(recording)}' stopped",
        ]
    )
    (log_dir / "2026-06-19 16-45-06.txt").write_text(log_text, encoding="utf-8")

    scan = obs.scan_obs_recordings(log_dir)

    assert scan["recording_active"] is False
    assert scan["latest_started_recording"]["stopped_in_logs"] is True


def test_status_refuses_cloud_when_no_local_stack(monkeypatch, tmp_path):
    obs = _patch_paths(monkeypatch, tmp_path)

    stack = obs.detect_local_transcript_stack()

    assert stack["local_only"] is True
    assert stack["cloud_transcription_refused"] is True
    assert stack["cloud_providers_allowed"] == []
    assert stack["can_transcribe_locally"] is False


def test_pull_sidecar_writes_transcript_and_receipt(monkeypatch, tmp_path):
    obs = _patch_paths(monkeypatch, tmp_path)
    log_dir = tmp_path / "obs" / "logs"
    log_dir.mkdir(parents=True)
    recording = tmp_path / "Videos" / "session.mkv"
    recording.parent.mkdir()
    recording.write_bytes(b"fake mkv bytes")
    sidecar = recording.with_suffix(".txt")
    sidecar.write_text("Captain's log: this is the local sidecar transcript.", encoding="utf-8")
    (log_dir / "2026-06-19 16-45-06.txt").write_text(
        f"16:45:15.077: [ffmpeg muxer: 'simple_file_output'] Writing file '{_obs_path(recording)}'...\n",
        encoding="utf-8",
    )

    result = obs.pull_active_transcript(log_dir=log_dir, notes="test pull")
    transcript_path = Path(result["transcript"]["path"])
    receipt_path = Path(result["receipt"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert transcript_path.exists()
    assert receipt_path.exists()
    assert receipt["operation"] == "obs_transcript_sidecar_pull"
    assert receipt["transcript_available"] is True
    assert receipt["source_sidecar_path"] == str(sidecar)
    assert receipt["raw_recording_copied"] is False
    assert receipt["cloud_uploads"] == 0
    assert receipt["files_moved"] == 0
    assert receipt["files_deleted"] == 0
    assert receipt["files_renamed"] == 0
    assert receipt["files_synced"] == 0
    assert receipt["git_commits"] == 0
    assert receipt["git_pushes"] == 0


def test_pull_without_sidecar_or_stack_writes_blocker_receipt(monkeypatch, tmp_path):
    obs = _patch_paths(monkeypatch, tmp_path)
    log_dir = tmp_path / "obs" / "logs"
    log_dir.mkdir(parents=True)
    recording = tmp_path / "Videos" / "session.mkv"
    recording.parent.mkdir()
    recording.write_bytes(b"fake mkv bytes")
    (log_dir / "2026-06-19 16-45-06.txt").write_text(
        f"16:45:15.077: [ffmpeg muxer: 'simple_file_output'] Writing file '{_obs_path(recording)}'...\n",
        encoding="utf-8",
    )

    result = obs.pull_active_transcript(log_dir=log_dir, notes="test blocker")
    receipt_path = Path(result["receipt"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result["transcript"] is None
    assert receipt["operation"] == "obs_transcript_pull_blocked"
    assert receipt["transcript_available"] is False
    assert "Cloud transcription was refused" in receipt["blocker"]
    assert receipt["raw_recording_copied"] is False
    assert receipt["cloud_uploads"] == 0


def test_sourcemap_ui_contains_obs_transcript_panel():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "Captain's Log Transcript" in html
    assert "obs-transcript-recording" in html
    assert "Refresh OBS transcript status" in html
    assert "Pull local transcript" in html
    assert "Write transcript receipt" in html
    assert "cloud transcription" in html
