# Internet Recall

Status: Live

ORACLE has a governed internet recall lane for public read-only lookup:

```text
/internet-search <query>
/web-search <query>
/internet-fetch <public-url>
/web-fetch <public-url>
GET /api/internet-recall/search?q=<query>
GET /api/internet-recall/fetch?url=<public-url>
```

Natural language forms such as `search the web for ...` route to the same lane.

## Provider chain

Searches try providers in order and stop at the first one with parseable
results. Every provider attempt is recorded in the receipt with its status
and which user-agent class was used.

1. **Memory Alpha** (`memory-alpha.fandom.com` MediaWiki API) — tried first
   when the query contains Star Trek terms (Jupiter Station, Starfleet,
   Voyager, Klingon, LCARS, ...). This is the canon Star Trek wiki, so Trek
   questions answer from the deepest source.
2. **DuckDuckGo HTML** — general web. Uses a generic browser user-agent
   because DuckDuckGo serves a bot-challenge page (HTTP 202) to non-browser
   agents; receipts record `user_agent: browser_generic`.
3. **Bing HTML** — fallback, same user-agent policy.
4. **Wikipedia full-text search** (`action=query&list=search`) — final
   fallback; handles conversational queries far better than the old
   prefix-only `opensearch`.

MediaWiki APIs (Memory Alpha, Wikipedia) are queried with the honest
`ORACLE.AI internet_recall` user-agent (`user_agent: oracle_declared`), which
is the etiquette those APIs prefer.

## Boundary

Internet recall is not browser control. It does not use Chrome, cookies, logged
in sessions, form submission, uploads, downloads, external send, canon
promotion, or durable memory promotion.

Allowed:

- public `http` and `https` GET requests
- search result recall
- public page text preview
- local JSONL receipts under `Memory/internet_recall_receipts.jsonl`

Blocked:

- `localhost`, loopback, private LAN, link-local, and reserved network targets
- `file://` and non-HTTP schemes
- browser profile or credential access
- form submit, post, upload, email, publish, or account action
- canon or memory promotion from web text without Noah.Physical approval

This gives ORACLE current public recall while keeping external action gates
intact.
