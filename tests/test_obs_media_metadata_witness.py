from __future__ import annotations

import sys
from pathlib import Path


WITNESS_DIR = Path(__file__).resolve().parents[1] / "tools" / "witness"
sys.path.insert(0, str(WITNESS_DIR))

import obs_media_metadata_witness as witness


def test_obs_state_marks_latest_recording_active() -> None:
    text = (
        "Writing file 'C:\\Videos\\old.mkv'\n"
        "Recording Stop\n"
        "Writing file 'C:\\Videos\\current.mov'\n"
    )
    assert witness.parse_obs_recording_state(text) == {
        "active": True,
        "recording_path": "C:\\Videos\\current.mov",
    }


def test_obs_state_marks_latest_recording_stopped() -> None:
    text = "Writing file 'C:\\Videos\\current.mov'\nRecording Stop\n"
    assert witness.parse_obs_recording_state(text) == {
        "active": False,
        "recording_path": "C:\\Videos\\current.mov",
    }


def test_media_discovery_uses_video_extensions_only(tmp_path: Path) -> None:
    (tmp_path / "clip.MOV").write_bytes(b"")
    (tmp_path / "recording.mkv").write_bytes(b"")
    (tmp_path / "screenshot.png").write_bytes(b"")
    names = sorted(path.name for path in witness.iter_media_files((tmp_path,)))
    assert names == ["clip.MOV", "recording.mkv"]


def test_cloud_placeholder_detection_uses_windows_recall_bit(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "online.mov"
    path.write_bytes(b"")

    class FakeStat:
        st_file_attributes = witness.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS

    monkeypatch.setattr(Path, "stat", lambda self: FakeStat())
    assert witness.is_cloud_placeholder(path) is True
