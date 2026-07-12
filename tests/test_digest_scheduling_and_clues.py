import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import sandbox_clues  # noqa: E402
import sandbox_daily_digest  # noqa: E402


def _make_pulse(workbench: Path, stamp: str) -> None:
    workbench.mkdir(parents=True, exist_ok=True)
    (workbench / f"oracle_self_prompt_{stamp}.ai").write_text(
        ".AI:ORACLE_SELF_PROMPT_CYCLE\n"
        f"timestamp=2026-07-11T{stamp[-6:-2]}:00Z\n"
        "\n"
        "child_response:\n"
        "selected_task: test task\n"
        "\n"
        "self_reflection:\n"
        "I completed exactly one sandbox-only self-prompt step and stopped.\n",
        encoding="utf-8",
    )


def test_daily_digest_is_idempotent_per_day(tmp_path):
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workbench = tmp_path / "workbench"
    receipts = tmp_path / "receipts"
    digest_dir = tmp_path / "digest"
    receipts.mkdir()
    _make_pulse(workbench, stamp)

    first = sandbox_daily_digest.write_daily_digest(
        pulse_dir=workbench, receipt_dir=receipts, digest_dir=digest_dir, force=False,
    )
    assert first["ok"] is True
    assert Path(first["digest_path"]).exists()
    assert Path(first["receipt_path"]).exists()
    receipt = json.loads(Path(first["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["canon_status"] == "sandbox_candidate"
    assert receipt["promotion_status"] == "not_promoted"
    assert receipt["boundary_check_result"]["boundary_ok"] is True

    second = sandbox_daily_digest.write_daily_digest(
        pulse_dir=workbench, receipt_dir=receipts, digest_dir=digest_dir, force=False,
    )
    assert second.get("skipped") is True
    assert "already exists" in second.get("reason", "")


def test_self_prompt_loop_schedules_daily_digest():
    source = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    loop_start = source.find("async def _autonomous_self_prompt_loop")
    assert loop_start > 0
    loop_body = source[loop_start:loop_start + 4000]
    assert "write_daily_digest" in loop_body
    assert "force=False" in loop_body


def test_sandbox_clues_report_is_read_only(tmp_path):
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workbench = tmp_path / "workbench"
    receipts = tmp_path / "receipts"
    journal = tmp_path / "journal"
    receipts.mkdir()
    journal.mkdir()
    _make_pulse(workbench, stamp)

    # A receipt whose SHA matches its file.
    target = workbench / "artifact.ai"
    target.write_text("hello sandbox", encoding="utf-8")
    import hashlib
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    (receipts / "sandbox_write_file_x_receipt.json").write_text(
        json.dumps({"final_path": str(target), "sha256": sha}), encoding="utf-8",
    )
    # A broken receipt pointing at a missing file.
    (receipts / "sandbox_write_file_y_receipt.json").write_text(
        json.dumps({"final_path": str(tmp_path / "gone.ai"), "sha256": "0" * 64}),
        encoding="utf-8",
    )

    before = sorted(p for p in tmp_path.rglob("*") if p.is_file())
    report = sandbox_clues.sandbox_clues_report(sandbox_root=tmp_path)
    after = sorted(p for p in tmp_path.rglob("*") if p.is_file())

    # Read-only guarantee: not one file created, modified list unchanged.
    assert before == after
    assert report["read_only"] is True
    assert report["wrote_files"] == 0
    assert report["totals"]["pulses"] == 1
    assert report["receipt_verification"]["sha_verified_match"] == 1
    assert report["receipt_verification"]["file_missing"] == 1
    assert any("missing file" in p for p in report["receipt_verification"]["problems"])

    text = sandbox_clues.render_sandbox_clues(report)
    assert "read-only" in text
    assert "next safest action" in text


def test_server_registers_sandbox_clues_command():
    source = (ROOT / "oracle_server.py").read_text(encoding="utf-8", errors="replace")
    assert '/sandbox-clues' in source
    assert "sandbox_clues_report" in source
