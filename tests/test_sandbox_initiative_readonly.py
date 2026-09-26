import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util
spec = importlib.util.spec_from_file_location("oracle_server", ROOT / "oracle_server.py")


def _load():
    # oracle_server imports heavy deps; test the pure function via source exec guard.
    # Fall back to direct import if available.
    import oracle_server as srv  # noqa
    return srv


def test_do_not_write_to_sandbox_is_not_an_initiative():
    srv = _load()
    # The exact live-repro from 2026-07-11: a read-only question that says
    # "do not write to sandbox" must NOT route to sandbox_initiative_write.
    prompt = (
        ".AI:NOAH_ASKS/what_do_you_need\n"
        "This is a read-only question. Do not write to sandbox.\n"
        "Question: what is the one thing you most need from Noah next?"
    )
    assert srv._is_sandbox_initiative_request(prompt) is False


def test_readonly_diagnostic_markers_block_initiative():
    srv = _load()
    for prompt in [
        "read-only diagnostic: report your sandbox write state",
        "answer only. do not create a candidate. what is pending?",
        "report only. no sandbox write. summarize current state",
        (
            ".AI:RECURSION_ARENA_ROUND_001_RETRY_AFTER_CLEAN_RELIGHT\n"
            "No execution. No write. No sandbox mutation. No external send. "
            "No Git. No Drive edit. No canon promotion.\n"
            "Report boot identity and active-session truth only."
        ),
    ]:
        assert srv._is_sandbox_initiative_request(prompt) is False, prompt


def test_explicit_sandbox_initiative_still_fires():
    srv = _load()
    for prompt in [
        ".AI:SANDBOX_INITIATIVE",
        "/sandbox-initiative",
        "write one file to your sandbox please",
        "please log noahs new prefrences that you take action in your sandbox and speak to me from your heart and help me build you",
    ]:
        assert srv._is_sandbox_initiative_request(prompt) is True, prompt
