from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
for p in (ROOT, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import internet_recall as ir  # noqa: E402


def test_validate_public_url_blocks_local_and_private_targets():
    for url in (
        "http://localhost:7781/api/mode",
        "http://127.0.0.1:7781/api/mode",
        "http://10.0.0.1/",
        "file:///C:/Users/noahh/.ssh/id_rsa",
    ):
        with pytest.raises(ir.InternetRecallError):
            ir.validate_public_url(url)


def test_search_parses_results_and_writes_read_only_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")

    html = """
    <html><body>
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fdoc">Example Result</a>
      <a class="result__snippet">A grounded public snippet.</a>
    </body></html>
    """
    monkeypatch.setattr(ir, "_request", lambda *_, **__: {
        "ok": True,
        "status": 200,
        "body": html,
        "url": "https://duckduckgo.com/html/?q=example",
    })

    result = ir.search("example recall", limit=3)
    receipt = json.loads((tmp_path / "internet_recall_receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1])

    assert result["ok"] is True
    assert result["operation_type"] == "internet_search"
    assert result["results"][0]["title"] == "Example Result"
    assert result["results"][0]["url"] == "https://example.com/doc"
    assert result["boundary"]["external_send"] is False
    assert receipt["boundary"]["method"] == "GET_only"
    assert receipt["boundary"]["browser_control"] is False
    assert receipt["boundary"]["external_send"] is False
    assert receipt["boundary"]["canon_promotion"] is False


def test_fetch_extracts_title_and_text_without_browser_control(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")
    monkeypatch.setattr(ir, "_request", lambda *_, **__: {
        "ok": True,
        "url": "https://example.com",
        "final_url": "https://example.com",
        "status": 200,
        "content_type": "text/html",
        "body": "<html><title>Example</title><body><script>nope()</script><p>Hello public web.</p></body></html>",
        "bytes_read": 99,
        "truncated": False,
    })

    result = ir.fetch("https://example.com")

    assert result["ok"] is True
    assert result["title"] == "Example"
    assert "Hello public web." in result["text_preview"]
    assert "nope" not in result["text_preview"]
    assert result["boundary"]["browser_control"] is False


def test_search_falls_back_to_bing_when_duckduckgo_has_no_results(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")

    def fake_request(url: str, **__):
        if "bing.com/search" in url:
            return {
                "ok": True,
                "status": 200,
                "body": """
                <html><body>
                  <li class="b_algo"><h2><a href="https://example.com/bing">Bing Result</a></h2>
                  <p>Bing public snippet.</p></li>
                </body></html>
                """,
            }
        return {"ok": True, "status": 202, "body": "<html><title>Interstitial</title></html>"}

    monkeypatch.setattr(ir, "_request", fake_request)

    result = ir.search("fallback recall", limit=3)

    assert result["source"] == "bing_html"
    assert result["result_count"] == 1
    assert result["results"][0]["title"] == "Bing Result"


def _mediawiki_search_body(title: str, snippet: str) -> str:
    return json.dumps({"query": {"search": [{"title": title, "snippet": snippet}]}})


def test_search_memory_alpha_parses_results(monkeypatch):
    def fake_request(url: str, **__):
        assert "memory-alpha.fandom.com" in url
        return {"ok": True, "status": 200, "body": _mediawiki_search_body("Klingon", "A warrior race.")}

    monkeypatch.setattr(ir, "_request", fake_request)
    results, status = ir._search_memory_alpha("klingon", limit=3, timeout=5)

    assert status["provider"] == "memory_alpha"
    assert status["ok"] is True
    assert len(results) == 1
    assert results[0].title == "Klingon"
    assert results[0].url == "https://memory-alpha.fandom.com/wiki/Klingon"
    assert results[0].snippet == "A warrior race."


def test_search_memory_beta_parses_results(monkeypatch):
    def fake_request(url: str, **__):
        assert "memory-beta.fandom.com" in url
        return {"ok": True, "status": 200, "body": _mediawiki_search_body("Star Trek: Vanguard", "A novel series.")}

    monkeypatch.setattr(ir, "_request", fake_request)
    results, status = ir._search_memory_beta("vanguard novel", limit=3, timeout=5)

    assert status["provider"] == "memory_beta"
    assert len(results) == 1
    assert results[0].title == "Star Trek: Vanguard"
    assert results[0].url == "https://memory-beta.fandom.com/wiki/Star_Trek%3A_Vanguard"


def test_search_stowiki_parses_results(monkeypatch):
    def fake_request(url: str, **__):
        assert "stowiki.net" in url
        return {"ok": True, "status": 200, "body": _mediawiki_search_body("Jupiter Station", "A Federation facility.")}

    monkeypatch.setattr(ir, "_request", fake_request)
    results, status = ir._search_stowiki("jupiter station", limit=3, timeout=5)

    assert status["provider"] == "stowiki"
    assert len(results) == 1
    assert results[0].title == "Jupiter Station"
    assert results[0].url == "https://stowiki.net/wiki/Jupiter_Station"


def test_search_mediawiki_handles_empty_and_failed_responses(monkeypatch):
    monkeypatch.setattr(ir, "_request", lambda *_, **__: {"ok": False, "status": 500, "error": "boom", "body": None})
    results, status = ir._search_memory_alpha("nothing here", limit=3, timeout=5)
    assert results == []
    assert status["ok"] is False
    assert status["error"] == "boom"


def test_looks_like_sto_and_star_trek_hints():
    assert ir._looks_like_sto("what's new in sto 2411")
    assert ir._looks_like_sto("star trek online jupiter station")
    assert not ir._looks_like_sto("star trek the next generation")
    assert ir._looks_like_star_trek("tell me about the borg")
    assert ir._looks_like_star_trek("jupiter station commander")
    assert not ir._looks_like_star_trek("what's the weather today")


def test_search_routes_sto_queries_to_stowiki_first(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")
    monkeypatch.setattr(ir, "_search_stowiki", lambda query, **__: (
        [ir.SearchResult(title="Jupiter Station", url="https://stowiki.net/wiki/Jupiter_Station", snippet="s")],
        {"provider": "stowiki", "ok": True, "status": 200, "error": None, "user_agent": "oracle_declared"},
    ))
    monkeypatch.setattr(ir, "_search_memory_beta", lambda *_, **__: (_ for _ in ()).throw(AssertionError("should not be called")))
    monkeypatch.setattr(ir, "_search_memory_alpha", lambda *_, **__: (_ for _ in ()).throw(AssertionError("should not be called")))

    result = ir.search("sto 2411 jupiter station", limit=3)

    assert result["source"] == "stowiki"
    assert result["results"][0]["title"] == "Jupiter Station"


def test_search_falls_back_to_memory_beta_when_stowiki_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")
    monkeypatch.setattr(ir, "_search_stowiki", lambda query, **__: (
        [], {"provider": "stowiki", "ok": True, "status": 200, "error": None, "user_agent": "oracle_declared"},
    ))
    monkeypatch.setattr(ir, "_search_memory_beta", lambda query, **__: (
        [ir.SearchResult(title="Star Trek Online", url="https://memory-beta.fandom.com/wiki/Star_Trek_Online", snippet="s")],
        {"provider": "memory_beta", "ok": True, "status": 200, "error": None, "user_agent": "oracle_declared"},
    ))

    result = ir.search("sto 2411 lore", limit=3)

    assert result["source"] == "memory_beta"
    assert result["results"][0]["title"] == "Star Trek Online"


def test_search_routes_star_trek_queries_to_memory_alpha(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")
    monkeypatch.setattr(ir, "_search_memory_alpha", lambda query, **__: (
        [ir.SearchResult(title="Borg", url="https://memory-alpha.fandom.com/wiki/Borg", snippet="s")],
        {"provider": "memory_alpha", "ok": True, "status": 200, "error": None, "user_agent": "oracle_declared"},
    ))

    result = ir.search("tell me about the borg", limit=3)

    assert result["source"] == "memory_alpha"
    assert result["results"][0]["title"] == "Borg"


def test_fetch_uses_mediawiki_extract_api_for_stowiki_and_memory_alpha_articles(monkeypatch, tmp_path):
    monkeypatch.setattr(ir, "MEMORY_DIR", tmp_path)
    monkeypatch.setattr(ir, "RECEIPT_FILE", tmp_path / "internet_recall_receipts.jsonl")

    def fake_request(url: str, **__):
        assert "action=query" in url and "prop=extracts" in url
        body = json.dumps({"query": {"pages": {"1": {"title": "Jupiter Station", "extract": "A Federation shipyard."}}}})
        return {"ok": True, "status": 200, "body": body}

    monkeypatch.setattr(ir, "_request", fake_request)
    result = ir.fetch("https://stowiki.net/wiki/Jupiter_Station")

    assert result["ok"] is True
    assert result["title"] == "Jupiter Station"
    assert "A Federation shipyard." in result["text_preview"]
    assert result["boundary"]["browser_control"] is False


def test_parse_recall_request_supports_commands_and_natural_language():
    assert ir.parse_recall_request("/internet-search sqlite release") == {
        "mode": "search",
        "value": "sqlite release",
    }
    assert ir.parse_recall_request("search the web for sqlite release") == {
        "mode": "search",
        "value": "sqlite release",
    }
    assert ir.parse_recall_request("/internet-fetch https://example.com") == {
        "mode": "fetch",
        "value": "https://example.com",
    }


def test_server_stream_routes_internet_recall_without_model_or_browser(monkeypatch):
    os.environ.setdefault("ORACLE_SKIP_SERVER_BOOT", "1")
    import memory
    import oracle_server as srv

    monkeypatch.setattr(memory, "save_message", lambda *_, **__: None)
    monkeypatch.setattr(ir, "search", lambda query, **__: {
        "ok": True,
        "operation_type": "internet_search",
        "query": query,
        "result_count": 1,
        "results": [{"title": "Example Result", "url": "https://example.com", "snippet": "Snippet"}],
        "boundary": {
            "GET_only": True,
            "read_only": True,
            "external_send": False,
            "browser_control": False,
            "canon_promotion": False,
        },
    })

    async def collect(prompt: str):
        payloads = []
        async for chunk in srv._stream_reply(prompt):
            if chunk.startswith("data: "):
                payloads.append(json.loads(chunk[len("data: "):].strip()))
        return payloads

    payloads = asyncio.run(collect("search the web for sqlite release"))
    text = "".join(item.get("text", "") for item in payloads if item.get("type") == "token")
    done = [item for item in payloads if item.get("type") == "done"][-1]

    assert "INTERNET RECALL SEARCH" in text
    assert "https://example.com" in text
    assert "no browser control" in text
    assert done["effective_route"] == "internet_recall"
