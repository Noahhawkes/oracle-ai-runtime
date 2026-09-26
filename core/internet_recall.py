"""Governed read-only internet recall for ORACLE.

This is not browser automation. It performs bounded HTTP GET requests for
search/result recall, records local receipts, and never submits forms, uses
cookies, controls a browser, uploads, logs in, or sends external messages.
"""
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    from root import ROOT as RUNTIME_ROOT
except Exception:  # pragma: no cover
    RUNTIME_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIR = RUNTIME_ROOT / "Memory"
RECEIPT_FILE = MEMORY_DIR / "internet_recall_receipts.jsonl"

USER_AGENT = "ORACLE.AI internet_recall/1.0 read-only"
# DuckDuckGo/Bing serve a bot-challenge page (HTTP 202 / empty shell) to
# non-browser user agents, so HTML search endpoints get a generic browser UA.
# MediaWiki APIs (Wikipedia, Memory Alpha) get the honest ORACLE UA, which
# their API etiquette prefers. The UA class used is recorded per provider.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
SEARCH_ENDPOINT = "https://duckduckgo.com/html/"
BING_ENDPOINT = "https://www.bing.com/search"
WIKIPEDIA_API_ENDPOINT = "https://en.wikipedia.org/w/api.php"
MEMORY_ALPHA_API_ENDPOINT = "https://memory-alpha.fandom.com/api.php"
MEMORY_ALPHA_ARTICLE_BASE = "https://memory-alpha.fandom.com/wiki/"
MEMORY_BETA_API_ENDPOINT = "https://memory-beta.fandom.com/api.php"
MEMORY_BETA_ARTICLE_BASE = "https://memory-beta.fandom.com/wiki/"
STOWIKI_API_ENDPOINT = "https://stowiki.net/w/api.php"
STOWIKI_ARTICLE_BASE = "https://stowiki.net/wiki/"

# Star Trek Online / licensed-works queries route to STOwiki (game canon)
# and Memory Beta (novels, comics, games) before the screen-canon wiki.
STO_HINTS = ("star trek online", "stowiki", "sto ", " sto", "2409", "2410", "2411")

# Queries matching any of these route to Memory Alpha (the canon Star Trek
# wiki) first, so ORACLE answers Trek questions from the deepest source.
STAR_TREK_HINTS = (
    "star trek", "startrek", "starfleet", "jupiter station", "memory alpha",
    "klingon", "vulcan", "romulan", "cardassian", "ferengi", "borg",
    "holodeck", "tricorder", "delta quadrant", "gamma quadrant",
    "prime directive", "united federation of planets", "q continuum",
    "deep space nine", "ds9", "uss voyager", "voyager", "ncc-1701",
    "warp core", "warp nacelle", "picard", "janeway", "sisko", "riker",
    "worf", "spock", "captain kirk", "lcars", "dilithium", "replicator",
)
MAX_QUERY_CHARS = 240
MAX_URL_CHARS = 2048
MAX_FETCH_BYTES = 256_000
MAX_TEXT_CHARS = 8000
DEFAULT_TIMEOUT = 8

BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}
BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".lan", ".home")


class InternetRecallError(ValueError):
    """Raised when internet recall would violate the read-only boundary."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class _ResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._active_href: str | None = None
        self._active_title: list[str] = []
        self._snippet: list[str] = []
        self._in_result_anchor = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: v or "" for k, v in attrs}
        cls = attrs_d.get("class", "")
        if tag == "a" and attrs_d.get("href"):
            href = attrs_d["href"]
            if "result__a" in cls or "result-link" in cls or "/l/?" in href or "uddg=" in href:
                self._active_href = _unwrap_duckduckgo_url(href)
                self._active_title = []
                self._in_result_anchor = True
        if tag in {"a", "td", "div"} and ("result__snippet" in cls or "result-snippet" in cls):
            self._snippet = []
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_anchor:
            title = _clean_text(" ".join(self._active_title))
            if title and self._active_href and _is_public_http_url(self._active_href, resolve_dns=False):
                if not any(r.url == self._active_href for r in self.results):
                    self.results.append(SearchResult(title=title, url=self._active_href))
            self._active_href = None
            self._active_title = []
            self._in_result_anchor = False
        if self._capture_snippet and tag in {"a", "td", "div"}:
            snippet = _clean_text(" ".join(self._snippet))
            if snippet and self.results and not self.results[-1].snippet:
                self.results[-1].snippet = snippet
            self._snippet = []
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._in_result_anchor:
            self._active_title.append(data)
        if self._capture_snippet:
            self._snippet.append(data)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: list[str] = []
        self.text: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title.append(data)
        else:
            self.text.append(data)


class _BingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_algo = False
        self._active_href: str | None = None
        self._active_title: list[str] = []
        self._capture_snippet = False
        self._snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: v or "" for k, v in attrs}
        cls = attrs_d.get("class", "")
        if tag == "li" and "b_algo" in cls:
            self._in_algo = True
        elif self._in_algo and tag == "a" and attrs_d.get("href"):
            href = html.unescape(attrs_d["href"])
            if _is_public_http_url(href, resolve_dns=False) and "bing.com" not in urllib.parse.urlparse(href).netloc.lower():
                self._active_href = href
                self._active_title = []
        elif self._in_algo and tag == "p":
            self._capture_snippet = True
            self._snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_href:
            title = _clean_text(" ".join(self._active_title))
            if title and not any(r.url == self._active_href for r in self.results):
                self.results.append(SearchResult(title=title, url=self._active_href))
            self._active_href = None
            self._active_title = []
        elif tag == "p" and self._capture_snippet:
            snippet = _clean_text(" ".join(self._snippet))
            if snippet and self.results and not self.results[-1].snippet:
                self.results[-1].snippet = snippet
            self._capture_snippet = False
            self._snippet = []
        elif tag == "li" and self._in_algo:
            self._in_algo = False

    def handle_data(self, data: str) -> None:
        if self._active_href:
            self._active_title.append(data)
        if self._capture_snippet:
            self._snippet.append(data)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _unwrap_duckduckgo_url(url: str) -> str:
    parsed = urllib.parse.urlparse(html.unescape(url))
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return urllib.parse.urljoin("https://duckduckgo.com", html.unescape(url))


def _host_is_blocked(host: str, *, resolve_dns: bool = True) -> bool:
    normalized = (host or "").strip().lower().rstrip(".")
    if not normalized:
        return True
    if normalized in BLOCKED_HOSTS or any(normalized.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(normalized.strip("[]"))
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        pass
    if not resolve_dns:
        return False
    try:
        infos = socket.getaddrinfo(normalized, None, proto=socket.IPPROTO_TCP)
    except Exception:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _is_public_http_url(url: str, *, resolve_dns: bool = True) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and not _host_is_blocked(parsed.hostname or "", resolve_dns=resolve_dns)


def validate_public_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        raise InternetRecallError("url is required")
    if len(value) > MAX_URL_CHARS:
        raise InternetRecallError("url is too long")
    if not urllib.parse.urlparse(value).scheme:
        value = "https://" + value
    if not _is_public_http_url(value):
        raise InternetRecallError("only public http/https URLs are allowed")
    return value


def _request(url: str, *, timeout: int = DEFAULT_TIMEOUT, max_bytes: int = MAX_FETCH_BYTES,
             user_agent: str = USER_AGENT) -> dict[str, Any]:
    safe_url = validate_public_url(url)
    req = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.2",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = validate_public_url(resp.geturl())
            raw = resp.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            return {
                "ok": True,
                "url": safe_url,
                "final_url": final_url,
                "status": getattr(resp, "status", 200),
                "content_type": resp.headers.get("Content-Type", ""),
                "body": raw.decode("utf-8", errors="replace"),
                "bytes_read": len(raw),
                "truncated": truncated,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": safe_url,
            "status": exc.code,
            "error": f"HTTPError:{exc.code}",
            "body": exc.read(min(max_bytes, 4096)).decode("utf-8", errors="replace"),
        }
    except Exception as exc:
        return {"ok": False, "url": safe_url, "status": None, "error": f"{type(exc).__name__}: {exc}", "body": ""}


def _strip_tags(value: str) -> str:
    return _clean_text(re.sub(r"<[^>]+>", "", value or ""))


def _search_mediawiki(api_endpoint: str, article_base: str, provider: str, query: str,
                      *, limit: int, timeout: int) -> tuple[list[SearchResult], dict[str, Any]]:
    """Full-text search against any MediaWiki API (Wikipedia, Memory Alpha)."""
    url = api_endpoint + "?" + urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": str(limit),
        "format": "json",
    })
    page = _request(url, timeout=timeout)
    results: list[SearchResult] = []
    if page.get("ok") and page.get("body"):
        try:
            data = json.loads(page["body"])
            for item in (data.get("query") or {}).get("search") or []:
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                item_url = article_base + urllib.parse.quote(title.replace(" ", "_"))
                if _is_public_http_url(item_url, resolve_dns=False):
                    results.append(SearchResult(title=title, url=item_url, snippet=_strip_tags(str(item.get("snippet") or ""))))
        except Exception:
            pass
    return results[:limit], {
        "provider": provider,
        "ok": page.get("ok"),
        "status": page.get("status"),
        "error": page.get("error"),
        "user_agent": "oracle_declared",
    }


def _search_wikipedia(query: str, *, limit: int, timeout: int) -> tuple[list[SearchResult], dict[str, Any]]:
    return _search_mediawiki(
        WIKIPEDIA_API_ENDPOINT, "https://en.wikipedia.org/wiki/", "wikipedia_search",
        query, limit=limit, timeout=timeout,
    )


def _search_memory_alpha(query: str, *, limit: int, timeout: int) -> tuple[list[SearchResult], dict[str, Any]]:
    return _search_mediawiki(
        MEMORY_ALPHA_API_ENDPOINT, MEMORY_ALPHA_ARTICLE_BASE, "memory_alpha",
        query, limit=limit, timeout=timeout,
    )


def _search_memory_beta(query: str, *, limit: int, timeout: int) -> tuple[list[SearchResult], dict[str, Any]]:
    return _search_mediawiki(
        MEMORY_BETA_API_ENDPOINT, MEMORY_BETA_ARTICLE_BASE, "memory_beta",
        query, limit=limit, timeout=timeout,
    )


def _search_stowiki(query: str, *, limit: int, timeout: int) -> tuple[list[SearchResult], dict[str, Any]]:
    return _search_mediawiki(
        STOWIKI_API_ENDPOINT, STOWIKI_ARTICLE_BASE, "stowiki",
        query, limit=limit, timeout=timeout,
    )


def _looks_like_star_trek(query: str) -> bool:
    q = query.lower()
    return any(hint in q for hint in STAR_TREK_HINTS)


def _looks_like_sto(query: str) -> bool:
    q = query.lower()
    return any(hint in q for hint in STO_HINTS)


# Article pages on these hosts sit behind bot challenges (Cloudflare), but
# their MediaWiki APIs are open. Fetches of /wiki/<Title> URLs are routed
# through the API's plain-text extract instead of scraping the HTML page.
MEDIAWIKI_ARTICLE_HOSTS = {
    "memory-alpha.fandom.com": MEMORY_ALPHA_API_ENDPOINT,
    "memory-beta.fandom.com": MEMORY_BETA_API_ENDPOINT,
    "stowiki.net": STOWIKI_API_ENDPOINT,
    "en.wikipedia.org": WIKIPEDIA_API_ENDPOINT,
}


def _mediawiki_extract_route(url: str) -> tuple[str, str] | None:
    """Return (api_endpoint, article_title) when the URL is a known wiki article."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    api_endpoint = MEDIAWIKI_ARTICLE_HOSTS.get(host)
    if not api_endpoint or not parsed.path.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(parsed.path[len("/wiki/"):]).replace("_", " ").strip()
    return (api_endpoint, title) if title else None


def _fetch_mediawiki_extract(api_endpoint: str, title: str, original_url: str,
                             *, timeout: int) -> dict[str, Any] | None:
    url = api_endpoint + "?" + urllib.parse.urlencode({
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "titles": title,
        "format": "json",
    })
    page = _request(url, timeout=timeout)
    if not (page.get("ok") and page.get("body")):
        return None
    try:
        data = json.loads(page["body"])
        pages = (data.get("query") or {}).get("pages") or {}
        entry = next(iter(pages.values()), {})
        extract = str(entry.get("extract") or "")
        if not extract:
            return None
        return {
            "ok": True,
            "url": original_url,
            "final_url": original_url,
            "status": page.get("status"),
            "content_type": "text/plain; mediawiki_api_extract",
            "title": str(entry.get("title") or title),
            "text": _clean_text(extract)[:MAX_TEXT_CHARS],
            "bytes_read": page.get("bytes_read", 0),
        }
    except Exception:
        return None


def _write_receipt(payload: dict[str, Any]) -> str:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "receipt_kind": "internet_recall_receipt",
        "schema_version": "internet_recall.v1",
        "timestamp": _now(),
        "boundary": {
            "method": "GET_only",
            "read_only": True,
            "browser_control": False,
            "cookie_jar": False,
            "login": False,
            "form_submit": False,
            "download_persisted": False,
            "external_send": False,
            "canon_promotion": False,
            "memory_promotion": False,
        },
        **payload,
    }
    receipt["receipt_hash_sha256"] = _sha256_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
    with RECEIPT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=True) + "\n")
    return str(RECEIPT_FILE)


def search(query: str, *, limit: int = 5, timeout: int = DEFAULT_TIMEOUT, write_receipt: bool = True) -> dict[str, Any]:
    q = _clean_text(str(query or ""))
    if not q:
        raise InternetRecallError("query is required")
    if len(q) > MAX_QUERY_CHARS:
        raise InternetRecallError("query is too long")
    bounded_limit = max(1, min(int(limit or 5), 10))
    provider_statuses: list[dict[str, Any]] = []
    parsed_results: list[SearchResult] = []
    source = "none"

    if _looks_like_sto(q):
        parsed_results, sto_status = _search_stowiki(q, limit=bounded_limit, timeout=timeout)
        provider_statuses.append(sto_status)
        if parsed_results:
            source = "stowiki"
        else:
            parsed_results, mb_status = _search_memory_beta(q, limit=bounded_limit, timeout=timeout)
            provider_statuses.append(mb_status)
            if parsed_results:
                source = "memory_beta"

    if not parsed_results and _looks_like_star_trek(q):
        parsed_results, ma_status = _search_memory_alpha(q, limit=bounded_limit, timeout=timeout)
        provider_statuses.append(ma_status)
        if parsed_results:
            source = "memory_alpha"

    url = SEARCH_ENDPOINT + "?" + urllib.parse.urlencode({"q": q})
    if not parsed_results:
        page = _request(url, timeout=timeout, user_agent=BROWSER_USER_AGENT)
        provider_statuses.append({"provider": "duckduckgo_html", "ok": page.get("ok"), "status": page.get("status"), "error": page.get("error"), "user_agent": "browser_generic"})
        parser = _ResultParser()
        if page.get("body"):
            parser.feed(page["body"])
        parsed_results = parser.results[:bounded_limit]
        source = "duckduckgo_html"

    if not parsed_results:
        bing_url = BING_ENDPOINT + "?" + urllib.parse.urlencode({"q": q})
        bing_page = _request(bing_url, timeout=timeout, user_agent=BROWSER_USER_AGENT)
        provider_statuses.append({"provider": "bing_html", "ok": bing_page.get("ok"), "status": bing_page.get("status"), "error": bing_page.get("error"), "user_agent": "browser_generic"})
        bing_parser = _BingParser()
        if bing_page.get("body"):
            bing_parser.feed(bing_page["body"])
        parsed_results = bing_parser.results[:bounded_limit]
        source = "bing_html"

    if not parsed_results:
        parsed_results, wiki_status = _search_wikipedia(q, limit=bounded_limit, timeout=timeout)
        provider_statuses.append(wiki_status)
        source = "wikipedia_search"

    results = [asdict(result) for result in parsed_results[:bounded_limit]]
    response = {
        "ok": bool(results) or any(bool(status.get("ok")) for status in provider_statuses),
        "operation_type": "internet_search",
        "query": q,
        "search_url": url,
        "fetched_at": _now(),
        "source": source,
        "result_count": len(results),
        "results": results,
        "network_status": {"providers": provider_statuses},
        "boundary": {
            "GET_only": True,
            "read_only": True,
            "external_send": False,
            "browser_control": False,
            "canon_promotion": False,
        },
    }
    if write_receipt:
        response["receipt_path"] = _write_receipt({
            "operation_type": "internet_search",
            "query_sha256": _sha256_text(q),
            "query_preview": q,
            "result_count": len(results),
            "urls": [r["url"] for r in results],
            "network_status": response["network_status"],
            "source": source,
        })
    return response


def fetch(url: str, *, timeout: int = DEFAULT_TIMEOUT, write_receipt: bool = True) -> dict[str, Any]:
    wiki_route = _mediawiki_extract_route(str(url or "").strip())
    if wiki_route:
        api_result = _fetch_mediawiki_extract(wiki_route[0], wiki_route[1], str(url).strip(), timeout=timeout)
        if api_result:
            page = api_result
            title = api_result["title"]
            text = api_result["text"]
        else:
            page = _request(url, timeout=timeout)
            parser = _TextParser()
            if page.get("body"):
                parser.feed(page["body"])
            title = _clean_text(" ".join(parser.title))
            text = _clean_text(" ".join(parser.text))[:MAX_TEXT_CHARS]
    else:
        page = _request(url, timeout=timeout)
        parser = _TextParser()
        if page.get("body"):
            parser.feed(page["body"])
        title = _clean_text(" ".join(parser.title))
        text = _clean_text(" ".join(parser.text))[:MAX_TEXT_CHARS]
    response = {
        "ok": bool(page.get("ok")),
        "operation_type": "internet_fetch",
        "url": page.get("url") or url,
        "final_url": page.get("final_url") or page.get("url") or url,
        "status": page.get("status"),
        "content_type": page.get("content_type", ""),
        "title": title,
        "text_preview": text,
        "fetched_at": _now(),
        "bytes_read": page.get("bytes_read", 0),
        "truncated": bool(page.get("truncated")),
        "error": page.get("error"),
        "boundary": {
            "GET_only": True,
            "read_only": True,
            "external_send": False,
            "browser_control": False,
            "canon_promotion": False,
        },
    }
    if write_receipt:
        response["receipt_path"] = _write_receipt({
            "operation_type": "internet_fetch",
            "url": response["url"],
            "final_url": response["final_url"],
            "status": response["status"],
            "ok": response["ok"],
            "title": title,
            "text_sha256": _sha256_text(text),
        })
    return response


def parse_recall_request(text: str) -> dict[str, str] | None:
    raw = str(text or "").strip()
    lower = raw.lower()
    if not raw:
        return None
    fetch_prefixes = ("/internet-fetch ", "/web-fetch ", "internet fetch ", "fetch url ", "browse to ")
    for prefix in fetch_prefixes:
        if lower.startswith(prefix):
            return {"mode": "fetch", "value": raw[len(prefix):].strip()}
    search_prefixes = (
        "/internet-search ", "/web-search ", "/internet-recall ", "internet recall ",
        "search the web for ", "search online for ", "look up online ", "look it up online ",
        "look this up online ",
    )
    for prefix in search_prefixes:
        if lower.startswith(prefix):
            return {"mode": "search", "value": raw[len(prefix):].strip()}
    if lower.startswith("search the web ") and len(raw) > len("search the web "):
        return {"mode": "search", "value": raw[len("search the web "):].strip()}
    return None


def format_recall(result: dict[str, Any]) -> str:
    boundary = "boundary: GET-only, read-only, no browser control, no login, no forms, no external send, no canon promotion"
    if result.get("operation_type") == "internet_fetch":
        lines = [
            "INTERNET RECALL FETCH",
            boundary,
            f"url: {result.get('final_url') or result.get('url')}",
            f"status: {result.get('status')}",
            f"title: {result.get('title') or 'UNKNOWN'}",
        ]
        if result.get("text_preview"):
            lines.append("")
            lines.append(str(result["text_preview"])[:1600])
        if result.get("receipt_path"):
            lines.append(f"\nreceipt_path: {result['receipt_path']}")
        return "\n".join(lines)

    lines = [
        "INTERNET RECALL SEARCH",
        boundary,
        f"query: {result.get('query')}",
        f"source: {result.get('source', 'UNKNOWN')}",
        f"result_count: {result.get('result_count', 0)}",
    ]
    for idx, item in enumerate(result.get("results") or [], start=1):
        lines.append(f"{idx}. {item.get('title') or 'Untitled'}")
        lines.append(f"   {item.get('url')}")
        if item.get("snippet"):
            lines.append(f"   {item.get('snippet')}")
    if not result.get("results"):
        providers = (result.get("network_status") or {}).get("providers") or []
        provider_summary = ", ".join(
            f"{p.get('provider')}:{p.get('status') or p.get('error') or 'unknown'}"
            for p in providers
        )
        lines.append(f"no_results: {provider_summary or 'search providers returned no parseable results'}")
    if result.get("receipt_path"):
        lines.append(f"\nreceipt_path: {result['receipt_path']}")
    return "\n".join(lines)


def self_check() -> dict[str, Any]:
    return {
        "ok": True,
        "module": "internet_recall",
        "search_endpoint": SEARCH_ENDPOINT,
        "providers": [
            "stowiki + memory_beta (star trek online queries)",
            "memory_alpha (star trek queries)",
            "duckduckgo_html", "bing_html", "wikipedia_search",
        ],
        "receipt_file": str(RECEIPT_FILE),
        "boundary": "public http/https GET only; no browser/session/form/send",
    }
