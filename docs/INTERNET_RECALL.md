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
