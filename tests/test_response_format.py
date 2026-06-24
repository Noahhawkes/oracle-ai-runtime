import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

import response_format as rf


def test_long_text_splits_into_short_paragraphs():
    text = " ".join(f"Sentence number {i} is here." for i in range(1, 11))
    out = rf.format_response(text, max_sentences=4)
    paras = [p for p in out.split("\n\n") if p.strip()]
    assert len(paras) >= 3  # 10 sentences / 4 per paragraph
    for p in paras:
        assert p.count(".") <= 4


def test_useful_lists_are_preserved():
    text = "Here are the roots:\n- C:/Oracle\n- C:/ORACLE.AI\n- OneDrive"
    out = rf.format_response(text)
    assert "- C:/Oracle" in out
    assert "- C:/ORACLE.AI" in out
    # Adjacent list items stay tight (no blank line injected between them).
    assert "- C:/Oracle\n- C:/ORACLE.AI" in out


def test_raw_json_dump_is_suppressed_by_default():
    raw = '{"files_seen": 42, "credential_risk": 1, "cloud_upload": false, "git_commit": false}'
    out = rf.format_response(raw)
    assert "files_seen" not in out
    assert "Status:" in out
    assert "raw output" in out.lower()


def test_traceback_is_suppressed_by_default():
    raw = 'Traceback (most recent call last):\n  File "x.py", line 1, in <module>\n    boom()\nNameError: boom'
    out = rf.format_response(raw)
    assert "Traceback" not in out
    assert "raw output" in out.lower()


def test_allow_raw_keeps_machine_output():
    raw = '{"a": 1, "b": 2, "c": 3}'
    out = rf.format_response(raw, allow_raw=True)
    assert '"a": 1' in out


def test_fenced_raw_block_inside_prose_is_replaced():
    text = (
        "Here is the result of the scan for you to review.\n\n"
        '```json\n{"files_seen": 42, "credential_risk": 1, "duplicate": 0}\n```\n\n'
        "Let me know if you want to promote anything."
    )
    out = rf.format_response(text)
    assert "files_seen" not in out
    assert "review" in out.lower()
    assert "promote" in out.lower()
    assert rf.RAW_SUPPRESSED_NOTE in out


def test_fenced_prose_block_is_kept():
    text = "Note this:\n\n```\nObserve many. Promote few.\n```\n\nThat is the law."
    out = rf.format_response(text)
    assert "Observe many. Promote few." in out


def test_format_structured_canonical_shape():
    out = rf.format_structured(
        "Scan complete.",
        what_i_saw="Three ORACLE files, one credential-risk file.",
        what_it_means="Nothing was promoted; the credential file is quarantined.",
        next_move="Review the intake before promotion.",
    )
    assert "**Status:**" in out
    assert "**What I saw:**" in out
    assert "**What it means:**" in out
    assert "**Next move:**" in out
    # Sections are separated by blank lines for readability.
    assert "\n\n" in out


def test_format_structured_omits_empty_sections():
    out = rf.format_structured("All good.")
    assert "**Status:**" in out
    assert "**What I saw:**" not in out


def test_format_uncertainty_labels_known_inferred_unknown():
    out = rf.format_uncertainty(
        known=["Server reachable on 127.0.0.1:7781"],
        inferred=["Port 7782 is the intended frontend"],
        unknown=["Contents of the lost thread"],
    )
    assert "**Known:**" in out
    assert "**Inferred:**" in out
    assert "**Unknown:**" in out


def test_status_top_line_is_prepended():
    out = rf.format_response("It worked fine.", status="Done.")
    assert out.startswith("**Status:** Done.")


def test_empty_text_is_safe():
    assert rf.format_response("") == "(no response)"


def test_is_raw_dump_detection():
    assert rf.is_raw_dump('{"a": 1, "b": 2}') is True
    assert rf.is_raw_dump("This is a normal human sentence.") is False


# ── compose_fallback (the witness voice when the local model times out) ─────────

def test_compose_fallback_acceptance_paragraph_not_status_line():
    out = rf.compose_fallback(
        "Oracle barely talks. Why can't she give me a paragraph?",
        recent_turns=[{"role": "user", "text": "hi"}, {"role": "oracle", "text": "hello"}],
        oracle_state={"cognition": "local_ready", "memory": 46, "mode": "Capture"},
    )
    # Not the old kazoo one-liner.
    assert out != "ORACLE awake."
    assert "\n\n" in out                      # multiple paragraphs
    assert "I heard you" in out               # acknowledges Noah
    assert "local model didn't answer" in out # honest, gentle fallback
    assert "recent thread" in out             # still answers from the thread
    assert "paragraph" in out.lower()


def test_compose_fallback_translates_state_to_human_language():
    out = rf.compose_fallback("status?", oracle_state={"memory": 46, "mode": "Capture"})
    assert "46" in out
    assert "Capture" in out
    assert "memory_count" not in out          # no raw key names leak


def test_compose_fallback_never_claims_memory_write():
    out = rf.compose_fallback("remember this please")
    assert "written to durable memory" in out  # explicit non-claim present
    assert "saved to memory" not in out.lower()


def test_compose_fallback_is_deterministic():
    a = rf.compose_fallback("same", oracle_state={"memory": 1})
    b = rf.compose_fallback("same", oracle_state={"memory": 1})
    assert a == b


def test_compose_fallback_includes_command_result():
    out = rf.compose_fallback("did it work?", command_result={"summary": "scan complete, 3 files"})
    assert "scan complete, 3 files" in out


def test_compose_fallback_handles_empty_input():
    out = rf.compose_fallback("")
    assert len(out) > 0
    assert "machine receipt" in out.lower()


def test_compose_fallback_suppresses_timeout_when_not_relevant():
    out = rf.compose_fallback("hi", oracle_state={"local_timeout": False})
    assert "local model didn't answer" not in out
    assert "recent thread" in out


# ── build_thread_response (voice-only POST /thread/respond handler) ─────────────

def test_thread_response_uses_model_text_when_present():
    out = rf.build_thread_response(
        "hi", model_text="Here is a clean paragraph answer.", used_model=True
    )
    assert out["status"] == "ok"
    assert "clean paragraph answer" in out["human_response"]
    assert out["machine_receipt"]["fallback_used"] is False
    assert out["machine_receipt"]["used_local_model"] is True


def test_thread_response_falls_back_without_model_text():
    out = rf.build_thread_response(
        "Oracle barely talks. Why can't she give me a paragraph?",
        recent_turns=[{"role": "user", "content": "hi"}],
        oracle_state={"mode": "capture", "cognition": "local_ready", "memory": 46},
    )
    assert out["status"] == "ok"
    assert "\n\n" in out["human_response"]            # readable paragraphs
    assert out["machine_receipt"]["fallback_used"] is True
    assert out["machine_receipt"]["used_local_model"] is False
    assert out["machine_receipt"]["used_thread"] is True


def test_thread_response_is_voice_only_never_writes_or_acts():
    out = rf.build_thread_response("anything", model_text="ok")
    assert out["machine_receipt"]["memory_written"] is False
    assert out["machine_receipt"]["actions_taken"] == []


def test_thread_response_suppresses_raw_model_dump():
    out = rf.build_thread_response(
        "status?", model_text='{"files_seen": 42, "git_commit": false, "cloud": false}'
    )
    assert "files_seen" not in out["human_response"]


def test_thread_response_used_thread_false_without_turns():
    out = rf.build_thread_response("hi", model_text="hello")
    assert out["machine_receipt"]["used_thread"] is False
