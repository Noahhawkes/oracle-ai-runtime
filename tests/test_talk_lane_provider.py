"""Talk-lane provider reroute (TALK_LANE_PROVIDER_REROUTE_V1).

Proves the opt-in frontier "mouth" for NOAH_DIRECT:
  - default (flag unset) behavior is a byte-identical no-op (local Ollama, qwen, cap 260)
  - ORACLE_TALK_PROVIDER=anthropic routes generation to the Anthropic client (mocked)
  - it fails SAFE to local on missing key / forced-local / provider error
  - the assembled grounding prompt is identical across providers
  - routing gates stay in front (action requests never reach the talk model)
  - independence guard (ORACLE_FORCE_LOCAL) still refuses cloud
  - the API key never leaks into the returned answer

No live API call is made; the provider is mocked throughout.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")

import oracle_server as srv  # noqa: E402
import llm  # noqa: E402

SENTINEL_KEY = "sk-ant-TALK-LANE-SENTINEL-DO-NOT-LEAK"


# ── helpers ─────────────────────────────────────────────────────────────────

class _FakeResp:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def _capture_local(monkeypatch):
    """Patch the Ollama HTTP call; return a dict that captures the sent payload."""
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp({"response": "LOCAL_OK"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


def _fake_anthropic(monkeypatch, capture: dict, text: str = "FRONTIER_OK"):
    """Patch llm.make_anthropic_client to return a mock client capturing kwargs."""
    class _Block:
        def __init__(self, t):
            self.text = t

    class _Msgs:
        def create(self, **kwargs):
            capture.update(kwargs)
            return types.SimpleNamespace(content=[_Block(text)])

    class _Client:
        messages = _Msgs()

    monkeypatch.setattr(llm, "make_anthropic_client", lambda: _Client())


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("ORACLE_TALK_PROVIDER", "ORACLE_TALK_MODEL", "ORACLE_TALK_MAX_TOKENS",
              "ORACLE_NOAH_DIRECT_MODEL", "ORACLE_FORCE_LOCAL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── tests ───────────────────────────────────────────────────────────────────

def test_default_flag_unset_is_local_noop(monkeypatch):
    cap = _capture_local(monkeypatch)
    # If anything tries the frontier with the flag unset, fail loudly.
    monkeypatch.setattr(srv, "_noah_direct_anthropic_reply",
                        lambda *a, **k: pytest.fail("frontier called with flag unset"))
    out = srv._noah_direct_reply("just saying hi")
    assert out == "LOCAL_OK"
    assert cap["url"] == "http://127.0.0.1:11434/api/generate"
    assert cap["payload"]["model"] == "qwen2.5:7b"
    assert cap["payload"]["options"]["num_predict"] == 260


def test_provider_anthropic_with_key_hits_frontier(monkeypatch):
    cap_local = _capture_local(monkeypatch)  # should stay untouched
    cap_call: dict = {}
    _fake_anthropic(monkeypatch, cap_call, text="FRONTIER_OK")
    monkeypatch.setenv("ORACLE_TALK_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)

    out = srv._noah_direct_reply("hello oracle")
    assert out == "FRONTIER_OK"
    assert cap_call.get("model") == llm.DEFAULT_CLOUD_MODEL
    assert cap_call.get("messages") == [{"role": "user", "content": "hello oracle"}]
    assert "url" not in cap_local  # local Ollama path was NOT used


def test_provider_anthropic_missing_key_falls_back_local(monkeypatch):
    cap = _capture_local(monkeypatch)
    monkeypatch.setenv("ORACLE_TALK_PROVIDER", "anthropic")
    # no ANTHROPIC_API_KEY set
    out = srv._noah_direct_reply("hi there")
    assert out == "LOCAL_OK"
    assert cap["payload"]["model"] == "qwen2.5:7b"


def test_provider_error_falls_back_local(monkeypatch):
    cap = _capture_local(monkeypatch)
    monkeypatch.setenv("ORACLE_TALK_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)

    def boom():
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm, "make_anthropic_client", boom)
    out = srv._noah_direct_reply("hi there")
    assert out == "LOCAL_OK"  # safe fallback, no crash


def test_grounding_prompt_identical_across_providers(monkeypatch):
    # local capture
    cap_local = _capture_local(monkeypatch)
    srv._noah_direct_reply("what is the plan today")
    local_prompt = cap_local["payload"]["prompt"]

    # anthropic capture (same input)
    cap_call: dict = {}
    _fake_anthropic(monkeypatch, cap_call)
    monkeypatch.setenv("ORACLE_TALK_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    srv._noah_direct_reply("what is the plan today")
    frontier_system = cap_call["system"]

    assert frontier_system == local_prompt  # grounding is byte-identical


def test_action_request_never_reaches_talk_model():
    action = "commit and push everything to github now"
    assert srv._noah_direct_is_action_request(action.lower()) is True
    assert srv._noah_direct_should_handle(action) is False


def test_talk_output_is_inert_text(monkeypatch):
    cap_call: dict = {}
    _fake_anthropic(monkeypatch, cap_call)
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    result = srv._noah_direct_anthropic_reply("system prompt here", "hello", 260)
    # The talk mouth returns plain text only — never an action handle/object.
    assert isinstance(result, str)


def test_force_local_refuses_cloud(monkeypatch):
    monkeypatch.setenv("ORACLE_FORCE_LOCAL", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    # llm factory raises under forced-local
    with pytest.raises(RuntimeError):
        llm.make_anthropic_client()
    # and the talk helper declines to cloud (returns None -> caller falls back local)
    assert srv._noah_direct_anthropic_reply("sys", "hi", 260) is None


def test_api_key_never_leaks_into_answer(monkeypatch):
    cap_call: dict = {}
    _fake_anthropic(monkeypatch, cap_call, text="here is your answer")
    monkeypatch.setenv("ORACLE_TALK_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    out = srv._noah_direct_reply("say something")
    assert SENTINEL_KEY not in out
