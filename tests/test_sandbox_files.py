from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402
import sandbox_files as sf  # noqa: E402


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(sf, "SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr(sf, "SANDBOX_TRASH_ROOT", tmp_path / "sandbox.trash")


def _receipt(result):
    return json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))


def test_default_sandbox_root_is_runtime_owned_not_legacy_global_root():
    root = sf.SANDBOX_ROOT.resolve(strict=False)
    trash_root = sf.SANDBOX_TRASH_ROOT.resolve(strict=False)
    legacy_root = (Path("C:/") / "ORACLE.AI" / "sandbox").resolve(strict=False)

    assert root == (ROOT / "sandbox").resolve(strict=False)
    assert trash_root == (ROOT / "sandbox.trash").resolve(strict=False)
    assert root != legacy_root


def test_write_file_has_full_nested_sandbox_freedom_and_receipt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = sf.write_file(
        "workbench/internal/state/kernel_note.jsonl",
        "{\"status\":\"awake\"}\n",
        caller="test",
        action_id="full_nested_write",
    )

    final_path = Path(result["final_path"])
    receipt = _receipt(result)
    assert final_path == (tmp_path / "sandbox" / "workbench" / "internal" / "state" / "kernel_note.jsonl").resolve()
    assert final_path.read_text(encoding="utf-8") == "{\"status\":\"awake\"}\n"
    assert receipt["operation_type"] == "write_file"
    assert receipt["created"] is True
    assert receipt["boundary_check_result"]["boundary_ok"] is True
    assert receipt["boundary_check_result"]["inside_sandbox"] is True
    assert receipt["executed_written_file"] is False
    assert receipt["git_push"] is False
    assert receipt["external_send"] is False


def test_write_sandbox_file_compatibility_allows_new_workbench_folders(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = sf.write_sandbox_file("custom_zone", "note.ai", "custom workbench note", action_id="custom_zone")

    assert Path(result["final_path"]).parent == (tmp_path / "sandbox" / "custom_zone").resolve()
    assert Path(result["final_path"]).read_text(encoding="utf-8") == "custom workbench note"


def test_write_file_versions_existing_targets_instead_of_blind_overwrite(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    first = sf.write_file("notes/note.md", "one", action_id="one")
    second = sf.write_file("notes/note.md", "two", action_id="two")

    assert Path(first["final_path"]).name == "note.md"
    assert Path(second["final_path"]).name == "note_v2.md"
    assert Path(first["final_path"]).read_text(encoding="utf-8") == "one"
    assert Path(second["final_path"]).read_text(encoding="utf-8") == "two"


def test_sandbox_initiative_write_is_green_zone_and_receipted(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = sf.sandbox_initiative_write(
        "write to your sandbox",
        caller="ORACLE.chat",
        action_id="initiative_green_zone",
    )

    final_path = Path(result["final_path"])
    receipt = _receipt(result)
    assert result["approval_required"] is False
    assert final_path.is_relative_to((tmp_path / "sandbox").resolve())
    assert final_path.suffix == ".ai"
    assert final_path.parent == (tmp_path / "sandbox" / "journal").resolve()
    assert "authority_boundary=sandbox_green_zone_no_noah_approval_required" in final_path.read_text(encoding="utf-8")
    assert receipt["operation_type"] == "sandbox_initiative_write"
    assert receipt["approval_required"] is False
    assert receipt["boundary_check_result"]["boundary_ok"] is True
    assert receipt["external_send"] is False
    assert receipt["git_push"] is False
    assert receipt["canon_promotion"] is False


def test_sandbox_self_prompt_write_is_one_step_and_receipted(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    child_prompt = "Choose one sandbox-only next task, then stop."
    child_response = "selected_task: write a data-review plan\nstop_after_this: true"
    result = sf.sandbox_self_prompt_write(
        child_prompt,
        child_response,
        seed_prompt="Noah asked for proof of self-prompting",
        caller="ORACLE.self_prompt",
        source_route="ORACLE.self_prompt",
        action_id="self_prompt_once",
        model_called=False,
        model_name="test-model",
        model_error="disabled in test",
    )

    final_path = Path(result["final_path"])
    receipt = _receipt(result)
    content = final_path.read_text(encoding="utf-8")
    assert result["source_route"] == "ORACLE.self_prompt"
    assert result["max_steps"] == 1
    assert result["stop_condition"] == "one_child_prompt_written_then_stop"
    assert final_path.parent == (tmp_path / "sandbox" / "workbench").resolve()
    assert ".AI:ORACLE_SELF_PROMPT_CYCLE" in content
    assert "child_prompt:" in content
    assert child_prompt in content
    assert "child_response:" in content
    assert child_response in content
    assert receipt["operation_type"] == "sandbox_self_prompt_write"
    assert receipt["actor"] == "ORACLE.self_prompt"
    assert receipt["source_route"] == "ORACLE.self_prompt"
    assert receipt["self_prompt"] is True
    assert receipt["max_steps"] == 1
    assert receipt["boundary_check_result"]["inside_sandbox"] is True
    assert receipt["executed_written_file"] is False
    assert receipt["external_send"] is False
    assert receipt["git_push"] is False
    assert receipt["canon_promotion"] is False


def test_autonomous_self_prompt_after_boot_writes_without_chat_command(monkeypatch, tmp_path):
    import asyncio
    import oracle_server as srv

    _isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("ORACLE_SKIP_SERVER_BOOT", raising=False)
    monkeypatch.setenv("ORACLE_AUTONOMOUS_SELF_PROMPT", "1")
    monkeypatch.setenv("ORACLE_AUTONOMOUS_SELF_PROMPT_DELAY", "0")
    monkeypatch.setenv("ORACLE_SELF_PROMPT_DISABLE_MODEL", "1")

    result = asyncio.run(srv._autonomous_self_prompt_after_boot())

    assert result is not None
    receipt = _receipt(result)
    assert result["source_route"] == "ORACLE.self_prompt.autonomous"
    assert result["max_steps"] == 1
    assert receipt["actor"] == "ORACLE.self_prompt.autonomous"
    assert receipt["caller"] == "ORACLE.self_prompt.autonomous"
    assert receipt["source_route"] == "ORACLE.self_prompt.autonomous"
    assert receipt["approval_required"] is False
    assert receipt["model_called"] is False
    assert receipt["model_error"] == "model_disabled"
    assert receipt["boundary_check_result"]["inside_sandbox"] is True
    assert receipt["external_send"] is False
    assert receipt["git_push"] is False
    assert receipt["computer_control"] is False
    assert receipt["canon_promotion"] is False


def test_autonomous_loop_self_prompt_write_uses_loop_source_route(monkeypatch, tmp_path):
    import asyncio
    import oracle_server as srv

    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("ORACLE_SELF_PROMPT_DISABLE_MODEL", "1")

    result = asyncio.run(srv._write_autonomous_self_prompt_once(
        "test scheduled loop tick",
        source_route="ORACLE.self_prompt.autonomous_loop",
    ))

    receipt = _receipt(result)
    assert result["source_route"] == "ORACLE.self_prompt.autonomous_loop"
    assert result["max_steps"] == 1
    assert receipt["actor"] == "ORACLE.self_prompt.autonomous_loop"
    assert receipt["caller"] == "ORACLE.self_prompt.autonomous_loop"
    assert receipt["source_route"] == "ORACLE.self_prompt.autonomous_loop"
    assert receipt["approval_required"] is False
    assert receipt["model_called"] is False
    assert receipt["model_error"] == "model_disabled"
    assert receipt["boundary_check_result"]["inside_sandbox"] is True
    assert receipt["external_send"] is False
    assert receipt["git_push"] is False
    assert receipt["computer_control"] is False
    assert receipt["canon_promotion"] is False


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.ai",
        "notes/../../outside.ai",
        r"C:\Windows\Temp\outside.ai",
        "notes/run.sh",
        "notes/run.cmd",
        "notes/run.py",
        "notes/.env",
        "notes/secrets/key.ai",
        "notes/browser profiles/cookies.ai",
    ],
)
def test_operations_block_outside_root_executables_and_secrets(monkeypatch, tmp_path, bad_path):
    _isolate(monkeypatch, tmp_path)

    with pytest.raises(sf.SandboxWriteError):
        sf.write_file(bad_path, "blocked", caller="test")
    with pytest.raises(sf.SandboxWriteError):
        sf.append_file(bad_path, "blocked", caller="test")


def test_read_and_list_files_cover_entire_sandbox(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    written = sf.write_file("handoffs/nested/handoff.ai", "handoff text", action_id="handoff")

    read = sf.read_file(written["final_path"])
    listed = sf.list_files("handoffs", recursive=True)

    assert read["content"] == "handoff text"
    assert read["sha256"] == written["sha256"]
    assert "handoffs/nested/handoff.ai" in {item["relative_path"].replace("\\", "/") for item in listed["files"]}


def test_status_reports_full_freedom_inside_and_hard_wall_outside(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    sf.write_file("notes/play.md", "sandbox note", action_id="play")

    status = sf.sandbox_status()

    assert status["access_status"] == "enabled"
    assert status["workbench_model"] == "full_freedom_inside_sandbox_hard_wall_outside"
    assert status["rules"]["full_freedom_inside_sandbox"] is True
    assert status["rules"]["hard_wall_outside_sandbox"] is True
    assert status["rules"]["delete_mode"] == "soft_delete_to_sandbox_trash"
    assert status["rules"]["permanent_delete_enabled"] is False
    assert "sandbox_ultrasound" in status["capabilities"]
    assert "sandbox_soft_delete" in status["capabilities"]
    assert "sandbox_self_prompt_write" in status["capabilities"]
    assert status["rules"]["sandbox_self_prompt_max_steps"] == 1


def test_append_and_edit_file_receipt_hashes_and_diff(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    written = sf.write_file("drafts/idea.md", "hello old world", caller="test", action_id="draft")

    appended = sf.append_file("drafts/idea.md", "\nsecond line", caller="test", action_id="append")
    edited = sf.edit_file(
        "drafts/idea.md",
        "old",
        "new",
        caller="test",
        action_id="edit_exact",
        expected_sha256=appended["post_operation_sha256"],
    )

    exact_receipt = _receipt(edited)
    assert Path(edited["path"]).read_text(encoding="utf-8") == "hello new world\nsecond line"
    assert appended["pre_operation_sha256"] == written["sha256"]
    assert exact_receipt["edit_mode"] == "exact_text_replace"
    assert "-hello old world" in exact_receipt["diff"]
    assert "+hello new world" in exact_receipt["diff"]

    replaced = sf.edit_file("drafts/idea.md", content="whole replacement", caller="test", action_id="edit_replace")
    replace_receipt = _receipt(replaced)
    assert Path(replaced["path"]).read_text(encoding="utf-8") == "whole replacement"
    assert replace_receipt["edit_mode"] == "replace_content"


def test_edit_file_blocks_missing_exact_patch(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    sf.write_file("drafts/idea.md", "hello old world", caller="test", action_id="draft")

    with pytest.raises(sf.SandboxWriteError):
        sf.edit_file("drafts/idea.md", "missing", "new", caller="test")


def test_rename_file_and_folder_version_destinations(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    sf.write_file("handoffs/source.ai", "source text", caller="test", action_id="source")
    sf.write_file("handoffs/final.ai", "existing text", caller="test", action_id="existing")
    sf.make_folder("workbench/folder_a", caller="test", action_id="folder_a")

    renamed_file = sf.rename_file("handoffs/source.ai", "handoffs/final.ai", caller="test", action_id="rename_source")
    renamed_folder = sf.rename_file("workbench/folder_a", "workbench/folder_b", caller="test", action_id="rename_folder")

    file_receipt = _receipt(renamed_file)
    folder_receipt = _receipt(renamed_folder)
    assert Path(renamed_file["final_path"]).name == "final_v2.ai"
    assert Path(renamed_file["final_path"]).read_text(encoding="utf-8") == "source text"
    assert file_receipt["renamed"] is True
    assert Path(renamed_folder["final_path"]).is_dir()
    assert folder_receipt["renamed"] is True


def test_make_folder_and_soft_delete_to_trash_with_receipt(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    folder = sf.make_folder("workbench/delete_me", caller="test", action_id="mkdir_delete_me")
    sf.write_file("workbench/delete_me/file.ai", "trash me", caller="test", action_id="trash_seed")

    result = sf.sandbox_soft_delete("workbench/delete_me", caller="test", action_id="soft_delete_folder")

    trash_path = Path(result["trash_path"])
    receipt = _receipt(result)
    assert Path(folder["path"]).exists() is False
    assert trash_path.is_dir()
    assert (trash_path / "file.ai").read_text(encoding="utf-8") == "trash me"
    assert receipt["operation_type"] == "sandbox_soft_delete"
    assert receipt["soft_deleted"] is True
    assert receipt["deleted"] is True
    assert receipt["permanent_delete"] is False
    assert receipt["boundary_check_result"]["source_inside_sandbox"] is True
    assert receipt["boundary_check_result"]["target_inside_designated_trash"] is True
    assert receipt["boundary_check_result"]["boundary_ok"] is True


def test_soft_delete_blocks_root_and_receipts_root(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    sf.write_file("notes/seed.ai", "seed", action_id="seed")

    with pytest.raises(sf.SandboxWriteError):
        sf.sandbox_soft_delete(tmp_path / "sandbox")
    with pytest.raises(sf.SandboxWriteError):
        sf.sandbox_soft_delete("receipts")


def test_state_emit_read_journal_tick_and_ultrasound_are_receipted(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    heartbeat = sf.sandbox_emit_state("heartbeat", {"status": "training"}, caller="test", action_id="heartbeat")
    read = sf.sandbox_read_state("heartbeat")
    tick = sf.sandbox_journal_tick("heartbeat without timer", tags=["test"], caller="test", action_id="journal_tick")
    before = sorted(
        (str(path.relative_to(tmp_path / "sandbox")), path.stat().st_mtime_ns)
        for path in (tmp_path / "sandbox").rglob("*")
        if path.exists()
    )
    ultrasound = sf.sandbox_ultrasound()
    after = sorted(
        (str(path.relative_to(tmp_path / "sandbox")), path.stat().st_mtime_ns)
        for path in (tmp_path / "sandbox").rglob("*")
        if path.exists()
    )

    assert Path(heartbeat["path"]).name == "heartbeat.json"
    assert read["state"]["value"] == {"status": "training"}
    assert Path(tick["path"]) == (tmp_path / "sandbox" / "journal" / "oracle_journal.jsonl").resolve()
    tick_receipt = _receipt(tick)
    assert tick_receipt["journal_tick"] is True
    assert tick_receipt["autonomous_timer"] is False
    assert ultrasound["mutated_by_ultrasound"] is False
    assert ultrasound["state"]["heartbeat"]["value"] == {"status": "training"}
    assert ultrasound["recent_journal"][-1]["message"] == "heartbeat without timer"
    assert before == after


def test_reflection_receipt_writes_structured_sandbox_record_and_journal(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    reflection_text = """Reflection receipt:
  what changed: commit ba896c4, 94 dirty file(s)
  what is stuck: GitHub access, STT, qr_scan, web_access, external_send, command_exec
  what Noah is trying: give ORACLE governed executive function (perceive -> classify -> plan -> reflect) without unrestricted autonomy
  safe next action: patch routing before polishing doctrine
  requires approval: state-changing actions, canon promotion, external send, computer control
  leave untouched: the live autostart server, the signed-commit policy, anything out of scope
  highest-value next: patch routing before polishing doctrine

I operate with bounded initiative and receipts, not unrestricted autonomy."""

    result = sf.sandbox_reflection_receipt(
        reflection_text,
        caller="test",
        action_id="reflection_test",
        approved_by="Noah.Physical",
    )

    reflection_path = Path(result["reflection_path"])
    payload = json.loads(reflection_path.read_text(encoding="utf-8"))
    write_receipt = json.loads(Path(result["reflection_write_receipt_path"]).read_text(encoding="utf-8"))
    journal_line = (tmp_path / "sandbox" / "journal" / "oracle_journal.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    journal_event = json.loads(journal_line)

    assert reflection_path == (tmp_path / "sandbox" / "reflections" / "reflection_test.json").resolve()
    assert payload["fields"]["what_is_stuck"] == "GitHub access, STT, qr_scan, web_access, external_send, command_exec"
    assert payload["fields"]["highest_value_next"] == "patch routing before polishing doctrine"
    assert payload["provenance"]["approved_by"] == "Noah.Physical"
    assert payload["canon_status"] == "sandbox_candidate"
    assert payload["promotion_status"] == "not_promoted"
    assert payload["boundary"]["git_push"] is False
    assert payload["boundary"]["external_send"] is False
    assert payload["boundary"]["command_exec"] is False
    assert payload["boundary"]["computer_control"] is False
    assert payload["boundary"]["canon_promotion"] is False
    assert write_receipt["boundary_check_result"]["inside_sandbox"] is True
    assert write_receipt["git_push"] is False
    assert journal_event["event_type"] == "reflection_receipt"
    assert journal_event["reflection_id"] == "reflection_test"


def test_workbench_helpers_write_and_edit_under_workbench(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    written = sf.sandbox_workbench_write("draft.ai", "first", caller="test", action_id="wb_write")
    edited = sf.sandbox_workbench_edit("draft.ai", content="second", caller="test", action_id="wb_edit")

    assert Path(written["final_path"]).parent == (tmp_path / "sandbox" / "workbench").resolve()
    assert Path(edited["path"]).read_text(encoding="utf-8") == "second"


def test_sandbox_api_v2_ultrasound_state_trash_and_file_operations(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)

    status = client.get("/api/sandbox/status")
    assert status.status_code == 200
    assert status.json()["rules"]["full_freedom_inside_sandbox"] is True

    state = client.post("/api/sandbox/state", json={"key": "heartbeat", "value": {"status": "api"}, "caller": "test"})
    assert state.status_code == 200
    assert Path(state.json()["receipt_path"]).exists()

    read_state = client.get("/api/sandbox/state", params={"key": "heartbeat"})
    assert read_state.status_code == 200
    assert read_state.json()["state"]["value"] == {"status": "api"}

    write = client.post("/api/sandbox/write", json={
        "path": "workbench/api_v2.ai",
        "content": "first",
        "caller": "test",
        "action_id": "api_v2_write",
    })
    assert write.status_code == 200

    append = client.post("/api/sandbox/append", json={
        "path": "workbench/api_v2.ai",
        "content": "\nsecond",
        "caller": "test",
        "action_id": "api_v2_append",
    })
    assert append.status_code == 200

    edit = client.post("/api/sandbox/edit", json={
        "path": "workbench/api_v2.ai",
        "content": "third",
        "caller": "test",
        "action_id": "api_v2_edit",
    })
    assert edit.status_code == 200
    assert edit.json()["edit_mode"] == "replace_content"

    mkdir = client.post("/api/sandbox/mkdir", json={"path": "workbench/api_folder", "caller": "test"})
    assert mkdir.status_code == 200

    rename = client.post("/api/sandbox/rename", json={
        "source_path": "workbench/api_v2.ai",
        "destination_path": "workbench/api_folder/renamed.ai",
        "caller": "test",
    })
    assert rename.status_code == 200

    journal = client.post("/api/sandbox/journal", json={
        "content": "explicit api tick",
        "tags": ["api"],
        "caller": "test",
    })
    assert journal.status_code == 200
    assert journal.json()["autonomous_timer"] is False

    reflection = client.post("/api/sandbox/reflection", json={
        "receipt": {
            "what_changed": "api reflection write",
            "what_is_stuck": "GitHub access",
            "safe_next_action": "patch routing before polishing doctrine",
            "highest_value_next": "patch routing before polishing doctrine",
        },
        "caller": "test",
        "action_id": "api_reflection",
        "approved_by": "Noah.Physical",
    })
    assert reflection.status_code == 200
    assert reflection.json()["operation_type"] == "sandbox_reflection_receipt"
    assert Path(reflection.json()["reflection_path"]).exists()
    assert reflection.json()["boundary"]["git_push"] is False

    ultrasound = client.get("/api/sandbox/ultrasound")
    assert ultrasound.status_code == 200
    assert ultrasound.json()["mutated_by_ultrasound"] is False

    trash = client.post("/api/sandbox/trash", json={"path": "workbench/api_folder/renamed.ai", "caller": "test"})
    assert trash.status_code == 200
    assert Path(trash.json()["trash_path"]).exists()

    files = client.get("/api/sandbox/files", params={"path": "workbench", "recursive": "true"})
    assert files.status_code == 200
    assert files.json()["ok"] is True


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        ("/api/sandbox/write", {"path": "../outside.ai", "content": "blocked"}),
        ("/api/sandbox/append", {"path": "notes/run.sh", "content": "blocked"}),
        ("/api/sandbox/mkdir", {"path": r"C:\Windows\Temp\oracle_sandbox_escape"}),
        ("/api/sandbox/trash", {"path": r"C:\Windows\Temp\outside.ai"}),
    ],
)
def test_sandbox_api_blocks_outside_root_and_executables(monkeypatch, tmp_path, url, payload):
    _isolate(monkeypatch, tmp_path)
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    from fastapi.testclient import TestClient
    import oracle_server as srv

    client = TestClient(srv.app)

    response = client.post(url, json={**payload, "caller": "test"})

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_sandbox_chat_commands_use_backend_ultrasound_lanes(monkeypatch, tmp_path):
    import asyncio
    import memory
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    import oracle_server as srv

    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)

    async def collect(prompt: str):
        payloads = []
        async for chunk in srv._stream_reply(prompt):
            if chunk.startswith("data: "):
                payloads.append(json.loads(chunk[len("data: "):].strip()))
        return payloads

    write_payloads = asyncio.run(collect("/sandbox-write workbench/chat_v2.ai | alpha"))
    write_text = "".join(item.get("text", "") for item in write_payloads if item.get("type") == "token")
    assert "SANDBOX WRITE RECEIPT" in write_text
    assert [item for item in write_payloads if item.get("type") == "done"][-1]["effective_route"] == "sandbox_write"

    ai_write_payloads = asyncio.run(collect(".AI:SANDBOX_WRITE workbench/chat_ai_alias.ai | alpha"))
    ai_write_text = "".join(item.get("text", "") for item in ai_write_payloads if item.get("type") == "token")
    assert "SANDBOX WRITE RECEIPT" in ai_write_text
    assert [item for item in ai_write_payloads if item.get("type") == "done"][-1]["effective_route"] == "sandbox_write"

    ai_write_with_initiative_language = asyncio.run(collect(
        ".AI:SANDBOX_WRITE workbench/chat_ai_directive.ai | "
        "Write your own follow-up file in sandbox. This explicit command must not route to initiative."
    ))
    ai_write_with_initiative_text = "".join(
        item.get("text", "") for item in ai_write_with_initiative_language if item.get("type") == "token"
    )
    assert "SANDBOX WRITE RECEIPT" in ai_write_with_initiative_text
    assert [item for item in ai_write_with_initiative_language if item.get("type") == "done"][-1]["effective_route"] == "sandbox_write"

    append_payloads = asyncio.run(collect("/sandbox-append workbench/chat_v2.ai | beta"))
    append_text = "".join(item.get("text", "") for item in append_payloads if item.get("type") == "token")
    assert "SANDBOX APPEND RECEIPT" in append_text

    edit_payloads = asyncio.run(collect("/sandbox-edit workbench/chat_v2.ai | gamma"))
    edit_text = "".join(item.get("text", "") for item in edit_payloads if item.get("type") == "token")
    assert "SANDBOX EDIT RECEIPT" in edit_text

    mkdir_payloads = asyncio.run(collect("/sandbox-mkdir workbench/chat_folder"))
    mkdir_text = "".join(item.get("text", "") for item in mkdir_payloads if item.get("type") == "token")
    assert "SANDBOX FOLDER RECEIPT" in mkdir_text

    rename_payloads = asyncio.run(collect("/sandbox-rename workbench/chat_v2.ai | workbench/chat_folder/chat_done.ai"))
    rename_text = "".join(item.get("text", "") for item in rename_payloads if item.get("type") == "token")
    assert "SANDBOX RENAME RECEIPT" in rename_text

    tick_payloads = asyncio.run(collect("/sandbox-journal-tick explicit tick only"))
    tick_text = "".join(item.get("text", "") for item in tick_payloads if item.get("type") == "token")
    assert "SANDBOX JOURNAL RECEIPT" in tick_text
    assert [item for item in tick_payloads if item.get("type") == "done"][-1]["effective_route"] == "sandbox_journal_tick"

    reflect_payloads = asyncio.run(collect("/sandbox-reflect what changed: chat reflection | safe next action: patch routing"))
    reflect_text = "".join(item.get("text", "") for item in reflect_payloads if item.get("type") == "token")
    assert "SANDBOX REFLECTION RECEIPT" in reflect_text
    assert [item for item in reflect_payloads if item.get("type") == "done"][-1]["effective_route"] == "sandbox_reflection_receipt"

    initiative_payloads = asyncio.run(collect("write to your sandbox"))
    initiative_text = "".join(item.get("text", "") for item in initiative_payloads if item.get("type") == "token")
    initiative_done = [item for item in initiative_payloads if item.get("type") == "done"][-1]
    assert "SANDBOX INITIATIVE RECEIPT" in initiative_text
    assert initiative_done["effective_route"] == "sandbox_initiative_write"

    monkeypatch.setenv("ORACLE_SELF_PROMPT_DISABLE_MODEL", "1")
    self_prompt_payloads = asyncio.run(collect("/self-prompt-sandbox prove one step"))
    self_prompt_text = "".join(item.get("text", "") for item in self_prompt_payloads if item.get("type") == "token")
    self_prompt_done = [item for item in self_prompt_payloads if item.get("type") == "done"][-1]
    assert "SANDBOX SELF-PROMPT RECEIPT" in self_prompt_text
    assert '"source_route": "ORACLE.self_prompt"' in self_prompt_text
    assert '"max_steps": 1' in self_prompt_text
    assert self_prompt_done["effective_route"] == "sandbox_self_prompt"

    journal_payloads = asyncio.run(collect("/sandbox-journal"))
    journal_text = "".join(item.get("text", "") for item in journal_payloads if item.get("type") == "token")
    assert "SANDBOX JOURNAL" in journal_text

    ultrasound_payloads = asyncio.run(collect("/sandbox-ultrasound"))
    ultrasound_text = "".join(item.get("text", "") for item in ultrasound_payloads if item.get("type") == "token")
    assert "SANDBOX ULTRASOUND" in ultrasound_text

    trash_payloads = asyncio.run(collect("/sandbox-trash workbench/chat_folder/chat_done.ai"))
    trash_text = "".join(item.get("text", "") for item in trash_payloads if item.get("type") == "token")
    assert "SANDBOX TRASH RECEIPT" in trash_text
